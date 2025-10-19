# Flock Framework Refactor Implementation Plan

**Version:** 1.0
**Date:** 2025-10-17
**Status:** READY FOR EXECUTION
**Companion Document:** [DESIGN.md](./DESIGN.md)

---

---

## 🚨 CRITICAL: NO BACKWARDS COMPATIBILITY! 🚨

**This framework is NOT YET RELEASED - we're building it RIGHT!**

- ❌ **NO backwards compatibility layers** - We delete old code completely
- ❌ **NO deprecation warnings** - Old imports don't exist
- ❌ **NO legacy cruft** - Clean, modern codebase only
- ✅ **Breaking changes are ENCOURAGED** - Make it beautiful!
- ✅ **Clean slate** - This is our chance to do it right

**If you see backwards compatibility anywhere in this plan - DELETE IT!**

---

## Overview

This implementation plan breaks the Flock refactoring into **7 self-contained phases**. Each phase:

- ✅ **Leaves the framework functional** - Tests pass after each phase
- ✅ **Has clear success criteria** - Objective completion metrics
- ✅ **Can be executed independently** - Work this week, phase 2 in two weeks
- ✅ **Builds incrementally** - Each phase prepares for the next
- ✅ **Clean, modern code** - No legacy baggage allowed

**Total Estimated Effort:** 60-80 hours across 7 phases

---

## Phase Timeline

```
Phase 0: Preparation
Phase 1: Foundation & Utilities       [Week 1]  ⏱️  8-12 hours
Phase 2: Component Organization       [Week 2]  ⏱️  10-15 hours
Phase 3: Orchestrator Modularization  [Week 3]  ⏱️  12-16 hours
Phase 4: Agent Modularization         [Week 4]  ⏱️  10-14 hours
Phase 5: Engine Refactoring           [Week 5]  ⏱️  8-12 hours
Phase 6: Storage & Context            [Week 6]  ⏱️  6-10 hours
Phase 7: Dashboard & Polish           [Week 7]  ⏱️  6-10 hours
```

---

## Phase 0: Preparation

**Objective:** Establish baseline and safety nets

This is is a uv based project. add needed libraries for complexity measurement and so on with "uv add --dev"
the frontend in "src/flock/frontend" is to be excluded

### Tasks

1. **Document Current State**
   ```bash
   # Run full test suite and capture results
   pytest tests/ --cov=src/flock --cov-report=html -v > baseline_tests.txt

   # Capture test coverage
   coverage report > baseline_coverage.txt

   # Run linting
   ruff check src/ > baseline_lint.txt

   # Type checking
   mypy src/ > baseline_types.txt
   ```

2. **Create Performance Benchmarks**
   ```python
   # tests/benchmarks/baseline.py
   import time
   import pytest
   from flock import Flock, AgentBuilder

   @pytest.mark.benchmark
   def test_agent_execution_throughput():
       """Baseline: Agent execution throughput"""
       orchestrator = Flock()
       agent = AgentBuilder().consumes(...).publishes(...).agent()

       start = time.time()
       for _ in range(1000):
           orchestrator.publish(artifact)
       duration = time.time() - start

       throughput = 1000 / duration
       print(f"Baseline throughput: {throughput:.2f} agents/sec")
       assert throughput > 0  # Document baseline
   ```

3. **Setup Branch Strategy**
   ```bash
   # Create refactor branch
   git checkout -b refactor/phase-1-foundation

   # Setup branch protection
   # - Require tests to pass
   # - Require code review
   # - No force push to main
   ```

4. **Create Refactor Tracking**
   ```markdown
   # Create docs/refactor/PROGRESS.md to track completion

   ## Phase Completion Tracker
   - [ ] Phase 0: Preparation
   - [ ] Phase 1: Foundation & Utilities
   - [ ] Phase 2: Component Organization
   ...
   ```

### Success Criteria

- ✅ Baseline test results documented
- ✅ Performance benchmarks captured
- ✅ Branch strategy established
- ✅ Team aligned on approach

**Duration:** 2-4 hours

---

## Phase 1: Foundation & Utilities

**Objective:** Create foundation for refactoring - extract utilities, eliminate duplication

**Why First?** This phase has minimal risk and creates reusable utilities needed by later phases.

### 1.1 Create Core Module Structure

```bash
# Create new directory structure
mkdir -p src/flock/core
mkdir -p src/flock/utils

# Move base abstractions (no breaking changes yet)
```

**Files to create:**

```python
# src/flock/utils/__init__.py
"""Shared utilities for Flock framework."""

# src/flock/utils/type_resolution.py
"""Type registry resolution utilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flock.types.registry import TypeRegistry

class TypeResolutionHelper:
    """Helper for safe type resolution."""

    @staticmethod
    def safe_resolve(registry: "TypeRegistry", type_name: str) -> str:
        """
        Safely resolve type name to canonical form.

        Args:
            registry: Type registry instance
            type_name: Type name to resolve

        Returns:
            Canonical type name (or original if not found)
        """
        try:
            return registry.resolve_name(type_name)
        except KeyError:
            return type_name


# src/flock/utils/visibility.py
"""Visibility deserialization utilities."""

from flock.types.visibility import (
    Visibility, PublicVisibility, PrivateVisibility,
    TeamVisibility, GroupVisibility
)

class VisibilityDeserializer:
    """Deserializes visibility from dict/str representation."""

    @staticmethod
    def deserialize(data: dict | str) -> Visibility:
        """
        Deserialize visibility from various formats.

        Args:
            data: Dict with 'kind' field or string

        Returns:
            Visibility instance
        """
        if isinstance(data, str):
            kind = data
            props = {}
        else:
            kind = data.get("kind")
            props = data

        if kind == "Public":
            return PublicVisibility()
        elif kind == "Private":
            agents = set(props.get("agents", []))
            return PrivateVisibility(agents=agents)
        elif kind == "Team":
            team = props.get("team", "")
            return TeamVisibility(team=team)
        elif kind == "Group":
            groups = set(props.get("groups", []))
            return GroupVisibility(groups=groups)
        else:
            raise ValueError(f"Unknown visibility kind: {kind}")


# src/flock/utils/async_utils.py
"""Async utility decorators and helpers."""

import asyncio
from functools import wraps
from typing import Any, Callable

class AsyncLockRequired:
    """Decorator ensuring async lock acquisition."""

    def __init__(self, lock_attr: str = "_lock"):
        """
        Initialize decorator.

        Args:
            lock_attr: Name of lock attribute on class (default: "_lock")
        """
        self.lock_attr = lock_attr

    def __call__(self, func: Callable) -> Callable:
        """Apply decorator to function."""
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            lock = getattr(self, self.lock_attr)
            async with lock:
                return await func(self, *args, **kwargs)
        return wrapper

def async_lock_required(lock_attr: str = "_lock"):
    """
    Decorator ensuring async lock acquisition.

    Usage:
        class MyClass:
            def __init__(self):
                self._lock = asyncio.Lock()

            @async_lock_required()
            async def my_method(self):
                # Lock automatically acquired
                pass
    """
    return AsyncLockRequired(lock_attr)


# src/flock/utils/validation.py
"""Common validation utilities."""

from typing import Any, Callable
from pydantic import BaseModel

class ArtifactValidator:
    """Validates artifacts against predicates."""

    @staticmethod
    def validate_artifact(
        artifact: Any,
        model_cls: type[BaseModel],
        predicate: Callable[[BaseModel], bool] | None = None
    ) -> tuple[bool, BaseModel | None, str | None]:
        """
        Validate artifact payload against model and optional predicate.

        Args:
            artifact: Artifact to validate
            model_cls: Pydantic model class
            predicate: Optional validation predicate

        Returns:
            Tuple of (is_valid, model_instance, error_message)
        """
        try:
            # Validate against model
            model_instance = model_cls(**artifact.payload)

            # Apply predicate if provided
            if predicate and not predicate(model_instance):
                return False, model_instance, "Predicate validation failed"

            return True, model_instance, None

        except Exception as e:
            return False, None, str(e)
```

