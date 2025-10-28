"""DashboardEventCollector - captures agent lifecycle events for real-time dashboard.

This component hooks into the agent execution lifecycle to emit WebSocket events.
Phase 1: Events stored in in-memory buffer (max 100 events).
Phase 3: Extended to emit via WebSocket using WebSocketManager.
"""

import asyncio
import hashlib
import json
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import PrivateAttr

from flock.api.events import (
    AgentActivatedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    MessagePublishedEvent,
    SubscriptionInfo,
    VisibilitySpec,
)
from flock.api.models.graph import GraphRun, GraphState
from flock.components.agent import AgentComponent
from flock.core.store import AgentSnapshotRecord, BlackboardStore
from flock.logging.logging import get_logger
from flock.utils.runtime import Context


logger = get_logger("dashboard.collector")

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from flock.api.websocket import WebSocketManager
    from flock.core import Agent
    from flock.core.artifacts import Artifact


@dataclass(slots=True)
class RunRecord:
    run_id: str
    agent_name: str
    correlation_id: str = ""
    status: str = "active"
    consumed_artifacts: list[str] = field(default_factory=list)
    produced_artifacts: list[str] = field(default_factory=list)
    duration_ms: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_graph_run(self) -> GraphRun:
        status = (
            self.status if self.status in {"active", "completed", "error"} else "active"
        )
        return GraphRun(
            run_id=self.run_id,
            agent_name=self.agent_name,
            correlation_id=self.correlation_id or None,
            status=status,  # type: ignore[arg-type]
            consumed_artifacts=list(self.consumed_artifacts),
            produced_artifacts=list(self.produced_artifacts),
            duration_ms=self.duration_ms,
            started_at=self.started_at,
            completed_at=self.completed_at,
            metrics=dict(self.metrics),
            error_message=self.error_message,
        )


@dataclass(slots=True)
class AgentSnapshot:
    name: str
    description: str
    subscriptions: list[str]
    output_types: list[str]
    labels: list[str]
    first_seen: datetime
    last_seen: datetime
    signature: str
    logic_operations: list[dict] = field(
        default_factory=list
    )  # Phase 1.2: JoinSpec/BatchSpec config


