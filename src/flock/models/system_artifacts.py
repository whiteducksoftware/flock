"""System-level artifact types published by the Flock orchestrator.

These artifacts provide workflow telemetry and error tracking.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from flock.registry import flock_type


@flock_type
class WorkflowError(BaseModel):
    """Error artifact published when an agent execution fails.

    This artifact is automatically published by the orchestrator when an agent
    raises an exception during execution. It includes the correlation_id to enable
    error tracking for workflows.

    The workflow continues execution for other branches even when this is published.
    """

    failed_agent: str = Field(description="Name of the agent that failed")
    error_type: str = Field(description="Type of exception that occurred")
    error_message: str = Field(description="Error message from the exception")
    timestamp: datetime = Field(description="When the error occurred")
    task_id: str | None = Field(
        default=None, description="Task ID of the failed execution"
    )


__all__ = ["WorkflowError"]
