"""Drive one isolated Flock instance through a single workflow.

Internal building block for :mod:`flock.application`. A ``WorkflowRuntime``
owns a freshly built :class:`~flock.core.Flock` for exactly one workflow: it
scopes the instance to the workflow id, publishes the input, reports progress
until the cascade is quiescent and tears everything down in a fixed order.

Unlike ``run_until_idle()`` it never runs idle hooks mid-workflow (which reset
circuit-breaker counters), flushes partial batches once no producer remains
and cancels in-flight agent tasks before closing their MCP sessions.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

    from flock.core import Flock
    from flock.core.artifacts import Artifact
    from flock.orchestrator.scheduler import AgentTaskOutcome


@dataclass
class RuntimeDiagnostics:
    """Facts about how a workflow's cascade ended."""

    partial_batches_flushed: int = 0
    incomplete_joins: int = 0
    leftover_tasks: int = 0
    tripped_agents: list[str] = field(default_factory=list)
    crashed_timers: list[str] = field(default_factory=list)


class WorkflowRuntime:
    """Own one Flock instance for the lifetime of one workflow."""

    def __init__(self, flock: Flock, workflow_id: str) -> None:
        self._flock = flock
        self._workflow_id = workflow_id
        self._removers: list[Callable[[], None]] = []
        self.diagnostics = RuntimeDiagnostics()
        self._closed = False

    @property
    def flock(self) -> Flock:
        return self._flock

    def install(
        self,
        *,
        on_publish: Callable[[Artifact], None],
        on_task_outcome: Callable[[AgentTaskOutcome], None],
    ) -> None:
        """Scope the instance and register observers (before any publication)."""
        self._flock._set_workflow_scope(self._workflow_id)
        self._removers.append(self._flock._add_publication_listener(on_publish))
        self._removers.append(
            self._flock._scheduler.add_task_outcome_listener(on_task_outcome)
        )

    async def start(self, value: BaseModel) -> None:
        """Initialize components once, then publish the workflow input."""
        await self._flock._run_initialize()
        await self._flock.publish(value, correlation_id=self._workflow_id)

    def is_quiescent(self) -> bool:
        """No agent task pending and no active timer."""
        return not self._flock._scheduler.pending_tasks and not (
            self._flock._has_active_timers()
        )

    async def wait_for_progress(self, wake: asyncio.Event) -> None:
        """Wait until some agent task finishes, new work appears or ``wake`` fires."""
        waiter = asyncio.ensure_future(wake.wait())
        try:
            pending = set(self._flock._scheduler.pending_tasks)
            if pending:
                await asyncio.wait(
                    {*pending, waiter}, return_when=asyncio.FIRST_COMPLETED
                )
                return
            # Only timers are active: keep native batch timeouts working and
            # wait for the next tick (or a short poll interval).
            if self._flock._lifecycle_manager.has_pending_batches:
                await self._flock._lifecycle_manager.start_batch_timeout_checker()
            activity = asyncio.ensure_future(
                self._flock._scheduler.wait_for_activity(timeout=0.1)
            )
            try:
                await asyncio.wait(
                    {activity, waiter}, return_when=asyncio.FIRST_COMPLETED
                )
            finally:
                activity.cancel()
        finally:
            waiter.cancel()

    async def flush_partial_batches(self) -> int:
        """Flush every partial batch; no producer remains once the cascade is quiescent.

        Returns:
            Number of batches that were flushed (and scheduled).
        """
        if not self._flock._lifecycle_manager.has_pending_batches:
            return 0
        flushed = 0

        async def schedule(
            agent_name: str, _subscription_index: int, artifacts: list[Artifact]
        ) -> None:
            nonlocal flushed
            agent = self._flock._agents.get(agent_name)
            if agent is not None and self._flock._schedule_task(
                agent, artifacts, is_batch=True
            ):
                flushed += 1

        await self._flock._lifecycle_manager.flush_all_batches(schedule)
        self.diagnostics.partial_batches_flushed += flushed
        return flushed

    def tripped_agents(self) -> set[str]:
        """Agents whose circuit breaker tripped during this workflow."""
        from flock.components.orchestrator import CircuitBreakerComponent

        tripped: set[str] = set()
        for component in self._flock._components:
            if isinstance(component, CircuitBreakerComponent):
                tripped |= component.tripped_agents
        return tripped

    def crashed_timers(self) -> set[str]:
        """Agents whose timer loop crashed during this workflow."""
        from flock.components.orchestrator.scheduling.timer import TimerComponent

        crashed: set[str] = set()
        for component in self._flock._components:
            if isinstance(component, TimerComponent):
                crashed |= component.crashed_timers
        return crashed

    def count_incomplete_joins(self) -> int:
        """Waiting AND-gate pools plus open JoinSpec groups."""
        joins = sum(
            len(groups)
            for groups in self._flock._correlation_engine.correlation_groups.values()
        )
        pools = getattr(self._flock._artifact_collector, "_waiting_pools", {})
        and_gates = sum(
            1
            for pool in pools.values()
            if any(artifacts for artifacts in pool.values())
        )
        return joins + and_gates

    async def close(self, grace: float) -> None:
        """Tear the instance down in a fixed, safe order (idempotent).

        Closes the scheduling gate, then delegates to ``Flock.shutdown()``:
        component hooks (stop timers), cancel and await agent tasks within
        ``grace``, lifecycle background tasks, MCP connections.
        """
        if self._closed:
            return
        self._closed = True
        flock = self._flock
        self.diagnostics.incomplete_joins = self.count_incomplete_joins()
        self.diagnostics.tripped_agents = sorted(self.tripped_agents())
        self.diagnostics.crashed_timers = sorted(self.crashed_timers())

        flock._scheduler.close_gate()
        # Flock.shutdown() owns the safe order: component hooks (timers), then
        # cancel + await agent tasks, then background tasks and MCP connections.
        await flock.shutdown(cancel_grace=grace)
        # Flock.shutdown() already logged tasks that outlived the grace period.
        self.diagnostics.leftover_tasks = sum(
            1 for task in flock._scheduler.pending_tasks if not task.done()
        )
        for remove in self._removers:
            remove()
        self._removers.clear()

    def describe(self) -> dict[str, Any]:
        """Diagnostics as plain data."""
        return {
            "partial_batches_flushed": self.diagnostics.partial_batches_flushed,
            "incomplete_joins": self.diagnostics.incomplete_joins,
            "leftover_tasks": self.diagnostics.leftover_tasks,
            "tripped_agents": list(self.diagnostics.tripped_agents),
            "crashed_timers": list(self.diagnostics.crashed_timers),
        }


__all__ = ["RuntimeDiagnostics", "WorkflowRuntime"]
