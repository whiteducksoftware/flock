# File: src/flock/core/logging.py
"""A unified logging module for Flock that works both in local/worker contexts and inside Temporal workflows.

Key points:
  - We always have Temporal imported, so we cannot decide based on import.
  - Instead, we dynamically check if we're in a workflow context by trying
    to call `workflow.info()`.
  - In a workflow, we use Temporal's built-in logger and skip debug/info/warning
    logs during replay.
  - Outside workflows, we use Loguru with rich formatting.
"""

import logging
import sys
from typing import Literal

from opentelemetry import trace

# Always import Temporal workflow (since it's part of the project)
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from loguru import logger as loguru_logger

# ENABLED_FLOCK_LOGGER_LEVELS constant removed

# Mapping from level names to numeric values
LOG_LEVELS: dict[str, int] = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "SUCCESS": 35,  # Custom success level
    "NO_LOGS": 100,  # Special level to disable logging
}


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


COLOR_MAP = {
    # Core & Orchestration
    "flock": "magenta",  # Color only
    "agent": "blue",  # Color only
    "workflow": "cyan",  # Color only
    "activities": "cyan",
    "context": "green",
    "mcp.server": "blue",
    "mcp.tool": "cyan",
    "mcp.client_manager": "light-blue",
    "mcp.client": "light-cyan",
    "mcp.callback.logging": "white",
    "mcp.callback.sampling": "pink",
    "mcp.callback.root": "light-yellow",
    "mcp.callback.message": "light-blue",
    # Components & Mechanisms
    "registry": "yellow",  # Color only
    "serialization": "yellow",
    "serialization.utils": "light-yellow",
    "evaluator": "light-blue",
    "module": "light-green",
    "router": "light-magenta",
    "mixin.dspy": "yellow",
    # Specific Modules (Examples)
    "memory": "yellow",
    "module.output": "green",
    "module.metrics": "blue",
    "module.zep": "red",
    "module.hierarchical": "light-green",
    # Tools & Execution
    "tools": "light-black",
    "interpreter": "light-yellow",
    # API Components
    "api": "white",  # Color only
    "api.main": "white",
    "api.endpoints": "light-black",
    "api.run_store": "light-black",
    "api.ui": "light-blue",  # Color only
    "api.ui.routes": "light-blue",
    "api.ui.utils": "cyan",
    # Default/Unknown
    "evaluators.declarative": "light-green",
    "unknown": "light-black",
}

LOGGERS = [
    "flock",  # Core Flock orchestration
    "flock.api", # Flock API specific logs
    "agent",  # General agent operations
    "context",  # Context management
    "registry",  # Unified registry operations (new)
    "serialization",  # General serialization (new - can be base for others)
    "serialization.utils",  # Serialization helpers (new, more specific)
    "evaluator",  # Base evaluator category (new/optional)
    "evaluators.declarative",  # Declarative evaluator specifics
    "module",  # Base module category (new/optional)
    "router",  # Base router category (new/optional)
    "mixin.dspy",  # DSPy integration specifics (new)
    "memory",  # Memory module specifics
    "module.output",  # Output module specifics (example specific module)
    "module.metrics",  # Metrics module specifics (example specific module)
    "module.zep",  # Zep module specifics (example specific module)
    "module.hierarchical",  # Hierarchical memory specifics (example specific module)
    "interpreter",  # Code interpreter (if still used)
    "activities",  # Temporal activities
    "workflow",  # Temporal workflow logic
    "tools",  # Tool execution/registration
    "api",  # General API server (new)
    "api.main",  # API main setup (new)
    "api.endpoints",  # API endpoints (new)
    "api.run_store",  # API run state management (new)
    "api.ui",  # UI general (new)
    "api.ui.routes",  # UI routes (new)
    "api.ui.utils",  # UI utils (new)
]

BOLD_CATEGORIES = [
    "flock",
    "agent",
    "workflow",
    "registry",
    "api",
    "api.ui",
]


