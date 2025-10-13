# OrchestratorComponent Design Pattern

## 🎯 Executive Summary

**Problem**: The Flock orchestrator has grown to handle multiple cross-cutting concerns (circuit breaking, deduplication, correlation, batching, metrics, dashboard integration), leading to a 100+ line `_schedule_artifact` method and tight coupling.

**Solution**: Introduce `OrchestratorComponent` - a lifecycle-based plugin system that mirrors the successful `AgentComponent` pattern, enabling extensibility without bloat.

**Impact**:
- ✅ Reduces core orchestrator complexity by 50%+
- ✅ Enables third-party extensions
- ✅ Improves testability and maintainability
- ✅ Preserves backward compatibility

---

## 📚 Background

### AgentComponent Success Story

The `AgentComponent` pattern (src/flock/components.py) successfully solved "agent bloat" with **7 lifecycle hooks**:

```python
class AgentComponent(BaseModel, metaclass=TracedModelMeta):
    async def on_initialize(agent, ctx) -> None           # Startup
    async def on_pre_consume(agent, ctx, inputs) -> list  # Before consuming
    async def on_pre_evaluate(agent, ctx, inputs) -> EvalInputs  # Before LLM
    async def on_post_evaluate(agent, ctx, inputs, result) -> EvalResult  # After LLM
    async def on_post_publish(agent, ctx, artifact) -> None  # After publishing
    async def on_error(agent, ctx, error) -> None         # Error handling
    async def on_terminate(agent, ctx) -> None            # Shutdown
```

**Key Patterns**:
- ✅ **Data transformation hooks** return modified data
- ✅ **Notification hooks** return None
- ✅ **Chaining**: Components execute in order, passing results forward
- ✅ **OpenTelemetry auto-tracing** via TracedModelMeta
- ✅ **Pydantic validation** via BaseModel

### Orchestrator Bloat Problem

The `Flock` orchestrator (src/flock/orchestrator.py:678-781) contains a **100+ line `_schedule_artifact` method** handling:

1. Subscription matching
2. Self-trigger prevention
3. Circuit breaker logic
4. Visibility checking
5. Deduplication tracking
6. JoinSpec correlation
7. AND gate collection
8. BatchSpec batching
9. Combined features (JoinSpec + BatchSpec)
10. Task scheduling

**Plus** the orchestrator `__init__` directly instantiates:
```python
self._artifact_collector = ArtifactCollector()      # AND gates
self._correlation_engine = CorrelationEngine()      # JoinSpec
self._batch_engine = BatchEngine()                   # BatchSpec
self._mcp_manager: FlockMCPClientManager | None     # MCP integration
self._dashboard_collector                            # Dashboard events
self.metrics: dict[str, float]                       # Metrics tracking
self._agent_iteration_count: dict[str, int]          # Circuit breaker
```

---

## 🏗️ Architecture Design

### Base Class