class DashboardEventCollector(AgentComponent):
    """Collects agent lifecycle events for dashboard visualization.

    Implements AgentComponent interface to hook into agent execution:
    - on_pre_consume: emits agent_activated
    - on_post_publish: emits message_published
    - on_terminate: emits agent_completed
    - on_error: emits agent_error

    Phase 1: Events stored in in-memory deque (max 100, LRU eviction).
    Phase 3: Emits events via WebSocket using WebSocketManager.

    Thread Safety:
    - Uses asyncio.Lock for all mutable state access (events, run_registry, etc.)
    - All operations that modify state are protected by async locks
    - No deadlocks: locks are always acquired in the same order and held briefly
    - Separate locks for different concerns to minimize contention

    Singleton:
    - __new__ override to ensure a single singleton instance
    - Singleton is used across entire application
    - all calls to DashboardEventCollector(...) will return the same instance, initialized with the parameters from the first call.
    """

    _instance: "DashboardEventCollector | None" = None
    _instance_lock: asyncio.Lock = asyncio.Lock()
    _initialized: bool = False

    priority: int = -100  # Run before other agent utilities for event capture

    # Use PrivateAttr for non-Pydantic fields (AgentComponent extends BaseModel)
    _events: deque[
        AgentActivatedEvent
        | MessagePublishedEvent
        | AgentCompletedEvent
        | AgentErrorEvent
    ] = PrivateAttr(default=None)

    # Track run start times for duration calculation
    _run_start_times: dict[str, float] = PrivateAttr(default_factory=dict)

    # WebSocketManager for broadcasting events
    _websocket_manager: Optional["WebSocketManager"] = PrivateAttr(default=None)

    # Asyncio locks for thread-safe operations (separate locks to minimize contention)
    _events_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _run_times_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _graph_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _snapshots_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    # Graph assembly helpers (protected by _graph_lock)
    _run_registry: dict[str, RunRecord] = PrivateAttr(default_factory=dict)
    _artifact_consumers: dict[str, set[str]] = PrivateAttr(
        default_factory=lambda: defaultdict(set)
    )
    _agent_status: dict[str, str] = PrivateAttr(default_factory=dict)

    # Agent snapshots (protected by _snapshots_lock)
    _agent_snapshots: dict[str, AgentSnapshot] = PrivateAttr(default_factory=dict)

    @classmethod
    async def reset_singleton(cls) -> None:
        """Reset the singleton instance (primarily for testing).

        Warning:
            This should only be used in tests. Calling this in production
            while DashboardEventCollector is already running my lead to unexpected behavior.
        """
        async with cls._instance_lock:
            if cls._instance is not None:
                logger.warning("Resetting DasboardEventCollector instance")
            cls._instance = None
            cls._initialized = False

    def __new__(cls):
        """Create or return the singleton instance (thread-safe).

        Returns:
            The singleton DashboardEventCollector instance.
        """
        # Simple singleton pattern - lock is acquired in async __ainit__ if needed
        if cls._instance is None:
            instance = super().__new__(cls)
            cls._instance = instance
            cls._initialized = True

    def __init__(self, *, store: BlackboardStore | None = None, **data):

        # Guard against re-initialization
        if self._initialized:
            logger.warning(
                "DasboardEventCollector singleton already initialized. Ignoring new parameters"
            )
            return

        super().__init__(**data)
        # In-memory buffer with max 100 events (LRU eviction) - protected by _events_lock
        self._events = deque(maxlen=100)
        # Run start times - protected by _run_times_lock
        self._run_start_times = {}
        self._websocket_manager = None

        # Initialize locks
        self._events_lock = asyncio.Lock()
        self._run_times_lock = asyncio.Lock()
        self._graph_lock = asyncio.Lock()
        self._snapshots_lock = asyncio.Lock()

        # Graph state - protected by _graph_lock
        self._run_registry = {}
        self._artifact_consumers = defaultdict(set)
        self._agent_status = {}

        # Snapshot state - protected by _snapshots_lock
        self._agent_snapshots = {}

        self._store: BlackboardStore | None = store
        self._persistent_loaded = False

    def set_websocket_manager(self, manager: "WebSocketManager") -> None:
        """Set WebSocketManager for broadcasting events.

        Args:
            manager: WebSocketManager instance to use for broadcasting

        Note:
            This is a simple setter that doesn't require locking as it's
            typically called once during initialization before any concurrent access.
        """
        self._websocket_manager = manager

    @property
    def events(self) -> deque:
        """Access events buffer.

        Warning:
            Direct access to events buffer is not thread-safe.
            For thread-safe access, use async methods like snapshot_events() instead.
            This property is maintained for backward compatibility.
        """
        return self._events

    async def snapshot_events(self) -> list:
        """Get thread-safe snapshot of current events.

        Returns:
            List of events (copy of deque contents)
        """
        async with self._events_lock:
            return list(self._events)

    async def on_pre_consume(
        self, agent: "Agent", ctx: Context, inputs: list["Artifact"]
    ) -> list["Artifact"]:
        """Emit agent_activated event when agent begins consuming (thread-safe).

        Args:
            agent: The agent that is consuming
            ctx: Execution context with correlation_id
            inputs: Artifacts being consumed

        Returns:
            Unmodified inputs (pass-through)
        """
        # Record start time for duration calculation (separate lock)
        async with self._run_times_lock:
            self._run_start_times[ctx.task_id] = datetime.now(UTC).timestamp()

        # Extract consumed types and artifact IDs
        consumed_types = list({artifact.type for artifact in inputs})
        consumed_artifacts = [str(artifact.id) for artifact in inputs]

        # Extract produced types from agent outputs
        produced_types = [output.spec.type_name for output in agent.outputs]

        correlation_id = str(ctx.correlation_id) if ctx.correlation_id else ""

        # Update graph state (hold lock briefly)
        async with self._graph_lock:
            run = self._ensure_run_record(
                run_id=ctx.task_id,
                agent_name=agent.name,
                correlation_id=correlation_id,
                ensure_started=True,
            )
            run.status = "active"
            for artifact_id in consumed_artifacts:
                if artifact_id not in run.consumed_artifacts:
                    run.consumed_artifacts.append(artifact_id)
                self._artifact_consumers[artifact_id].add(agent.name)
            self._agent_status[agent.name] = "running"

        # Update agent snapshot (separate lock to avoid contention)
        await self._update_agent_snapshot(agent)

        # Build subscription info from agent's subscriptions
        subscription_info = SubscriptionInfo(from_agents=[], tags=[], mode="both")

        if agent.subscriptions:
            # Get first subscription's config (agents typically have one)
            sub = agent.subscriptions[0]
            subscription_info.from_agents = (
                list(sub.from_agents) if sub.from_agents else []
            )
            subscription_info.tags = list(sub.tags) if sub.tags else []
            subscription_info.mode = sub.mode

        # Create event
        event = AgentActivatedEvent(
            correlation_id=correlation_id,
            agent_name=agent.name,
            agent_id=agent.name,
            run_id=ctx.task_id,  # Unique ID for this agent run
            consumed_types=consumed_types,
            consumed_artifacts=consumed_artifacts,
            produced_types=produced_types,
            subscription_info=subscription_info,
            labels=list(agent.labels),
            tenant_id=agent.tenant_id,
            max_concurrency=agent.max_concurrency,
        )

        # Store event (separate lock for events buffer)
        async with self._events_lock:
            self._events.append(event)

        logger.info(
            f"Agent activated: {agent.name} (correlation_id={event.correlation_id})"
        )

        # Broadcast via WebSocket if manager is configured
        if self._websocket_manager:
            await self._websocket_manager.broadcast(event)
        else:
            logger.warning("WebSocket manager not configured, event not broadcast")

        return inputs

    async def on_post_publish(
        self, agent: "Agent", ctx: Context, artifact: "Artifact"
    ) -> None:
        """Emit message_published event when artifact is published (thread-safe).

        Args:
            agent: The agent that published the artifact
            ctx: Execution context with correlation_id
            artifact: The published artifact
        """
        # Convert visibility to VisibilitySpec
        visibility_spec = self._convert_visibility(artifact.visibility)
        correlation_id = str(ctx.correlation_id) if ctx.correlation_id else ""
        artifact_id = str(artifact.id)

        # Update graph state (hold lock briefly)
        async with self._graph_lock:
            run = self._ensure_run_record(
                run_id=ctx.task_id,
                agent_name=agent.name,
                correlation_id=correlation_id,
                ensure_started=True,
            )
            run.status = "active"
            if artifact_id not in run.produced_artifacts:
                run.produced_artifacts.append(artifact_id)

        # Update agent snapshot (separate lock)
        await self._update_agent_snapshot(agent)

        # Create event
        event = MessagePublishedEvent(
            correlation_id=correlation_id,
            artifact_id=str(artifact.id),
            artifact_type=artifact.type,
            produced_by=artifact.produced_by,
            payload=artifact.payload,
            visibility=visibility_spec,
            tags=list(artifact.tags) if artifact.tags else [],
            partition_key=artifact.partition_key,
            version=artifact.version,
            consumers=[],  # Phase 1: empty, Phase 3: compute from subscription matching
        )

        # Store event (separate lock)
        async with self._events_lock:
            self._events.append(event)

        logger.info(
            f"Message published: {artifact.type} by {artifact.produced_by} (correlation_id={event.correlation_id})"
        )

        # Broadcast via WebSocket if manager is configured
        if self._websocket_manager:
            await self._websocket_manager.broadcast(event)
        else:
            logger.warning("WebSocket manager not configured, event not broadcast")

    async def on_terminate(self, agent: "Agent", ctx: Context) -> None:
        """Emit agent_completed event when agent finishes successfully (thread-safe).

        Args:
            agent: The agent that completed
            ctx: Execution context with final state
        """
        # Calculate duration (separate lock)
        async with self._run_times_lock:
            start_time = self._run_start_times.get(ctx.task_id)
            if start_time:
                duration_ms = (datetime.now(UTC).timestamp() - start_time) * 1000
                del self._run_start_times[ctx.task_id]
            else:
                duration_ms = 0.0

        # Extract artifacts produced from context state (if tracked)
        artifacts_produced = ctx.state.get("artifacts_produced", [])
        if not isinstance(artifacts_produced, list):
            artifacts_produced = []

        # Extract metrics from context state (if tracked)
        metrics = ctx.state.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}

        # Create event
        event = AgentCompletedEvent(
            correlation_id=str(ctx.correlation_id) if ctx.correlation_id else "",
            agent_name=agent.name,
            run_id=ctx.task_id,
            duration_ms=duration_ms,
            artifacts_produced=artifacts_produced,
            metrics=metrics,
            final_state=dict(ctx.state),
        )

        # Store event (separate lock)
        async with self._events_lock:
            self._events.append(event)

        # Update graph state (separate lock)
        correlation_id = str(ctx.correlation_id) if ctx.correlation_id else ""
        async with self._graph_lock:
            run = self._ensure_run_record(
                run_id=ctx.task_id,
                agent_name=agent.name,
                correlation_id=correlation_id,
                ensure_started=True,
            )
            run.status = "completed"
            run.duration_ms = duration_ms
            run.metrics = dict(metrics)
            run.completed_at = datetime.now(UTC)
            for artifact_id in artifacts_produced:
                if artifact_id not in run.produced_artifacts:
                    run.produced_artifacts.append(artifact_id)
            self._agent_status[agent.name] = "idle"

        # Update agent snapshot (separate lock)
        await self._update_agent_snapshot(agent)

        # Broadcast via WebSocket if manager is configured
        if self._websocket_manager:
            await self._websocket_manager.broadcast(event)

    async def on_error(self, agent: "Agent", ctx: Context, error: Exception) -> None:
        """Emit agent_error event when agent execution fails (thread-safe).

        Args:
            agent: The agent that failed
            ctx: Execution context
            error: The exception that was raised
        """
        # Get error details
        error_type = type(error).__name__
        error_message = str(error)
        # Use traceback.format_exception to get traceback from exception object
        error_traceback = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        failed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        # Clean up start time tracking (separate lock)
        async with self._run_times_lock:
            if ctx.task_id in self._run_start_times:
                del self._run_start_times[ctx.task_id]

        # Create event
        event = AgentErrorEvent(
            correlation_id=str(ctx.correlation_id) if ctx.correlation_id else "",
            agent_name=agent.name,
            run_id=ctx.task_id,
            error_type=error_type,
            error_message=error_message,
            traceback=error_traceback,
            failed_at=failed_at,
        )

        # Store event (separate lock)
        async with self._events_lock:
            self._events.append(event)

        # Update graph state (separate lock)
        correlation_id = str(ctx.correlation_id) if ctx.correlation_id else ""
        async with self._graph_lock:
            run = self._ensure_run_record(
                run_id=ctx.task_id,
                agent_name=agent.name,
                correlation_id=correlation_id,
                ensure_started=True,
            )
            run.status = "error"
            run.error_message = error_message
            run.completed_at = datetime.now(UTC)
            self._agent_status[agent.name] = "error"

        # Update agent snapshot (separate lock)
        await self._update_agent_snapshot(agent)

        # Broadcast via WebSocket if manager is configured
        if self._websocket_manager:
            await self._websocket_manager.broadcast(event)

    async def snapshot_graph_state(self) -> GraphState:
        """Return a thread-safe snapshot of runs, consumptions, and agent status.

        Returns:
            GraphState snapshot with copies of internal state
        """
        async with self._graph_lock:
            consumptions = {
                artifact_id: sorted(consumers)
                for artifact_id, consumers in self._artifact_consumers.items()
            }
            runs = [record.to_graph_run() for record in self._run_registry.values()]
            agent_status = dict(self._agent_status)
        return GraphState(
            consumptions=consumptions, runs=runs, agent_status=agent_status
        )

    async def snapshot_agent_registry(self) -> dict[str, AgentSnapshot]:
        """Return a thread-safe snapshot of all known agents (active and inactive).

        Returns:
            Dictionary mapping agent names to AgentSnapshot objects
        """
        await self.load_persistent_snapshots()
        async with self._snapshots_lock:
            return {
                name: self._clone_snapshot(snapshot)
                for name, snapshot in self._agent_snapshots.items()
            }

    async def load_persistent_snapshots(self) -> None:
        """Load agent snapshots from persistent store (thread-safe).

        Only loads once per instance lifetime.
        """
        if self._store is None or self._persistent_loaded:
            return

        records = await self._store.load_agent_snapshots()

        async with self._snapshots_lock:
            for record in records:
                self._agent_snapshots[record.agent_name] = AgentSnapshot(
                    name=record.agent_name,
                    description=record.description,
                    subscriptions=list(record.subscriptions),
                    output_types=list(record.output_types),
                    labels=list(record.labels),
                    first_seen=record.first_seen,
                    last_seen=record.last_seen,
                    signature=record.signature,
                )
            self._persistent_loaded = True

    async def clear_agent_registry(self) -> None:
        """Clear cached agent metadata (thread-safe, for explicit resets)."""
        async with self._snapshots_lock:
            self._agent_snapshots.clear()
        if self._store is not None:
            await self._store.clear_agent_snapshots()

    def _ensure_run_record(
        self,
        *,
        run_id: str,
        agent_name: str,
        correlation_id: str,
        ensure_started: bool = False,
    ) -> RunRecord:
        """Internal helper to get or create run record.

        Warning:
            Caller MUST hold _graph_lock before calling this method!

        Args:
            run_id: Unique run identifier
            agent_name: Name of the agent
            correlation_id: Correlation ID for the run
            ensure_started: Whether to set started_at if not already set

        Returns:
            RunRecord for the specified run_id
        """
        run = self._run_registry.get(run_id)
        if not run:
            run = RunRecord(
                run_id=run_id,
                agent_name=agent_name,
                correlation_id=correlation_id,
                started_at=datetime.now(UTC) if ensure_started else None,
            )
            self._run_registry[run_id] = run
        else:
            run.agent_name = agent_name
            if correlation_id:
                run.correlation_id = correlation_id
            if ensure_started and run.started_at is None:
                run.started_at = datetime.now(UTC)
        return run

    async def _update_agent_snapshot(self, agent: "Agent") -> None:
        """Update agent snapshot with current agent state (thread-safe).

        Acquires _snapshots_lock internally. Safe to call from any context.

        Args:
            agent: Agent to update snapshot for
        """
        now = datetime.now(UTC)
        description = agent.description or ""
        subscriptions = sorted({
            type_name
            for subscription in getattr(agent, "subscriptions", [])
            for type_name in getattr(subscription, "type_names", [])
        })
        output_types = sorted({
            output.spec.type_name
            for output in getattr(agent, "outputs", [])
            if getattr(output, "spec", None) is not None
            and getattr(output.spec, "type_name", "")
        })
        labels = sorted(agent.labels)

        signature_payload = {
            "description": description,
            "subscriptions": subscriptions,
            "output_types": output_types,
            "labels": labels,
        }
        signature = hashlib.sha256(
            json.dumps(signature_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        async with self._snapshots_lock:
            snapshot = self._agent_snapshots.get(agent.name)
            if snapshot is None:
                snapshot = AgentSnapshot(
                    name=agent.name,
                    description=description,
                    subscriptions=subscriptions,
                    output_types=output_types,
                    labels=labels,
                    first_seen=now,
                    last_seen=now,
                    signature=signature,
                )
                self._agent_snapshots[agent.name] = snapshot
            else:
                snapshot.description = description
                snapshot.subscriptions = subscriptions
                snapshot.output_types = output_types
                snapshot.labels = labels
                snapshot.last_seen = now
                snapshot.signature = signature

        # Persist to store outside of lock to avoid blocking
        if self._store is not None:
            # Re-acquire lock to get snapshot for persistence
            async with self._snapshots_lock:
                snapshot = self._agent_snapshots.get(agent.name)
            if snapshot:
                record = self._snapshot_to_record(snapshot)
                await self._store.upsert_agent_snapshot(record)

    @staticmethod
    def _clone_snapshot(snapshot: AgentSnapshot) -> AgentSnapshot:
        return AgentSnapshot(
            name=snapshot.name,
            description=snapshot.description,
            subscriptions=list(snapshot.subscriptions),
            output_types=list(snapshot.output_types),
            labels=list(snapshot.labels),
            first_seen=snapshot.first_seen,
            last_seen=snapshot.last_seen,
            signature=snapshot.signature,
            logic_operations=[
                dict(op) for op in snapshot.logic_operations
            ],  # Phase 1.2
        )

    def _snapshot_to_record(self, snapshot: AgentSnapshot) -> AgentSnapshotRecord:
        return AgentSnapshotRecord(
            agent_name=snapshot.name,
            description=snapshot.description,
            subscriptions=list(snapshot.subscriptions),
            output_types=list(snapshot.output_types),
            labels=list(snapshot.labels),
            first_seen=snapshot.first_seen,
            last_seen=snapshot.last_seen,
            signature=snapshot.signature,
        )

    def _convert_visibility(self, visibility) -> VisibilitySpec:
        """Convert flock.visibility.Visibility to VisibilitySpec.

        Args:
            visibility: Visibility object from artifact

        Returns:
            VisibilitySpec for event serialization
        """
        # Get visibility kind from class name, stripping "Visibility" suffix
        class_name = type(visibility).__name__
        kind = class_name.removesuffix("Visibility")

        spec = VisibilitySpec(kind=kind)

        # Extract type-specific fields
        if kind == "Private":
            spec.agents = (
                list(visibility.agents) if hasattr(visibility, "agents") else []
            )
        elif kind == "Labelled":
            spec.required_labels = (
                list(visibility.required_labels)
                if hasattr(visibility, "required_labels")
                else []
            )
        elif kind == "Tenant":
            spec.tenant_id = (
                visibility.tenant_id if hasattr(visibility, "tenant_id") else None
            )

        return spec


__all__ = ["AgentSnapshot", "DashboardEventCollector"]
