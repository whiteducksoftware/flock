# OrchestratorComponent + Logging: Unified Implementation Plan

> **Single-document guide for implementing OrchestratorComponent with integrated logging**
>
> This plan merges architecture implementation (Spec 004) with logging strategy, giving you one comprehensive guide to follow from start to finish.

---

## 📋 Pre-Implementation Checklist

- [ ] Context Ingestion section complete with all required specs
- [ ] Implementation phases logically organized  
- [ ] Each phase starts with test definition (TDD approach)
- [ ] Logging integrated at each phase (not retrofitted)
- [ ] Dependencies between phases identified
- [ ] Final validation phase included
- [ ] No placeholder content remains

---

## 🎯 Goals

This implementation delivers **TWO outcomes in ONE effort**:

1. ✅ **Clean Architecture**: Refactor 138-line `_schedule_artifact` into pluggable components
2. ✅ **Observability**: Comprehensive logging for production debugging

**Why Together?** Adding logs while writing code is 10x easier than retrofitting later.

---

## 📚 Context Priming

*GATE: You MUST fully read all files mentioned before starting implementation.*

### Required Reading

1. **Architecture Specification**:
   - `docs/internal/system-improvements/orchestrator-component-design.md` - Complete design spec

2. **Logging Strategy**:
   - `docs/internal/system-improvements/LOGGING_QUICK_REFERENCE.md` - Quick patterns
   - `docs/internal/system-improvements/logging-strategy-summary.md` - Strategy overview

3. **Reference Patterns**:
   - `src/flock/components.py` (lines 24-90) - AgentComponent pattern to mirror
   - `src/flock/logging/logging.py` - FlockLogger implementation
   - `tests/test_components.py` (lines 1-100) - Test structure

### Key Design Decisions

1. **Mirror AgentComponent Pattern**: Pydantic + TracedMetaMeta (proven success)
2. **8 Lifecycle Hooks**: Exactly 8 hooks matching orchestrator scheduling flow
3. **Priority-Based Ordering**: Components execute in priority order (lower = earlier)
4. **Backward Compatibility**: Auto-add default components to preserve existing behavior
5. **ScheduleDecision Enum**: CONTINUE, SKIP, DEFER (not boolean)
6. **CollectionResult Dataclass**: Contains artifacts + complete flag
7. **Component Chaining**: Hooks execute in sequence, passing results forward
8. **OpenTelemetry Auto-Tracing**: Via TracedModelMeta
9. **Structured Logging**: key=value format for searchability

### Development Commands

```bash
# Tests
pytest tests/test_orchestrator_component*.py -v

# Coverage
pytest --cov=src/flock/orchestrator_component --cov=src/flock/orchestrator

# Lint
ruff check src/flock/

# Format
ruff format src/flock/
```

---

## 📐 Logging Principles

Follow these throughout ALL phases:

1. **Log at lifecycle boundaries** (init, hook execution, shutdown)
2. **Log scheduling decisions** (CONTINUE, SKIP, DEFER)
3. **Log data transformations** (artifact collection, filtering)
4. **Log errors with context** (component name, input data, exception)
5. **Use structured format**: `logger.info(f"Action: key=value, key2=value2")`

### Logging Levels

| Level | When | Example |
|-------|------|---------|
| **DEBUG** | Internal flow, state | `"Circuit breaker check: agent=X, count=5/1000"` |
| **INFO** | Lifecycle, decisions | `"Agent scheduled: name=X, artifacts=2"` |
| **WARNING** | Issues, limits | `"Circuit breaker at 95%: agent=X"` |
| **ERROR** | Failures | `"Agent execution failed: error=X"` |
| **SUCCESS** | Completions | `"Workflow completed: artifacts=10"` |

---

## 🏗️ Phase 1: Base Classes and Enums

**Goal**: Foundation classes with logging infrastructure

**Time**: 4-6 hours

### Context Reading

