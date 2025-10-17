"""This module sets up OpenTelemetry tracing for a service."""

import os
import sys

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# from temporalio import workflow
from flock.logging.span_middleware.baggage_span_processor import (
    BaggageAttributeSpanProcessor,
)
from flock.logging.telemetry_exporter.duckdb_exporter import (
    DuckDBSpanExporter,
)

# with workflow.unsafe.imports_passed_through():
from flock.logging.telemetry_exporter.file_exporter import (
    FileSpanExporter,
)
from flock.logging.telemetry_exporter.sqlite_exporter import (
    SqliteTelemetryExporter,
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
        jaeger_endpoint: str | None = None,
        jaeger_transport: str = "grpc",
        local_logging_dir: str | None = None,
        file_export_name: str | None = None,
        sqlite_db_name: str | None = None,
        duckdb_name: str | None = None,
        duckdb_ttl_days: int | None = None,
        enable_jaeger: bool = True,
        enable_file: bool = True,
        enable_sql: bool = True,
        enable_duckdb: bool = True,
        enable_otlp: bool = True,
        otlp_protocol: str = "grpc",
        otlp_endpoint: str = "http://localhost:4317",
        batch_processor_options: dict | None = None,
    ):
        """:param service_name: Name of your service.

        :param jaeger_endpoint: The Jaeger collector gRPC endpoint (e.g., "localhost:14250").
        :param file_export_path: If provided, spans will be written to this file.
        :param sqlite_db_path: If provided, spans will be stored in this SQLite DB.
        :param duckdb_ttl_days: Delete traces older than this many days (default: None = keep forever).
        :param batch_processor_options: Dict of options for BatchSpanProcessor (e.g., {"max_export_batch_size": 10}).
        """
        self.service_name = service_name
        self.jaeger_endpoint = jaeger_endpoint
        self.jaeger_transport = jaeger_transport
        self.file_export_name = file_export_name
        self.sqlite_db_name = sqlite_db_name
        self.duckdb_name = duckdb_name
        self.duckdb_ttl_days = duckdb_ttl_days
        self.local_logging_dir = local_logging_dir
        self.batch_processor_options = batch_processor_options or {}
        self.enable_jaeger = enable_jaeger
        self.enable_file = enable_file
        self.enable_sql = enable_sql
        self.enable_duckdb = enable_duckdb
        self.enable_otlp = enable_otlp
        self.otlp_protocol = otlp_protocol
        self.otlp_endpoint = otlp_endpoint
        self.global_tracer = None
        self._configured: bool = False

    def _should_setup(self) -> bool:
        # Respect explicit disable flag for tests and minimal setups
        if os.environ.get("FLOCK_DISABLE_TELEMETRY_AUTOSETUP", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        try:
            # If a provider is already installed (typically by user/tests), don't override it
            from opentelemetry.sdk.trace import (
                TracerProvider as SDKTracerProvider,  # type: ignore
            )

            current = trace.get_tracer_provider()
            if isinstance(current, SDKTracerProvider):
                return False
        except Exception:
            # If SDK isn't available or introspection fails, fall back to enabling
            pass
        return True

    def setup_tracing(self):
        """Set up OpenTelemetry tracing with the specified exporters."""
        if self._configured:
            return
        if not self._should_setup():
            return

        # Create a Resource with the service name.
        resource = Resource(attributes={"service.name": self.service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # List to collect our span processors.
        span_processors = []

        # If a Jaeger endpoint is specified, add the Jaeger exporter.
        if self.jaeger_endpoint and self.enable_jaeger:
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

            span_processors.append(SimpleSpanProcessor(jaeger_exporter))

        if self.enable_otlp:
            if self.otlp_protocol == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                otlp_exporter = OTLPSpanExporter(
                    endpoint=self.otlp_endpoint,
                    insecure=True,
                )
            elif self.otlp_protocol == "http":
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                otlp_exporter = OTLPSpanExporter(
                    endpoint=self.otlp_endpoint,
                )
            else:
                raise ValueError(
                    "Invalid OTEL_EXPORTER_OTLP_PROTOCOL specified. Use 'grpc' or 'http'."
                )

            span_processors.append(SimpleSpanProcessor(otlp_exporter))

        # If a file path is provided, add the custom file exporter.
        if self.file_export_name and self.enable_file:
            file_exporter = FileSpanExporter(
                self.local_logging_dir, self.file_export_name
            )
            span_processors.append(SimpleSpanProcessor(file_exporter))

        # If a SQLite database path is provided, ensure the DB exists and add the SQLite exporter.
        if self.sqlite_db_name and self.enable_sql:
            sqlite_exporter = SqliteTelemetryExporter(
                self.local_logging_dir, self.sqlite_db_name
            )
            span_processors.append(SimpleSpanProcessor(sqlite_exporter))

        # If a DuckDB database path is provided, add the DuckDB exporter.
        if self.duckdb_name and self.enable_duckdb:
            duckdb_exporter = DuckDBSpanExporter(
                self.local_logging_dir, self.duckdb_name, ttl_days=self.duckdb_ttl_days
            )
            span_processors.append(SimpleSpanProcessor(duckdb_exporter))

        # Register all span processors with the provider.
        for processor in span_processors:
            provider.add_span_processor(processor)

        provider.add_span_processor(
            BaggageAttributeSpanProcessor(baggage_keys=["session_id", "run_id"])
        )
        self.global_tracer = trace.get_tracer("flock")
        sys.excepthook = self.log_exception_to_otel
        self._configured = True

    def log_exception_to_otel(self, exc_type, exc_value, exc_traceback):
        """Log unhandled exceptions to OpenTelemetry."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow normal handling of KeyboardInterrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        if not self.global_tracer:
            return

        # Use OpenTelemetry to record the exception
        with self.global_tracer.start_as_current_span("UnhandledException") as span:
            span.record_exception(exc_value)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc_value)))
