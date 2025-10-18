"""Lifecycle management for background tasks and cleanup.

Phase 5A: Extracted from orchestrator.py to isolate background task coordination.

This module handles background tasks for batch timeouts and correlation cleanup,
reducing orchestrator complexity and centralizing async task management.
"""

from __future__ import annotations

import asyncio
import logging
from asyncio import Task
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.orchestrator.batch_accumulator import BatchEngine
    from flock.orchestrator.correlation_engine import CorrelationEngine


class LifecycleManager:
    """Manages background tasks for batch and correlation lifecycle.

    This module centralizes all background task management for:
    - Correlation group cleanup (time-based expiry)
    - Batch timeout checking (timeout-based flushing)

    Phase 5A: Extracted to reduce orchestrator complexity and improve testability.
    """

    def __init__(
        self,
        *,
        correlation_engine: CorrelationEngine,
        batch_engine: BatchEngine,
        cleanup_interval: float = 0.1,
    ):
        """Initialize LifecycleManager with engines and intervals.

        Args:
            correlation_engine: Engine managing correlation groups
            batch_engine: Engine managing batch accumulation
            cleanup_interval: How often to check for expiry (seconds, default: 0.1)
        """
        self._correlation_engine = correlation_engine
        self._batch_engine = batch_engine
        self._cleanup_interval = cleanup_interval

        # Background tasks
        self._correlation_cleanup_task: Task[Any] | None = None
        self._batch_timeout_task: Task[Any] | None = None

        # Callback for batch timeout flushing (set by orchestrator)
        self._batch_timeout_callback: Any | None = None

        self._logger = logging.getLogger(__name__)

    async def start_correlation_cleanup(self) -> None:
        """Start background correlation cleanup loop if not already running.

        This ensures expired correlation groups are periodically discarded.
        Called when there are pending correlations during run_until_idle.
        """
        if (
            self._correlation_cleanup_task is None
            or self._correlation_cleanup_task.done()
        ):
            self._correlation_cleanup_task = asyncio.create_task(
                self._correlation_cleanup_loop()
            )

    def set_batch_timeout_callback(self, callback: Any) -> None:
        """Set the callback to invoke when batches timeout.

        Args:
            callback: Async function to call when timeout checking. Should handle
                flushing expired batches and scheduling agent tasks.
        """
        self._batch_timeout_callback = callback

    async def start_batch_timeout_checker(self) -> None:
        """Start background batch timeout checker loop if not already running.

        This ensures timeout-expired batches are periodically flushed.
        Called when there are pending batches during run_until_idle.
        """
        if self._batch_timeout_task is None or self._batch_timeout_task.done():
            self._batch_timeout_task = asyncio.create_task(
                self._batch_timeout_checker_loop()
            )

    async def shutdown(self) -> None:
        """Cancel and cleanup all background tasks.

        Called during orchestrator shutdown to ensure clean resource cleanup.
        """
        # Cancel correlation cleanup task if running
        if self._correlation_cleanup_task and not self._correlation_cleanup_task.done():
            self._correlation_cleanup_task.cancel()
            try:
                await self._correlation_cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel batch timeout checker if running
        if self._batch_timeout_task and not self._batch_timeout_task.done():
            self._batch_timeout_task.cancel()
            try:
                await self._batch_timeout_task
            except asyncio.CancelledError:
                pass

    # Background Loops ─────────────────────────────────────────────────────

    async def _correlation_cleanup_loop(self) -> None:
        """Background task that periodically cleans up expired correlation groups.

        Runs continuously until all correlation groups are cleared or orchestrator shuts down.
        Checks every 100ms for time-based expired correlations and discards them.
        """
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval)
                self._cleanup_expired_correlations()

                # Stop if no correlation groups remain
                if not self._correlation_engine.correlation_groups:
                    self._correlation_cleanup_task = None
                    break
        except asyncio.CancelledError:
            # Clean shutdown
            self._correlation_cleanup_task = None
            raise

    def _cleanup_expired_correlations(self) -> None:
        """Clean up all expired correlation groups across all subscriptions.

        Called periodically by background task to enforce time-based correlation windows.
        Discards incomplete correlations that have exceeded their time window.
        """
        # Get all active subscription keys
        for agent_name, subscription_index in list(
            self._correlation_engine.correlation_groups.keys()
        ):
            self._correlation_engine.cleanup_expired(agent_name, subscription_index)

    async def _batch_timeout_checker_loop(self) -> None:
        """Background task that periodically checks for batch timeouts.

        Runs continuously until all batches are cleared or orchestrator shuts down.
        Checks every 100ms for expired batches and flushes them via callback.
        """
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval)

                # Call the timeout callback to check and flush expired batches
                if self._batch_timeout_callback:
                    await self._batch_timeout_callback()

                # Stop if no batches remain
                if not self._batch_engine.batches:
                    self._batch_timeout_task = None
                    break
        except asyncio.CancelledError:
            # Clean shutdown
            self._batch_timeout_task = None
            raise

    # Helper Methods ───────────────────────────────────────────────────────

    async def check_batch_timeouts(self, orchestrator_callback: Any) -> None:
        """Check all batches for timeout expiry and invoke callback for expired batches.

        This method is called periodically by the background timeout checker
        or manually (in tests) to enforce timeout-based batching.

        Args:
            orchestrator_callback: Async function to call for each expired batch.
                Signature: async def callback(agent_name: str, subscription_index: int,
                                              artifacts: list[Artifact]) -> None
        """
        expired_batches = self._batch_engine.check_timeouts()

        for agent_name, subscription_index in expired_batches:
            # Flush the expired batch
            artifacts = self._batch_engine.flush_batch(agent_name, subscription_index)

            if artifacts is not None:
                # Invoke orchestrator callback to schedule task
                await orchestrator_callback(agent_name, subscription_index, artifacts)

    async def flush_all_batches(self, orchestrator_callback: Any) -> None:
        """Flush all partial batches (for shutdown - ensures zero data loss).

        Args:
            orchestrator_callback: Async function to call for each flushed batch.
                Signature: async def callback(agent_name: str, subscription_index: int,
                                              artifacts: list[Artifact]) -> None
        """
        all_batches = self._batch_engine.flush_all()

        for agent_name, subscription_index, artifacts in all_batches:
            # Invoke orchestrator callback to schedule task
            await orchestrator_callback(agent_name, subscription_index, artifacts)

    # Properties ───────────────────────────────────────────────────────────

    @property
    def has_pending_correlations(self) -> bool:
        """Check if there are any pending correlation groups."""
        return any(
            groups and any(group.waiting_artifacts for group in groups.values())
            for groups in self._correlation_engine.correlation_groups.values()
        )

    @property
    def has_pending_batches(self) -> bool:
        """Check if there are any pending batches."""
        return any(
            accumulator.artifacts for accumulator in self._batch_engine.batches.values()
        )


__all__ = ["LifecycleManager"]