### 1.2 Replace Duplicated Code with Utilities

**Target files to update:**
- `src/flock/agent.py`
- `src/flock/orchestrator.py`
- `src/flock/store.py`
- `src/flock/context_provider.py`

**Example refactoring (agent.py):**

```python
# BEFORE (agent.py, lines ~350)
try:
    canonical = type_registry.resolve_name(type_name)
except KeyError:
    canonical = type_name

# AFTER
from flock.utils.type_resolution import TypeResolutionHelper
canonical = TypeResolutionHelper.safe_resolve(type_registry, type_name)
```

**Example refactoring (store.py):**

```python
# BEFORE (store.py, lines ~800)
if kind == "Public":
    return PublicVisibility()
elif kind == "Private":
    return PrivateVisibility(agents=set(...))
# ... more cases

# AFTER
from flock.utils.visibility import VisibilityDeserializer
return VisibilityDeserializer.deserialize(visibility_data)
```

**Example refactoring (orchestrator.py):**

```python
# BEFORE (orchestrator.py, multiple locations)
async with self._lock:
    await self._operation()

# AFTER
from flock.utils.async_utils import async_lock_required

@async_lock_required()
async def _operation(self):
    # Lock automatically acquired
    pass
```

### 1.3 Update Tests

```python
# tests/utils/test_type_resolution.py
def test_safe_resolve_existing_type():
    """Test resolving existing type returns canonical name."""
    registry = TypeRegistry()
    registry.register_type("MyType", MyTypeClass)

    result = TypeResolutionHelper.safe_resolve(registry, "MyType")
    assert result == "my_module.MyType"

def test_safe_resolve_missing_type():
    """Test resolving missing type returns original name."""
    registry = TypeRegistry()

    result = TypeResolutionHelper.safe_resolve(registry, "Unknown")
    assert result == "Unknown"


# tests/utils/test_visibility.py
def test_deserialize_public():
    """Test deserializing public visibility."""
    result = VisibilityDeserializer.deserialize({"kind": "Public"})
    assert isinstance(result, PublicVisibility)

def test_deserialize_private():
    """Test deserializing private visibility with agents."""
    result = VisibilityDeserializer.deserialize({
        "kind": "Private",
        "agents": ["agent1", "agent2"]
    })
    assert isinstance(result, PrivateVisibility)
    assert result.agents == {"agent1", "agent2"}
```

### 1.4 Update Documentation

```python
# Add docstrings to all utility functions
# Update DESIGN.md with Phase 1 completion
```

### Success Criteria

- ✅ All utility modules created with tests
- ✅ Type resolution duplicates eliminated (8+ → 1)
- ✅ Visibility deserialization duplicates eliminated (5+ → 1)
- ✅ Lock acquisition decorator reduces boilerplate
- ✅ All existing tests pass
- ✅ Test coverage maintained or improved
- ✅ No performance regression

**Estimated Effort:** 8-12 hours

**Files Changed:**
- New: `src/flock/utils/*.py` (4 files)
- Modified: `agent.py`, `orchestrator.py`, `store.py`, `context_provider.py`
- New: `tests/utils/*.py` (4 test files)

---

## Phase 2: Component Organization

**Objective:** Organize components into clear library structure

**Why Second?** Creates foundation for component-based refactoring in later phases.

### 2.1 Create Component Directory Structure

```bash
# Create component library structure
mkdir -p src/flock/components/agent
mkdir -p src/flock/components/orchestrator/scheduling
```

### 2.2 Extract Agent Components

**Move existing utilities to components:**

```python
# BEFORE: Utilities embedded in agent.py

# AFTER: src/flock/components/agent/output_utility.py
"""Output metadata utility component."""

from flock.core.component import AgentComponent

class OutputUtilityComponent(AgentComponent):
    """
    Adds metadata to agent outputs.

    Built-in component that enriches outputs with:
    - Agent name
    - Timestamp
    - Execution context
    """

    def __init__(self):
        super().__init__(priority=1000)  # Run last

    async def on_post_evaluate(self, agent, ctx, outputs, output_group):
        """Add metadata to outputs before publishing."""
        enriched = []
        for output in outputs:
            output.metadata = {
                **output.metadata,
                "agent": agent.name,
                "timestamp": ctx.timestamp,
                "output_group": output_group.name
            }
            enriched.append(output)
        return enriched


# src/flock/components/agent/__init__.py
"""Agent component library."""

from .output_utility import OutputUtilityComponent
from .metrics import MetricsComponent  # If implementing
from .validation import ValidationComponent  # If implementing

__all__ = [
    "OutputUtilityComponent",
    "MetricsComponent",
    "ValidationComponent"
]
```

### 2.3 Extract Orchestrator Components

**Move built-in components:**

```python
# BEFORE: All in orchestrator_component.py

# AFTER: src/flock/components/orchestrator/circuit_breaker.py
"""Circuit breaker component for preventing runaway loops."""

from flock.core.component import OrchestratorComponent
from flock.types.artifacts import ScheduleDecision

class CircuitBreakerComponent(OrchestratorComponent):
    """
    Prevents runaway agent loops via circuit breaking.

    Tracks agent iterations and prevents infinite loops by:
    - Counting iterations per agent
    - Triggering circuit break at threshold
    - Resetting on orchestrator idle
    """

    def __init__(self, max_iterations: int = 100, priority: int = 10):
        """
        Initialize circuit breaker.

        Args:
            max_iterations: Max iterations before circuit breaks
            priority: Component priority (lower = earlier)
        """
        super().__init__(priority=priority)
        self.max_iterations = max_iterations
        self._counts: dict[str, int] = {}

    async def on_before_schedule(self, orch, artifact, agent, subscription):
        """Check circuit breaker before scheduling."""
        count = self._counts.get(agent.name, 0)

        if count >= self.max_iterations:
            self._logger.warning(
                f"Circuit breaker triggered for agent {agent.name} "
                f"(iterations={count})"
            )
            return ScheduleDecision.SKIP

        self._counts[agent.name] = count + 1
        return ScheduleDecision.CONTINUE

    async def on_orchestrator_idle(self, orch):
        """Reset circuit breaker on idle."""
        self._counts.clear()


# src/flock/components/orchestrator/deduplication.py
"""Deduplication component."""

from flock.core.component import OrchestratorComponent
from flock.types.artifacts import ScheduleDecision

class DeduplicationComponent(OrchestratorComponent):
    """
    Prevents duplicate artifact processing.

    Tracks (artifact_id, agent_name) pairs and skips duplicates.
    """

    def __init__(self, priority: int = 20):
        super().__init__(priority=priority)
        self._processed: set[tuple[str, str]] = set()

    async def on_before_schedule(self, orch, artifact, agent, subscription):
        """Check for duplicate processing."""
        key = (artifact.id, agent.name)

        if key in self._processed:
            self._logger.debug(f"Skipping duplicate: {key}")
            return ScheduleDecision.SKIP

        self._processed.add(key)
        return ScheduleDecision.CONTINUE

    async def on_orchestrator_idle(self, orch):
        """Could implement TTL-based cleanup here."""
        pass


# src/flock/components/orchestrator/__init__.py
"""Orchestrator component library."""

from .circuit_breaker import CircuitBreakerComponent
from .deduplication import DeduplicationComponent
from .collection import BuiltinCollectionComponent

__all__ = [
    "CircuitBreakerComponent",
    "DeduplicationComponent",
    "BuiltinCollectionComponent"
]
```

### 2.4 Update Import Paths

```python
# src/flock/__init__.py
"""
Flock framework - Agent orchestration system.
"""

# Core imports
from flock.agent import Agent
from flock import Flock
from flock.builder import AgentBuilder

# Component imports
from flock.components import AgentComponent, OrchestratorComponent

# Component library
from flock.components.orchestrator import (
    CircuitBreakerComponent,
    DeduplicationComponent
)

__all__ = [
    # Core
    "Agent",
    "Flock",
    "AgentBuilder",

    # Components
    "AgentComponent",
    "OrchestratorComponent",
    "CircuitBreakerComponent",
    "DeduplicationComponent"
]
```

