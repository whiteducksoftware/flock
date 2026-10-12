"""This module sets up OpenTelemetry tracing for a service."""

import os
import sys
import threading
import time
import weakref

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

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

      - Export spans via OTLP (gRPC or HTTP).
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

        # The legacy Jaeger exporter packages were removed: they cannot be
        # installed next to current OpenTelemetry releases. Jaeger ingests
        # OTLP natively, so point OTEL_EXPORTER_OTLP_ENDPOINT at it instead.
        if self.jaeger_endpoint and self.enable_jaeger:
            raise ValueError(
                "The Jaeger exporter is no longer supported. Jaeger accepts OTLP "
                "natively: set OTEL_EXPORTER_OTLP_ENDPOINT (enable_otlp=True) to "
                "your Jaeger collector's OTLP endpoint instead."
            )

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

            span_processors.append(self._batched(otlp_exporter))

        # If a file path is provided, add the custom file exporter.
        if self.file_export_name and self.enable_file:
            file_exporter = FileSpanExporter(
                self.local_logging_dir, self.file_export_name
            )
            span_processors.append(self._batched(file_exporter))

        # If a SQLite database path is provided, ensure the DB exists and add the SQLite exporter.
        if self.sqlite_db_name and self.enable_sql:
            sqlite_exporter = SqliteTelemetryExporter(
                self.local_logging_dir, self.sqlite_db_name
            )
            span_processors.append(self._batched(sqlite_exporter))

        # If a DuckDB database path is provided, add the DuckDB exporter.
        if self.duckdb_name and self.enable_duckdb:
            duckdb_exporter = DuckDBSpanExporter(
                self.local_logging_dir, self.duckdb_name, ttl_days=self.duckdb_ttl_days
            )
            span_processors.append(self._batched(duckdb_exporter))

        # Register all span processors with the provider.
        for processor in span_processors:
            provider.add_span_processor(processor)

        provider.add_span_processor(
            BaggageAttributeSpanProcessor(baggage_keys=["session_id", "run_id"])
        )
        self.global_tracer = trace.get_tracer("flock")
        self._previous_excepthook = sys.excepthook
        sys.excepthook = self.log_exception_to_otel
        self._configured = True

    def _batched(self, exporter: SpanExporter) -> BatchSpanProcessor:
        """The exporter behind a batch processor.

        Spans go out in batches from the processor's thread, not one at a time
        from the thread that ends them, mostly the event loop (#601). A batch
        goes out at least every second, since the dashboard reads the trace
        file, unless ``OTEL_BSP_SCHEDULE_DELAY`` or ``batch_processor_options``
        say otherwise; the other ``OTEL_BSP_*`` variables apply as well.
        """
        options = dict(self.batch_processor_options)
        if "OTEL_BSP_SCHEDULE_DELAY" not in os.environ:
            options.setdefault("schedule_delay_millis", 1000)
        return BatchSpanProcessor(exporter, **options)

    def log_exception_to_otel(self, exc_type, exc_value, exc_traceback):
        """Log unhandled exceptions to OpenTelemetry."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow normal handling of KeyboardInterrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        if self.global_tracer:
            # Use OpenTelemetry to record the exception
            with self.global_tracer.start_as_current_span("UnhandledException") as span:
                span.record_exception(exc_value)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc_value)))

        # Chain to the hook that was installed before us so tracebacks still print.
        previous = getattr(self, "_previous_excepthook", None)
        if previous is not None and previous is not self.log_exception_to_otel:
            previous(exc_type, exc_value, exc_traceback)


# The flush running for each tracer provider (one at a time; a stalled exporter
# would otherwise collect a thread per call)
_flushes: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_flushes_lock = threading.Lock()


def _stopped(provider) -> bool:
    """Whether every batch processor of the provider was shut down and its worker,
    which still exports during a shutdown, has finished: nothing is left to write."""
    processors = getattr(
        getattr(provider, "_active_span_processor", None), "_span_processors", ()
    )
    batches = [p for p in processors if isinstance(p, BatchSpanProcessor)]

    def drained(processor) -> bool:
        state = getattr(processor, "_batch_processor", None)
        worker = getattr(state, "_worker_thread", None)
        return bool(getattr(state, "_shutdown", False)) and not (
            worker is not None and worker.is_alive()
        )

    return bool(batches) and all(drained(p) for p in batches)


def _flush_in_thread(provider, flush, timeout_millis: int):
    """The provider's flush running now, else a new one."""
    with _flushes_lock:
        running = _flushes.get(provider)
        if running is None or not running[0].is_alive():
            outcome: list[bool] = []
            worker = threading.Thread(
                target=lambda: outcome.append(bool(flush(timeout_millis))),
                name="flock-trace-flush",
                daemon=True,
            )
            worker.start()
            running = (worker, outcome)
            _flushes[provider] = running
        return running


def flush_traces(timeout_millis: int = 5_000) -> bool:
    """Write the spans still waiting in a batch, waiting at most ``timeout_millis``.

    OpenTelemetry's ``force_flush`` can block longer than its timeout on a slow
    exporter, so it runs in a thread of its own that is left behind after the
    timeout. A later call waits for that flush and then flushes again, for the
    spans that ended meanwhile. Returns whether the flush finished in time and
    succeeded; a provider that was shut down has nothing left to write.
    """
    provider = trace.get_tracer_provider()
    flush = getattr(provider, "force_flush", None)
    if not callable(flush):
        return True
    deadline = time.monotonic() + timeout_millis / 1000
    with _flushes_lock:
        older = _flushes.get(provider)
    if older is not None and older[0].is_alive():
        older[0].join(max(0.0, deadline - time.monotonic()))
        if older[0].is_alive():
            return False
    if _stopped(provider):
        return True
    remaining = max(0, int((deadline - time.monotonic()) * 1000))
    worker, outcome = _flush_in_thread(provider, flush, remaining)
    worker.join(max(0.0, deadline - time.monotonic()))
    return not worker.is_alive() and outcome == [True]