- [ ] Base class architecture (orchestrator-component-design.md lines 72-330)
- [ ] ScheduleDecision enum (orchestrator-component-design.md lines 309-313)
- [ ] CollectionResult dataclass (orchestrator-component-design.md lines 315-329)
- [ ] AgentComponent pattern (src/flock/components.py lines 51-90)
- [ ] TracedModelMeta usage (src/flock/components.py lines 24-30)

### Write Tests First

Create `tests/test_orchestrator_component.py`:

```python
import pytest
from flock.orchestrator_component import (
    OrchestratorComponent,
    ScheduleDecision,
    CollectionResult,
)

def test_schedule_decision_enum():
    """Test ScheduleDecision has CONTINUE, SKIP, DEFER."""
    assert ScheduleDecision.CONTINUE == "CONTINUE"
    assert ScheduleDecision.SKIP == "SKIP"
    assert ScheduleDecision.DEFER == "DEFER"

def test_collection_result_immediate():
    """Test CollectionResult.immediate() factory."""
    from flock.artifacts import Artifact
    artifacts = [Artifact(...)]
    result = CollectionResult.immediate(artifacts)
    assert result.complete is True
    assert result.artifacts == artifacts

def test_collection_result_waiting():
    """Test CollectionResult.waiting() factory."""
    result = CollectionResult.waiting()
    assert result.complete is False
    assert result.artifacts == []

def test_orchestrator_component_fields():
    """Test OrchestratorComponent has required fields."""
    component = OrchestratorComponent()
    assert hasattr(component, 'name')
    assert hasattr(component, 'config')
    assert hasattr(component, 'priority')
    assert component.priority == 0  # Default

def test_orchestrator_component_hooks():
    """Test OrchestratorComponent has all 8 lifecycle hooks."""
    component = OrchestratorComponent()
    assert hasattr(component, 'on_initialize')
    assert hasattr(component, 'on_artifact_published')
    assert hasattr(component, 'on_before_schedule')
    assert hasattr(component, 'on_collect_artifacts')
    assert hasattr(component, 'on_before_agent_schedule')
    assert hasattr(component, 'on_agent_scheduled')
    assert hasattr(component, 'on_orchestrator_idle')
    assert hasattr(component, 'on_shutdown')

def test_component_priority_ordering():
    """Test components sort by priority."""
    c1 = OrchestratorComponent(priority=10)
    c2 = OrchestratorComponent(priority=5)
    c3 = OrchestratorComponent(priority=20)
    components = [c1, c2, c3]
    components.sort(key=lambda c: c.priority)
    assert components == [c2, c1, c3]
```

**Checklist**:
- [ ] Test ScheduleDecision enum has CONTINUE, SKIP, DEFER values
- [ ] Test CollectionResult dataclass has artifacts and complete fields
- [ ] Test CollectionResult.immediate() returns complete=True
- [ ] Test CollectionResult.waiting() returns complete=False
- [ ] Test OrchestratorComponent has name, config, priority fields
- [ ] Test OrchestratorComponent has all 8 lifecycle hooks
- [ ] Test OrchestratorComponent uses TracedModelMeta
- [ ] Test component priority ordering

### Implement

Create `src/flock/orchestrator_component.py`:

```python
"""OrchestratorComponent base class and supporting types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from flock.logging.auto_trace import AutoTracedMeta
from flock.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.agent import Agent
    from flock.artifacts import Artifact
    from flock.orchestrator import Flock
    from flock.subscription import Subscription
    import asyncio

# Initialize logger for components
logger = get_logger("flock.component")


class ScheduleDecision(str, Enum):
    """Decision returned by on_before_schedule hook.
    
    Examples:
        >>> decision = ScheduleDecision.CONTINUE
        >>> if decision == ScheduleDecision.SKIP:
        ...     # Don't schedule agent
    """
    CONTINUE = "CONTINUE"  # Proceed with scheduling
    SKIP = "SKIP"  # Skip this agent/subscription
    DEFER = "DEFER"  # Defer until later (e.g., waiting for AND gate)


@dataclass
class CollectionResult:
    """Result from on_collect_artifacts hook.
    
    Indicates whether artifact collection is complete and which artifacts
    should be passed to the agent.
    
    Examples:
        >>> # Immediate scheduling (single artifact)
        >>> result = CollectionResult.immediate([artifact])
        
        >>> # Waiting for more artifacts (AND gate, JoinSpec, BatchSpec)
        >>> result = CollectionResult.waiting()
    """
    artifacts: list[Artifact]
    complete: bool
    
    @classmethod
    def immediate(cls, artifacts: list[Artifact]) -> CollectionResult:
        """Create result for immediate scheduling."""
        return cls(artifacts=artifacts, complete=True)
    
    @classmethod
    def waiting(cls) -> CollectionResult:
        """Create result indicating collection is incomplete."""
        return cls(artifacts=[], complete=False)


class OrchestratorComponentConfig(BaseModel):
    """Configuration for orchestrator components."""
    pass  # Can be extended by specific components


class OrchestratorComponent(BaseModel, metaclass=AutoTracedMeta):
    """Base class for orchestrator components with lifecycle hooks.
    
    All public methods are automatically traced via OpenTelemetry.
    
    Components extend orchestrator functionality without modifying core code.
    Execute in priority order (lower priority = earlier execution).
    
    Examples:
        >>> class CircuitBreakerComponent(OrchestratorComponent):
        ...     max_iterations: int = 1000
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
        
        Use for: Resource allocation, loading state, setup.
        """
        pass
    
    async def on_artifact_published(
        self, orchestrator: Flock, artifact: Artifact
    ) -> Artifact | None:
        """Called when artifact is published to blackboard.
        
        Return modified artifact or None to block publishing.
        Components execute in priority order, passing artifact forward.
        
        Use for: Filtering, transformation, validation, enrichment.
        """
        return artifact
    
    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Called before scheduling an agent for an artifact.
        
        Return CONTINUE to proceed, SKIP to skip this agent, DEFER to wait.
        
        Use for: Circuit breaking, deduplication, rate limiting, policy checks.
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
        
        Return CollectionResult if this component handles collection,
        or None to let next component handle it.
        
        First component to return non-None wins (short-circuit).
        
        Use for: AND gates, JoinSpec correlation, BatchSpec batching.
        """
        return None  # Let other components handle
    
    async def on_before_agent_schedule(
        self, orchestrator: Flock, agent: Agent, artifacts: list[Artifact]
    ) -> list[Artifact] | None:
        """Called before final agent scheduling with collected artifacts.
        
        Return modified artifacts or None to block scheduling.
        Components execute in priority order, passing artifacts forward.
        
        Use for: Final validation, artifact transformation, enrichment.
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
        
        Use for: Metrics, logging, event emission, monitoring.
        """
        pass
    
    async def on_orchestrator_idle(self, orchestrator: Flock) -> None:
        """Called when orchestrator becomes idle (no pending tasks).
        
        Use for: Cleanup, state reset, checkpointing, metrics flush.
        """
        pass
    
    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Called when orchestrator shuts down.
        
        Use for: Resource cleanup, final metrics, persistence.
        """
        pass


__all__ = [
    "OrchestratorComponent",
    "OrchestratorComponentConfig",
    "ScheduleDecision",
    "CollectionResult",
]
```

**Implementation Checklist**:
- [ ] Create `src/flock/orchestrator_component.py`
- [ ] Implement ScheduleDecision enum (String enum with 3 values)
- [ ] Implement CollectionResult dataclass (with factories)
- [ ] Implement OrchestratorComponentConfig class
- [ ] Implement OrchestratorComponent base class (8 hooks)
- [ ] Apply TracedModelMeta metaclass
- [ ] Add logger initialization: `logger = get_logger("flock.component")`
- [ ] Add comprehensive docstrings
- [ ] Export classes in `__all__`

**Logging in Phase 1**: No logging in base class (hooks are no-ops).

### Validate