def color_for_category(category: str) -> str:
    """Return the Rich markup color code name for the given category."""
    # Handle potentially nested names like 'serialization.utils'
    # Try exact match first, then go up the hierarchy
    if category in COLOR_MAP:
        return COLOR_MAP[category]
    parts = category.split(".")
    # Try progressively shorter parent categories
    for i in range(len(parts) - 1, 0, -1):
        parent_category = ".".join(parts[:i])
        if parent_category in COLOR_MAP:
            return COLOR_MAP[parent_category]
    # Fallback to default 'unknown' color
    return COLOR_MAP.get("unknown", "light-black")  # Final fallback


def custom_format(record):
    """A formatter that applies truncation and sequential styling tags."""
    t = record["time"].strftime("%Y-%m-%d %H:%M:%S")
    level_name = record["level"].name
    category = record["extra"].get("category", "unknown")
    trace_id = record["extra"].get("trace_id", "no-trace")
    color_tag = color_for_category(category)  # Get the color tag name (e.g., "yellow")

    message = record["message"]
    message = message.replace("{", "{{").replace("}", "}}")

    # MAX_LENGTH = 500 # Example value
    if len(message) > MAX_LENGTH:
        truncated_chars = len(message) - MAX_LENGTH
        message = (
            message[:MAX_LENGTH] + f"<yellow>...+({truncated_chars} chars)</yellow>"
        )

    # Determine if category needs bolding (can refine this logic)
    needs_bold = category in BOLD_CATEGORIES

    # Apply tags sequentially
    category_styled = f"[{category}]"  # Start with the plain category name
    category_styled = f"<{color_tag}>{category_styled}</{color_tag}>"  # Wrap with color
    if needs_bold:
        category_styled = f"<bold>{category_styled}</bold>"  # Wrap with bold if needed

    # Final format string using sequential tags for category
    return (
        f"<green>{t}</green> | <level>{level_name: <8}</level> | "
        f"<cyan>[trace_id: {trace_id}]</cyan> | "
        f"{category_styled} | {message}\n"  # Apply the sequentially styled category
    )


class ImmediateFlushSink:
    """A custom Loguru sink that writes to a stream and flushes immediately after each message.

    This ensures that logs appear in real time.
    """

    def __init__(self, stream=None):
        """Initialize the ImmediateFlushSink.

        Args:
            stream (Stream, optional): The stream to write to. Defaults to sys.stderr.
        """
        self._stream = stream if stream else sys.stderr

    def write(self, message):
        """Write a message to the stream and flush immediately.

        Args:
            message (str): The message to write.
        """
        self._stream.write(message)
        self._stream.flush()

    def flush(self):
        """Flush the stream."""
        self._stream.flush()


class PrintAndFlushSink:
    """A Loguru sink.

    forcibly prints each log record and flushes immediately,
    mimicking print(..., flush=True).
    """

    def write(self, message: str):
        """Write a message to the stream and flush immediately.

        Args:
            message (str): The message to write.
        """
        # message already ends with a newline
        print(message, end="", flush=True)

    def flush(self):
        """Flush the stream.

        Already flushed on every write call.
        """
        pass


# Configure Loguru for non-workflow (local/worker) contexts.
# Note that in workflow code, we will use Temporal's workflow.logger instead.
loguru_logger.remove()
loguru_logger.add(
    PrintAndFlushSink(),
    level="DEBUG",
    colorize=True,
    format=custom_format,
)
logging.basicConfig(level=LOG_LEVELS["ERROR"])  # Default to ERROR level for fallback
# Optionally add a file handler, e.g.:
# loguru_logger.add("logs/flock.log", rotation="100 MB", retention="30 days", level="DEBUG")


