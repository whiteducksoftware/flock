"""DuckDB exporter for OpenTelemetry spans - optimized for analytical queries."""

import json
from pathlib import Path

import duckdb
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import Status, StatusCode

from flock.logging.telemetry_exporter.base_exporter import TelemetryExporter


_COLUMNS = (
    "trace_id",
    "span_id",
    "parent_id",
    "name",
    "service",
    "operation",
    "kind",
    "start_time",
    "end_time",
    "duration_ms",
    "status_code",
    "status_description",
    "attributes",
    "events",
    "links",
    "resource",
)

# Rows per INSERT: DuckDB runs each statement on its own, so one statement with
# many rows writes a batch about ten times faster than a statement per row (#601)
_ROWS_PER_INSERT = 128


def _insert_sql(rows: int) -> str:
    """An INSERT OR REPLACE of ``rows`` spans (a span exported again replaces itself)."""
    row = "(" + ", ".join("?" * len(_COLUMNS)) + ")"
    return (
        f"INSERT OR REPLACE INTO spans ({', '.join(_COLUMNS)}) VALUES "  # nosec B608
        + ", ".join([row] * rows)
    )


class DuckDBSpanExporter(TelemetryExporter):
    """Export spans to DuckDB for fast analytical queries.

    DuckDB is a columnar analytical database optimized for OLAP workloads,
    making it 10-100x faster than SQLite for trace analytics like:
    - Aggregations (avg/p95/p99 duration)
    - Time-range queries
    - Service/operation filtering
    - Complex analytical queries

    The database is a single file with zero configuration required.
    """

    def __init__(
        self, dir: str, db_name: str = "traces.duckdb", ttl_days: int | None = None
    ):
        """Initialize the DuckDB exporter.

        Args:
            dir: Directory where the database file will be created
            db_name: Name of the DuckDB file (default: traces.duckdb)
            ttl_days: Delete traces older than this many days (default: None = keep forever)
        """
        super().__init__()
        self.telemetry_path = Path(dir)
        self.telemetry_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.telemetry_path / db_name
        self.ttl_days = ttl_days

        # Initialize database and create schema
        self._init_database()

    def _init_database(self):
        """Create the spans table if it doesn't exist."""
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spans (
                    trace_id VARCHAR NOT NULL,
                    span_id VARCHAR PRIMARY KEY,
                    parent_id VARCHAR,
                    name VARCHAR NOT NULL,
                    service VARCHAR,
                    operation VARCHAR,
                    kind VARCHAR,
                    start_time BIGINT NOT NULL,
                    end_time BIGINT NOT NULL,
                    duration_ms DOUBLE NOT NULL,
                    status_code VARCHAR NOT NULL,
                    status_description VARCHAR,
                    attributes JSON,
                    events JSON,
                    links JSON,
                    resource JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # trace_id serves lookups of one trace. Indexes on service,
            # start_time, name and created_at took space (5.5 of 143 MB at
            # 20,000 spans) and sped up no query of the dashboard (#601):
            # earlier files lose them
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_id ON spans(trace_id)")
            for column in ("service", "start_time", "name", "created_at"):
                conn.execute(f"DROP INDEX IF EXISTS idx_{column}")  # nosec B608

        # Cleanup old traces if TTL is configured
        if self.ttl_days is not None:
            self._cleanup_old_traces()

    def _cleanup_old_traces(self):
        """Delete traces older than TTL_DAYS.

        This runs on exporter initialization to keep the database size manageable.
        """
        if self.ttl_days is None:
            return

        try:
            with duckdb.connect(str(self.db_path)) as conn:
                # Delete spans older than TTL
                # Note: DuckDB doesn't support ? placeholders inside INTERVAL expressions
                # Safe: ttl_days is guaranteed to be an int, no injection risk
                query = f"""
                    DELETE FROM spans
                    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '{self.ttl_days} DAYS'
                """  # nosec B608
                result = conn.execute(query)

                deleted_count = result.fetchall()[0][0] if result else 0

                if deleted_count > 0:
                    print(
                        f"[DuckDB TTL] Deleted {deleted_count} spans older than {self.ttl_days} days"
                    )

        except Exception as e:
            print(f"[DuckDB TTL] Error cleaning up old traces: {e}")

    def _span_to_record(self, span):
        """Convert a ReadableSpan to a database record."""
        context = span.get_span_context()
        status = span.status or Status(StatusCode.UNSET)

        # Extract service and operation from span name
        # Format: "ServiceName.operation_name"
        parts = span.name.split(".", 1)
        service = parts[0] if len(parts) > 0 else "unknown"
        operation = parts[1] if len(parts) > 1 else span.name

        # Calculate duration in milliseconds
        duration_ms = (span.end_time - span.start_time) / 1_000_000

        # Serialize complex fields to JSON
        attributes_json = json.dumps(dict(span.attributes or {}))
        events_json = json.dumps([
            {
                "name": event.name,
                "timestamp": event.timestamp,
                "attributes": dict(event.attributes or {}),
            }
            for event in span.events
        ])
        links_json = json.dumps([
            {
                "context": {
                    "trace_id": format(link.context.trace_id, "032x"),
                    "span_id": format(link.context.span_id, "016x"),
                },
                "attributes": dict(link.attributes or {}),
            }
            for link in span.links
        ])
        resource_json = json.dumps(dict(span.resource.attributes.items()))

        # Get parent span ID if exists
        parent_id = None
        if span.parent and span.parent.span_id != 0:
            parent_id = format(span.parent.span_id, "016x")

        return {
            "trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x"),
            "parent_id": parent_id,
            "name": span.name,
            "service": service,
            "operation": operation,
            "kind": span.kind.name if span.kind else None,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "duration_ms": duration_ms,
            "status_code": status.status_code.name,
            "status_description": status.description,
            "attributes": attributes_json,
            "events": events_json,
            "links": links_json,
            "resource": resource_json,
        }

    def export(self, spans):
        """Export a batch of spans to DuckDB in one transaction: all or none."""
        try:
            records = [self._span_to_record(span) for span in spans]
            if not records:
                return SpanExportResult.SUCCESS
            with duckdb.connect(str(self.db_path)) as conn:
                conn.execute("BEGIN TRANSACTION")
                for start in range(0, len(records), _ROWS_PER_INSERT):
                    part = records[start : start + _ROWS_PER_INSERT]
                    conn.execute(
                        _insert_sql(len(part)),
                        [record[column] for record in part for column in _COLUMNS],
                    )
                conn.execute("COMMIT")
            return SpanExportResult.SUCCESS
        except Exception as e:
            print(f"Error exporting spans to DuckDB: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Cleanup resources."""
        # DuckDB connections are managed per-transaction, no cleanup needed