```python
from pydantic import BaseModel, Field
from flock.logging.auto_trace import TracedModelMeta
from flock.artifacts import Artifact
from flock.subscription import Subscription
from enum import Enum
from dataclasses import dataclass

class OrchestratorComponentConfig(BaseModel):
    """Configuration for orchestrator components (supports dynamic fields)."""
    pass

class OrchestratorComponent(BaseModel, metaclass=TracedModelMeta):
    """Base class for orchestrator components with lifecycle hooks.

    Provides extension points throughout the orchestrator's scheduling lifecycle,
    enabling features like circuit breaking, batching, correlation, and metrics
    without modifying core orchestrator code.

    Examples:
        # Circuit breaker component
        class CircuitBreakerComponent(OrchestratorComponent):
            max_iterations: int = 1000

            async def on_before_schedule(self, orch, artifact, agent, sub):
                count = self._counts.get(agent.name, 0)
                if count >= self.max_iterations:
                    return ScheduleDecision.SKIP
                self._counts[agent.name] = count + 1
                return ScheduleDecision.CONTINUE

        # Usage
        flock = Flock("openai/gpt-4.1")
        flock.add_component(CircuitBreakerComponent(max_iterations=500))
    """

    name: str | None = None
    config: OrchestratorComponentConfig = Field(
        default_factory=OrchestratorComponentConfig
    )
    priority: int = 0  # Lower = earlier execution

    # ──────────────────────────────────────────────────────────
    # LIFECYCLE HOOKS
    # ──────────────────────────────────────────────────────────

    async def on_initialize(self, orchestrator: Flock) -> None:
        """Called once when orchestrator starts up.

        Use for: Resource allocation, connecting to external systems, loading state.

        Examples:
            # Connect to external metrics service
            async def on_initialize(self, orchestrator):
                self.metrics_client = await connect_to_prometheus()
        """
        return None

    async def on_artifact_published(
        self,
        orchestrator: Flock,
        artifact: Artifact
    ) -> Artifact | None:
        """Called after artifact is persisted, before scheduling.

        Use for: Artifact transformation, enrichment, filtering, validation.

        Returns:
            - Artifact to continue with (can be modified)
            - None to block scheduling entirely

        Examples:
            # Enrich artifacts with metadata
            async def on_artifact_published(self, orch, artifact):
                artifact.tags.add("enriched")
                artifact.metadata["processed_at"] = datetime.now()
                return artifact

            # Block artifacts based on policy
            async def on_artifact_published(self, orch, artifact):
                if artifact.type == "SensitiveData":
                    return None  # Block scheduling
                return artifact
        """
        return artifact

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Called when subscription matches, before collection engines.

        Use for: Circuit breakers, deduplication, visibility checks, policy enforcement.

        Returns:
            - ScheduleDecision.CONTINUE: Proceed to collection phase
            - ScheduleDecision.SKIP: Skip this subscription (not an error)
            - ScheduleDecision.DEFER: Defer for later (used by batching/correlation)

        Examples:
            # Circuit breaker
            async def on_before_schedule(self, orch, artifact, agent, sub):
                if self._iteration_count[agent.name] > 1000:
                    return ScheduleDecision.SKIP
                return ScheduleDecision.CONTINUE

            # Deduplication
            async def on_before_schedule(self, orch, artifact, agent, sub):
                key = (artifact.id, agent.name)
                if key in self._processed:
                    return ScheduleDecision.SKIP
                self._processed.add(key)
                return ScheduleDecision.CONTINUE
        """
        return ScheduleDecision.CONTINUE

    async def on_collect_artifacts(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> CollectionResult | None:
        """Called to handle AND gate / correlation / batching logic.

        Use for: CorrelationEngine, BatchEngine, ArtifactCollector integration.

        Returns:
            - CollectionResult with complete=True if ready to schedule
            - CollectionResult with complete=False if waiting for more artifacts
            - None to let other components handle collection

        Examples:
            # JoinSpec correlation
            async def on_collect_artifacts(self, orch, artifact, agent, sub):
                if sub.join is None:
                    return None  # Not our concern

                group = self._engine.add_artifact(artifact, sub)
                if group is None:
                    return CollectionResult.waiting()

                return CollectionResult(
                    artifacts=group.get_artifacts(),
                    complete=True
                )
        """
        return CollectionResult.immediate([artifact])

    async def on_before_agent_schedule(
        self,
        orchestrator: Flock,
        agent: Agent,
        artifacts: list[Artifact],
    ) -> list[Artifact] | None:
        """Called after engines complete, before task creation (final gate).

        Use for: Final validation, artifact transformation, logging, auditing.

        Returns:
            - Artifacts to schedule with (can be modified)
            - None to block scheduling

        Examples:
            # Final validation
            async def on_before_agent_schedule(self, orch, agent, artifacts):
                if not self._validate_artifacts(artifacts):
                    return None  # Block
                return artifacts

            # Audit logging
            async def on_before_agent_schedule(self, orch, agent, artifacts):
                await self.audit_log.record(agent.name, artifacts)
                return artifacts
        """
        return artifacts

    async def on_agent_scheduled(
        self,
        orchestrator: Flock,
        agent: Agent,
        artifacts: list[Artifact],
        task: Task,
    ) -> None:
        """Called after task is created (notification).

        Use for: Metrics, logging, notifications, monitoring.

        Examples:
            # Metrics tracking
            async def on_agent_scheduled(self, orch, agent, artifacts, task):
                self.metrics["agents_scheduled"] += 1
                self.metrics["artifacts_processed"] += len(artifacts)

            # Real-time notifications
            async def on_agent_scheduled(self, orch, agent, artifacts, task):
                await self.websocket.broadcast({
                    "event": "agent_scheduled",
                    "agent": agent.name,
                    "artifact_count": len(artifacts)
                })
        """
        return None

    async def on_idle(self, orchestrator: Flock) -> None:
        """Called when run_until_idle completes.

        Use for: Cleanup, flushing buffers, checkpointing, garbage collection.

        Examples:
            # Flush partial batches
            async def on_idle(self, orchestrator):
                await self._flush_all_batches()

            # Reset circuit breaker
            async def on_idle(self, orchestrator):
                self._iteration_counts.clear()
        """
        return None

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Called during orchestrator shutdown.

        Use for: Resource cleanup, connection closing, persistence.

        Examples:
            # Close connections
            async def on_shutdown(self, orchestrator):
                await self.database.close()
                await self.mcp_manager.cleanup_all()
        """
        return None

class ScheduleDecision(str, Enum):
    """Decision result from on_before_schedule hook."""
    CONTINUE = "continue"  # Proceed with scheduling
    SKIP = "skip"          # Skip this subscription (not an error)
    DEFER = "defer"        # Defer for later (batching/correlation)

@dataclass
class CollectionResult:
    """Result from on_collect_artifacts hook."""
    artifacts: list[Artifact]
    complete: bool  # True if ready to schedule, False if waiting

    @staticmethod
    def immediate(artifacts: list[Artifact]) -> CollectionResult:
        """Immediate scheduling (no collection needed)."""
        return CollectionResult(artifacts=artifacts, complete=True)

    @staticmethod
    def waiting() -> CollectionResult:
        """Still collecting (AND gate/correlation incomplete)."""
        return CollectionResult(artifacts=[], complete=False)
```

