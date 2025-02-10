# File: src/flock/core/logging.py
"""A unified logging module for Flock that works both in local/worker contexts
and inside Temporal workflows.

Key points:
  - We always have Temporal imported, so we cannot decide based on import.
  - Instead, we dynamically check if we're in a workflow context by trying
    to call `workflow.info()`.
  - In a workflow, we use Temporal’s built-in logger and skip debug/info/warning
    logs during replay.
  - Outside workflows, we use Loguru with rich formatting.
"""

import sys

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
        if hasattr(workflow.info(), "is_replaying"):
            return True
        else:
            return False
    except Exception:
        return False


# Configure Loguru for non-workflow (local/worker) contexts.
# Note that in workflow code, we will use Temporal's workflow.logger instead.
loguru_logger.remove()
loguru_logger.add(
    sys.stderr,
    level="DEBUG",
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
)
# Optionally add a file handler, e.g.:
# loguru_logger.add("logs/flock.log", rotation="100 MB", retention="30 days", level="DEBUG")


# Define a dummy logger that does nothing
class DummyLogger:
    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass

    def success(self, *args, **kwargs):
        pass


dummy_logger = DummyLogger()


class FlockLogger:
    """A unified logger that selects the appropriate logging mechanism based on context.

    - If running in a workflow context, it uses Temporal's built‑in logger.
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
        else:
            # Bind a new Loguru logger with the given name as context.
            return loguru_logger.bind(name=self.name)

    def debug(self, message: str, *args, **kwargs):
        self._get_logger().debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._get_logger().info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._get_logger().warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._get_logger().error(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self._get_logger().exception(message, *args, **kwargs)

    def success(self, message: str, *args, **kwargs):
        self._get_logger().success(message, *args, **kwargs)


def get_logger(name: str = "flock") -> FlockLogger:
    """Returns a FlockLogger instance for the given name.

    Import and use this function throughout your Flock code instead of importing Loguru directly.
    """
    return FlockLogger(name)
