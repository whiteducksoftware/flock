"""A simple exporter that writes span data as JSON lines into a file."""

import json

from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import Status, StatusCode
from temporalio import workflow

from flock.core.logging.telemetry_exporter.base_exporter import (
    TelemetryExporter,
)

with workflow.unsafe.imports_passed_through():
    from pathlib import Path


class FileSpanExporter(TelemetryExporter):
    """A simple exporter that writes span data as JSON lines into a file."""

    def __init__(self, dir: str, file_path: str = "flock_events.jsonl"):
        """Initialize the exporter with a file path."""
        super().__init__()
        self.telemetry_path = Path(dir)
        self.telemetry_path.mkdir(parents=True, exist_ok=True)
        self.file_path = self.telemetry_path.joinpath(file_path).__str__()

    def _span_to_json(self, span):
        """Convert a ReadableSpan to a JSON-serializable dict."""
        context = span.get_span_context()
        status = span.status or Status(StatusCode.UNSET)

        return {
            "name": span.name,
            "context": {
                "trace_id": format(context.trace_id, "032x"),
                "span_id": format(context.span_id, "016x"),
                "trace_flags": context.trace_flags,
                "trace_state": str(context.trace_state),
            },
            "kind": span.kind.name if span.kind else None,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "status": {
                "status_code": status.status_code.name,
                "description": status.description,
            },
            "attributes": dict(span.attributes or {}),
            "events": [
                {
                    "name": event.name,
                    "timestamp": event.timestamp,
                    "attributes": dict(event.attributes or {}),
                }
                for event in span.events
            ],
            "links": [
                {
                    "context": {
                        "trace_id": format(link.context.trace_id, "032x"),
                        "span_id": format(link.context.span_id, "016x"),
                    },
                    "attributes": dict(link.attributes or {}),
                }
                for link in span.links
            ],
            "resource": {
                attr_key: attr_value
                for attr_key, attr_value in span.resource.attributes.items()
            },
        }

    def export(self, spans):
        """Write spans to a log file."""
        try:
            with open(self.file_path, "a") as f:
                for span in spans:
                    json_span = self._span_to_json(span)
                    f.write(f"{json.dumps(json_span)}\n")
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        # Nothing special needed on shutdown.
        pass
