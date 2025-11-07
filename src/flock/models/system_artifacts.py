"""System-level artifact types published by the Flock orchestrator.

These artifacts provide workflow telemetry and error tracking.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


@flock_type
class TimerTick(BaseModel):
    """Internal artifact published by timer component to trigger scheduled agents.

    This is an internal infrastructure artifact. User agents receive
    empty input (ctx.artifacts = []) with timer metadata in context.
    """

    model_config = ConfigDict(frozen=True)

    timer_name: str = Field(description="Agent name for filtering")
    fire_time: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When the timer fired"
    )
    iteration: int = Field(default=0, description="Number of times timer has fired")
    schedule_spec: dict[str, Any] = Field(
        default_factory=dict, description="Original schedule config"
    )


__all__ = ["TimerTick", "WorkflowError"]
