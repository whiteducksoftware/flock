"""Deduplication component to prevent duplicate artifact processing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flock.components.orchestrator.base import OrchestratorComponent, ScheduleDecision


if TYPE_CHECKING:
    from flock.core import Agent, Flock
    from flock.core.artifacts import Artifact
    from flock.core.subscription import Subscription


class DeduplicationComponent(OrchestratorComponent):
    """Deduplication to prevent agents from processing same artifact multiple times.

    Tracks which artifacts have been processed by which agents and skips
    duplicate scheduling attempts.

    Priority: 20 (runs after circuit breaker at 10)

    Examples:
        >>> # Auto-added to all orchestrators
        >>> flock = Flock("openai/gpt-4.1")

        >>> # Deduplication prevents:
        >>> # - Agents re-processing artifacts they already handled
        >>> # - Feedback loops from agent self-triggers
        >>> # - Duplicate work from retry logic
    """

    priority: int = 20  # Run after circuit breaker (10)
    name: str = "deduplication"

    def __init__(self, **kwargs):
        """Initialize deduplication with empty processed set."""
        super().__init__(**kwargs)
        self._processed: set[tuple[str, str]] = set()  # (artifact_id, agent_name)

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Check if artifact has already been processed by this agent.

        Returns SKIP if agent has already processed this artifact,
        preventing duplicate work.
        """
        key = (str(artifact.id), agent.name)

        if key in self._processed:
            # Already processed - skip
            return ScheduleDecision.SKIP

        # Not yet processed - allow
        return ScheduleDecision.CONTINUE

    async def on_before_agent_schedule(
        self, orchestrator: Flock, agent: Agent, artifacts: list[Artifact]
    ) -> list[Artifact]:
        """Mark artifacts as processed before agent execution.

        This ensures artifacts are marked as seen even if agent execution fails,
        preventing infinite retry loops.
        """
        for artifact in artifacts:
            key = (str(artifact.id), agent.name)
            self._processed.add(key)

        return artifacts


__all__ = ["DeduplicationComponent"]
