"""This module sets up OpenTelemetry tracing for a service."""

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)

from flock.core.logging.telemetry_exporter.file_span import FileSpanExporter
from flock.core.logging.telemetry_exporter.sqllite_span import (
    SQLiteSpanExporter,
)


class TelemetryConfig:
    """This configuration class sets up OpenTelemetry tracing.

      - Export spans to a Jaeger collector using gRPC.
      - Write spans to a file.
      - Save spans in a SQLite database.

    Only exporters with a non-None configuration will be activated.
    """

    def __init__(
        self,
        service_name: str,
        jaeger_endpoint: str = None,
        jaeger_transport: str = "grpc",
        file_export_path: str = None,
        sqlite_db_path: str = None,
        batch_processor_options: dict = None,
    ):
        """:param service_name: Name of your service.

        :param jaeger_endpoint: The Jaeger collector gRPC endpoint (e.g., "localhost:14250").
        :param file_export_path: If provided, spans will be written to this file.
        :param sqlite_db_path: If provided, spans will be stored in this SQLite DB.
        :param batch_processor_options: Dict of options for BatchSpanProcessor (e.g., {"max_export_batch_size": 10}).
        """
        self.service_name = service_name
        self.jaeger_endpoint = jaeger_endpoint
        self.jaeger_transport = jaeger_transport
        self.file_export_path = file_export_path
        self.sqlite_db_path = sqlite_db_path
        self.batch_processor_options = batch_processor_options or {}

    def setup_tracing(self):
        # Create a Resource with the service name.
        resource = Resource(attributes={"service.name": self.service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # List to collect our span processors.
        span_processors = []

        # If a Jaeger endpoint is specified, add the Jaeger gRPC exporter.
        if self.jaeger_endpoint:
            if self.jaeger_transport == "grpc":
                from opentelemetry.exporter.jaeger.proto.grpc import (
                    JaegerExporter,
                )

                jaeger_exporter = JaegerExporter(
                    endpoint=self.jaeger_endpoint,
                    insecure=True,
                )
            elif self.jaeger_transport == "http":
                from opentelemetry.exporter.jaeger.thrift import JaegerExporter

                jaeger_exporter = JaegerExporter(
                    collector_endpoint=self.jaeger_endpoint,
                )
            else:
                raise ValueError(
                    "Invalid JAEGER_TRANSPORT specified. Use 'grpc' or 'http'."
                )

            span_processors.append(
                BatchSpanProcessor(
                    jaeger_exporter, **self.batch_processor_options
                )
            )

        # If a file path is provided, add the custom file exporter.
        if self.file_export_path:
            file_exporter = FileSpanExporter(self.file_export_path)
            span_processors.append(
                BatchSpanProcessor(
                    file_exporter, **self.batch_processor_options
                )
            )

        # If a SQLite database path is provided, add the custom SQLite exporter.
        if self.sqlite_db_path:
            sqlite_exporter = SQLiteSpanExporter(self.sqlite_db_path)
            span_processors.append(
                BatchSpanProcessor(
                    sqlite_exporter, **self.batch_processor_options
                )
            )

        # Register all span processors with the provider.
        for processor in span_processors:
            provider.add_span_processor(processor)

        # Return a tracer instance.
        return trace.get_tracer(__name__)
