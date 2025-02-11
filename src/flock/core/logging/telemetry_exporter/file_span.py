import json

from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)


class FileSpanExporter(SpanExporter):
    """A simple exporter that writes span data as JSON lines into a file."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def export(self, spans) -> SpanExportResult:
        try:
            with open(self.file_path, "a") as f:
                for span in spans:
                    # Create a dictionary representation of the span.
                    span_dict = {
                        "name": span.name,
                        "trace_id": format(span.context.trace_id, "032x"),
                        "span_id": format(span.context.span_id, "016x"),
                        "start_time": span.start_time,
                        "end_time": span.end_time,
                        "attributes": span.attributes,
                        "status": str(span.status),
                    }
                    f.write(json.dumps(span_dict) + "\n")
            return SpanExportResult.SUCCESS
        except Exception as e:
            print("Error exporting spans to file:", e)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        # Nothing special needed on shutdown.
        pass
