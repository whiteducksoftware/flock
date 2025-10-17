"""Metaclass for automatic method tracing via OpenTelemetry."""

from __future__ import annotations

import json
import os

from flock.logging.trace_and_logged import _trace_filter_config, traced_and_logged


# Check if auto-tracing is enabled via environment variable
ENABLE_AUTO_TRACE = os.getenv("FLOCK_AUTO_TRACE", "true").lower() in {
    "true",
    "1",
    "yes",
    "on",
}


# Parse trace filter configuration from environment variables
def _parse_trace_filters():
    """Parse FLOCK_TRACE_SERVICES and FLOCK_TRACE_IGNORE from environment."""
    # Parse FLOCK_TRACE_SERVICES (whitelist)
    services_env = os.getenv("FLOCK_TRACE_SERVICES", "")
    if services_env:
        try:
            services_list = json.loads(services_env)
            if isinstance(services_list, list):
                # Store as lowercase set for case-insensitive matching
                _trace_filter_config.services = {
                    s.lower() for s in services_list if isinstance(s, str)
                }
        except (json.JSONDecodeError, ValueError):
            print(f"Warning: Invalid FLOCK_TRACE_SERVICES format: {services_env}")

    # Parse FLOCK_TRACE_IGNORE (blacklist)
    ignore_env = os.getenv("FLOCK_TRACE_IGNORE", "")
    if ignore_env:
        try:
            ignore_list = json.loads(ignore_env)
            if isinstance(ignore_list, list):
                _trace_filter_config.ignore_operations = {
                    op for op in ignore_list if isinstance(op, str)
                }
        except (json.JSONDecodeError, ValueError):
            print(f"Warning: Invalid FLOCK_TRACE_IGNORE format: {ignore_env}")


# Auto-configure logging and telemetry when auto-tracing is enabled
if ENABLE_AUTO_TRACE:
    # Configure trace filters first
    _parse_trace_filters()
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

    # Parse TTL (Time To Live) for trace cleanup
    trace_ttl_days = None
    ttl_env = os.getenv("FLOCK_TRACE_TTL_DAYS", "")
    if ttl_env:
        try:
            trace_ttl_days = int(ttl_env)
        except ValueError:
            print(f"Warning: Invalid FLOCK_TRACE_TTL_DAYS value: {ttl_env}")

    telemetry_config = TelemetryConfig(
        service_name="flock-auto-trace",
        enable_jaeger=False,
        enable_file=False,  # Disable file export, use DuckDB instead
        enable_sql=False,
        enable_duckdb=enable_file_export,  # Use DuckDB when file export is enabled
        enable_otlp=enable_otlp_export,
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        local_logging_dir=".flock",
        duckdb_name="traces.duckdb",
        duckdb_ttl_days=trace_ttl_days,
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
