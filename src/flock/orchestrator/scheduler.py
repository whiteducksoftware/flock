"""Agent scheduling engine."""

from __future__ import annotations

import asyncio
from asyncio import Task
from typing import TYPE_CHECKING, Any

from flock.components.orchestrator import ScheduleDecision


if TYPE_CHECKING:
    from flock.agent import Agent
    from flock.core import Flock
    from flock.core.artifacts import Artifact
    from flock.core.visibility import AgentIdentity
    from flock.orchestrator import ComponentRunner


class AgentScheduler:
    """Schedules agents for execution based on artifact subscriptions.

    Responsibilities:
    - Match artifacts to agent subscriptions
    - Run scheduling hooks via ComponentRunner
    - Create agent execution tasks
    - Manage task lifecycle
    - Track processed artifacts for deduplication
    """

    def __init__(self, orchestrator: Flock, component_runner: ComponentRunner):
        """Initialize scheduler.

        Args:
            orchestrator: Flock orchestrator instance
            component_runner: Runner for executing component hooks
        """
        self._orchestrator = orchestrator
        self._component_runner = component_runner
        self._tasks: set[Task[Any]] = set()
        self._processed: set[tuple[str, str]] = set()
        self._logger = orchestrator._logger

    async def schedule_artifact(self, artifact: Artifact) -> None:
        """Schedule agents for an artifact using component hooks.

        Args:
            artifact: Published artifact to match against subscriptions
        """
        # Initialize components on first artifact
        if not self._component_runner.is_initialized:
            await self._component_runner.run_initialize(self._orchestrator)

        # Component hook - artifact published (can transform or block)
        artifact = await self._component_runner.run_artifact_published(
            self._orchestrator, artifact
        )
        if artifact is None:
            return  # Artifact blocked by component

        for agent in self._orchestrator.agents:
            identity = agent.identity
            for subscription in agent.subscriptions:
                if not subscription.accepts_events():
                    continue

                # Check prevent_self_trigger
                if agent.prevent_self_trigger and artifact.produced_by == agent.name:
                    continue  # Skip - agent produced this artifact

                # Visibility check
                if not self._check_visibility(artifact, identity):
                    continue

                # Subscription match check
                if not subscription.matches(artifact):
                    continue

                # Component hook - before schedule (circuit breaker, deduplication)
                decision = await self._component_runner.run_before_schedule(
                    self._orchestrator, artifact, agent, subscription
                )
                if decision == ScheduleDecision.SKIP:
                    continue
                if decision == ScheduleDecision.DEFER:
                    continue

                # Component hook - collect artifacts (AND gates, correlation, batching)
                collection = await self._component_runner.run_collect_artifacts(
                    self._orchestrator, artifact, agent, subscription
                )
                if not collection.complete:
                    continue  # Still collecting

                artifacts = collection.artifacts

                # Component hook - before agent schedule (final validation)
                artifacts = await self._component_runner.run_before_agent_schedule(
                    self._orchestrator, agent, artifacts
                )
                if artifacts is None:
                    continue  # Scheduling blocked

                # Schedule agent task
                is_batch_execution = subscription.batch is not None
                task = self.schedule_task(agent, artifacts, is_batch=is_batch_execution)

                # Component hook - agent scheduled (notification)
                await self._component_runner.run_agent_scheduled(
                    self._orchestrator, agent, artifacts, task
                )

    def schedule_task(
        self, agent: Agent, artifacts: list[Artifact], is_batch: bool = False
    ) -> Task[Any]:
        """Schedule agent task and return the task handle.

        Args:
            agent: Agent to execute
            artifacts: Input artifacts
            is_batch: Whether this is batch execution

        Returns:
            Asyncio task handle
        """
        task = asyncio.create_task(
            self._orchestrator._run_agent_task(agent, artifacts, is_batch=is_batch)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def record_agent_run(self, agent: Agent) -> None:
        """Record agent run metric.

        Args:
            agent: Agent that ran
        """
        self._orchestrator.metrics["agent_runs"] += 1

    def mark_processed(self, artifact: Artifact, agent: Agent) -> None:
        """Mark artifact as processed by agent.

        Args:
            artifact: Processed artifact
            agent: Agent that processed it
        """
        key = (str(artifact.id), agent.name)
        self._processed.add(key)

    def seen_before(self, artifact: Artifact, agent: Agent) -> bool:
        """Check if artifact was already processed by agent.

        Args:
            artifact: Artifact to check
            agent: Agent to check

        Returns:
            True if already processed
        """
        key = (str(artifact.id), agent.name)
        return key in self._processed

    def _check_visibility(self, artifact: Artifact, identity: AgentIdentity) -> bool:
        """Check if artifact is visible to agent.

        Args:
            artifact: Artifact to check
            identity: Agent identity

        Returns:
            True if visible
        """
        try:
            return artifact.visibility.allows(identity)
        except AttributeError:  # pragma: no cover - fallback
            return True

    @property
    def pending_tasks(self) -> set[Task[Any]]:
        """Get set of pending agent tasks.

        Returns:
            Set of asyncio tasks
        """
        return self._tasks


__all__ = ["AgentScheduler"]
