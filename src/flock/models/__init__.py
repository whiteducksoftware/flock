"""System data models for Flock.

This module contains system-level artifact types used by the orchestrator
for error handling, workflow tracking, and internal communication.
"""

from flock.models.system_artifacts import WorkflowError


__all__ = ["WorkflowError"]
