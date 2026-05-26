


from pydantic import Field

from flock.core.config.flock_agent_config import FlockAgentConfig


class ScheduledAgentConfig(FlockAgentConfig):
    """Configuration specific to agents that run on a schedule."""
    schedule_expression: str = Field(
        ...,
        description="Defines when the agent should run. "
                    "Examples: 'every 60m', 'every 1h', 'daily at 02:00', '0 */2 * * *' (cron expression)"
    )
    enabled: bool = Field(
        True,
        description="Whether the scheduled agent is enabled. "
                    "If False, the agent will not run even if the schedule expression is valid."
    )
    initial_run: bool = Field(
        False,
        description="If True, the agent will run immediately after being scheduled, "
                    "regardless of the schedule expression."
    )
    max_runs: int = Field(
        0,
        description="Maximum number of times the agent can run. "
                    "0 means unlimited runs. If set, the agent will stop running after reaching this limit."
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure schedule_expression is always set
        if 'schedule_expression' not in kwargs:
            raise ValueError("schedule_expression is required for ScheduledAgentConfig")

        # Validate initial_run and max_runs
        if self.initial_run and self.max_runs > 0:
            raise ValueError("Cannot set initial_run to True if max_runs is greater than 0")
