"""Exporter for storing OpenTelemetry spans in SQLite."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace.export import SpanExportResult

from flock.core.logging.telemetry_exporter.base_exporter import (
    TelemetryExporter,
)


class SqliteTelemetryExporter(TelemetryExporter):
    """Exporter for storing OpenTelemetry spans in SQLite."""

    def __init__(self, dir: str, db_path: str = "flock_events.db"):
        """Initialize the SQLite exporter.

        Args:
            db_path: Path to the SQLite database file
        """
        super().__init__()
        self.telemetry_path = Path(dir)
        self.telemetry_path.mkdir(parents=True, exist_ok=True)
        # Create an absolute path to the database file:
        self.db_path = self.telemetry_path.joinpath(db_path).resolve().__str__()
        # Use the absolute path when connecting:
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._initialize_database()

    def _initialize_database(self):
        """Set up the SQLite database schema."""
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

    def _convert_attributes(self, attributes: dict[str, Any]) -> str:
        """Convert span attributes to a JSON string.

        Args:
            attributes: Dictionary of span attributes

        Returns:
            JSON string representation of attributes
        """
        # Convert attributes to a serializable format
        serializable_attrs = {}
        for key, value in attributes.items():
            # Convert complex types to strings if needed
            if isinstance(value, dict | list | tuple):
                serializable_attrs[key] = json.dumps(value)
            else:
                serializable_attrs[key] = str(value)
        return json.dumps(serializable_attrs)

    def export(self, spans) -> SpanExportResult:
        """Export spans to SQLite."""
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
                        self._convert_attributes(span.attributes),
                        str(span.status),
                    ),
                )
            self.conn.commit()
            return SpanExportResult.SUCCESS
        except Exception as e:
            print("Error exporting spans to SQLite:", e)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Cleanup resources."""
        pass