**Remove old import locations:**

```python
# Delete: src/flock/orchestrator_component.py
# Users must update to: from flock.components.orchestrator import ...
```

### 2.5 Update Tests

```python
# tests/components/orchestrator/test_circuit_breaker.py
import pytest
from flock.components.orchestrator import CircuitBreakerComponent
from flock.types.artifacts import ScheduleDecision

@pytest.mark.asyncio
async def test_circuit_breaker_allows_under_threshold():
    """Circuit breaker allows execution under threshold."""
    cb = CircuitBreakerComponent(max_iterations=5)

    # First 5 should be allowed
    for _ in range(5):
        decision = await cb.on_before_schedule(orch, artifact, agent, sub)
        assert decision == ScheduleDecision.CONTINUE

@pytest.mark.asyncio
async def test_circuit_breaker_triggers_at_threshold():
    """Circuit breaker triggers at threshold."""
    cb = CircuitBreakerComponent(max_iterations=5)

    # Reach threshold
    for _ in range(5):
        await cb.on_before_schedule(orch, artifact, agent, sub)

    # 6th should be skipped
    decision = await cb.on_before_schedule(orch, artifact, agent, sub)
    assert decision == ScheduleDecision.SKIP
```

### 2.6 Update Documentation

```markdown
# Update docs/components.md (if exists) with new structure

## Component Library

### Agent Components

Located in `flock.components.agent`:

- `OutputUtilityComponent` - Adds metadata to outputs
- `MetricsComponent` - Tracks execution metrics
- `ValidationComponent` - Validates inputs/outputs

### Orchestrator Components

Located in `flock.components.orchestrator`:

- `CircuitBreakerComponent` - Prevents runaway loops
- `DeduplicationComponent` - Prevents duplicate processing
- `BuiltinCollectionComponent` - AND gates, correlation, batching
```

### Success Criteria

- ✅ Component library structure created
- ✅ All built-in components moved to library
- ✅ All existing tests pass
- ✅ New component tests added
- ✅ Documentation updated

**Estimated Effort:** 10-15 hours

**Files Changed:**
- New: `src/flock/components/agent/*.py` (3-5 files)
- New: `src/flock/components/orchestrator/*.py` (3-5 files)
- Modified: `src/flock/__init__.py`
- Deprecated: `src/flock/orchestrator_component.py`
- New: `tests/components/**/*.py` (6-10 test files)

---

## Phase 3: Orchestrator Modularization

**Objective:** Break orchestrator.py into focused modules

**Why Third?** Orchestrator is central but well-tested. Modularization here has high impact.

### 3.1 Extract Component Runner

**Create orchestrator/component_runner.py:**

```python
# src/flock/orchestrator/component_runner.py
"""Component hook execution with logging and error handling."""

from typing import AsyncGenerator, Any
from flock.core.component import OrchestratorComponent
from flock.logging import get_logger

class ComponentRunner:
    """
    Executes component hooks with standardized error handling.

    Responsibilities:
    - Run hooks in priority order
    - Log execution
    - Handle errors consistently
    - Collect results
    """

    def __init__(self, components: list[OrchestratorComponent]):
        """
        Initialize component runner.

        Args:
            components: List of components (will be sorted by priority)
        """
        self._components = sorted(components, key=lambda c: c.priority)
        self._logger = get_logger(__name__)

    def add_component(self, component: OrchestratorComponent):
        """Add component and re-sort by priority."""
        self._components.append(component)
        self._components.sort(key=lambda c: c.priority)

    async def run_hook(
        self,
        hook_name: str,
        *args: Any,
        **kwargs: Any
    ) -> AsyncGenerator[tuple[OrchestratorComponent, Any], None]:
        """
        Run named hook on all components.

        Args:
            hook_name: Name of hook method (e.g., "on_initialize")
            *args: Positional arguments for hook
            **kwargs: Keyword arguments for hook

        Yields:
            Tuples of (component, result) for each component
        """
        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            # Check if component implements this hook
            if not hasattr(component, hook_name):
                continue

            self._logger.debug(f"Running {hook_name}: component={comp_name}")

            try:
                hook_method = getattr(component, hook_name)
                result = await hook_method(*args, **kwargs)
                yield component, result

            except Exception as e:
                self._logger.exception(
                    f"Component {comp_name} failed in {hook_name}: {e}"
                )
                raise
```

### 3.2 Extract Artifact Manager

```python
# src/flock/orchestrator/artifact_manager.py
"""Artifact publishing and persistence."""

from flock.storage.base import BlackboardStore
from flock.types.artifacts import Artifact
from flock.logging import get_logger

class ArtifactManager:
    """
    Manages artifact publishing and persistence.

    Responsibilities:
    - Persist artifacts to store
    - Trigger scheduling after publish
    - Handle publishing errors
    """

    def __init__(self, store: BlackboardStore, scheduler: "AgentScheduler"):
        """
        Initialize artifact manager.

        Args:
            store: Blackboard store for persistence
            scheduler: Scheduler for triggering agent execution
        """
        self._store = store
        self._scheduler = scheduler
        self._logger = get_logger(__name__)

    async def persist_and_schedule(self, artifact: Artifact):
        """
        Persist artifact and trigger scheduling.

        Args:
            artifact: Artifact to publish
        """
        self._logger.debug(f"Publishing artifact: {artifact.id}")

        # Persist to store
        await self._store.publish(artifact)

        # Trigger scheduling
        await self._scheduler.schedule_artifact(artifact)

    async def publish_outputs(self, agent: "Agent", artifacts: list[Artifact]):
        """
        Publish multiple output artifacts from agent.

        Args:
            agent: Agent that produced outputs
            artifacts: List of output artifacts
        """
        for artifact in artifacts:
            # Add agent metadata
            artifact.metadata["source_agent"] = agent.name

            # Publish
            await self.persist_and_schedule(artifact)
```

### 3.3 Extract Scheduler

```python
# src/flock/orchestrator/scheduler.py
"""Agent scheduling engine."""

import asyncio
from typing import TYPE_CHECKING
from flock.subscriptions.matcher import SubscriptionMatcher
from flock.types.artifacts import Artifact, ScheduleDecision
from flock.logging import get_logger

if TYPE_CHECKING:
    from flock.core.agent import Agent
    from flock.orchestrator.component_runner import ComponentRunner

class AgentScheduler:
    """
    Schedules agents for execution based on artifact subscriptions.

    Responsibilities:
    - Match artifacts to agent subscriptions
    - Run scheduling hooks
    - Create agent execution tasks
    - Manage task lifecycle
    """

    def __init__(self, component_runner: "ComponentRunner"):
        """
        Initialize scheduler.

        Args:
            component_runner: Runner for executing component hooks
        """
        self._agents: dict[str, "Agent"] = {}
        self._components = component_runner
        self._matcher = SubscriptionMatcher()
        self._tasks: set[asyncio.Task] = set()
        self._logger = get_logger(__name__)

    def register_agent(self, agent: "Agent"):
        """Register agent for scheduling."""
        self._agents[agent.name] = agent
        self._logger.info(f"Registered agent: {agent.name}")

    async def schedule_artifact(self, artifact: Artifact):
        """
        Schedule agents based on artifact.

        Args:
            artifact: Published artifact to match against subscriptions
        """
        # Find matching agent/subscription pairs
        matches = self._matcher.find_matches(artifact, self._agents.values())

        for agent, subscription in matches:
            await self._schedule_agent(artifact, agent, subscription)

    async def _schedule_agent(
        self,
        artifact: Artifact,
        agent: "Agent",
        subscription: "Subscription"
    ):
        """Schedule single agent execution."""

        # Run before_schedule hooks
        decision = await self._run_before_schedule_hooks(artifact, agent, subscription)

        if decision == ScheduleDecision.SKIP:
            self._logger.debug(f"Skipping agent {agent.name} (decision=SKIP)")
            return

        # Collect artifacts (AND gates, correlation, batching)
        collection = await self._run_collection_hooks(artifact, agent, subscription)

        if not collection.ready:
            self._logger.debug(f"Collection not ready for {agent.name}")
            return

        # Create agent execution task
        task = asyncio.create_task(
            agent.execute(collection.artifacts, subscription)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        # Notify components
        await self._run_agent_scheduled_hooks(agent, task)

    async def _run_before_schedule_hooks(self, artifact, agent, subscription):
        """Run on_before_schedule hooks."""
        decision = ScheduleDecision.CONTINUE

        async for component, result in self._components.run_hook(
            "on_before_schedule", artifact, agent, subscription
        ):
            if result == ScheduleDecision.SKIP:
                decision = ScheduleDecision.SKIP
                break
            elif result == ScheduleDecision.DEFER:
                decision = ScheduleDecision.DEFER

        return decision

    # ... more hook methods
```