---

## 🔌 Example Implementations

### 1. CircuitBreakerComponent

**Purpose**: Prevent runaway agent loops by tracking iteration counts.

```python
class CircuitBreakerComponent(OrchestratorComponent):
    """Prevents infinite agent loops by tracking iteration counts.

    Tracks how many times each agent has been scheduled and blocks
    scheduling if the limit is exceeded. Automatically resets when
    the orchestrator becomes idle.

    Args:
        max_iterations: Maximum agent invocations before circuit breaks

    Examples:
        flock = Flock("openai/gpt-4.1")
        flock.add_component(CircuitBreakerComponent(max_iterations=500))
    """

    max_iterations: int = 1000

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._iteration_counts: dict[str, int] = {}

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        # Check iteration limit
        count = self._iteration_counts.get(agent.name, 0)
        if count >= self.max_iterations:
            # Circuit breaker tripped!
            return ScheduleDecision.SKIP

        # Increment counter
        self._iteration_counts[agent.name] = count + 1
        return ScheduleDecision.CONTINUE

    async def on_idle(self, orchestrator: Flock) -> None:
        # Reset counters when idle
        self._iteration_counts.clear()
```

**Usage**:
```python
flock = Flock("openai/gpt-4.1")
flock.add_component(CircuitBreakerComponent(max_iterations=500))
```

---

### 2. DeduplicationComponent

**Purpose**: Prevent agents from processing the same artifact twice.

