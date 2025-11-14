"""Flock logging system with Rich integration and structured logging support.

Public entry points:
- configure_logging: configure Flock + external logging levels
- get_logger: obtain a module-specific FlockLogger instance
"""

from flock.logging.logging import configure_logging, get_logger


__all__ = ["configure_logging", "get_logger"]