def get_default_severity(level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NO_LOGS", "SUCCESS"] | int) -> int:
    """Get the default severity for a given level."""
    if isinstance(level, str):
        level_str = level.upper()
        return LOG_LEVELS.get(level_str, LOG_LEVELS["ERROR"])
    return level


def configure_logging(flock_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NO_LOGS", "SUCCESS"] | int,
                      external_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NO_LOGS", "SUCCESS"] | int,
                      specific_levels: dict[str, Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NO_LOGS", "SUCCESS"] | int] | None = None) -> None:
    """Configure both external and internal Flock logging systems.

    Args:
        flock_level (str | int): The default logging level (e.g., "INFO", "ERROR", "DEBUG") or numeric level for Flock logging.
        external_level (str | int): The default logging level (e.g., "INFO", "ERROR", "DEBUG") or numeric level for external logging.
        specific_levels (dict[str, str | int] | None, optional): A dictionary mapping
            logger names to their specific logging levels. Defaults to None.
    """
    # Get default severity

    external_severity = get_default_severity(external_level)
    logging.basicConfig(level=external_severity)


    flock_severity = get_default_severity(flock_level)

    specific_severities = {}
    if specific_levels:
        for name, logger_level in specific_levels.items():
            severity = get_default_severity(logger_level)
            specific_severities[name] = severity

    # Apply to all cached loggers
    for logger_name, log_instance in _LOGGER_CACHE.items():
        target_severity = flock_severity
        if logger_name in specific_severities:
            target_severity = specific_severities[logger_name]

        log_instance.min_level_severity = target_severity




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


# Maximum length for log messages before truncation
MAX_LENGTH = 500


class FlockLogger:
    """A unified logger that selects the appropriate logging mechanism based on context.

    - If running in a workflow context, it uses Temporal's built-in logger.
      Additionally, if workflow.info().is_replaying is True, it suppresses debug/info/warning logs.
    - Otherwise, it uses Loguru.
    """

    def __init__(self, name: str, initial_min_level_severity: int):
        """Initialize the FlockLogger.

        Args:
            name (str): The name of the logger.
            initial_min_level_severity (int): The minimum severity level for messages to be logged.
        """
        self.name = name
        self.min_level_severity = initial_min_level_severity

    def _get_logger(self):
        if in_workflow_context():
            # Use Temporal's workflow.logger inside a workflow context.
            return workflow.logger
        # Bind our logger with category and trace_id
        return loguru_logger.bind(
            name=self.name,
            category=self.name,  # Customize this per module (e.g., "flock", "agent", "context")
            trace_id=get_current_trace_id(),
        )

    def _truncate_message(self, message: str, max_length: int) -> str:
        """Truncate a message if it exceeds max_length and add truncation indicator."""
        if len(message) > max_length:
            truncated_chars = len(message) - max_length
            return (
                message[:max_length] + f"...<yellow>+({truncated_chars} chars)</yellow>"
            )
        return message

    def debug(
        self,
        message: str,
        *args,
        flush: bool = False,
        max_length: int = MAX_LENGTH,
        **kwargs,
    ) -> None:
        current_method_severity = LOG_LEVELS["DEBUG"]
        if self.min_level_severity == LOG_LEVELS["NO_LOGS"] or \
           current_method_severity < self.min_level_severity:
            return
        """Debug a message.

        Args:
            message (str): The message to debug.
            flush (bool, optional): Whether to flush the message. Defaults to False.
            max_length (int, optional): The maximum length of the message. Defaults to MAX_LENGTH.
        """
        message = self._truncate_message(message, max_length)
        self._get_logger().debug(message, *args, **kwargs)

    def info(
        self,
        message: str,
        *args,
        flush: bool = False,
        max_length: int = MAX_LENGTH,
        **kwargs,
    ) -> None:
        current_method_severity = LOG_LEVELS["INFO"]
        if self.min_level_severity == LOG_LEVELS["NO_LOGS"] or \
           current_method_severity < self.min_level_severity:
            return
        """Info a message.

        Args:
            message (str): The message to info.
            flush (bool, optional): Whether to flush the message. Defaults to False.
            max_length (int, optional): The maximum length of the message. Defaults to MAX_LENGTH.
        """
        message = self._truncate_message(message, max_length)
        self._get_logger().info(message, *args, **kwargs)

    def warning(
        self,
        message: str,
        *args,
        flush: bool = False,
        max_length: int = MAX_LENGTH,
        **kwargs,
    ) -> None:
        current_method_severity = LOG_LEVELS["WARNING"]
        if self.min_level_severity == LOG_LEVELS["NO_LOGS"] or \
           current_method_severity < self.min_level_severity:
            return
        """Warning a message.

        Args:
            message (str): The message to warning.
            flush (bool, optional): Whether to flush the message. Defaults to False.
            max_length (int, optional): The maximum length of the message. Defaults to MAX_LENGTH.
        """
        message = self._truncate_message(message, max_length)
        self._get_logger().warning(message, *args, **kwargs)

    def error(
        self,
        message: str,
        *args,
        flush: bool = False,
        max_length: int = MAX_LENGTH,
        **kwargs,
    ) -> None:
        current_method_severity = LOG_LEVELS["ERROR"]
        if self.min_level_severity == LOG_LEVELS["NO_LOGS"] or \
           current_method_severity < self.min_level_severity:
            return
        """Error a message.

        Args:
            message (str): The message to error.
            flush (bool, optional): Whether to flush the message. Defaults to False.
            max_length (int, optional): The maximum length of the message. Defaults to MAX_LENGTH.
        """
        message = self._truncate_message(message, max_length)
        self._get_logger().error(message, *args, **kwargs)

    def exception(
        self,
        message: str,
        *args,
        flush: bool = False,
        max_length: int = MAX_LENGTH,
        **kwargs,
    ) -> None:
        current_method_severity = LOG_LEVELS["ERROR"] # Exception implies ERROR level
        if self.min_level_severity == LOG_LEVELS["NO_LOGS"] or \
           current_method_severity < self.min_level_severity:
            return
        """Exception a message.

        Args:
            message (str): The message to exception.
            flush (bool, optional): Whether to flush the message. Defaults to False.
            max_length (int, optional): The maximum length of the message. Defaults to MAX_LENGTH.
        """
        message = self._truncate_message(message, max_length)
        self._get_logger().exception(message, *args, **kwargs)

    def success(
        self,
        message: str,
        *args,
        flush: bool = False,
        max_length: int = MAX_LENGTH,
        **kwargs,
    ) -> None:
        current_method_severity = LOG_LEVELS["SUCCESS"]
        if self.min_level_severity == LOG_LEVELS["NO_LOGS"] or \
           current_method_severity < self.min_level_severity:
            return
        """Success a message.

        Args:
            message (str): The message to success.
            flush (bool, optional): Whether to flush the message. Defaults to False.
            max_length (int, optional): The maximum length of the message. Defaults to MAX_LENGTH.
        """
        message = self._truncate_message(message, max_length)
        self._get_logger().success(message, *args, **kwargs)


_LOGGER_CACHE: dict[str, FlockLogger] = {}


def get_logger(name: str = "flock") -> FlockLogger:
    """Return a cached FlockLogger instance for the given name.

    If the logger doesn't exist, it is created with 'enable_logging' set to False
    by default (i.e., errors-only mode). Its state can then be changed by calling
    the `configure_logging()` function.
    If a logger with the given name already exists in the cache, its 'min_level_severity'
    state is NOT modified by this function; it's simply returned.
    """
    if name not in _LOGGER_CACHE:
        # New loggers default to errors-only (min_level_severity = ERROR_SEVERITY)
        # until explicitly configured by configure_logging()
        _LOGGER_CACHE[name] = FlockLogger(name, LOG_LEVELS["ERROR"])
    # The min_level_severity state of existing or newly created loggers
    # should be managed by the configure_logging() function.
    return _LOGGER_CACHE[name]


def get_module_loggers() -> list[FlockLogger]:
    """Return a cached FlockLogger instance for the given module name."""
    result = []
    for kvp in _LOGGER_CACHE:
        if kvp.startswith("module."):
            result.append(_LOGGER_CACHE[kvp])

    return result


def truncate_for_logging(obj, max_item_length=100, max_items=10):
    """Truncate large data structures for logging purposes."""
    if isinstance(obj, str) and len(obj) > max_item_length:
        return obj[:max_item_length] + f"... ({len(obj) - max_item_length} more chars)"
    elif isinstance(obj, dict):
        if len(obj) > max_items:
            return {
                k: truncate_for_logging(v)
                for i, (k, v) in enumerate(obj.items())
                if i < max_items
            }
        return {k: truncate_for_logging(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        if len(obj) > max_items:
            return [truncate_for_logging(item) for item in obj[:max_items]] + [
                f"... ({len(obj) - max_items} more items)"
            ]
        return [truncate_for_logging(item) for item in obj]
    return obj