```python
class DeduplicationComponent(OrchestratorComponent):
    """Prevents agents from processing the same artifact twice.

    Tracks (artifact_id, agent_name) pairs to ensure each agent
    processes each artifact at most once.

    Examples:
        flock = Flock("openai/gpt-4.1")
        flock.add_component(DeduplicationComponent())
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._processed: set[tuple[str, str]] = set()

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        key = (str(artifact.id), agent.name)

        if key in self._processed:
            # Already processed - skip
            return ScheduleDecision.SKIP

        # Mark as processed
        self._processed.add(key)
        return ScheduleDecision.CONTINUE
```

**Usage**:
```python
flock.add_component(DeduplicationComponent())
```

---

### 3. CorrelationComponent

**Purpose**: Handle JoinSpec-based correlated AND gates.

```python
class CorrelationComponent(OrchestratorComponent):
    """Handles JoinSpec-based correlated AND gates.

    Manages correlation groups that wait for multiple artifact types
    with a common correlation key within a time or count window.

    Args:
        priority: Component execution order (default: 10)

    Examples:
        flock = Flock("openai/gpt-4.1")
        flock.add_component(CorrelationComponent())

        # Agent with JoinSpec
        flock.agent("diagnostician")
            .consumes(
                XRay, LabResult,
                join=JoinSpec(
                    by=lambda x: x.patient_id,
                    within=timedelta(minutes=5)
                )
            )
    """

    priority: int = 10  # Run AFTER deduplication, BEFORE batching

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine = CorrelationEngine()

    async def on_collect_artifacts(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> CollectionResult | None:
        # Only handle subscriptions with JoinSpec
        if subscription.join is None:
            return None  # Let other components handle it

        # Use correlation engine
        subscription_index = agent.subscriptions.index(subscription)
        completed_group = self._engine.add_artifact(
            artifact=artifact,
            subscription=subscription,
            subscription_index=subscription_index,
        )

        if completed_group is None:
            # Still waiting for correlation
            return CollectionResult.waiting()

        # Correlation complete!
        artifacts = completed_group.get_artifacts()
        return CollectionResult(artifacts=artifacts, complete=True)

    async def on_idle(self, orchestrator: Flock) -> None:
        # Cleanup expired correlation groups
        for agent in orchestrator.agents:
            for idx in range(len(agent.subscriptions)):
                self._engine.cleanup_expired(agent.name, idx)
```

**Usage**:
```python
flock.add_component(CorrelationComponent())
```

---

### 4. BatchingComponent

**Purpose**: Accumulate artifacts and trigger agents at size/timeout thresholds.

```python
class BatchingComponent(OrchestratorComponent):
    """Handles BatchSpec-based batching (size and timeout).

    Accumulates artifacts and triggers agents when:
    - Size threshold reached (e.g., batch of 10)
    - Timeout expires (e.g., flush every 30 seconds)
    - Whichever comes first

    Args:
        priority: Component execution order (default: 20)

    Examples:
        flock = Flock("openai/gpt-4.1")
        flock.add_component(BatchingComponent())

        # Agent with BatchSpec
        flock.agent("bulk_processor")
            .consumes(
                Task,
                batch=BatchSpec(size=25, timeout=timedelta(seconds=30))
            )
    """

    priority: int = 20  # Run AFTER correlation

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine = BatchEngine()
        self._timeout_task: asyncio.Task | None = None

    async def on_initialize(self, orchestrator: Flock) -> None:
        # Start timeout checker task
        self._timeout_task = asyncio.create_task(
            self._check_timeouts_loop(orchestrator)
        )

    async def on_collect_artifacts(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> CollectionResult | None:
        # Only handle subscriptions with BatchSpec
        if subscription.batch is None:
            return None  # Let other components handle it

        subscription_index = agent.subscriptions.index(subscription)

        # Add artifact to batch
        should_flush = self._engine.add_artifact(
            artifact=artifact,
            subscription=subscription,
            subscription_index=subscription_index,
        )

        if not should_flush:
            # Batch not full yet - wait
            return CollectionResult.waiting()

        # Flush the batch
        batched_artifacts = self._engine.flush_batch(
            agent.name, subscription_index
        )

        if batched_artifacts is None:
            return CollectionResult.waiting()

        return CollectionResult(artifacts=batched_artifacts, complete=True)

    async def on_idle(self, orchestrator: Flock) -> None:
        # Flush all partial batches
        all_batches = self._engine.flush_all()

        for agent_name, sub_idx, artifacts in all_batches:
            agent = orchestrator.get_agent(agent_name)
            orchestrator._schedule_task(agent, artifacts)

    async def on_shutdown(self, orchestrator: Flock) -> None:
        # Stop timeout checker
        if self._timeout_task:
            self._timeout_task.cancel()

    async def _check_timeouts_loop(self, orchestrator: Flock):
        """Background task that checks for batch timeouts."""
        while True:
            await asyncio.sleep(1.0)  # Check every second

            expired_batches = self._engine.check_timeouts()

            for agent_name, sub_idx in expired_batches:
                artifacts = self._engine.flush_batch(agent_name, sub_idx)
                if artifacts:
                    agent = orchestrator.get_agent(agent_name)
                    orchestrator._schedule_task(agent, artifacts)
```