```bash
# Run tests
pytest tests/test_orchestrator_component.py -v

# Check coverage
pytest tests/test_orchestrator_component.py --cov=src/flock/orchestrator_component

# Lint
ruff check src/flock/orchestrator_component.py

# Format
ruff format src/flock/orchestrator_component.py
```

**Validation Checklist**:
- [ ] All tests passing
- [ ] Coverage >80%
- [ ] Ruff linting passes
- [ ] All 8 hooks defined with correct signatures
- [ ] TracedModelMeta applied
- [ ] Logger initialized

### Commit Checkpoint

```bash
git add src/flock/orchestrator_component.py tests/test_orchestrator_component.py
git commit -m "Phase 1: OrchestratorComponent base classes

- Implement ScheduleDecision enum (CONTINUE, SKIP, DEFER)
- Implement CollectionResult dataclass with factories
- Implement OrchestratorComponent with 8 lifecycle hooks
- Add OpenTelemetry auto-tracing via TracedModelMeta
- Initialize logger for component subsystem
- 100% test coverage for base classes"
```

---

## 🏗️ Phase 2: Orchestrator Integration

**Goal**: Add component management to Flock orchestrator

**Time**: 2-4 hours

### Context Reading

- [ ] Component management API (orchestrator-component-design.md lines 944-980)
- [ ] Backward compatibility strategy (orchestrator-component-design.md lines 1032-1033)
- [ ] Current Flock.__init__ (src/flock/orchestrator.py lines 86-150)

### Write Tests

Add to `tests/test_orchestrator_component.py`:

```python
def test_flock_add_component(orchestrator):
    """Test Flock.add_component() method."""
    from flock.orchestrator_component import OrchestratorComponent
    
    component = OrchestratorComponent(name="test_comp", priority=5)
    result = orchestrator.add_component(component)
    
    # Method chaining
    assert result is orchestrator
    
    # Component stored
    assert component in orchestrator._components

def test_flock_component_priority_sorting(orchestrator):
    """Test components are sorted by priority after add."""
    from flock.orchestrator_component import OrchestratorComponent
    
    c1 = OrchestratorComponent(priority=10)
    c2 = OrchestratorComponent(priority=5)
    c3 = OrchestratorComponent(priority=20)
    
    orchestrator.add_component(c1)
    orchestrator.add_component(c2)
    orchestrator.add_component(c3)
    
    # Should be sorted: [c2(5), c1(10), c3(20)]
    assert orchestrator._components[0].priority == 5
    assert orchestrator._components[1].priority == 10
    assert orchestrator._components[2].priority == 20

def test_flock_initializes_with_empty_components():
    """Test Flock starts with no components (before auto-add)."""
    from flock.orchestrator import Flock
    flock = Flock("openai/gpt-4.1")
    # Will have default components auto-added in Phase 7
    # For now, just verify _components list exists
    assert hasattr(flock, '_components')
```

**Test Checklist**:
- [ ] Test add_component() accepts OrchestratorComponent
- [ ] Test add_component() returns self (method chaining)
- [ ] Test components stored in priority order
- [ ] Test Flock initializes with _components list

### Implement

Modify `src/flock/orchestrator.py`:

```python
# Add import at top of file
from flock.orchestrator_component import OrchestratorComponent

class Flock(metaclass=AutoTracedMeta):
    def __init__(
        self,
        model: str | None = None,
        *,
        store: BlackboardStore | None = None,
        max_agent_iterations: int = 1000,
    ) -> None:
        # ... existing init code ...
        
        # Component system
        self._components: list[OrchestratorComponent] = []
        self._components_initialized: bool = False
        
        # Log component system initialization
        self._logger.debug("Orchestrator initialized: components=[]")
        
        # ... rest of init ...

    def add_component(self, component: OrchestratorComponent) -> "Flock":
        """Add an OrchestratorComponent to this orchestrator.
        
        Components execute in priority order (lower priority = earlier).
        
        Args:
            component: Component to add
            
        Returns:
            Self for method chaining
            
        Examples:
            >>> flock = Flock("openai/gpt-4.1")
            >>> flock.add_component(CircuitBreakerComponent(max_iterations=500))
            >>> flock.add_component(MetricsComponent())
        """
        self._components.append(component)
        self._components.sort(key=lambda c: c.priority)
        
        self._logger.info(
            f"Component added: name={component.name or component.__class__.__name__}, "
            f"priority={component.priority}, total_components={len(self._components)}"
        )
        
        return self
```

