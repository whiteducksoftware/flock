"""RetentionPolicyComponent — prunes old changelog events on a schedule."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, PrivateAttr

from flock.components.orchestrator.base import OrchestratorComponent
from flock.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core import Flock
    from flock.core.store import BlackboardStore

logger = get_logger("flock.components.orchestrator.retention")


class RetentionConfig(BaseModel):
    """Configuration for the retention policy component.

    Attributes:
        max_age: Maximum age for changelog events. Events older than this are pruned.
        max_count: Maximum number of events to keep. None means no count limit.
        check_interval: How often to run the pruning check.
    """

    max_age: timedelta = Field(default_factory=lambda: timedelta(days=7))
    max_count: int | None = None
    check_interval: timedelta = Field(default_factory=lambda: timedelta(hours=1))


class RetentionPolicyComponent(OrchestratorComponent):
    """Periodically prunes old changelog events based on age and/or count limits.

    Runs a background asyncio task that wakes at ``check_interval`` and removes
    events that exceed the configured retention window.

    Examples:
        >>> from datetime import timedelta
        >>> config = RetentionConfig(max_age=timedelta(days=3), max_count=10000)
        >>> component = RetentionPolicyComponent(retention=config)
    """

    name: str = "retention_policy"
    priority: int = 90  # Runs late — housekeeping, not on the scheduling path
    retention: RetentionConfig = Field(default_factory=RetentionConfig)

    _store: BlackboardStore | None = PrivateAttr(default=None)
    _task: asyncio.Task | None = PrivateAttr(default=None)

    async def on_initialize(self, orchestrator: Flock) -> None:
        """Acquire a reference to the blackboard store and launch the pruning loop."""
        self._store = orchestrator.store
        self._task = asyncio.create_task(
            self._pruning_loop(), name="retention-policy-loop"
        )
        logger.info(
            "Retention policy started (max_age=%s, max_count=%s, interval=%s)",
            self.retention.max_age,
            self.retention.max_count,
            self.retention.check_interval,
        )

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Cancel the background task and wait for clean exit."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Retention policy stopped.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _pruning_loop(self) -> None:
        """Background loop: sleep, then prune. Repeats until cancelled."""
        try:
            while True:
                await asyncio.sleep(self.retention.check_interval.total_seconds())
                await self._run_prune()
        except asyncio.CancelledError:
            # Clean exit on shutdown
            return

    async def _run_prune(self) -> None:
        """Execute a single pruning pass (age-based, then count-based)."""
        if self._store is None:
            return

        total_pruned = 0

        # Age-based pruning
        cutoff = datetime.now(UTC) - self.retention.max_age
        pruned = await self._store.prune_changelog(before_time=cutoff)
        total_pruned += pruned

        # Count-based pruning
        if self.retention.max_count is not None:
            pruned = await self._prune_by_count(self.retention.max_count)
            total_pruned += pruned

        if total_pruned > 0:
            logger.info("Retention policy pruned %d changelog events.", total_pruned)

    async def _prune_by_count(self, keep_latest: int) -> int:
        """Remove oldest events so that at most *keep_latest* remain."""
        if self._store is None:
            return 0

        oldest_seq, latest_seq = await self._store.get_changelog_bounds()
        if oldest_seq == 0 and latest_seq == 0:
            return 0  # Empty changelog

        total_events = latest_seq - oldest_seq + 1
        if total_events <= keep_latest:
            return 0  # Within budget

        # Everything before this seq should be removed
        cutoff_seq = latest_seq - keep_latest + 1
        return await self._store.prune_changelog(before_seq=cutoff_seq)


__all__ = ["RetentionConfig", "RetentionPolicyComponent"]