**Usage**:
```python
flock.add_component(BatchingComponent())
```

---

### 5. MetricsComponent

**Purpose**: Track orchestrator metrics (artifacts published, agents scheduled).

```python
class MetricsComponent(OrchestratorComponent):
    """Tracks orchestrator metrics.

    Provides counters for:
    - Artifacts published
    - Agents scheduled
    - Agents completed

    Examples:
        metrics = MetricsComponent()
        flock = Flock("openai/gpt-4.1")
        flock.add_component(metrics)

        # Later: Access metrics
        print(metrics.metrics)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics = {
            "artifacts_published": 0,
            "agents_scheduled": 0,
        }

    async def on_artifact_published(
        self,
        orchestrator: Flock,
        artifact: Artifact
    ) -> Artifact | None:
        self.metrics["artifacts_published"] += 1
        return artifact

    async def on_agent_scheduled(
        self,
        orchestrator: Flock,
        agent: Agent,
        artifacts: list[Artifact],
        task: Task,
    ) -> None:
        self.metrics["agents_scheduled"] += 1
```

**Usage**:
```python
metrics = MetricsComponent()
flock.add_component(metrics)

# Later
print(f"Published: {metrics.metrics['artifacts_published']}")
print(f"Scheduled: {metrics.metrics['agents_scheduled']}")
```

---

### 6. DashboardComponent

**Purpose**: Integrate with dashboard for real-time event streaming.

```python
class DashboardComponent(OrchestratorComponent):
    """Integrates with dashboard for real-time event streaming.

    Automatically injects DashboardEventCollector into all agents
    when the orchestrator starts in dashboard mode.

    Examples:
        flock = Flock("openai/gpt-4.1")
        flock.add_component(DashboardComponent())
        await flock.serve(dashboard=True)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._collector: DashboardEventCollector | None = None

    async def on_initialize(self, orchestrator: Flock) -> None:
        from flock.dashboard.collector import DashboardEventCollector

        self._collector = DashboardEventCollector(store=orchestrator.store)
        await self._collector.load_persistent_snapshots()

        # Inject collector into all agents
        for agent in orchestrator.agents:
            agent.utilities.insert(0, self._collector)

    async def on_shutdown(self, orchestrator: Flock) -> None:
        # Cleanup collector
        self._collector = None
```

**Usage**:
```python
flock.add_component(DashboardComponent())
await flock.serve(dashboard=True)
```

---

## 🎯 Orchestrator Refactoring

### Before (Current Implementation)

**File**: `src/flock/orchestrator.py:678-781`