### 3.4 Extract MCP Manager

```python
# src/flock/orchestrator/mcp_manager.py
"""MCP server lifecycle management."""

from typing import Any
from flock.mcp.integration import MCPIntegration
from flock.logging import get_logger

class MCPManager:
    """
    Manages MCP server lifecycle for orchestrator.

    Responsibilities:
    - Start/stop MCP servers
    - Fetch available tools
    - Manage server configurations
    """

    def __init__(self):
        self._integration = MCPIntegration()
        self._servers: dict[str, Any] = {}
        self._logger = get_logger(__name__)

    async def add_server(self, config: "MCPServerConfig"):
        """
        Add and start MCP server.

        Args:
            config: Server configuration
        """
        self._logger.info(f"Starting MCP server: {config.name}")
        server = await self._integration.start_server(config)
        self._servers[config.name] = server

    async def get_tools(self, agent_name: str) -> list[Any]:
        """
        Get available tools for agent.

        Args:
            agent_name: Name of requesting agent

        Returns:
            List of available MCP tools
        """
        # Fetch tools from all servers
        tools = []
        for server_name, server in self._servers.items():
            server_tools = await self._integration.get_tools(server)
            tools.extend(server_tools)

        return tools

    async def shutdown(self):
        """Shutdown all MCP servers."""
        for server_name, server in self._servers.items():
            self._logger.info(f"Stopping MCP server: {server_name}")
            await self._integration.stop_server(server)

        self._servers.clear()
```

### 3.5 Update Main Orchestrator

```python
# src/flock/orchestrator/orchestrator.py (simplified!)
"""Main orchestrator implementation."""

from flock.storage.base import BlackboardStore
from flock.orchestrator.scheduler import AgentScheduler
from flock.orchestrator.artifact_manager import ArtifactManager
from flock.orchestrator.mcp_manager import MCPManager
from flock.orchestrator.component_runner import ComponentRunner
from flock.logging import get_logger

class Flock:
    """
    Agent orchestration framework.

    Responsibilities:
    - Initialize subsystems
    - Provide public API
    - Coordinate between managers
    """

    def __init__(
        self,
        store: BlackboardStore,
        scheduler: AgentScheduler | None = None,
        default_components: list | None = None
    ):
        """
        Initialize orchestrator.

        Args:
            store: Blackboard store for persistence
            scheduler: Optional custom scheduler (default: AgentScheduler)
            default_components: Built-in components to include
        """
        self._logger = get_logger(__name__)

        # Initialize component runner
        components = default_components or self._get_default_components()
        self._components = ComponentRunner(components)

        # Initialize managers
        self._scheduler = scheduler or AgentScheduler(self._components)
        self._artifacts = ArtifactManager(store, self._scheduler)
        self._mcp = MCPManager()

        self._store = store

    def add_agent(self, agent: "Agent"):
        """Register agent with orchestrator."""
        self._scheduler.register_agent(agent)

    async def publish(self, artifact: "Artifact"):
        """Publish artifact to blackboard."""
        await self._artifacts.persist_and_schedule(artifact)

    def add_component(self, component: "OrchestratorComponent"):
        """Add orchestrator component."""
        self._components.add_component(component)

    async def add_mcp_server(self, config: "MCPServerConfig"):
        """Add MCP server."""
        await self._mcp.add_server(config)

    @staticmethod
    def _get_default_components():
        """Get default built-in components."""
        from flock.components.orchestrator import (
            CircuitBreakerComponent,
            DeduplicationComponent,
            BuiltinCollectionComponent
        )
        return [
            CircuitBreakerComponent(priority=10),
            DeduplicationComponent(priority=20),
            BuiltinCollectionComponent(priority=100)
        ]
```

### 3.6 Update Tests

```python
# tests/orchestrator/test_component_runner.py
@pytest.mark.asyncio
async def test_component_runner_executes_hooks_in_priority_order():
    """Component runner executes hooks in priority order."""
    results = []

    class TestComponent(OrchestratorComponent):
        def __init__(self, priority, name):
            super().__init__(priority=priority)
            self.name = name

        async def on_initialize(self, orch):
            results.append(self.name)

    runner = ComponentRunner([
        TestComponent(priority=30, name="third"),
        TestComponent(priority=10, name="first"),
        TestComponent(priority=20, name="second")
    ])

    async for _, _ in runner.run_hook("on_initialize", None):
        pass

    assert results == ["first", "second", "third"]


# tests/orchestrator/test_artifact_manager.py
@pytest.mark.asyncio
async def test_artifact_manager_persists_and_schedules():
    """Artifact manager persists then triggers scheduling."""
    mock_store = MagicMock()
    mock_scheduler = MagicMock()

    manager = ArtifactManager(mock_store, mock_scheduler)
    artifact = Artifact(...)

    await manager.persist_and_schedule(artifact)

    mock_store.publish.assert_called_once_with(artifact)
    mock_scheduler.schedule_artifact.assert_called_once_with(artifact)
```

### Success Criteria

- ✅ Orchestrator broken into 5 focused modules (<400 LOC each)
- ✅ Component runner eliminates hook execution duplication
- ✅ Clear separation of concerns (scheduling, artifacts, MCP, components)
- ✅ All existing tests pass
- ✅ New unit tests for each module
- ✅ No performance regression

**Estimated Effort:** 12-16 hours

**Files Changed:**
- New: `src/flock/orchestrator/component_runner.py`
- New: `src/flock/orchestrator/artifact_manager.py`
- New: `src/flock/orchestrator/scheduler.py`
- New: `src/flock/orchestrator/mcp_manager.py`
- Modified: `src/flock/orchestrator/orchestrator.py` (simplified from 1,746 → ~400 LOC)
- New: `tests/orchestrator/test_*.py` (4 test files)

---

## Phase 4: Agent Modularization

**Objective:** Break agent.py into focused modules

**Why Fourth?** Agent is complex but can now leverage orchestrator refactoring patterns.

### 4.1 Extract Lifecycle Manager

```python
# src/flock/agent/lifecycle.py
"""Agent lifecycle management."""

from flock.core.component import AgentComponent
from flock.logging import get_logger

class AgentLifecycle:
    """
    Manages agent execution lifecycle.

    Responsibilities:
    - Execute lifecycle hooks in correct order
    - Handle errors at each stage
    - Coordinate utilities (AgentComponents)
    """

    def __init__(self, utilities: list[AgentComponent]):
        """
        Initialize lifecycle manager.

        Args:
            utilities: List of agent components (sorted by priority)
        """
        self._utilities = sorted(utilities, key=lambda u: u.priority)
        self._logger = get_logger(__name__)

    async def run_initialize(self, agent, ctx):
        """Run on_initialize hooks."""
        for utility in self._utilities:
            await utility.on_initialize(agent, ctx)

    async def run_pre_consume(self, agent, ctx, inputs):
        """Run on_pre_consume hooks."""
        for utility in self._utilities:
            inputs = await utility.on_pre_consume(agent, ctx, inputs)
        return inputs

    async def run_pre_evaluate(self, agent, ctx, inputs):
        """Run on_pre_evaluate hooks."""
        for utility in self._utilities:
            inputs = await utility.on_pre_evaluate(agent, ctx, inputs)
        return inputs

    async def run_post_evaluate(self, agent, ctx, outputs, output_group):
        """Run on_post_evaluate hooks."""
        for utility in self._utilities:
            outputs = await utility.on_post_evaluate(agent, ctx, outputs, output_group)
        return outputs

    async def run_post_publish(self, agent, ctx, artifact):
        """Run on_post_publish hooks."""
        for utility in self._utilities:
            await utility.on_post_publish(agent, ctx, artifact)

    async def run_terminate(self, agent, ctx):
        """Run on_terminate hooks."""
        for utility in self._utilities:
            await utility.on_terminate(agent, ctx)

    async def run_error(self, agent, ctx, error):
        """Run on_error hooks."""
        for utility in self._utilities:
            await utility.on_error(agent, ctx, error)
```

