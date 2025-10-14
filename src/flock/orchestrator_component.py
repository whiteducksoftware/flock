"""OrchestratorComponent base class and supporting types."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from flock.components import TracedModelMeta
from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from flock.agent import Agent
    from flock.artifacts import Artifact
    from flock.orchestrator import Flock
    from flock.subscription import Subscription

# Initialize logger for components
logger = get_logger("flock.component")


class ScheduleDecision(str, Enum):
    """Decision returned by on_before_schedule hook.

    Determines whether to proceed with agent scheduling after subscription match.

    Attributes:
        CONTINUE: Proceed with artifact collection and scheduling
        SKIP: Skip this agent/subscription (not an error, just filtered out)
        DEFER: Defer scheduling for later (used by batching/correlation)

    Examples:
        >>> # Circuit breaker that skips after limit
        >>> if iteration_count >= max_iterations:
        ...     return ScheduleDecision.SKIP

        >>> # Normal case: proceed
        >>> return ScheduleDecision.CONTINUE
    """

    CONTINUE = "CONTINUE"  # Proceed with scheduling
    SKIP = "SKIP"  # Skip this subscription (not an error)
    DEFER = "DEFER"  # Defer until later (e.g., waiting for AND gate)


@dataclass
class CollectionResult:
    """Result from on_collect_artifacts hook.

    Indicates whether artifact collection is complete and which artifacts
    should be passed to the agent for execution.

    Attributes:
        artifacts: List of artifacts collected for this subscription
        complete: True if collection is complete and agent should be scheduled,
                 False if still waiting for more artifacts (AND gate, correlation, batch)

    Examples:
        >>> # Immediate scheduling (single artifact, no collection needed)
        >>> result = CollectionResult.immediate([artifact])

        >>> # Waiting for more artifacts (AND gate incomplete)
        >>> result = CollectionResult.waiting()

        >>> # Collection complete with multiple artifacts
        >>> result = CollectionResult(artifacts=[art1, art2, art3], complete=True)
    """

    artifacts: list[Artifact]
    complete: bool

    @classmethod
    def immediate(cls, artifacts: list[Artifact]) -> CollectionResult:
        """Create result for immediate scheduling (no collection needed).

        Args:
            artifacts: Artifacts to schedule agent with

        Returns:
            CollectionResult with complete=True

        Examples:
            >>> result = CollectionResult.immediate([artifact])
            >>> assert result.complete is True
        """
        return cls(artifacts=artifacts, complete=True)

    @classmethod
    def waiting(cls) -> CollectionResult:
        """Create result indicating collection is incomplete (waiting for more).

        Returns:
            CollectionResult with complete=False and empty artifacts list

        Examples:
            >>> result = CollectionResult.waiting()
            >>> assert result.complete is False
            >>> assert result.artifacts == []
        """
        return cls(artifacts=[], complete=False)


class OrchestratorComponentConfig(BaseModel):
    """Configuration for orchestrator components.

    Base configuration class that can be extended by specific components.

    Examples:
        >>> # Simple usage (no extra config)
        >>> config = OrchestratorComponentConfig()

        >>> # Extended by specific components
        >>> class CircuitBreakerConfig(OrchestratorComponentConfig):
        ...     max_iterations: int = 1000
    """

    # Can be extended by specific components


class OrchestratorComponent(BaseModel, metaclass=TracedModelMeta):
    """Base class for orchestrator components with lifecycle hooks.

    Components extend orchestrator functionality without modifying core code.
    Execute in priority order (lower priority number = earlier execution).

    All public methods are automatically traced via OpenTelemetry through
    the TracedModelMeta metaclass (which combines Pydantic's ModelMetaclass
    with AutoTracedMeta).

    Lifecycle hooks are called at specific points during orchestrator execution:
    1. on_initialize: Once at orchestrator startup
    2. on_artifact_published: After artifact persisted, before scheduling
    3. on_before_schedule: Before scheduling an agent (filter/policy)
    4. on_collect_artifacts: Handle AND gates/correlation/batching
    5. on_before_agent_schedule: Final gate before task creation
    6. on_agent_scheduled: After task created (notification)
    7. on_orchestrator_idle: When orchestrator becomes idle
    8. on_shutdown: During orchestrator shutdown

    Attributes:
        name: Optional component name (for logging/debugging)
        config: Component configuration
        priority: Execution priority (lower = earlier, default=0)

    Examples:
        >>> # Simple component
        >>> class LoggingComponent(OrchestratorComponent):
        ...     async def on_agent_scheduled(self, orch, agent, artifacts, task):
        ...         print(f"Agent {agent.name} scheduled with {len(artifacts)} artifacts")

        >>> # Circuit breaker component
        >>> class CircuitBreakerComponent(OrchestratorComponent):
        ...     max_iterations: int = 1000
        ...     _counts: dict = PrivateAttr(default_factory=dict)
        ...
        ...     async def on_before_schedule(self, orch, artifact, agent, sub):
        ...         count = self._counts.get(agent.name, 0)
        ...         if count >= self.max_iterations:
        ...             return ScheduleDecision.SKIP
        ...         self._counts[agent.name] = count + 1
        ...         return ScheduleDecision.CONTINUE
    """

    name: str | None = None
    config: OrchestratorComponentConfig = Field(default_factory=OrchestratorComponentConfig)
    priority: int = 0  # Lower priority = earlier execution

    # ──────────────────────────────────────────────────────────
    # LIFECYCLE HOOKS (Override in subclasses)
    # ──────────────────────────────────────────────────────────

    async def on_initialize(self, orchestrator: Flock) -> None:
        """Called once when orchestrator starts up.

        Use for: Resource allocation, loading state, connecting to external systems.

        Args:
            orchestrator: Flock orchestrator instance

        Examples:
            >>> async def on_initialize(self, orchestrator):
            ...     self.metrics_client = await connect_to_prometheus()
            ...     self._state = await load_checkpoint()
        """

    async def on_artifact_published(
        self, orchestrator: Flock, artifact: Artifact
    ) -> Artifact | None:
        """Called when artifact is published to blackboard, before scheduling.

        Components execute in priority order, each receiving the artifact
        from the previous component (chaining).

        Use for: Filtering, transformation, validation, enrichment.

        Args:
            orchestrator: Flock orchestrator instance
            artifact: Published artifact

        Returns:
            Modified artifact to continue with, or None to block scheduling entirely

        Examples:
            >>> # Enrich artifact with metadata
            >>> async def on_artifact_published(self, orch, artifact):
            ...     artifact.tags.add("processed")
            ...     return artifact

            >>> # Block sensitive artifacts
            >>> async def on_artifact_published(self, orch, artifact):
            ...     if artifact.type == "SensitiveData":
            ...         return None  # Block
            ...     return artifact
        """
        return artifact

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Called before scheduling an agent for a matched subscription.

        Use for: Circuit breaking, deduplication, rate limiting, policy checks.

        Args:
            orchestrator: Flock orchestrator instance
            artifact: Artifact that matched subscription
            agent: Agent to potentially schedule
            subscription: Subscription that matched

        Returns:
            ScheduleDecision (CONTINUE, SKIP, or DEFER)

        Examples:
            >>> # Circuit breaker
            >>> async def on_before_schedule(self, orch, artifact, agent, sub):
            ...     if self._counts.get(agent.name, 0) >= 1000:
            ...         return ScheduleDecision.SKIP
            ...     return ScheduleDecision.CONTINUE

            >>> # Deduplication
            >>> async def on_before_schedule(self, orch, artifact, agent, sub):
            ...     key = (artifact.id, agent.name)
            ...     if key in self._processed:
            ...         return ScheduleDecision.SKIP
            ...     self._processed.add(key)
            ...     return ScheduleDecision.CONTINUE
        """
        return ScheduleDecision.CONTINUE

    async def on_collect_artifacts(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> CollectionResult | None:
        """Called to collect artifacts for agent execution.

        First component to return non-None wins (short-circuit).

        Use for: AND gates, JoinSpec correlation, BatchSpec batching.

        Args:
            orchestrator: Flock orchestrator instance
            artifact: Current artifact
            agent: Agent to schedule
            subscription: Matched subscription

        Returns:
            CollectionResult if this component handles collection,
            or None to let next component handle it

        Examples:
            >>> # JoinSpec correlation
            >>> async def on_collect_artifacts(self, orch, artifact, agent, sub):
            ...     if sub.join is None:
            ...         return None  # Not our concern
            ...
            ...     group = self._engine.add_artifact(artifact, sub)
            ...     if group is None:
            ...         return CollectionResult.waiting()
            ...
            ...     return CollectionResult.immediate(group.get_artifacts())
        """
        return None  # Let other components handle

    async def on_before_agent_schedule(
        self, orchestrator: Flock, agent: Agent, artifacts: list[Artifact]
    ) -> list[Artifact] | None:
        """Called before final agent scheduling with collected artifacts.

        Components execute in priority order, each receiving artifacts
        from the previous component (chaining).

        Use for: Final validation, artifact transformation, enrichment.

        Args:
            orchestrator: Flock orchestrator instance
            agent: Agent to schedule
            artifacts: Collected artifacts

        Returns:
            Modified artifacts to schedule with, or None to block scheduling

        Examples:
            >>> # Final validation
            >>> async def on_before_agent_schedule(self, orch, agent, artifacts):
            ...     if len(artifacts) == 0:
            ...         return None  # Block empty schedules
            ...     return artifacts

            >>> # Artifact enrichment
            >>> async def on_before_agent_schedule(self, orch, agent, artifacts):
            ...     for artifact in artifacts:
            ...         artifact.metadata["scheduled_at"] = datetime.now()
            ...     return artifacts
        """
        return artifacts

    async def on_agent_scheduled(
        self,
        orchestrator: Flock,
        agent: Agent,
        artifacts: list[Artifact],
        task: asyncio.Task,
    ) -> None:
        """Called after agent task is scheduled (notification only).

        Exceptions in this hook are logged but don't block scheduling.

        Use for: Metrics, logging, event emission, monitoring.

        Args:
            orchestrator: Flock orchestrator instance
            agent: Scheduled agent
            artifacts: Artifacts agent was scheduled with
            task: Asyncio task that was created

        Examples:
            >>> # Metrics tracking
            >>> async def on_agent_scheduled(self, orch, agent, artifacts, task):
            ...     self.metrics["agents_scheduled"] += 1
            ...     self.metrics["artifacts_processed"] += len(artifacts)

            >>> # WebSocket notification
            >>> async def on_agent_scheduled(self, orch, agent, artifacts, task):
            ...     await self.ws.broadcast({
            ...         "event": "agent_scheduled",
            ...         "agent": agent.name,
            ...         "count": len(artifacts)
            ...     })
        """

    async def on_orchestrator_idle(self, orchestrator: Flock) -> None:
        """Called when orchestrator becomes idle (no pending tasks).

        Use for: Cleanup, state reset, checkpointing, metrics flush.

        Args:
            orchestrator: Flock orchestrator instance

        Examples:
            >>> # Reset circuit breaker
            >>> async def on_orchestrator_idle(self, orchestrator):
            ...     self._iteration_counts.clear()

            >>> # Flush metrics
            >>> async def on_orchestrator_idle(self, orchestrator):
            ...     await self.metrics_client.flush()
        """

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Called when orchestrator shuts down.

        Use for: Resource cleanup, connection closing, final persistence.

        Args:
            orchestrator: Flock orchestrator instance

        Examples:
            >>> # Close connections
            >>> async def on_shutdown(self, orchestrator):
            ...     await self.database.close()
            ...     await self.mcp_manager.cleanup_all()

            >>> # Save checkpoint
            >>> async def on_shutdown(self, orchestrator):
            ...     await save_checkpoint(self._state)
        """


class BuiltinCollectionComponent(OrchestratorComponent):
    """Built-in component that handles AND gates, correlation, and batching.

    This component wraps the existing ArtifactCollector, CorrelationEngine,
    and BatchEngine to provide collection logic via the component system.

    Priority: 100 (runs after user components for circuit breaking/dedup)
    """

    priority: int = 100  # Run late (after circuit breaker/dedup components)
    name: str = "builtin_collection"

    async def on_collect_artifacts(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> CollectionResult | None:
        """Handle AND gates, correlation (JoinSpec), and batching (BatchSpec).

        This maintains backward compatibility with existing collection engines
        while allowing user components to override collection logic.
        """
        from datetime import timedelta

        # Check if subscription has required attributes (defensive for mocks/tests)
        if (
            not hasattr(subscription, "join")
            or not hasattr(subscription, "type_models")
            or not hasattr(subscription, "batch")
        ):
            # Fallback: immediate with single artifact
            return CollectionResult.immediate([artifact])

        # JoinSpec CORRELATION: Check if subscription has correlated AND gate
        if subscription.join is not None:
            subscription_index = agent.subscriptions.index(subscription)
            completed_group = orchestrator._correlation_engine.add_artifact(
                artifact=artifact,
                subscription=subscription,
                subscription_index=subscription_index,
            )

            # Start correlation cleanup task if time-based window
            if (
                isinstance(subscription.join.within, timedelta)
                and orchestrator._correlation_cleanup_task is None
            ):
                import asyncio

                orchestrator._correlation_cleanup_task = asyncio.create_task(
                    orchestrator._correlation_cleanup_loop()
                )

            if completed_group is None:
                # Still waiting for correlation to complete
                await orchestrator._emit_correlation_updated_event(
                    agent_name=agent.name,
                    subscription_index=subscription_index,
                    artifact=artifact,
                )
                return CollectionResult.waiting()

            # Correlation complete!
            artifacts = completed_group.get_artifacts()
        else:
            # AND GATE: Use artifact collector for simple AND gates (no correlation)
            is_complete, artifacts = orchestrator._artifact_collector.add_artifact(
                agent, subscription, artifact
            )

            if not is_complete:
                return CollectionResult.waiting()

        # BatchSpec BATCHING: Check if subscription has batch accumulator
        if subscription.batch is not None:
            subscription_index = agent.subscriptions.index(subscription)

            # Treat artifact groups as single batch items
            if subscription.join is not None or len(subscription.type_models) > 1:
                should_flush = orchestrator._batch_engine.add_artifact_group(
                    artifacts=artifacts,
                    subscription=subscription,
                    subscription_index=subscription_index,
                )

                if subscription.batch.timeout and orchestrator._batch_timeout_task is None:
                    import asyncio

                    orchestrator._batch_timeout_task = asyncio.create_task(
                        orchestrator._batch_timeout_checker_loop()
                    )
            else:
                # Single type: Add each artifact individually
                should_flush = False
                for single_artifact in artifacts:
                    should_flush = orchestrator._batch_engine.add_artifact(
                        artifact=single_artifact,
                        subscription=subscription,
                        subscription_index=subscription_index,
                    )

                    if subscription.batch.timeout and orchestrator._batch_timeout_task is None:
                        import asyncio

                        orchestrator._batch_timeout_task = asyncio.create_task(
                            orchestrator._batch_timeout_checker_loop()
                        )

                    if should_flush:
                        break

            if not should_flush:
                # Batch not full yet
                await orchestrator._emit_batch_item_added_event(
                    agent_name=agent.name,
                    subscription_index=subscription_index,
                    subscription=subscription,
                    artifact=artifact,
                )
                return CollectionResult.waiting()

            # Flush batch
            batched_artifacts = orchestrator._batch_engine.flush_batch(
                agent.name, subscription_index
            )

            if batched_artifacts is None:
                return CollectionResult.waiting()

            artifacts = batched_artifacts

        # Collection complete!
        return CollectionResult.immediate(artifacts)


class CircuitBreakerComponent(OrchestratorComponent):
    """Circuit breaker to prevent runaway agent loops.

    Tracks iteration count per agent and blocks scheduling when limit is reached.
    Automatically resets counters when orchestrator becomes idle.

    Priority: 10 (runs early, before deduplication)

    Configuration:
        max_iterations: Maximum iterations per agent before circuit breaker trips

    Examples:
        >>> # Use default (1000 iterations)
        >>> flock = Flock("openai/gpt-4.1")

        >>> # Custom limit
        >>> flock = Flock("openai/gpt-4.1")
        >>> for component in flock._components:
        ...     if component.name == "circuit_breaker":
        ...         component.max_iterations = 500
    """

    priority: int = 10  # Run early (before dedup at 20)
    name: str = "circuit_breaker"
    max_iterations: int = 1000  # Default from orchestrator

    def __init__(self, max_iterations: int = 1000, **kwargs):
        """Initialize circuit breaker with iteration limit.

        Args:
            max_iterations: Maximum iterations per agent (default 1000)
        """
        super().__init__(**kwargs)
        self.max_iterations = max_iterations
        self._iteration_counts: dict[str, int] = {}

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Check if agent has exceeded iteration limit.

        Returns SKIP if agent has reached max_iterations, preventing
        potential infinite loops.

        Uses orchestrator.max_agent_iterations if available, otherwise
        falls back to self.max_iterations.
        """
        current_count = self._iteration_counts.get(agent.name, 0)

        # Check orchestrator property first (allows runtime modification)
        # Fall back to component's max_iterations if orchestrator property doesn't exist
        max_limit = self.max_iterations
        if hasattr(orchestrator, "max_agent_iterations"):
            orch_limit = orchestrator.max_agent_iterations
            # Only use orchestrator limit if it's a valid int
            if isinstance(orch_limit, int):
                max_limit = orch_limit

        if current_count >= max_limit:
            # Circuit breaker tripped
            return ScheduleDecision.SKIP

        # Increment counter
        self._iteration_counts[agent.name] = current_count + 1
        return ScheduleDecision.CONTINUE

    async def on_orchestrator_idle(self, orchestrator: Flock) -> None:
        """Reset iteration counters when orchestrator becomes idle.

        This prevents the circuit breaker from permanently blocking agents
        across different workflow runs.
        """
        self._iteration_counts.clear()


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


__all__ = [
    "BuiltinCollectionComponent",
    "CircuitBreakerComponent",
    "CollectionResult",
    "DeduplicationComponent",
    "OrchestratorComponent",
    "OrchestratorComponentConfig",
    "ScheduleDecision",
]