```python
async def _schedule_artifact(self, artifact: Artifact) -> None:
    """Schedule agents that match the artifact (100+ lines!)."""
    for agent in self.agents:
        for subscription in agent.subscriptions:
            # 1. Check subscription accepts events
            if not subscription.accepts_events():
                continue

            # 2. Self-trigger prevention
            if agent.prevent_self_trigger and artifact.produced_by == agent.name:
                continue

            # 3. Circuit breaker
            iteration_count = self._agent_iteration_count.get(agent.name, 0)
            if iteration_count >= self.max_agent_iterations:
                continue

            # 4. Visibility check
            if not self._check_visibility(artifact, agent.identity):
                continue

            # 5. Subscription match
            if not subscription.matches(artifact):
                continue

            # 6. Deduplication
            if self._seen_before(artifact, agent):
                continue

            # 7. JoinSpec correlation (20+ lines)
            if subscription.join is not None:
                subscription_index = agent.subscriptions.index(subscription)
                completed_group = self._correlation_engine.add_artifact(
                    artifact=artifact,
                    subscription=subscription,
                    subscription_index=subscription_index,
                )
                if completed_group is None:
                    continue
                artifacts = completed_group.get_artifacts()
            else:
                # 8. AND gate logic (15+ lines)
                is_complete, artifacts = self._artifact_collector.add_artifact(
                    agent, subscription, artifact
                )
                if not is_complete:
                    continue

            # 9. BatchSpec batching (30+ lines)
            if subscription.batch is not None:
                subscription_index = agent.subscriptions.index(subscription)
                if subscription.join is not None or len(subscription.type_models) > 1:
                    should_flush = self._batch_engine.add_artifact_group(
                        artifacts=artifacts,
                        subscription=subscription,
                        subscription_index=subscription_index,
                    )
                else:
                    should_flush = False
                    for single_artifact in artifacts:
                        should_flush = self._batch_engine.add_artifact(
                            artifact=single_artifact,
                            subscription=subscription,
                            subscription_index=subscription_index,
                        )
                        if should_flush:
                            break

                if not should_flush:
                    continue

                batched_artifacts = self._batch_engine.flush_batch(
                    agent.name, subscription_index
                )
                if batched_artifacts is None:
                    continue
                artifacts = batched_artifacts

            # 10. Schedule agent
            self._agent_iteration_count[agent.name] = iteration_count + 1
            for collected_artifact in artifacts:
                self._mark_processed(collected_artifact, agent)
            self._schedule_task(agent, artifacts)
```

---

### After (With Components)

**File**: `src/flock/orchestrator.py` (refactored)