### 4.2 Extract Output Processor

```python
# src/flock/agent/output_processor.py
"""Output validation and processing."""

from flock.types.artifacts import Artifact, OutputGroup
from flock.utils.validation import ArtifactValidator
from flock.logging import get_logger

class OutputProcessor:
    """
    Validates and processes agent outputs.

    Responsibilities:
    - Validate outputs against output group specs
    - Apply visibility controls
    - Filter invalid outputs
    - Build published artifacts
    """

    def __init__(self):
        self._logger = get_logger(__name__)
        self._validator = ArtifactValidator()

    async def process_outputs(
        self,
        agent: "Agent",
        outputs: list[Any],
        output_group: OutputGroup
    ) -> list[Artifact]:
        """
        Process raw outputs into artifacts.

        Args:
            agent: Agent that produced outputs
            outputs: Raw output data
            output_group: Output group specification

        Returns:
            List of validated artifacts ready to publish
        """
        artifacts = []

        for output_spec in output_group.outputs:
            # Validate output
            is_valid, model, error = self._validator.validate_artifact(
                output,
                output_spec.model_cls,
                output_spec.predicate
            )

            if not is_valid:
                self._logger.warning(
                    f"Invalid output from {agent.name}: {error}"
                )
                continue

            # Build artifact
            artifact = Artifact(
                type=output_spec.type,
                payload=model.dict(),
                visibility=output_spec.visibility,
                metadata={
                    "agent": agent.name,
                    "output_group": output_group.name
                }
            )

            artifacts.append(artifact)

        return artifacts
```

### 4.3 Extract Context Resolver

```python
# src/flock/agent/context_resolver.py
"""Context provider resolution."""

from flock.context.base import BaseContextProvider
from flock.types.artifacts import Artifact
from flock.logging import get_logger

class ContextResolver:
    """
    Resolves context providers for agent execution.

    Responsibilities:
    - Determine which context provider to use
    - Fetch artifacts via provider
    - Build execution context
    """

    def __init__(self, default_provider: BaseContextProvider | None = None):
        """
        Initialize context resolver.

        Args:
            default_provider: Default context provider (if none specified)
        """
        self._default_provider = default_provider
        self._logger = get_logger(__name__)

    async def resolve_context(
        self,
        agent: "Agent",
        subscription: "Subscription",
        trigger_artifacts: list[Artifact]
    ) -> "AgentContext":
        """
        Resolve context for agent execution.

        Args:
            agent: Agent being executed
            subscription: Subscription that triggered execution
            trigger_artifacts: Artifacts that triggered execution

        Returns:
            Resolved agent context
        """
        # Determine provider
        provider = agent.context_provider or self._default_provider

        if provider is None:
            self._logger.warning(f"No context provider for {agent.name}")
            artifacts = trigger_artifacts
        else:
            # Fetch context artifacts
            request = self._build_context_request(
                agent, subscription, trigger_artifacts
            )
            artifacts = await provider.get_artifacts(request)

        # Build context
        return AgentContext(
            agent=agent,
            subscription=subscription,
            trigger_artifacts=trigger_artifacts,
            artifacts=artifacts
        )
```

### 4.4 Simplify Main Agent

```python
# src/flock/agent/agent.py (simplified!)
"""Agent implementation."""

from flock.agent.lifecycle import AgentLifecycle
from flock.agent.output_processor import OutputProcessor
from flock.agent.context_resolver import ContextResolver
from flock.core.engine import EngineComponent
from flock.logging import get_logger

class Agent:
    """
    Autonomous processing unit.

    Responsibilities:
    - Coordinate execution flow
    - Delegate to specialized managers
    - Provide public API
    """

    def __init__(
        self,
        name: str,
        subscriptions: list["Subscription"],
        output_groups: list["OutputGroup"],
        engines: list[EngineComponent],
        utilities: list[AgentComponent] | None = None,
        context_provider: BaseContextProvider | None = None
    ):
        """Initialize agent."""
        self.name = name
        self.subscriptions = subscriptions
        self.output_groups = output_groups
        self.engines = engines
        self.context_provider = context_provider

        # Initialize managers
        self._lifecycle = AgentLifecycle(utilities or [])
        self._output_processor = OutputProcessor()
        self._context_resolver = ContextResolver()

        self._logger = get_logger(__name__)

    async def execute(
        self,
        artifacts: list[Artifact],
        subscription: "Subscription"
    ) -> list[Artifact]:
        """
        Execute agent on artifacts.

        Args:
            artifacts: Trigger artifacts
            subscription: Matching subscription

        Returns:
            List of output artifacts to publish
        """
        # Resolve context
        ctx = await self._context_resolver.resolve_context(
            self, subscription, artifacts
        )

        # Run lifecycle
        await self._lifecycle.run_initialize(self, ctx)

        try:
            # Pre-consume
            inputs = await self._lifecycle.run_pre_consume(self, ctx, artifacts)

            # Execute engines for each output group
            all_outputs = []
            for output_group in self.output_groups:
                # Pre-evaluate
                inputs = await self._lifecycle.run_pre_evaluate(self, ctx, inputs)

                # Evaluate
                for engine in self.engines:
                    result = await engine.evaluate(self, ctx, inputs, output_group)
                    outputs = result.outputs

                # Post-evaluate
                outputs = await self._lifecycle.run_post_evaluate(
                    self, ctx, outputs, output_group
                )

                # Process outputs
                artifacts = await self._output_processor.process_outputs(
                    self, outputs, output_group
                )

                all_outputs.extend(artifacts)

            return all_outputs

        except Exception as e:
            await self._lifecycle.run_error(self, ctx, e)
            raise

        finally:
            await self._lifecycle.run_terminate(self, ctx)
```

### 4.5 Update Tests

```python
# tests/agent/test_lifecycle.py
@pytest.mark.asyncio
async def test_lifecycle_runs_hooks_in_order():
    """Lifecycle runs hooks in correct order."""
    order = []

    class TestUtility(AgentComponent):
        async def on_initialize(self, agent, ctx):
            order.append("initialize")

        async def on_pre_consume(self, agent, ctx, inputs):
            order.append("pre_consume")
            return inputs

    lifecycle = AgentLifecycle([TestUtility()])

    await lifecycle.run_initialize(agent, ctx)
    await lifecycle.run_pre_consume(agent, ctx, inputs)

    assert order == ["initialize", "pre_consume"]


# tests/agent/test_output_processor.py
@pytest.mark.asyncio
async def test_output_processor_validates_outputs():
    """Output processor validates against output specs."""
    processor = OutputProcessor()

    # Invalid output (missing required field)
    outputs = [{"incomplete": "data"}]
    output_group = OutputGroup(
        outputs=[OutputSpec(type="MyType", model_cls=MyModel)]
    )

    artifacts = await processor.process_outputs(agent, outputs, output_group)

    # Should filter out invalid
    assert len(artifacts) == 0
```

### Success Criteria

