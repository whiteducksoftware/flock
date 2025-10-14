# OrchestratorComponent Logging Implementation Guide

## 🎯 Purpose

This guide specifies **exactly what and where to log** during the OrchestratorComponent implementation (Spec 004). It ensures consistent, debuggable logging across all phases.

---

## 📋 Logging Principles for Components

1. **Log at lifecycle boundaries** (initialization, hook execution, shutdown)
2. **Log scheduling decisions** (CONTINUE, SKIP, DEFER)
3. **Log data transformations** (artifact collection, filtering)
4. **Log errors with context** (component name, input data, exception)
5. **Use DEBUG for internals, INFO for user-visible events**

---

## 🏗️ Phase 1: Base Classes and Enums

### File: `src/flock/orchestrator_component.py`

#### Logger Initialization
```python
from flock.logging.logging import get_logger

logger = get_logger("flock.component")
```

#### OrchestratorComponent Base Class

**No logging needed in base class** - default hook implementations are no-ops. Logging happens in concrete implementations.

**Exception**: Add debug log in hook runner methods (Phase 3).

---

## 🏗️ Phase 2: Orchestrator Integration

### File: `src/flock/orchestrator.py`

#### In `Flock.__init__` (Component Storage)

```python
def __init__(self, model: str | None = None, *, store: BlackboardStore | None = None, ...):
    # ... existing init code ...
    self._components: list[OrchestratorComponent] = []
    self._components_initialized: bool = False
    
    logger.debug(f"Orchestrator initialized: components=[]")  # Initial state
```

#### In `add_component()`

```python
def add_component(self, component: OrchestratorComponent) -> Self:
    """Add an OrchestratorComponent to this orchestrator."""
    self._components.append(component)
    self._components.sort(key=lambda c: c.priority)
    
    logger.info(
        f"Component added: name={component.name or component.__class__.__name__}, "
        f"priority={component.priority}, total_components={len(self._components)}"
    )
    
    return self
```

---

## 🏗️ Phase 3: Component Hook Runner Methods

### File: `src/flock/orchestrator.py`

#### General Pattern for Hook Runners

**DEBUG logs**: Log hook invocation with component details  
**WARNING logs**: Log if hook raises exception (before propagating)  
**INFO logs**: Log significant decisions (e.g., scheduling blocked)

#### `_run_initialize()`

```python
async def _run_initialize(self) -> None:
    """Initialize all components in priority order (called once)."""
    if self._components_initialized:
        return
    
    logger.info(f"Initializing {len(self._components)} orchestrator components")
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        logger.debug(f"Initializing component: name={comp_name}, priority={component.priority}")
        
        try:
            await component.on_initialize(self)
        except Exception as e:
            logger.error(f"Component initialization failed: name={comp_name}, error={str(e)}")
            raise  # Re-raise after logging
    
    self._components_initialized = True
    logger.success(f"All components initialized: count={len(self._components)}")
```

#### `_run_artifact_published()`

```python
async def _run_artifact_published(self, artifact: Artifact) -> Artifact | None:
    """Run on_artifact_published hooks (returns modified artifact or None to block)."""
    current_artifact = artifact
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        logger.debug(
            f"Running on_artifact_published: component={comp_name}, "
            f"artifact_type={current_artifact.type}, artifact_id={current_artifact.id}"
        )
        
        try:
            result = await component.on_artifact_published(self, current_artifact)
            
            if result is None:
                logger.info(
                    f"Artifact blocked by component: component={comp_name}, "
                    f"artifact_type={current_artifact.type}, artifact_id={current_artifact.id}"
                )
                return None
            
            current_artifact = result
        except Exception as e:
            logger.error(
                f"Component hook failed: component={comp_name}, hook=on_artifact_published, error={str(e)}"
            )
            raise
    
    return current_artifact
```

#### `_run_before_schedule()`

```python
async def _run_before_schedule(
    self, artifact: Artifact, agent: Agent, subscription: Subscription
) -> ScheduleDecision:
    """Run on_before_schedule hooks (returns CONTINUE, SKIP, or DEFER)."""
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        logger.debug(
            f"Running on_before_schedule: component={comp_name}, "
            f"agent={agent.name}, artifact_type={artifact.type}"
        )
        
        try:
            decision = await component.on_before_schedule(self, artifact, agent, subscription)
            
            if decision == ScheduleDecision.SKIP:
                logger.info(
                    f"Scheduling skipped by component: component={comp_name}, "
                    f"agent={agent.name}, artifact_type={artifact.type}, decision=SKIP"
                )
                return ScheduleDecision.SKIP
            
            if decision == ScheduleDecision.DEFER:
                logger.debug(
                    f"Scheduling deferred by component: component={comp_name}, "
                    f"agent={agent.name}, decision=DEFER"
                )
                return ScheduleDecision.DEFER
            
        except Exception as e:
            logger.error(
                f"Component hook failed: component={comp_name}, hook=on_before_schedule, error={str(e)}"
            )
            raise
    
    return ScheduleDecision.CONTINUE
```