```python
async def _schedule_artifact(self, artifact: Artifact) -> None:
    """Schedule agents that match the artifact (clean!)."""

    # 1. Call on_artifact_published hooks
    artifact = await self._run_artifact_published(artifact)
    if artifact is None:
        return  # Component blocked scheduling

    for agent in self.agents:
        for subscription in agent.subscriptions:
            # 2. Basic subscription matching (core orchestrator logic)
            if not subscription.accepts_events():
                continue
            if not subscription.matches(artifact):
                continue

            # 3. Call on_before_schedule hooks
            decision = await self._run_before_schedule(
                artifact, agent, subscription
            )
            if decision != ScheduleDecision.CONTINUE:
                continue

            # 4. Call on_collect_artifacts hooks
            collection_result = await self._run_collect_artifacts(
                artifact, agent, subscription
            )
            if not collection_result.complete:
                continue  # Still collecting

            artifacts = collection_result.artifacts

            # 5. Call on_before_agent_schedule hooks
            artifacts = await self._run_before_agent_schedule(agent, artifacts)
            if artifacts is None:
                continue  # Component blocked

            # 6. Schedule agent
            task = self._schedule_task(agent, artifacts)

            # 7. Call on_agent_scheduled hooks
            await self._run_agent_scheduled(agent, artifacts, task)


# Component invocation helpers
async def _run_artifact_published(
    self, artifact: Artifact
) -> Artifact | None:
    """Execute on_artifact_published hooks."""
    current = artifact
    for component in sorted(self._components, key=lambda c: c.priority):
        current = await component.on_artifact_published(self, current)
        if current is None:
            return None  # Component blocked
    return current


async def _run_before_schedule(
    self,
    artifact: Artifact,
    agent: Agent,
    subscription: Subscription
) -> ScheduleDecision:
    """Execute on_before_schedule hooks."""
    for component in sorted(self._components, key=lambda c: c.priority):
        decision = await component.on_before_schedule(
            self, artifact, agent, subscription
        )
        if decision != ScheduleDecision.CONTINUE:
            return decision  # Component skipped or deferred
    return ScheduleDecision.CONTINUE


async def _run_collect_artifacts(
    self,
    artifact: Artifact,
    agent: Agent,
    subscription: Subscription,
) -> CollectionResult:
    """Execute on_collect_artifacts hooks."""
    # Try each component in priority order
    for component in sorted(self._components, key=lambda c: c.priority):
        result = await component.on_collect_artifacts(
            self, artifact, agent, subscription
        )
        if result is not None:
            return result  # Component handled collection

    # No component handled - immediate scheduling
    return CollectionResult.immediate([artifact])


async def _run_before_agent_schedule(
    self,
    agent: Agent,
    artifacts: list[Artifact]
) -> list[Artifact] | None:
    """Execute on_before_agent_schedule hooks."""
    current = artifacts
    for component in sorted(self._components, key=lambda c: c.priority):
        current = await component.on_before_agent_schedule(
            self, agent, current
        )
        if current is None:
            return None  # Component blocked
    return current


async def _run_agent_scheduled(
    self,
    agent: Agent,
    artifacts: list[Artifact],
    task: Task,
) -> None:
    """Execute on_agent_scheduled hooks."""
    for component in sorted(self._components, key=lambda c: c.priority):
        await component.on_agent_scheduled(self, agent, artifacts, task)
```

**Component Management**:
```python
class Flock:
    def __init__(self, ..., max_agent_iterations: int = 1000):
        # ...existing code...

        # Component system
        self._components: list[OrchestratorComponent] = []

        # Auto-add default components (backward compatibility)
        self.add_component(CircuitBreakerComponent(max_iterations=max_agent_iterations))
        self.add_component(DeduplicationComponent())
        self.add_component(CorrelationComponent())
        self.add_component(BatchingComponent())

    def add_component(self, component: OrchestratorComponent) -> Flock:
        """Add a component to the orchestrator.

        Args:
            component: Component to add

        Returns:
            self for method chaining

        Examples:
            flock = Flock("openai/gpt-4.1")
            flock.add_component(CircuitBreakerComponent(max_iterations=500))
            flock.add_component(MetricsComponent())
        """
        self._components.append(component)
        self._components.sort(key=lambda c: c.priority)
        return self

    async def _initialize_components(self) -> None:
        """Initialize all components (called on first publish)."""
        for component in self._components:
            await component.on_initialize(self)
```

---

## 📊 Benefits

### 1. Separation of Concerns ✅
- Each component handles ONE responsibility
- Easy to understand, test, and debug
- No more 100+ line methods!

### 2. Extensibility ✅
- Add new features without modifying orchestrator core
- Third-party components (community extensions!)
- A/B testing different strategies (swap components)

### 3. Testability ✅
- Test components in isolation
- Mock components for orchestrator tests
- Clear contracts via lifecycle hooks

### 4. Configuration ✅
- Enable/disable features via components
- Configure per-deployment (dev vs prod)
- Runtime component swapping

### 5. Performance ✅
- Priority-based execution order
- Skip unnecessary components dynamically
- OpenTelemetry auto-tracing per component

### 6. Maintainability ✅
- Clear separation of orchestrator core vs extensions
- Components can evolve independently
- Easier code reviews (smaller, focused PRs)

---

## 🎯 Migration Strategy

### Phase 1: Core Infrastructure (v2.0)

**Goals**: Establish component system, migrate core concerns