- ✅ Agent broken into 4 focused modules (<400 LOC each)
- ✅ Clear separation of concerns (lifecycle, outputs, context)
- ✅ Lifecycle manager eliminates hook execution duplication
- ✅ All existing tests pass
- ✅ New unit tests for each module
- ✅ No performance regression

**Estimated Effort:** 10-14 hours

**Files Changed:**
- New: `src/flock/agent/lifecycle.py`
- New: `src/flock/agent/output_processor.py`
- New: `src/flock/agent/context_resolver.py`
- Modified: `src/flock/agent/agent.py` (simplified from 1,578 → ~400 LOC)
- New: `tests/agent/test_*.py` (3 test files)

---

## Phase 5: Engine Refactoring

**Objective:** Modularize DSPy engine into focused components

**Why Fifth?** Engine is well-isolated and can now leverage agent patterns.

### 5.1 Extract Signature Builder

```python
# src/flock/engines/dspy/signature_builder.py
"""DSPy signature building from output specs."""

from typing import Any
import dspy
from flock.types.artifacts import OutputGroup
from flock.logging import get_logger

class DSPySignatureBuilder:
    """
    Builds DSPy signatures from output group specifications.

    Responsibilities:
    - Convert output specs to DSPy fields
    - Handle semantic field naming
    - Detect collisions
    - Support batching/fan-out
    """

    def __init__(self):
        self._logger = get_logger(__name__)

    def build_signature(
        self,
        output_group: OutputGroup,
        is_batch: bool = False,
        fan_out: int = 1
    ) -> type[dspy.Signature]:
        """
        Build DSPy signature from output group.

        Args:
            output_group: Output group specification
            is_batch: Whether this is batch mode
            fan_out: Number of outputs per input

        Returns:
            DSPy Signature class
        """
        fields = {}

        for output_spec in output_group.outputs:
            field_name = self._build_field_name(output_spec)
            field_type = self._build_field_type(
                output_spec, is_batch, fan_out
            )
            fields[field_name] = field_type

        # Create signature class
        signature_cls = type(
            f"{output_group.name}Signature",
            (dspy.Signature,),
            fields
        )

        return signature_cls

    def _build_field_name(self, output_spec) -> str:
        """Build field name from output spec."""
        # Handle semantic naming (Field → Type mapping)
        if output_spec.semantic_name:
            return output_spec.semantic_name
        return output_spec.type.lower()

    def _build_field_type(self, output_spec, is_batch, fan_out):
        """Build field type with proper annotations."""
        base_type = output_spec.model_cls

        # Apply fan-out
        if fan_out > 1:
            base_type = list[base_type]

        # Apply batching
        if is_batch:
            base_type = list[base_type]

        return dspy.OutputField(
            desc=output_spec.description or "",
            type=base_type
        )
```

### 5.2 Extract Streaming Executor

```python
# src/flock/engines/dspy/streaming_executor.py
"""DSPy program streaming execution."""

import asyncio
from typing import AsyncGenerator, Any
import dspy
from flock.logging import get_logger

class DSPyStreamingExecutor:
    """
    Executes DSPy programs with streaming support.

    Responsibilities:
    - Execute DSPy programs
    - Stream outputs (CLI vs WebSocket modes)
    - Handle errors during execution
    """

    def __init__(self, stream_mode: str = "cli"):
        """
        Initialize streaming executor.

        Args:
            stream_mode: Streaming mode ("cli" or "websocket")
        """
        self.stream_mode = stream_mode
        self._logger = get_logger(__name__)

    async def execute_streaming(
        self,
        program: dspy.Program,
        inputs: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute program with streaming.

        Args:
            program: DSPy program to execute
            inputs: Input dictionary

        Yields:
            Streaming outputs
        """
        if self.stream_mode == "cli":
            async for output in self._stream_cli(program, inputs):
                yield output
        elif self.stream_mode == "websocket":
            async for output in self._stream_websocket(program, inputs):
                yield output
        else:
            # Non-streaming fallback
            result = await self._execute_sync(program, inputs)
            yield result

    async def _stream_cli(self, program, inputs):
        """Stream with CLI formatting."""
        # ... CLI-specific streaming logic
        pass

    async def _stream_websocket(self, program, inputs):
        """Stream with WebSocket formatting."""
        # ... WebSocket-specific streaming logic
        pass

    async def _execute_sync(self, program, inputs):
        """Execute without streaming."""
        return await asyncio.to_thread(program, **inputs)
```

### 5.3 Extract Artifact Materializer

```python
# src/flock/engines/dspy/artifact_materializer.py
"""Materializes DSPy predictions into artifacts."""

from typing import Any
from flock.types.artifacts import Artifact
from flock.logging import get_logger

class DSPyArtifactMaterializer:
    """
    Materializes DSPy predictions into artifacts.

    Responsibilities:
    - Parse DSPy prediction objects
    - Extract typed payloads
    - Handle batching/fan-out
    - Build artifact metadata
    """

    def __init__(self):
        self._logger = get_logger(__name__)

    def materialize(
        self,
        prediction: Any,
        output_spec: "OutputSpec",
        is_batch: bool = False
    ) -> list[Artifact]:
        """
        Materialize prediction into artifacts.

        Args:
            prediction: DSPy prediction object
            output_spec: Output specification
            is_batch: Whether this is batch mode

        Returns:
            List of materialized artifacts
        """
        # Extract payload
        payload = self._extract_payload(prediction, output_spec)

        # Handle batching
        if is_batch:
            return self._materialize_batch(payload, output_spec)
        else:
            return [self._materialize_single(payload, output_spec)]

    def _extract_payload(self, prediction, output_spec) -> dict:
        """Extract payload from DSPy prediction."""
        # Parse prediction to dict
        if hasattr(prediction, "dict"):
            return prediction.dict()
        elif isinstance(prediction, dict):
            return prediction
        else:
            return {"value": prediction}

    def _materialize_single(self, payload, output_spec) -> Artifact:
        """Materialize single artifact."""
        return Artifact(
            type=output_spec.type,
            payload=payload,
            visibility=output_spec.visibility,
            metadata={"engine": "dspy"}
        )

    def _materialize_batch(self, payloads, output_spec) -> list[Artifact]:
        """Materialize batch of artifacts."""
        return [
            self._materialize_single(payload, output_spec)
            for payload in payloads
        ]
```

### 5.4 Simplify Main Engine

```python
# src/flock/engines/dspy/engine.py (simplified!)
"""DSPy engine implementation."""

import dspy
from flock.core.engine import EngineComponent
from flock.engines.dspy.signature_builder import DSPySignatureBuilder
from flock.engines.dspy.streaming_executor import DSPyStreamingExecutor
from flock.engines.dspy.artifact_materializer import DSPyArtifactMaterializer
from flock.logging import get_logger

class DSPyEngine(EngineComponent):
    """
    DSPy-based LLM engine.

    Responsibilities:
    - Configure DSPy settings
    - Coordinate signature building, execution, materialization
    - Auto-detect batching/fan-out
    """

    def __init__(
        self,
        lm: dspy.LM,
        program: dspy.Program | None = None,
        stream: bool = False
    ):
        """
        Initialize DSPy engine.

        Args:
            lm: DSPy language model
            program: Optional custom DSPy program
            stream: Enable streaming
        """
        self.lm = lm
        self.program = program
        self.stream = stream

        # Initialize subsystems
        self._signature_builder = DSPySignatureBuilder()
        self._executor = DSPyStreamingExecutor()
        self._materializer = DSPyArtifactMaterializer()

        self._logger = get_logger(__name__)

        # Configure DSPy
        dspy.configure(lm=lm)

    async def evaluate(self, agent, ctx, inputs, output_group):
        """
        Evaluate inputs to produce outputs.

        Auto-detects:
        - Batching from ctx.is_batch
        - Fan-out from output_group.outputs[*].count
        - Multi-output from len(output_group.outputs)
        """
        # Auto-detection
        is_batch = ctx.is_batch
        fan_out = output_group.outputs[0].count if output_group.outputs else 1

        # Build signature
        signature = self._signature_builder.build_signature(
            output_group, is_batch, fan_out
        )

        # Choose program
        program = self.program or dspy.Predict(signature)

        # Execute
        if self.stream:
            prediction = await self._executor.execute_streaming(program, inputs)
        else:
            prediction = program(**inputs)

        # Materialize artifacts
        artifacts = []
        for output_spec in output_group.outputs:
            output_artifacts = self._materializer.materialize(
                prediction, output_spec, is_batch
            )
            artifacts.extend(output_artifacts)

        return EvalResult(outputs=artifacts)
```

