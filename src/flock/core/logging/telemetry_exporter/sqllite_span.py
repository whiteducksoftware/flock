import json
import sqlite3

from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)


class SQLiteSpanExporter(SpanExporter):
    """A custom exporter that writes span data into a SQLite database."""

    def __init__(self, sqlite_db_path: str):
        self.sqlite_db_path = sqlite_db_path
        self.conn = sqlite3.connect(
            self.sqlite_db_path, check_same_thread=False
        )
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS spans (
                id TEXT PRIMARY KEY,
                name TEXT,
                trace_id TEXT,
                span_id TEXT,
                start_time INTEGER,
                end_time INTEGER,
                attributes TEXT,
                status TEXT
            )
            """
        )
        self.conn.commit()

    def export(self, spans) -> SpanExportResult:
        try:
            cursor = self.conn.cursor()
            for span in spans:
                span_id = format(span.context.span_id, "016x")
                trace_id = format(span.context.trace_id, "032x")
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO spans 
                    (id, name, trace_id, span_id, start_time, end_time, attributes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        span_id,
                        span.name,
                        trace_id,
                        span_id,
                        span.start_time,
                        span.end_time,
                        json.dumps(span.attributes),
                        str(span.status),
                    ),
                )
            self.conn.commit()
            return SpanExportResult.SUCCESS
        except Exception as e:
            print("Error exporting spans to SQLite:", e)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        self.conn.close()
