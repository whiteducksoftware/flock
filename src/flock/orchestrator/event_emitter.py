"""Event emission for real-time dashboard updates.

Phase 5A: Extracted from orchestrator.py to reduce coupling to dashboard.

This module handles WebSocket event emission for dashboard visualization of
batch and correlation logic operations. Separating this code reduces the
orchestrator's dependency on dashboard-specific components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.components.server.control.helpers import (  # noqa: F401
        _get_batch_state,
        _get_correlation_groups,
    )
    from flock.components.server.models.events import (  # noqa: F401
        BatchItemAddedEvent,
        CorrelationGroupUpdatedEvent,
        ExternalAgentCompletedEvent,
        ExternalAgentFailedEvent,
        ExternalAgentSpawnedEvent,
    )

    from flock.core.artifacts import Artifact
    from flock.core.subscription import Subscription
    from flock.orchestrator.batch_accumulator import BatchEngine
    from flock.orchestrator.correlation_engine import CorrelationEngine


class EventEmitter:
    """Manages WebSocket event emission for dashboard updates.

    This module is responsible for broadcasting real-time events about
    batch accumulation and correlation group status to connected dashboard
    clients via WebSocket.

    Phase 5A: Extracted to reduce orchestrator coupling to dashboard.
    """

    def __init__(self, websocket_manager: Any | None = None):
        """Initialize EventEmitter with WebSocket manager.

        Args:
            websocket_manager: WebSocket manager instance for broadcasting events.
                If None, event emission is disabled (dashboard not active).
        """
        self._websocket_manager = websocket_manager

    def set_websocket_manager(self, websocket_manager: Any | None) -> None:
        """Update the WebSocket manager (called when dashboard is enabled).

        Args:
            websocket_manager: WebSocket manager instance for broadcasting
        """
        self._websocket_manager = websocket_manager

    async def emit_correlation_updated(
        self,
        *,
        correlation_engine: CorrelationEngine,
        agent_name: str,
        subscription_index: int,
        artifact: Artifact,
    ) -> None:
        """Emit CorrelationGroupUpdatedEvent for real-time dashboard updates.

        Called when an artifact is added to a correlation group that is not yet complete.

        Args:
            correlation_engine: CorrelationEngine instance with current state
            agent_name: Name of the agent with the JoinSpec subscription
            subscription_index: Index of the subscription in the agent's subscriptions list
            artifact: The artifact that triggered this update
        """
        # Only emit if dashboard is enabled
        if self._websocket_manager is None:
            return

        # Deferred imports — circular-import safe (server -> core -> orchestrator)
        from flock.components.server.control.helpers import _get_correlation_groups
        from flock.components.server.models.events import CorrelationGroupUpdatedEvent

        # Get current correlation groups state from engine
        groups = _get_correlation_groups(
            correlation_engine, agent_name, subscription_index
        )

        if not groups:
            return  # No groups to report (shouldn't happen, but defensive)

        # Find the group that was just updated (match by last updated time or artifact ID)
        # For now, we'll emit an event for the FIRST group that's still waiting
        # In practice, the artifact we just added should be in one of these groups
        for group_state in groups:
            if not group_state["is_complete"]:
                # Build and emit event
                event = CorrelationGroupUpdatedEvent(
                    agent_name=agent_name,
                    subscription_index=subscription_index,
                    correlation_key=group_state["correlation_key"],
                    collected_types=group_state["collected_types"],
                    required_types=group_state["required_types"],
                    waiting_for=group_state["waiting_for"],
                    elapsed_seconds=group_state["elapsed_seconds"],
                    expires_in_seconds=group_state["expires_in_seconds"],
                    expires_in_artifacts=group_state["expires_in_artifacts"],
                    artifact_id=str(artifact.id),
                    artifact_type=artifact.type,
                    is_complete=group_state["is_complete"],
                )

                # Broadcast via WebSocket
                await self._websocket_manager.broadcast(event)
                break  # Only emit one event per artifact addition

    async def emit_batch_item_added(
        self,
        *,
        batch_engine: BatchEngine,
        agent_name: str,
        subscription_index: int,
        subscription: Subscription,
        artifact: Artifact,
    ) -> None:
        """Emit BatchItemAddedEvent for real-time dashboard updates.

        Called when an artifact is added to a batch that hasn't reached flush threshold.

        Args:
            batch_engine: BatchEngine instance with current state
            agent_name: Name of the agent with the BatchSpec subscription
            subscription_index: Index of the subscription in the agent's subscriptions list
            subscription: The subscription with BatchSpec configuration
            artifact: The artifact that triggered this update
        """
        # Only emit if dashboard is enabled
        if self._websocket_manager is None:
            return

        # Deferred imports — circular-import safe (server -> core -> orchestrator)
        from flock.components.server.control.helpers import _get_batch_state
        from flock.components.server.models.events import BatchItemAddedEvent

        # Get current batch state from engine
        batch_state = _get_batch_state(
            batch_engine, agent_name, subscription_index, subscription.batch
        )

        if not batch_state:
            return  # No batch to report (shouldn't happen, but defensive)

        # Build and emit event
        event = BatchItemAddedEvent(
            agent_name=agent_name,
            subscription_index=subscription_index,
            items_collected=batch_state["items_collected"],
            items_target=batch_state.get("items_target"),
            items_remaining=batch_state.get("items_remaining"),
            elapsed_seconds=batch_state["elapsed_seconds"],
            timeout_seconds=batch_state.get("timeout_seconds"),
            timeout_remaining_seconds=batch_state.get("timeout_remaining_seconds"),
            will_flush=batch_state["will_flush"],
            artifact_id=str(artifact.id),
            artifact_type=artifact.type,
        )

        # Broadcast via WebSocket
        await self._websocket_manager.broadcast(event)

    # ------------------------------------------------------------------
    # Unit 10: External agent lifecycle events
    # ------------------------------------------------------------------

    async def emit_external_agent_spawned(
        self,
        agent_name: str,
        session_mode: str,
        adapter_type: str,
        trigger_artifact_id: str | None = None,
    ) -> None:
        """Emit ExternalAgentSpawnedEvent when an external agent process is spawned.

        Args:
            agent_name: Name of the external agent
            session_mode: Session mode (e.g. "oneshot", "persistent")
            adapter_type: Adapter type (e.g. "subprocess", "docker", "ssh")
            trigger_artifact_id: Optional artifact ID that triggered the spawn
        """
        if self._websocket_manager is None:
            return

        from flock.components.server.models.events import ExternalAgentSpawnedEvent

        event = ExternalAgentSpawnedEvent(
            agent_name=agent_name,
            session_mode=session_mode,
            adapter_type=adapter_type,
            trigger_artifact_id=trigger_artifact_id,
        )

        await self._websocket_manager.broadcast(event)

    async def emit_external_agent_completed(
        self,
        agent_name: str,
        session_id: str | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        """Emit ExternalAgentCompletedEvent when an external agent finishes.

        Args:
            agent_name: Name of the external agent
            session_id: Optional session identifier (for persistent sessions)
            duration_ms: Execution time in milliseconds
        """
        if self._websocket_manager is None:
            return

        from flock.components.server.models.events import ExternalAgentCompletedEvent

        event = ExternalAgentCompletedEvent(
            agent_name=agent_name,
            session_id=session_id,
            duration_ms=duration_ms,
        )

        await self._websocket_manager.broadcast(event)

    async def emit_external_agent_failed(
        self,
        agent_name: str,
        error: str,
        session_id: str | None = None,
    ) -> None:
        """Emit ExternalAgentFailedEvent when an external agent process fails.

        Args:
            agent_name: Name of the external agent
            error: Error message / reason for failure
            session_id: Optional session identifier (for persistent sessions)
        """
        if self._websocket_manager is None:
            return

        from flock.components.server.models.events import ExternalAgentFailedEvent

        event = ExternalAgentFailedEvent(
            agent_name=agent_name,
            error=error,
            session_id=session_id,
        )

        await self._websocket_manager.broadcast(event)


__all__ = ["EventEmitter"]
