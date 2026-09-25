"""Agent scheduling engine."""

from __future__ import annotations

import asyncio
from asyncio import Task
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from flock.components.orchestrator import ScheduleDecision


if TYPE_CHECKING:
    from flock.agent import Agent
    from flock.core import Flock
    from flock.core.artifacts import Artifact
    from flock.core.visibility import AgentIdentity
    from flock.orchestrator import ComponentRunner


@dataclass(frozen=True, slots=True)
class AgentTaskOutcome:
    """Terminal outcome of one scheduled agent task.

    Recorded by the scheduler when the task finishes. ``failed`` means the task
    ended with an exception that escaped the agent run (for example while
    building its context or persisting its outputs) - engine failures that are
    published as ``WorkflowError`` artifacts end as ``completed``.
    """

    agent_name: str
    task_id: str
    outcome: Literal["completed", "failed", "cancelled"]
    exc_type: str | None = None


TaskOutcomeListener = Callable[[AgentTaskOutcome], None]


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
        self._fallback_component_runner = component_runner
        self._runner_override: ComponentRunner | None = None
        self._tasks: set[Task[Any]] = set()
        self._processed: set[tuple[str, str]] = set()
        self._logger = orchestrator._logger
        # Gate for new work; closed while an owner tears the instance down.
        self._accepting = True
        self._outcome_listeners: list[TaskOutcomeListener] = []
        self._task_meta: dict[Task[Any], tuple[str, str]] = {}
        # Set whenever work is scheduled or finishes, so waiters can re-check.
        self._activity = asyncio.Event()

    @property
    def _component_runner(self) -> ComponentRunner:
        """The orchestrator's current component runner (single source of truth).

        An explicitly assigned runner (tests, extensions) takes precedence.
        """
        if self._runner_override is not None:
            return self._runner_override
        runner = getattr(self._orchestrator, "_component_runner", None)
        return runner if runner is not None else self._fallback_component_runner

    @_component_runner.setter
    def _component_runner(self, runner: ComponentRunner) -> None:
        self._runner_override = runner

    async def schedule_artifact(self, artifact: Artifact) -> None:
        """Schedule agents for an artifact using component hooks.

        Args:
            artifact: Published artifact to match against subscriptions
        """
        # Initialize components on first artifact (same entry point as
        # run_until*, so timers are registered and hooks run exactly once)
        if not self._component_runner.is_initialized:
            await self._orchestrator._run_initialize()

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
                if not artifacts:
                    continue  # Scheduling blocked, or every artifact was deferred

                # Schedule agent task
                is_batch_execution = subscription.batch is not None
                task = self.schedule_task(agent, artifacts, is_batch=is_batch_execution)
                if task is None:
                    continue  # Scheduling gate closed

                # Component hook - agent scheduled (notification)
                await self._component_runner.run_agent_scheduled(
                    self._orchestrator, agent, artifacts, task
                )

    def schedule_task(
        self, agent: Agent, artifacts: list[Artifact], is_batch: bool = False
    ) -> Task[Any] | None:
        """Schedule agent task and return the task handle.

        Args:
            agent: Agent to execute
            artifacts: Input artifacts
            is_batch: Whether this is batch execution

        Returns:
            Asyncio task handle, or None when the scheduling gate is closed
        """
        if not self._accepting:
            self._logger.debug(
                f"Scheduling gate closed: agent '{agent.name}' was not scheduled"
            )
            return None

        task_id = str(uuid4())
        task = asyncio.create_task(
            self._orchestrator._run_agent_task(
                agent, artifacts, is_batch=is_batch, task_id=task_id
            )
        )
        self._tasks.add(task)
        self._task_meta[task] = (agent.name, task_id)
        task.add_done_callback(self._on_task_done)
        self._activity.set()
        return task

    def _on_task_done(self, task: Task[Any]) -> None:
        """Record the task's outcome and release it in one step.

        Recording and discarding happen in the same callback so a waiter that
        sees an empty task set never misses a failure that is still pending.
        """
        agent_name, task_id = self._task_meta.pop(task, ("unknown", "unknown"))
        if task.cancelled():
            outcome = AgentTaskOutcome(agent_name, task_id, "cancelled")
        else:
            exc = task.exception()  # also marks the exception as retrieved
            if exc is None:
                outcome = AgentTaskOutcome(agent_name, task_id, "completed")
            else:
                self._logger.error(
                    f"Agent task failed outside the agent run: agent={agent_name}, "
                    f"task={task_id}, error={type(exc).__name__}"
                )
                outcome = AgentTaskOutcome(
                    agent_name, task_id, "failed", type(exc).__name__
                )
        self._tasks.discard(task)
        for listener in list(self._outcome_listeners):
            try:
                listener(outcome)
            except Exception:  # pragma: no cover - defensive
                self._logger.exception("Task outcome listener failed")
        self._activity.set()

    def add_task_outcome_listener(
        self, listener: TaskOutcomeListener
    ) -> Callable[[], None]:
        """Register a listener for agent task outcomes.

        Returns:
            Callable that unregisters the listener.
        """
        self._outcome_listeners.append(listener)

        def _remove() -> None:
            if listener in self._outcome_listeners:
                self._outcome_listeners.remove(listener)

        return _remove

    def close_gate(self) -> None:
        """Stop scheduling new agent tasks."""
        self._accepting = False

    def open_gate(self) -> None:
        """Resume scheduling new agent tasks."""
        self._accepting = True

    @property
    def accepting(self) -> bool:
        """Whether new agent tasks are scheduled."""
        return self._accepting

    async def wait_for_activity(self, timeout: float | None = None) -> None:  # noqa: ASYNC109
        """Wait until work is scheduled or finishes (or the timeout passes)."""
        self._activity.clear()
        try:
            await asyncio.wait_for(self._activity.wait(), timeout)
        except TimeoutError:
            pass

    async def cancel_all(self, grace: float) -> set[Task[Any]]:
        """Cancel every pending agent task and wait up to ``grace`` seconds.

        Returns:
            Tasks that did not finish within the grace period (for example
            work blocked in a thread that cannot be interrupted).
        """
        pending = {task for task in self._tasks if not task.done()}
        for task in pending:
            task.cancel()
        if not pending:
            return set()
        _done, still_running = await asyncio.wait(pending, timeout=grace)
        return set(still_running)

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


__all__ = ["AgentScheduler", "AgentTaskOutcome", "TaskOutcomeListener"]
