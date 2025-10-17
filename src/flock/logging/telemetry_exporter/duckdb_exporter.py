"""DuckDB exporter for OpenTelemetry spans - optimized for analytical queries."""

import json
from pathlib import Path

import duckdb
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import Status, StatusCode

from flock.logging.telemetry_exporter.base_exporter import TelemetryExporter


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

            # Create indexes for common query patterns
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_id ON spans(trace_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_service ON spans(service)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_start_time ON spans(start_time)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_name ON spans(name)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created_at ON spans(created_at)"
            )

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
        """Export spans to DuckDB."""
        try:
            with duckdb.connect(str(self.db_path)) as conn:
                for span in spans:
                    record = self._span_to_record(span)

                    # Insert span record
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO spans (
                            trace_id, span_id, parent_id, name, service, operation,
                            kind, start_time, end_time, duration_ms,
                            status_code, status_description,
                            attributes, events, links, resource
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            record["trace_id"],
                            record["span_id"],
                            record["parent_id"],
                            record["name"],
                            record["service"],
                            record["operation"],
                            record["kind"],
                            record["start_time"],
                            record["end_time"],
                            record["duration_ms"],
                            record["status_code"],
                            record["status_description"],
                            record["attributes"],
                            record["events"],
                            record["links"],
                            record["resource"],
                        ),
                    )

            return SpanExportResult.SUCCESS
        except Exception as e:
            print(f"Error exporting spans to DuckDB: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Cleanup resources."""
        # DuckDB connections are managed per-transaction, no cleanup needed