#### `_run_collect_artifacts()`

```python
async def _run_collect_artifacts(
    self, artifact: Artifact, agent: Agent, subscription: Subscription
) -> CollectionResult:
    """Run on_collect_artifacts hooks (returns first non-None result)."""
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        logger.debug(
            f"Running on_collect_artifacts: component={comp_name}, "
            f"agent={agent.name}, artifact_type={artifact.type}"
        )
        
        try:
            result = await component.on_collect_artifacts(self, artifact, agent, subscription)
            
            if result is not None:
                logger.debug(
                    f"Collection handled by component: component={comp_name}, "
                    f"complete={result.complete}, artifact_count={len(result.artifacts)}"
                )
                return result
        except Exception as e:
            logger.error(
                f"Component hook failed: component={comp_name}, hook=on_collect_artifacts, error={str(e)}"
            )
            raise
    
    # Default: immediate scheduling with single artifact
    logger.debug(
        f"No component handled collection, using default: "
        f"agent={agent.name}, artifact_type={artifact.type}"
    )
    return CollectionResult.immediate([artifact])
```

#### `_run_before_agent_schedule()`

```python
async def _run_before_agent_schedule(
    self, agent: Agent, artifacts: list[Artifact]
) -> list[Artifact] | None:
    """Run on_before_agent_schedule hooks (returns modified artifacts or None to block)."""
    current_artifacts = artifacts
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        logger.debug(
            f"Running on_before_agent_schedule: component={comp_name}, "
            f"agent={agent.name}, artifact_count={len(current_artifacts)}"
        )
        
        try:
            result = await component.on_before_agent_schedule(self, agent, current_artifacts)
            
            if result is None:
                logger.info(
                    f"Agent scheduling blocked by component: component={comp_name}, "
                    f"agent={agent.name}"
                )
                return None
            
            current_artifacts = result
        except Exception as e:
            logger.error(
                f"Component hook failed: component={comp_name}, "
                f"hook=on_before_agent_schedule, error={str(e)}"
            )
            raise
    
    return current_artifacts
```

#### `_run_agent_scheduled()`

```python
async def _run_agent_scheduled(
    self, agent: Agent, artifacts: list[Artifact], task: asyncio.Task
) -> None:
    """Run on_agent_scheduled hooks (notification only, no return value)."""
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        logger.debug(
            f"Running on_agent_scheduled: component={comp_name}, "
            f"agent={agent.name}, artifact_count={len(artifacts)}"
        )
        
        try:
            await component.on_agent_scheduled(self, agent, artifacts, task)
        except Exception as e:
            logger.warning(
                f"Component notification hook failed (non-critical): "
                f"component={comp_name}, hook=on_agent_scheduled, error={str(e)}"
            )
            # Don't propagate - this is a notification hook
```

#### `_run_idle()`

```python
async def _run_idle(self) -> None:
    """Run on_orchestrator_idle hooks when orchestrator becomes idle."""
    logger.debug(f"Running on_orchestrator_idle hooks: component_count={len(self._components)}")
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        try:
            await component.on_orchestrator_idle(self)
        except Exception as e:
            logger.warning(
                f"Component idle hook failed (non-critical): "
                f"component={comp_name}, hook=on_orchestrator_idle, error={str(e)}"
            )
```

#### `_run_shutdown()`

```python
async def _run_shutdown(self) -> None:
    """Run on_shutdown hooks when orchestrator shuts down."""
    logger.info(f"Shutting down {len(self._components)} orchestrator components")
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        logger.debug(f"Shutting down component: name={comp_name}")
        
        try:
            await component.on_shutdown(self)
        except Exception as e:
            logger.error(
                f"Component shutdown failed: component={comp_name}, "
                f"hook=on_shutdown, error={str(e)}"
            )
            # Continue shutting down other components
```

---

## 🏗️ Phase 5: CircuitBreakerComponent

### File: `src/flock/orchestrator_component.py`

#### Component Initialization

