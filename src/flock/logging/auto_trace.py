"""Metaclass for automatic method tracing via OpenTelemetry."""

from __future__ import annotations

import os

from flock.logging.trace_and_logged import traced_and_logged


# Check if auto-tracing is enabled via environment variable
ENABLE_AUTO_TRACE = os.getenv("FLOCK_AUTO_TRACE", "true").lower() in {"true", "1", "yes", "on"}


# Auto-configure logging and telemetry when auto-tracing is enabled
if ENABLE_AUTO_TRACE:
    from flock.logging.logging import configure_logging
    from flock.logging.telemetry import TelemetryConfig

    # Configure logging to DEBUG
    configure_logging(
        flock_level="DEBUG",
        external_level="WARNING",
        specific_levels={
            "tools": "DEBUG",
            "agent": "DEBUG",
            "flock": "DEBUG",
        },
    )

    # Initialize telemetry for OTEL trace context
    # Only enable exporters if explicitly configured via env vars
    enable_file_export = os.getenv("FLOCK_TRACE_FILE", "false").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    enable_otlp_export = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") is not None

    telemetry_config = TelemetryConfig(
        service_name="flock-auto-trace",
        enable_jaeger=False,
        enable_file=enable_file_export,
        enable_sql=False,
        enable_otlp=enable_otlp_export,
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        local_logging_dir=".flock",
        file_export_name="traces.jsonl",
    )
    telemetry_config.setup_tracing()


class AutoTracedMeta(type):
    """Metaclass that automatically applies @traced_and_logged to all public methods.

    This enables automatic OpenTelemetry span creation and debug logging for all
    method calls on classes using this metaclass.

    Control via environment variable:
        FLOCK_AUTO_TRACE=true   - Enable auto-tracing (default)
        FLOCK_AUTO_TRACE=false  - Disable auto-tracing

    Example:
        class Agent(metaclass=AutoTracedMeta):
            def execute(self, ctx, artifacts):
                # Automatically traced and logged
                ...
    """

    def __new__(mcs, name, bases, namespace, **kwargs):
        """Create a new class with auto-traced methods."""
        if not ENABLE_AUTO_TRACE:
            # If auto-tracing is disabled, return the class unchanged
            return super().__new__(mcs, name, bases, namespace, **kwargs)

        # Apply @traced_and_logged to all public methods
        for attr_name, attr_value in list(namespace.items()):
            # Skip private methods (starting with _)
            if attr_name.startswith("_"):
                continue

            # Skip non-callables
            if not callable(attr_value):
                continue

            # Skip if already traced
            if getattr(attr_value, "_traced", False):
                continue

            # Skip if explicitly marked to skip tracing
            if getattr(attr_value, "_skip_trace", False):
                continue

            # Apply the decorator
            traced_func = traced_and_logged(attr_value)
            traced_func._traced = True  # Mark as traced to avoid double-wrapping
            namespace[attr_name] = traced_func

        return super().__new__(mcs, name, bases, namespace, **kwargs)


def skip_trace(func):
    """Decorator to mark a method to skip auto-tracing.

    Use this for methods that are called very frequently or are not
    interesting for debugging purposes.

    Example:
        class Agent(metaclass=AutoTracedMeta):
            @skip_trace
            def _internal_helper(self):
                # Not traced
                ...
    """
    func._skip_trace = True
    return func
