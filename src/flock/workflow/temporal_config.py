# src/flock/config/temporal_config.py

"""Pydantic models for configuring Temporal execution settings."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

# Conditionally import for type hinting only
if TYPE_CHECKING:
    from temporalio.common import RetryPolicy

# Note: Importing temporalio types directly into config models can complicate serialization
# if these models are meant to be purely data containers (e.g., for YAML/JSON).
# We define the structure and provide a helper method to convert to the actual Temporal object.
# Be careful if using workflow/activity decorators directly on methods within these config models.
from pydantic import BaseModel, Field


class TemporalRetryPolicyConfig(BaseModel):
    """Configuration parameters for Temporal Retry Policies."""

    initial_interval: timedelta = Field(
        default=timedelta(seconds=1),
        description="Initial delay before the first retry.",
    )
    backoff_coefficient: float = Field(
        default=2.0, description="Multiplier for the delay between retries."
    )
    maximum_interval: timedelta | None = Field(
        default=timedelta(seconds=100),
        description="Maximum delay between retries.",
    )
    maximum_attempts: int = Field(
        default=3,
        description="Maximum number of retry attempts (0 means no retries after first failure).",
    )
    non_retryable_error_types: list[str] = Field(
        default_factory=list,
        description="List of error type names (strings) that should not be retried.",
    )

    # Helper to convert to actual Temporalio object when needed (e.g., in workflow/executor)
    def to_temporalio_policy(self) -> RetryPolicy:
        # Import locally to avoid making temporalio a hard dependency of the config module itself
        # The type hint RetryPolicy is now available due to TYPE_CHECKING block
        from temporalio.common import RetryPolicy

        return RetryPolicy(
            initial_interval=self.initial_interval,
            backoff_coefficient=self.backoff_coefficient,
            maximum_interval=self.maximum_interval,
            maximum_attempts=self.maximum_attempts,
            non_retryable_error_types=self.non_retryable_error_types,
        )


class TemporalWorkflowConfig(BaseModel):
    """Configuration specific to Temporal Workflow Execution for a Flock."""

    task_queue: str = Field(
        default="flock-queue",
        description="Default task queue for the workflow execution.",
    )
    workflow_execution_timeout: timedelta | None = Field(
        default=None,  # Default to no timeout (Temporal server default)
        description="Total time limit for the workflow execution.",
    )
    workflow_run_timeout: timedelta | None = Field(
        default=None,  # Default to no timeout (Temporal server default)
        description="Time limit for a single workflow run attempt.",
    )
    # Default retry policy for activities if not specified per-agent
    default_activity_retry_policy: TemporalRetryPolicyConfig = Field(
        default_factory=TemporalRetryPolicyConfig,
        description="Default retry policy applied to activities if not overridden by the agent.",
    )


class TemporalActivityConfig(BaseModel):
    """Configuration specific to Temporal Activity Execution (per Agent)."""

    task_queue: str | None = Field(
        default=None,
        description="Specific task queue for this agent's activity execution (overrides workflow default).",
    )
    start_to_close_timeout: timedelta | None = Field(
        default=timedelta(minutes=5),  # Default to 5 minutes
        description="Time limit for a single activity attempt.",
    )
    retry_policy: TemporalRetryPolicyConfig | None = Field(
        default=None,
        description="Specific retry policy for this activity (overrides workflow default).",
    )
    # Other timeouts like schedule_to_start, heartbeat_timeout could be added here if needed