```python
class CircuitBreakerComponent(OrchestratorComponent):
    """Circuit breaker that prevents runaway agents."""
    
    max_iterations: int = 1000
    _iteration_counts: dict[str, int] = PrivateAttr(default_factory=dict)
    
    async def on_initialize(self, orchestrator: Flock) -> None:
        """Initialize circuit breaker state."""
        logger.info(
            f"CircuitBreakerComponent initialized: max_iterations={self.max_iterations}"
        )
```

#### Before Schedule Hook

```python
    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Check circuit breaker and increment counter."""
        count = self._iteration_counts.get(agent.name, 0)
        
        if count >= self.max_iterations:
            logger.warning(
                f"Circuit breaker TRIPPED: agent={agent.name}, "
                f"iterations={count}/{self.max_iterations}"
            )
            return ScheduleDecision.SKIP
        
        # Increment counter
        self._iteration_counts[agent.name] = count + 1
        
        # Log warning at 95% capacity
        if count >= self.max_iterations * 0.95:
            logger.warning(
                f"Circuit breaker approaching limit: agent={agent.name}, "
                f"iterations={count}/{self.max_iterations} (95%)"
            )
        else:
            logger.debug(
                f"Circuit breaker check: agent={agent.name}, "
                f"iterations={count}/{self.max_iterations}"
            )
        
        return ScheduleDecision.CONTINUE
```

#### Idle Hook (Reset)

```python
    async def on_orchestrator_idle(self, orchestrator: Flock) -> None:
        """Reset circuit breaker counters when orchestrator is idle."""
        if self._iteration_counts:
            logger.info(
                f"Circuit breaker reset: agent_count={len(self._iteration_counts)}"
            )
            self._iteration_counts.clear()
```

---

## 🏗️ Phase 6: DeduplicationComponent

### File: `src/flock/orchestrator_component.py`

#### Component Initialization

```python
class DeduplicationComponent(OrchestratorComponent):
    """Deduplication that prevents duplicate artifact processing."""
    
    _processed: set[tuple[str, str]] = PrivateAttr(default_factory=set)
    
    async def on_initialize(self, orchestrator: Flock) -> None:
        """Initialize deduplication state."""
        logger.info("DeduplicationComponent initialized")
```

#### Before Schedule Hook

```python
    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Check if (artifact, agent) pair already processed."""
        key = (str(artifact.id), agent.name)
        
        if key in self._processed:
            logger.info(
                f"Deduplication BLOCKED duplicate: "
                f"artifact_id={artifact.id}, artifact_type={artifact.type}, agent={agent.name}"
            )
            return ScheduleDecision.SKIP
        
        # Mark as processed
        self._processed.add(key)
        
        logger.debug(
            f"Deduplication check passed: "
            f"artifact_id={artifact.id}, agent={agent.name}, "
            f"total_processed={len(self._processed)}"
        )
        
        return ScheduleDecision.CONTINUE
```

---

## 🏗️ Phase 7: Integration & Backward Compatibility

### File: `src/flock/orchestrator.py`

#### In `Flock.__init__` (Auto-add Default Components)

```python
def __init__(self, model: str | None = None, *, store: BlackboardStore | None = None, ...):
    # ... existing init code ...
    
    # Auto-add default components for backward compatibility
    self.add_component(CircuitBreakerComponent(max_iterations=max_agent_iterations))
    self.add_component(DeduplicationComponent())
    
    logger.info(
        f"Orchestrator initialized with default components: "
        f"circuit_breaker (max={max_agent_iterations}), deduplication"
    )
```

#### In Refactored `_schedule_artifact()`

**Add component initialization check**:
```python
async def _schedule_artifact(self, artifact: Artifact) -> None:
    """Schedule matching agents for an artifact (using components)."""
    # Initialize components on first artifact
    if not self._components_initialized:
        await self._run_initialize()
    
    logger.debug(
        f"Scheduling artifact: type={artifact.type}, id={artifact.id}, "
        f"produced_by={artifact.produced_by}"
    )
    
    # ... rest of scheduling logic ...
```