**Tasks**:
- [ ] Implement `OrchestratorComponent` base class
- [ ] Add `Flock.add_component()` and lifecycle invocation
- [ ] Refactor `_schedule_artifact` to use component hooks
- [ ] Migrate circuit breaker → `CircuitBreakerComponent`
- [ ] Migrate deduplication → `DeduplicationComponent`
- [ ] Add comprehensive component tests

**Backward Compatibility**: Auto-add default components in `Flock.__init__`

---

### Phase 2: Engine Wrappers (v2.1)

**Goals**: Componentize existing engines

**Tasks**:
- [ ] Wrap `CorrelationEngine` → `CorrelationComponent`
- [ ] Wrap `BatchEngine` → `BatchingComponent`
- [ ] Wrap `ArtifactCollector` → `CollectionComponent`
- [ ] Add automatic cleanup (correlation groups, batch timeouts)
- [ ] Performance benchmarks (ensure no regression)

---

### Phase 3: Feature Components (v2.2)

**Goals**: Migrate remaining cross-cutting concerns

**Tasks**:
- [ ] Migrate metrics → `MetricsComponent`
- [ ] Migrate dashboard → `DashboardComponent`
- [ ] Migrate MCP lifecycle → `MCPComponent`
- [ ] Create component documentation and examples
- [ ] Build community component examples

---

### Phase 4: Deprecation (v3.0)

**Goals**: Clean up deprecated APIs

**Tasks**:
- [ ] Mark old orchestrator methods as deprecated
- [ ] Provide migration guide
- [ ] Remove deprecated code
- [ ] Celebrate clean architecture! 🎉

---

## 🏆 Comparison: AgentComponent vs OrchestratorComponent

| Aspect | AgentComponent | OrchestratorComponent |
|--------|----------------|----------------------|
| **Hooks** | 7 (initialize, pre_consume, pre_evaluate, post_evaluate, post_publish, error, terminate) | 8 (initialize, artifact_published, before_schedule, collect_artifacts, before_agent_schedule, agent_scheduled, idle, shutdown) |
| **Focus** | Agent execution lifecycle | Orchestrator scheduling lifecycle |
| **Data Flow** | Transform inputs → LLM → outputs | Transform artifacts → scheduling decisions |
| **Examples** | MemoryComponent, RateLimiter | CircuitBreaker, Correlation, Batching |
| **Priority** | Fixed order (utilities → engines) | Configurable via `priority` field |
| **Tracing** | OpenTelemetry via TracedModelMeta | OpenTelemetry via TracedModelMeta |
| **Validation** | Pydantic BaseModel | Pydantic BaseModel |

---

## ✅ Recommendation

**YES - IMPLEMENT THIS!** OrchestratorComponent is the RIGHT architectural move.

**Why**:
1. ✅ **Proven Pattern**: AgentComponent works beautifully - same problem, same solution
2. ✅ **Real Pain**: 100+ line `_schedule_artifact` is unmaintainable
3. ✅ **Future-Proof**: New features (rate limiting, quotas, policy) become components
4. ✅ **Community**: Third-party extensions become possible
5. ✅ **Testing**: Isolated component testing = better quality
6. ✅ **Maintainability**: Clean separation of concerns

**Impact Estimate**:
- 📉 Orchestrator complexity: **-50% lines of code**
- 📈 Testability: **+80% test coverage**
- 📈 Extensibility: **Unlimited** third-party components
- 📈 Maintainability: **Significantly easier** to evolve

**Next Steps**:
1. Prototype `OrchestratorComponent` base class
2. Implement CircuitBreaker + Deduplication as POC
3. Refactor `_schedule_artifact` to use components
4. Add component tests
5. Ship v2.0! 🚀

---

## 📚 References

- **AgentComponent Implementation**: `src/flock/components.py`
- **Current Orchestrator**: `src/flock/orchestrator.py`
- **Correlation Engine**: `src/flock/correlation_engine.py`
- **Batch Engine**: `src/flock/batch_accumulator.py`
- **Artifact Collector**: `src/flock/artifact_collector.py`