**Implementation Checklist**:
- [ ] Add `_components: list[OrchestratorComponent]` to __init__
- [ ] Add `_components_initialized: bool` to __init__
- [ ] Log initialization: `logger.debug("Orchestrator initialized: components=[]")`
- [ ] Implement add_component() with priority sorting
- [ ] Log component addition at INFO level
- [ ] Import OrchestratorComponent at top

### Validate

```bash
pytest tests/test_orchestrator_component.py::test_flock* -v
pytest --cov=src/flock/orchestrator --cov-append
ruff check src/flock/orchestrator.py
```

**Validation Checklist**:
- [ ] Tests passing
- [ ] Coverage maintained
- [ ] Linting passes
- [ ] Fluent API works (method chaining)
- [ ] Logging verified (check test output)

### Commit Checkpoint

```bash
git add src/flock/orchestrator.py tests/test_orchestrator_component.py
git commit -m "Phase 2: Add component management to Flock orchestrator

- Add _components list to Flock.__init__
- Implement add_component() with priority sorting
- Add INFO logging for component addition
- Method chaining support (fluent API)
- Tests for component management"
```

---

## 🏗️ Phase 3: Component Hook Runner Methods

**Goal**: Implement 8 hook runner methods with comprehensive logging

**Time**: 8-12 hours

### Context Reading

- [ ] Hook invocation pattern (orchestrator-component-design.md lines 868-941)
- [ ] Hook chaining logic (data transformation vs notification)
- [ ] AgentComponent hook execution (src/flock/components.py lines 60-89)

### Write Tests

Add to `tests/test_orchestrator_component.py`:

```python
@pytest.mark.asyncio
async def test_run_artifact_published_chains_components(orchestrator):
    """Test _run_artifact_published chains components in priority order."""
    from flock.orchestrator_component import OrchestratorComponent
    from flock.artifacts import Artifact
    
    call_order = []
    
    class TestComponent1(OrchestratorComponent):
        priority = 1
        async def on_artifact_published(self, orch, artifact):
            call_order.append('comp1')
            # Transform artifact
            artifact.tags.add('comp1')
            return artifact
    
    class TestComponent2(OrchestratorComponent):
        priority = 2
        async def on_artifact_published(self, orch, artifact):
            call_order.append('comp2')
            artifact.tags.add('comp2')
            return artifact
    
    orchestrator.add_component(TestComponent2())  # Higher priority
    orchestrator.add_component(TestComponent1())  # Lower priority (runs first)
    
    artifact = Artifact(type="Test", payload={}, produced_by="test")
    result = await orchestrator._run_artifact_published(artifact)
    
    # Components run in priority order
    assert call_order == ['comp1', 'comp2']
    # Artifact transformed by both
    assert 'comp1' in result.tags
    assert 'comp2' in result.tags

@pytest.mark.asyncio
async def test_run_artifact_published_stops_on_none(orchestrator):
    """Test _run_artifact_published stops if component returns None."""
    from flock.orchestrator_component import OrchestratorComponent
    
    class BlockingComponent(OrchestratorComponent):
        async def on_artifact_published(self, orch, artifact):
            return None  # Block publishing
    
    orchestrator.add_component(BlockingComponent())
    
    from flock.artifacts import Artifact
    artifact = Artifact(type="Test", payload={}, produced_by="test")
    result = await orchestrator._run_artifact_published(artifact)
    
    assert result is None  # Blocked

@pytest.mark.asyncio
async def test_run_before_schedule_continues(orchestrator):
    """Test _run_before_schedule returns CONTINUE by default."""
    from flock.orchestrator_component import OrchestratorComponent, ScheduleDecision
    from flock.artifacts import Artifact
    from flock.agent import Agent
    from flock.subscription import Subscription
    
    orchestrator.add_component(OrchestratorComponent())
    
    artifact = Artifact(type="Test", payload={}, produced_by="test")
    agent = Agent("test_agent", orchestrator=orchestrator)
    subscription = Subscription(agent_name="test_agent", types=["Test"])
    
    decision = await orchestrator._run_before_schedule(artifact, agent, subscription)
    assert decision == ScheduleDecision.CONTINUE

@pytest.mark.asyncio
async def test_run_before_schedule_stops_on_skip(orchestrator):
    """Test _run_before_schedule stops on SKIP."""
    from flock.orchestrator_component import OrchestratorComponent, ScheduleDecision
    
    class SkipComponent(OrchestratorComponent):
        async def on_before_schedule(self, orch, artifact, agent, sub):
            return ScheduleDecision.SKIP
    
    orchestrator.add_component(SkipComponent())
    
    from flock.artifacts import Artifact
    from flock.agent import Agent
    from flock.subscription import Subscription
    
    artifact = Artifact(type="Test", payload={}, produced_by="test")
    agent = Agent("test_agent", orchestrator=orchestrator)
    subscription = Subscription(agent_name="test_agent", types=["Test"])
    
    decision = await orchestrator._run_before_schedule(artifact, agent, subscription)
    assert decision == ScheduleDecision.SKIP

# Add similar tests for:
# - test_run_collect_artifacts_returns_first_non_none
# - test_run_collect_artifacts_default_immediate
# - test_run_before_agent_schedule_chains_transformations
# - test_run_before_agent_schedule_stops_on_none
# - test_run_agent_scheduled_executes_all
# - test_run_initialize_calls_all_components
# - test_run_idle_calls_all_components
# - test_run_shutdown_calls_all_components
# - test_hook_runner_handles_exceptions
```

### Implement

Add to `src/flock/orchestrator.py`:

```python
# Component Hook Runners
# ─────────────────────────────────────────────────────────────

async def _run_initialize(self) -> None:
    """Initialize all components in priority order (called once)."""
    if self._components_initialized:
        return
    
    self._logger.info(f"Initializing {len(self._components)} orchestrator components")
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        self._logger.debug(
            f"Initializing component: name={comp_name}, priority={component.priority}"
        )
        
        try:
            await component.on_initialize(self)
        except Exception as e:
            self._logger.error(
                f"Component initialization failed: name={comp_name}, error={str(e)}"
            )
            raise
    
    self._components_initialized = True
    self._logger.success(f"All components initialized: count={len(self._components)}")

async def _run_artifact_published(self, artifact: Artifact) -> Artifact | None:
    """Run on_artifact_published hooks (returns modified artifact or None to block)."""
    current_artifact = artifact
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        self._logger.debug(
            f"Running on_artifact_published: component={comp_name}, "
            f"artifact_type={current_artifact.type}, artifact_id={current_artifact.id}"
        )
        
        try:
            result = await component.on_artifact_published(self, current_artifact)
            
            if result is None:
                self._logger.info(
                    f"Artifact blocked by component: component={comp_name}, "
                    f"artifact_type={current_artifact.type}, artifact_id={current_artifact.id}"
                )
                return None
            
            current_artifact = result
        except Exception as e:
            self._logger.error(
                f"Component hook failed: component={comp_name}, "
                f"hook=on_artifact_published, error={str(e)}"
            )
            raise
    
    return current_artifact

async def _run_before_schedule(
    self, artifact: Artifact, agent: Agent, subscription: Subscription
) -> ScheduleDecision:
    """Run on_before_schedule hooks (returns CONTINUE, SKIP, or DEFER)."""
    from flock.orchestrator_component import ScheduleDecision
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        self._logger.debug(
            f"Running on_before_schedule: component={comp_name}, "
            f"agent={agent.name}, artifact_type={artifact.type}"
        )
        
        try:
            decision = await component.on_before_schedule(self, artifact, agent, subscription)
            
            if decision == ScheduleDecision.SKIP:
                self._logger.info(
                    f"Scheduling skipped by component: component={comp_name}, "
                    f"agent={agent.name}, artifact_type={artifact.type}, decision=SKIP"
                )
                return ScheduleDecision.SKIP
            
            if decision == ScheduleDecision.DEFER:
                self._logger.debug(
                    f"Scheduling deferred by component: component={comp_name}, "
                    f"agent={agent.name}, decision=DEFER"
                )
                return ScheduleDecision.DEFER
            
        except Exception as e:
            self._logger.error(
                f"Component hook failed: component={comp_name}, "
                f"hook=on_before_schedule, error={str(e)}"
            )
            raise
    
    return ScheduleDecision.CONTINUE

async def _run_collect_artifacts(
    self, artifact: Artifact, agent: Agent, subscription: Subscription
) -> CollectionResult:
    """Run on_collect_artifacts hooks (returns first non-None result)."""
    from flock.orchestrator_component import CollectionResult
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        self._logger.debug(
            f"Running on_collect_artifacts: component={comp_name}, "
            f"agent={agent.name}, artifact_type={artifact.type}"
        )
        
        try:
            result = await component.on_collect_artifacts(self, artifact, agent, subscription)
            
            if result is not None:
                self._logger.debug(
                    f"Collection handled by component: component={comp_name}, "
                    f"complete={result.complete}, artifact_count={len(result.artifacts)}"
                )
                return result
        except Exception as e:
            self._logger.error(
                f"Component hook failed: component={comp_name}, "
                f"hook=on_collect_artifacts, error={str(e)}"
            )
            raise
    
    # Default: immediate scheduling with single artifact
    self._logger.debug(
        f"No component handled collection, using default: "
        f"agent={agent.name}, artifact_type={artifact.type}"
    )
    return CollectionResult.immediate([artifact])

async def _run_before_agent_schedule(
    self, agent: Agent, artifacts: list[Artifact]
) -> list[Artifact] | None:
    """Run on_before_agent_schedule hooks (returns modified artifacts or None to block)."""
    current_artifacts = artifacts
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        self._logger.debug(
            f"Running on_before_agent_schedule: component={comp_name}, "
            f"agent={agent.name}, artifact_count={len(current_artifacts)}"
        )
        
        try:
            result = await component.on_before_agent_schedule(self, agent, current_artifacts)
            
            if result is None:
                self._logger.info(
                    f"Agent scheduling blocked by component: component={comp_name}, "
                    f"agent={agent.name}"
                )
                return None
            
            current_artifacts = result
        except Exception as e:
            self._logger.error(
                f"Component hook failed: component={comp_name}, "
                f"hook=on_before_agent_schedule, error={str(e)}"
            )
            raise
    
    return current_artifacts

async def _run_agent_scheduled(
    self, agent: Agent, artifacts: list[Artifact], task: asyncio.Task
) -> None:
    """Run on_agent_scheduled hooks (notification only, no return value)."""
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        self._logger.debug(
            f"Running on_agent_scheduled: component={comp_name}, "
            f"agent={agent.name}, artifact_count={len(artifacts)}"
        )
        
        try:
            await component.on_agent_scheduled(self, agent, artifacts, task)
        except Exception as e:
            self._logger.warning(
                f"Component notification hook failed (non-critical): "
                f"component={comp_name}, hook=on_agent_scheduled, error={str(e)}"
            )
            # Don't propagate - this is a notification hook

async def _run_idle(self) -> None:
    """Run on_orchestrator_idle hooks when orchestrator becomes idle."""
    self._logger.debug(
        f"Running on_orchestrator_idle hooks: component_count={len(self._components)}"
    )
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        
        try:
            await component.on_orchestrator_idle(self)
        except Exception as e:
            self._logger.warning(
                f"Component idle hook failed (non-critical): "
                f"component={comp_name}, hook=on_orchestrator_idle, error={str(e)}"
            )

async def _run_shutdown(self) -> None:
    """Run on_shutdown hooks when orchestrator shuts down."""
    self._logger.info(f"Shutting down {len(self._components)} orchestrator components")
    
    for component in self._components:
        comp_name = component.name or component.__class__.__name__
        self._logger.debug(f"Shutting down component: name={comp_name}")
        
        try:
            await component.on_shutdown(self)
        except Exception as e:
            self._logger.error(
                f"Component shutdown failed: component={comp_name}, "
                f"hook=on_shutdown, error={str(e)}"
            )
            # Continue shutting down other components
```