### Success Criteria

- ✅ DSPy engine broken into 4 focused modules (~400 LOC each)
- ✅ Clear separation: signature building, execution, materialization
- ✅ Main engine simplified from 1,797 → ~400 LOC
- ✅ All existing tests pass
- ✅ New unit tests for each module
- ✅ No performance regression

**Estimated Effort:** 8-12 hours

**Files Changed:**
- New: `src/flock/engines/dspy/signature_builder.py`
- New: `src/flock/engines/dspy/streaming_executor.py`
- New: `src/flock/engines/dspy/artifact_materializer.py`
- Modified: `src/flock/engines/dspy/engine.py` (simplified from 1,797 → ~400 LOC)
- New: `tests/engines/dspy/test_*.py` (3 test files)

---

## Phase 6: Storage & Context

**Objective:** Modularize storage layer and context providers

**Why Sixth?** Storage and context are foundational but less urgent than core orchestration.

### 6.1 Extract Query Builder

```python
# src/flock/storage/sqlite/query_builder.py
"""SQL query building utilities."""

from flock.types.artifacts import FilterConfig
from flock.logging import get_logger

class SQLiteQueryBuilder:
    """
    Builds SQL queries with proper escaping.

    Responsibilities:
    - Build SELECT queries from filters
    - Handle WHERE clauses safely
    - Prevent SQL injection
    """

    def __init__(self):
        self._logger = get_logger(__name__)

    def build_query(self, filters: FilterConfig) -> tuple[str, list]:
        """
        Build SQL query from filters.

        Args:
            filters: Filter configuration

        Returns:
            Tuple of (sql_string, parameters)
        """
        query = "SELECT * FROM artifacts"
        params = []
        where_clauses = []

        # Type filter
        if filters.types:
            placeholders = ",".join("?" * len(filters.types))
            where_clauses.append(f"type IN ({placeholders})")
            params.extend(filters.types)

        # Tag filter
        if filters.tags:
            for key, value in filters.tags.items():
                where_clauses.append("json_extract(tags, ?) = ?")
                params.extend([f"$.{key}", value])

        # Visibility filter
        if filters.visibility:
            vis_clause, vis_params = self._build_visibility_clause(
                filters.visibility
            )
            where_clauses.append(vis_clause)
            params.extend(vis_params)

        # Combine clauses
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Ordering and limits
        query += " ORDER BY created_at DESC"
        query += f" LIMIT ? OFFSET ?"
        params.extend([filters.limit, filters.offset])

        return query, params

    def _build_visibility_clause(self, visibility) -> tuple[str, list]:
        """Build WHERE clause for visibility."""
        # ... visibility-specific SQL logic
        pass
```

### 6.2 Simplify SQLite Store

```python
# src/flock/storage/sqlite/store.py (simplified!)
"""SQLite blackboard store."""

from flock.storage.base import BlackboardStore
from flock.storage.sqlite.query_builder import SQLiteQueryBuilder
from flock.storage.sqlite.schema import SchemaManager
from flock.logging import get_logger

class SQLiteStore(BlackboardStore):
    """
    SQLite-based blackboard storage.

    Responsibilities:
    - Manage SQLite connection
    - Delegate query building
    - Handle transactions
    """

    def __init__(self, db_path: str):
        """Initialize SQLite store."""
        self.db_path = db_path
        self._conn = None
        self._query_builder = SQLiteQueryBuilder()
        self._schema_manager = SchemaManager()
        self._logger = get_logger(__name__)

    async def initialize(self):
        """Initialize database schema."""
        self._conn = await aiosqlite.connect(self.db_path)
        await self._schema_manager.create_tables(self._conn)

    async def publish(self, artifact: Artifact):
        """Publish artifact to database."""
        query = """
        INSERT INTO artifacts (id, type, payload, visibility, created_at)
        VALUES (?, ?, ?, ?, ?)
        """
        params = [
            artifact.id,
            artifact.type,
            json.dumps(artifact.payload),
            json.dumps(artifact.visibility.dict()),
            artifact.created_at.isoformat()
        ]

        await self._conn.execute(query, params)
        await self._conn.commit()

    async def query_artifacts(self, filters: FilterConfig):
        """Query artifacts with filters."""
        # Delegate to query builder
        query, params = self._query_builder.build_query(filters)

        # Execute query
        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()

        # Deserialize
        artifacts = [self._row_to_artifact(row) for row in rows]
        return artifacts
```

### Success Criteria

- ✅ SQLite store simplified from 1,233 → ~400 LOC
- ✅ Query builder extracted for reusability and testing
- ✅ Schema management separated
- ✅ All existing tests pass
- ✅ New unit tests for query builder
- ✅ No performance regression

**Estimated Effort:** 6-10 hours

**Files Changed:**
- New: `src/flock/storage/sqlite/query_builder.py`
- New: `src/flock/storage/sqlite/schema.py`
- Modified: `src/flock/storage/sqlite/store.py` (simplified from 1,233 → ~400 LOC)
- New: `tests/storage/sqlite/test_query_builder.py`

---

## Phase 7: Dashboard & Polish

**Objective:** Clean up dashboard, remove dead code, final polish

**Why Last?** Dashboard is less critical; polish after core refactoring complete.

### 7.1 Extract API Routes

```python
# src/flock/dashboard/routes/control.py
"""Control API endpoints."""

from fastapi import APIRouter
from flock.logging import get_logger

router = APIRouter(prefix="/api/control")

@router.post("/start")
async def start_orchestrator():
    """Start orchestrator."""
    # ... implementation

@router.post("/stop")
async def stop_orchestrator():
    """Stop orchestrator."""
    # ... implementation


# src/flock/dashboard/routes/traces.py
"""Trace API endpoints."""

from fastapi import APIRouter
from flock.logging import get_logger

router = APIRouter(prefix="/api/traces")

@router.get("/{trace_id}")
async def get_trace(trace_id: str):
    """Get trace by ID."""
    # ... implementation


# src/flock/dashboard/routes/websocket.py
"""WebSocket streaming endpoint."""

from fastapi import APIRouter, WebSocket
from flock.logging import get_logger

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    # ... implementation
```

### 7.2 Simplify Dashboard Service

```python
# src/flock/dashboard/service.py (simplified!)
"""Dashboard FastAPI service."""

from fastapi import FastAPI
from flock.dashboard.routes import control, traces, themes, websocket
from flock.logging import get_logger

def create_dashboard_app(orchestrator: "Flock") -> FastAPI:
    """
    Create FastAPI dashboard application.

    Args:
        orchestrator: Flock orchestrator instance

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(title="Flock Dashboard")

    # Include routers
    app.include_router(control.router)
    app.include_router(traces.router)
    app.include_router(themes.router)
    app.include_router(websocket.router)

    # Store orchestrator reference
    app.state.orchestrator = orchestrator

    return app
```

### 7.3 Remove Dead Code

**Target locations:**
- `src/flock/logging/logging.py` - Remove commented-out workflow detection
- `src/flock/orchestrator.py` - Remove unused `_patch_litellm_proxy_imports()`
- `src/flock/agent.py` - Remove unused exception handlers
- All `# pragma: no cover` that should be covered

**Process:**
```python
# BEFORE (logging/logging.py, lines 44-51)
# def _detect_temporal_workflow():
#     try:
#         from temporalio import workflow
#         if workflow.in_workflow():
#             return workflow.logger()
#     except Exception:
#         pass
#     return None

# AFTER
# Completely removed - no longer needed
```

### 7.4 Standardize Patterns

