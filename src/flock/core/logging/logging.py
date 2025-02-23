# File: src/flock/core/logging.py
"""A unified logging module for Flock that works both in local/worker contexts and inside Temporal workflows.

Key points:
  - We always have Temporal imported, so we cannot decide based on import.
  - Instead, we dynamically check if we're in a workflow context by trying
    to call `workflow.info()`.
  - In a workflow, we use Temporal’s built-in logger and skip debug/info/warning
    logs during replay.
  - Outside workflows, we use Loguru with rich formatting.
"""

import sys

from opentelemetry import trace

# Always import Temporal workflow (since it's part of the project)
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from loguru import logger as loguru_logger


def in_workflow_context() -> bool:
    """Returns True if this code is running inside a Temporal workflow context.

    It does this by attempting to call workflow.info() and returning True
    if successful. Otherwise, it returns False.
    """
    try:
        workflow.logger.debug("Checking if in workflow context...")
        # loguru_logger.debug("Checking if in workflow context...")
        # This call will succeed only if we're in a workflow context.
        return bool(hasattr(workflow.info(), "is_replaying"))
    except Exception:
        return False


def get_current_trace_id() -> str:
    """Fetch the current trace ID from OpenTelemetry, if available."""
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()
    # Format the trace_id as hex (if valid)
    if span_context.is_valid:
        return format(span_context.trace_id, "032x")
    return "no-trace"


# ---------------------------------------------------------------------
# 2. A color map for different logger names
#    You can add or change entries as you like.
# ---------------------------------------------------------------------
COLOR_MAP = {
    "flock": "magenta",
    "interpreter": "cyan",
    "memory": "yellow",
    "activities": "blue",
    "context": "green",
    "registry": "white",
    "tools": "light-black",
    "agent": "light-magenta",
}

LOGGERS = [
    "flock",
    "interpreter",
    "memory",
    "activities",
    "context",
    "registry",
    "tools",
    "agent",
]


def color_for_category(category: str) -> str:
    """Return the ANSI color code name for the given category."""
    return COLOR_MAP.get(category, "magenta")  # fallback color


def custom_format(record):
    """A function-based formatter for Loguru that.

    - Prints the time in green
    - Prints the level with Loguru's <level> tag
    - Prints the trace_id in cyan
    - Looks up the category in the record's extras and applies a color
    - Finally prints the message
    """
    t = record["time"].strftime("%Y-%m-%d %H:%M:%S")
    level_name = record["level"].name
    category = record["extra"].get("category", "unknown")
    trace_id = record["extra"].get("trace_id", "no-trace")
    color = color_for_category(category)
    message = record["message"]

    return (
        f"<green>{t}</green> | <level>{level_name: <8}</level> | "
        f"<cyan>[trace_id: {trace_id}]</cyan> | "
        f"<{color}>[{category}]</{color}> | {message}\n"
    )


class ImmediateFlushSink:
    """A custom Loguru sink that writes to a stream and flushes immediately after each message.
    This ensures that logs appear in real time.
    """

    def __init__(self, stream=None):
        self._stream = stream if stream else sys.stderr

    def write(self, message):
        self._stream.write(message)
        self._stream.flush()

    def flush(self):
        self._stream.flush()


class PrintAndFlushSink:
    """A Loguru sink that forcibly prints each log record and flushes immediately,
    mimicking print(..., flush=True).
    """

    def write(self, message: str):
        # message already ends with a newline
        print(message, end="", flush=True)

    def flush(self):
        pass  # Already flushed on every write call.


# Configure Loguru for non-workflow (local/worker) contexts.
# Note that in workflow code, we will use Temporal's workflow.logger instead.
loguru_logger.remove()
loguru_logger.add(
    PrintAndFlushSink(),
    level="DEBUG",
    colorize=True,
    format=custom_format,
)
# Optionally add a file handler, e.g.:
# loguru_logger.add("logs/flock.log", rotation="100 MB", retention="30 days", level="DEBUG")


# Define a dummy logger that does nothing
class DummyLogger:
    """A dummy logger that does nothing when called."""

    def debug(self, *args, **kwargs):  # noqa: D102
        pass

    def info(self, *args, **kwargs):  # noqa: D102
        pass

    def warning(self, *args, **kwargs):  # noqa: D102
        pass

    def error(self, *args, **kwargs):  # noqa: D102
        pass

    def exception(self, *args, **kwargs):  # noqa: D102
        pass

    def success(self, *args, **kwargs):  # noqa: D102
        pass


dummy_logger = DummyLogger()


class FlockLogger:
    """A unified logger that selects the appropriate logging mechanism based on context.

    - If running in a workflow context, it uses Temporal's built-in logger.
      Additionally, if workflow.info().is_replaying is True, it suppresses debug/info/warning logs.
    - Otherwise, it uses Loguru.
    """

    def __init__(self, name: str, enable_logging: bool = False):
        self.name = name
        self.enable_logging = enable_logging

    def _get_logger(self):
        if not self.enable_logging:
            return dummy_logger
        if in_workflow_context():
            # Use Temporal's workflow.logger inside a workflow context.
            return workflow.logger
        # Bind our logger with category and trace_id
        return loguru_logger.bind(
            name=self.name,
            category=self.name,  # Customize this per module (e.g., "flock", "agent", "context")
            trace_id=get_current_trace_id(),
        )

    def debug(self, message: str, *args, flush: bool = False, **kwargs) -> None:
        self._get_logger().debug(message, *args, **kwargs)

    def info(self, message: str, *args, flush: bool = False, **kwargs) -> None:
        self._get_logger().info(message, *args, **kwargs)

    def warning(
        self, message: str, *args, flush: bool = False, **kwargs
    ) -> None:
        self._get_logger().warning(message, *args, **kwargs)

    def error(self, message: str, *args, flush: bool = False, **kwargs) -> None:
        self._get_logger().error(message, *args, **kwargs)

    def exception(
        self, message: str, *args, flush: bool = False, **kwargs
    ) -> None:
        self._get_logger().exception(message, *args, **kwargs)

    def success(
        self, message: str, *args, flush: bool = False, **kwargs
    ) -> None:
        self._get_logger().success(message, *args, **kwargs)


_LOGGER_CACHE: dict[str, FlockLogger] = {}


def get_logger(name: str = "flock", enable_logging: bool = True) -> FlockLogger:
    """Return a cached FlockLogger instance for the given name.
    If the logger doesn't exist, create it.
    If it does exist, update 'enable_logging' if a new value is passed.
    """
    if name not in _LOGGER_CACHE:
        _LOGGER_CACHE[name] = FlockLogger(name, enable_logging)
    else:
        _LOGGER_CACHE[name].enable_logging = enable_logging
    return _LOGGER_CACHE[name]


def get_module_loggers() -> list[FlockLogger]:
    """Return a cached FlockLogger instance for the given module name."""
    result = []
    for kvp in _LOGGER_CACHE:
        if kvp.startswith("module."):
            result.append(_LOGGER_CACHE[kvp])

    return result