**Implementation Checklist**:
- [ ] Implement _run_initialize() with INFO/DEBUG logging
- [ ] Implement _run_artifact_published() with artifact transformation
- [ ] Implement _run_before_schedule() with decision logging
- [ ] Implement _run_collect_artifacts() with default behavior
- [ ] Implement _run_before_agent_schedule() with artifact chaining
- [ ] Implement _run_agent_scheduled() with non-critical error handling
- [ ] Implement _run_idle() with component count logging
- [ ] Implement _run_shutdown() with cleanup logging
- [ ] Add comprehensive logging at each hook
- [ ] Handle exceptions appropriately (propagate vs log)

**Logging Checklist for Phase 3**:
- [ ] DEBUG logs for each hook invocation
- [ ] INFO logs for significant decisions (SKIP, block)
- [ ] WARNING logs for non-critical failures (notifications)
- [ ] ERROR logs for critical failures (with re-raise)
- [ ] SUCCESS log for initialization complete
- [ ] Structured format (key=value pairs)

### Validate

```bash
pytest tests/test_orchestrator_component.py::test_run_* -v
pytest --cov=src/flock/orchestrator --cov-append
ruff check src/flock/orchestrator.py
```

**Validation Checklist**:
- [ ] All hook runner tests passing
- [ ] Coverage >80%
- [ ] Linting passes
- [ ] Priority ordering working
- [ ] Chaining logic working
- [ ] Exception handling working
- [ ] Logging verified in test output

### Commit Checkpoint

```bash
git add src/flock/orchestrator.py tests/test_orchestrator_component.py
git commit -m "Phase 3: Implement component hook runners with logging

- Implement 8 hook runner methods (_run_initialize, _run_artifact_published, etc.)
- Add comprehensive DEBUG/INFO/WARNING/ERROR logging at each hook
- Implement priority-based execution order
- Implement component chaining (transformations)
- Implement short-circuit logic (SKIP, None, first non-None)
- Add exception handling with appropriate propagation
- Tests for all hook runners and edge cases"
```

---

*[Continue with Phases 4-7 following the same pattern: Context → Tests → Implement → Logging → Validate → Commit]*

---

## 🎯 Success Metrics (End of Implementation)

### Architecture
- [ ] OrchestratorComponent base class implemented
- [ ] 8 hook runner methods working
- [ ] CircuitBreakerComponent migrated
- [ ] DeduplicationComponent migrated
- [ ] `_schedule_artifact` reduced from 138 to <50 lines
- [ ] ALL existing tests passing (743 tests)
- [ ] Performance overhead <5%

### Logging
- [ ] Component lifecycle logged (init, hooks, shutdown)
- [ ] Scheduling decisions logged (SKIP, DEFER, CONTINUE)
- [ ] Circuit breaker state logged (counts, warnings, trips)
- [ ] Deduplication logged (blocks, passes)
- [ ] Hook execution logged (entry, results, errors)
- [ ] Structured format validated (key=value pairs)
- [ ] Performance overhead <1ms per log

---

*This unified plan continues with Phases 4-7 (Refactor _schedule_artifact, CircuitBreaker, Deduplication, Integration) following the same structure. See PLAN.md and LOGGING_GUIDE.md for complete phase details.*
