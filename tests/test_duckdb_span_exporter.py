"""The DuckDB span exporter writes a batch of spans in one transaction (#601)."""

import json

import duckdb
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from flock.logging.telemetry_exporter.duckdb_exporter import DuckDBSpanExporter


def _spans(count: int):
    """Finished spans with their index as an attribute."""
    finished = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(finished))
    tracer = provider.get_tracer("test")
    for index in range(count):
        with tracer.start_as_current_span(
            f"Agent.step_{index % 3}", attributes={"index": index}
        ):
            pass
    provider.shutdown()
    return list(finished.get_finished_spans())


def _rows(exporter: DuckDBSpanExporter):
    with duckdb.connect(str(exporter.db_path), read_only=True) as conn:
        return conn.execute(
            "SELECT name, attributes FROM spans ORDER BY start_time"
        ).fetchall()


def test_a_batch_is_written_and_a_batch_sent_again_replaces_its_spans(tmp_path):
    exporter = DuckDBSpanExporter(str(tmp_path), "traces.duckdb")
    spans = _spans(300)  # more rows than one insert statement takes

    assert exporter.export(spans) is SpanExportResult.SUCCESS
    assert exporter.export(spans[:10]) is SpanExportResult.SUCCESS

    rows = _rows(exporter)
    assert len(rows) == 300
    assert rows[42][0] == "Agent.step_0"
    assert json.loads(rows[42][1]) == {"index": 42}


def test_a_batch_that_fails_writes_none_of_its_spans(tmp_path, monkeypatch):
    exporter = DuckDBSpanExporter(str(tmp_path), "traces.duckdb")
    spans = _spans(200)
    record = exporter._span_to_record

    def without_name_at_150(span):
        row = record(span)
        if span is spans[150]:
            row["name"] = None  # NOT NULL: the insert of the second part fails
        return row

    monkeypatch.setattr(exporter, "_span_to_record", without_name_at_150)

    assert exporter.export(spans) is SpanExportResult.FAILURE
    assert _rows(exporter) == []


def test_only_trace_id_is_indexed_also_in_an_earlier_trace_file(tmp_path):
    path = tmp_path / "traces.duckdb"
    DuckDBSpanExporter(str(tmp_path), "traces.duckdb")
    # A trace file from an earlier version has four more indexes
    with duckdb.connect(str(path)) as conn:
        for column in ("service", "start_time", "name", "created_at"):
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{column} ON spans({column})")

    DuckDBSpanExporter(str(tmp_path), "traces.duckdb")

    with duckdb.connect(str(path), read_only=True) as conn:
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'spans'"
            ).fetchall()
        }
    assert indexes == {"idx_trace_id"}