**Error Handling:**
```python
# Create error handling guide in docs/patterns/error_handling.md

## Error Handling Patterns

### Pattern 1: Specific Exception Types
```python
try:
    result = operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
except KeyError as e:
    logger.error(f"Missing key: {e}")
    raise
```

### Pattern 2: Error Context
```python
try:
    result = operation()
except Exception as e:
    logger.exception("Operation failed", extra={
        "operation": "operation_name",
        "input": input_data
    })
    raise OperationError("Failed") from e
```

### Anti-Pattern: Broad Exception Swallow
```python
# DON'T DO THIS
try:
    result = operation()
except Exception:
    pass  # Silent failure - NEVER DO THIS
```
```

**Async Patterns:**
```python
# Create async patterns guide in docs/patterns/async_patterns.md

## Async Patterns

### Pattern 1: Sequential Operations
```python
# Use when operations depend on each other
result1 = await operation1()
result2 = await operation2(result1)
result3 = await operation3(result2)
```

### Pattern 2: Parallel Operations
```python
# Use when operations are independent
results = await asyncio.gather(
    operation1(),
    operation2(),
    operation3()
)
```

### Pattern 3: Fire-and-Forget
```python
# Use for background tasks
task = asyncio.create_task(background_operation())
# Don't await - let it run in background
```
```

### 7.5 Update All Documentation

**Create/Update:**
- `docs/architecture.md` - High-level architecture overview
- `docs/contributing.md` - Contribution guidelines
- `docs/patterns/` - Common patterns and anti-patterns
- `docs/migration.md` - Migration guide for API changes
- `README.md` - Update with new import paths

### Success Criteria

- ✅ Dashboard simplified from 1,411 → ~200 LOC (main file)
- ✅ All dead code removed
- ✅ Pattern documentation complete
- ✅ All documentation updated
- ✅ Migration guide complete
- ✅ All existing tests pass
- ✅ Final code quality checks pass (ruff, mypy)

**Estimated Effort:** 6-10 hours

**Files Changed:**
- New: `src/flock/dashboard/routes/*.py` (4 files)
- Modified: `src/flock/dashboard/service.py` (simplified from 1,411 → ~200 LOC)
- Modified: Remove dead code from multiple files
- New: `docs/patterns/*.md` (3-5 docs)
- Modified: `README.md`, `docs/*.md`

---

## Phase Completion Checklist

After **each phase**, verify:

### Code Quality

```bash
# Linting
ruff check src/

# Type checking
mypy src/

# Tests
pytest tests/ --cov=src/flock --cov-report=html

# Coverage maintained
# (Compare to baseline)
```

### Performance

```bash
# Run benchmarks
pytest tests/benchmarks/ -v

# Compare to baseline
# Max regression: 10%
```

### Documentation

- [ ] All new modules have docstrings
- [ ] All public methods documented
- [ ] DESIGN.md updated with phase completion
- [ ] PROGRESS.md updated

### Tests

- [ ] All existing tests pass
- [ ] New unit tests for extracted modules
- [ ] Integration tests still pass
- [ ] Test coverage maintained or improved

### Git Hygiene

```bash
# Commit changes
git add -A
git commit -m "feat: Phase X - <phase_name>

- Extracted <module> from <original>
- Created <new_modules>
- All tests pass
- No performance regression

Refs: #refactor-phase-X"

# Push to branch
git push origin refactor/phase-X
```

---

## Risk Mitigation

### If Tests Fail

1. **Stop immediately** - Don't continue to next phase
2. **Identify failing tests** - Run `pytest -v --tb=short`
3. **Debug systematically:**
   - Check recent changes
   - Review test expectations
   - Verify behavior preservation
4. **Fix or rollback** - Either fix the issue or `git revert`
5. **Re-validate** - Ensure all tests pass before continuing

### If Performance Regresses

1. **Profile the regression** - Use `cProfile` or `py-spy`
2. **Identify bottleneck** - Compare before/after
3. **Optimize or rollback:**
   - If fixable quickly (<2 hours), optimize
   - If complex, rollback and reconsider approach
4. **Re-benchmark** - Ensure performance restored

### If Scope Grows

1. **Pause and assess** - Don't let phase balloon
2. **Create follow-up ticket** - Move new work to future phase
3. **Focus on phase objectives** - Strict boundaries
4. **Time-box** - If phase exceeds estimate by 50%, stop and replan

---

## Post-Refactor Validation

After **all phases complete**, perform comprehensive validation:

### 1. Full Test Suite

```bash
# Run everything
pytest tests/ --cov=src/flock --cov-report=html --cov-report=term

# Verify coverage
# Target: ≥ baseline coverage
```

### 2. Integration Tests

```bash
# Run integration test suite
pytest tests/integration/ -v

# Verify end-to-end workflows
```

### 3. Performance Benchmarks

```bash
# Run full benchmark suite
pytest tests/benchmarks/ -v --benchmark-compare=baseline

# Verify no regression >10%
```

### 4. Code Quality Metrics

```bash
# Linting
ruff check src/ --statistics

# Type checking
mypy src/ --show-error-codes

# Complexity analysis
radon cc src/ -a -nb

# Maintainability index
radon mi src/ -n B
```

### 5. Documentation Review

- [ ] All modules documented
- [ ] Architecture docs accurate
- [ ] Migration guide complete
- [ ] Examples updated
- [ ] README.md reflects new structure

### 6. Success Metrics

Compare against targets from DESIGN.md:

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Large classes (>1000 LOC) | 0 | ? | ✅/❌ |
| Code duplication patterns | <3 | ? | ✅/❌ |
| Nested conditionals (5+) | 0 | ? | ✅/❌ |
| Test coverage | ≥Baseline | ? | ✅/❌ |
| Performance regression | <10% | ? | ✅/❌ |

---

## Timeline Summary

**Conservative Estimate:**
- Week 1: Phase 1 (Foundation)
- Week 2: Phase 2 (Components)
- Week 3: Phase 3 (Orchestrator)
- Week 4: Phase 4 (Agent)
- Week 5: Phase 5 (Engine)
- Week 6: Phase 6 (Storage)
- Week 7: Phase 7 (Dashboard)

**Aggressive Estimate:**
- Weeks 1-2: Phases 1-2
- Weeks 3-4: Phases 3-4
- Week 5: Phase 5
- Week 6: Phases 6-7

**Reality:**
- Plan for conservative timeline
- Budget 20% buffer for unexpected issues
- Can parallelize some work (e.g., Phase 5 & 6)

---

## Next Steps

1. **Get Approval** - Review DESIGN.md and IMPLEMENTATION_PLAN.md
2. **Setup Environment** - Create branches, establish baselines (Phase 0)
3. **Start Phase 1** - Begin with foundation & utilities
4. **Iterate** - Complete one phase at a time
5. **Celebrate** - Each phase completion is a win! 🎉

---

## Appendix: Quick Reference

### Phase Dependencies

```
Phase 0 (Prep) → Phase 1 (Foundation)
                      ↓
                 Phase 2 (Components)
                      ↓
         ┌────────────┴────────────┐
         ↓                         ↓
    Phase 3 (Orchestrator)    Phase 4 (Agent)
         ↓                         ↓
    Phase 5 (Engine)          Phase 6 (Storage)
         └────────────┬────────────┘
                      ↓
                 Phase 7 (Polish)
```

### Command Cheat Sheet

```bash
# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src/flock --cov-report=html

# Run specific test file
pytest tests/utils/test_type_resolution.py -v

# Run linting
ruff check src/

# Run type checking
mypy src/

# Run benchmarks
pytest tests/benchmarks/ -v

# Format code
ruff format src/

# Git workflow
git checkout -b refactor/phase-X
git add -A
git commit -m "feat: Phase X - ..."
git push origin refactor/phase-X
```

---

**Document Status:** READY FOR EXECUTION
**Next:** Begin Phase 0 preparation, then Phase 1 implementation

**Let's build the most beautiful Flock possible! 🚀**