**Log component hook execution**:
```python
    # Component hook: on_artifact_published
    artifact = await self._run_artifact_published(artifact)
    if artifact is None:
        logger.debug("Artifact blocked by component hook: on_artifact_published")
        return
    
    # ... subscription matching loop ...
    
    # Component hook: on_before_schedule
    decision = await self._run_before_schedule(artifact, agent, subscription)
    if decision == ScheduleDecision.SKIP:
        logger.debug(
            f"Scheduling skipped by component: agent={agent.name}, "
            f"artifact_type={artifact.type}"
        )
        continue
    
    # Component hook: on_collect_artifacts
    collection = await self._run_collect_artifacts(artifact, agent, subscription)
    if not collection.complete:
        logger.debug(
            f"Collection incomplete: agent={agent.name}, "
            f"waiting_for_more_artifacts=True"
        )
        continue
    
    artifacts = collection.artifacts
    
    # Component hook: on_before_agent_schedule
    artifacts = await self._run_before_agent_schedule(agent, artifacts)
    if artifacts is None:
        logger.debug(f"Agent scheduling blocked by component: agent={agent.name}")
        continue
    
    # Schedule task
    task = self._schedule_task(agent, artifacts)
    
    # Component hook: on_agent_scheduled (notification)
    await self._run_agent_scheduled(agent, artifacts, task)
    
    logger.info(
        f"Agent scheduled: name={agent.name}, artifact_count={len(artifacts)}, "
        f"is_batch={is_batch_execution}"
    )
```

#### In `run_until_idle()`

```python
async def run_until_idle(self) -> None:
    """Run until all tasks complete."""
    logger.debug("Waiting for orchestrator to become idle")
    
    while self._tasks:
        await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)
    
    # Component hook: on_orchestrator_idle
    await self._run_idle()
    
    logger.success(
        f"Orchestrator idle: artifacts_published={self.metrics['artifacts_published']}, "
        f"agent_runs={self.metrics['agent_runs']}"
    )
```

---

## 📊 Logging Summary by Phase

### Phase 1 (Base Classes)
- **No logs** - Base class has no behavior

### Phase 2 (Orchestrator Integration)
- `INFO`: Component added
- `DEBUG`: Orchestrator initialized

### Phase 3 (Hook Runners)
- `INFO`: Component initialization started/completed
- `INFO`: Artifact blocked by component
- `INFO`: Scheduling blocked by component
- `DEBUG`: Hook execution for each component
- `ERROR`: Hook execution failures
- `WARNING`: Non-critical hook failures (notifications)

### Phase 5 (CircuitBreaker)
- `INFO`: Component initialized
- `INFO`: Circuit breaker reset
- `WARNING`: Circuit breaker tripped
- `WARNING`: Circuit breaker at 95% capacity
- `DEBUG`: Circuit breaker check passed

### Phase 6 (Deduplication)
- `INFO`: Component initialized
- `INFO`: Duplicate blocked
- `DEBUG`: Deduplication check passed

### Phase 7 (Integration)
- `INFO`: Orchestrator initialized with default components
- `INFO`: Agent scheduled
- `DEBUG`: Scheduling artifact
- `DEBUG`: Component hook results
- `SUCCESS`: Orchestrator idle

---

## 🎯 Log Level Guidelines

| Level | Use Case | Example Count per Workflow |
|-------|----------|---------------------------|
| **DEBUG** | Component hook execution, state checks | 100-500 logs |
| **INFO** | Lifecycle events, scheduling decisions | 10-50 logs |
| **WARNING** | Circuit breaker warnings, approaching limits | 0-5 logs |
| **ERROR** | Hook failures, component errors | 0 logs (ideal) |
| **SUCCESS** | Workflow completion | 1 log |

---

## 🧪 Testing Logging

### Capture Logs in Tests

```python
import pytest
from flock.logging.logging import get_logger, configure_logging

@pytest.fixture
def captured_logs():
    """Capture Flock logs during test."""
    logs = []
    
    # Configure logging to capture
    configure_logging(flock_level="DEBUG", external_level="ERROR")
    
    # TODO: Implement log capture mechanism
    # (Can use Loguru's .add() with custom handler)
    
    yield logs

def test_component_logging(captured_logs):
    """Test that components log appropriately."""
    flock = Flock("openai/gpt-4.1")
    
    # Verify initialization logs
    assert any("Component added" in log for log in captured_logs)
    assert any("CircuitBreakerComponent" in log for log in captured_logs)
```

---

## 📋 Validation Checklist

Before merging each phase:

- [ ] All hook runners log entry with component name
- [ ] All decisions (SKIP, DEFER, block) logged at INFO
- [ ] All hook failures logged at ERROR
- [ ] All state transitions logged at DEBUG
- [ ] Component initialization logged at INFO
- [ ] Component shutdown logged at DEBUG
- [ ] No sensitive data in logs (artifact payloads truncated)
- [ ] Log format consistent (key=value pairs)
- [ ] Trace IDs included automatically
- [ ] Performance impact <1ms per log

---

*Reference: `docs/internal/system-improvements/logging-strategy.md` for framework-wide logging strategy*
