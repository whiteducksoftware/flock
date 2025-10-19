# Flock Framework Refactor Design Document

**Version:** 1.0
**Date:** 2025-10-17
**Status:** DRAFT
**Goal:** Transform Flock into the most beautiful, maintainable, and well-architected agent orchestration framework possible

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

---

## Executive Summary

This document outlines a comprehensive refactoring strategy for the Flock framework. The refactoring will modernize the codebase architecture, improve maintainability, and leverage the existing component system (AgentComponent/OrchestratorComponent) more extensively while maintaining 100% behavioral compatibility.

**Key Principles:**
- ✅ **Breaking changes allowed** - API changes are acceptable since the framework isn't released
- ❌ **No regressions allowed** - All features must continue working
- 📦 **Phased approach** - Each phase is self-contained and leaves the framework functional
- 🏗️ **Component-first design** - Leverage AgentComponent/OrchestratorComponent extensively
- 🎯 **Clear organization** - Logical project structure with consistent patterns

---

## Current State Analysis

### Architecture Overview

Flock is a **blackboard-based agent orchestration framework** with:

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                          │
│  (User agents, workflows, business logic)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    ORCHESTRATOR (Flock)                          │
│  • Agent registration & lifecycle                               │
│  • Artifact publishing & scheduling                             │
│  • Component hook execution (plugin system)                      │
│  • Context provider resolution                                  │
│  • MCP server management                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼────────┐  ┌──────▼─────────┐
│   COMPONENTS   │  │   AGENTS      │  │  STORAGE       │
│                │  │               │  │                │
│ • Built-in:   │  │ • Utilities    │  │ • Artifacts    │
│   - Circuit   │  │   (lifecycle) │  │ • Consumptions │
│     Breaker   │  │               │  │ • Snapshots    │
│   - Dedupe    │  │ • Engines      │  │                │
│   - Collection│  │   (evaluation) │  │ Backends:      │
│               │  │               │  │ • In-memory    │
│ • Custom:     │  │ • Subscriptions│  │ • SQLite       │
│   - Metrics   │  │   (triggers)  │  │                │
│   - Rate limit│  │               │  │                │
│   - Caching   │  │ • Outputs      │  │                │
│               │  │   (publish)   │  │                │
└──────────────┘  └───────────────┘  └────────────────┘
```

### Core Abstractions

1. **Agent** - Autonomous processing unit with lifecycle hooks
2. **AgentComponent** - Lifecycle interceptor for agent execution (utilities)
3. **EngineComponent** - Evaluation strategy for processing inputs → outputs
4. **OrchestratorComponent** - System-wide orchestration hooks
5. **Flock (Orchestrator)** - Central coordination hub
6. **BlackboardStore** - Artifact persistence layer
7. **ContextProvider** - Security boundary for artifact access

### Strengths

✅ **Clear separation of concerns** - Well-defined boundaries between layers
✅ **Extensible plugin architecture** - Component system is powerful
✅ **Security by design** - Context providers as security boundaries
✅ **Type safety** - Pydantic models throughout
✅ **Sophisticated scheduling** - AND gates, correlation, batching

### Critical Issues

#### 1. **God Classes** (5 files >1,000 LOC)

| File | Lines | Primary Issue |
|------|-------|---------------|
| `dspy_engine.py` | 1,797 | Monolithic class handling DSPy execution, streaming, formatting, signature building, artifact materialization |
| `orchestrator.py` | 1,746 | Handles agent management, publishing, scheduling, MCP, component lifecycle, batch/correlation |
| `agent.py` | 1,578 | Agent with 40+ methods for execution pipeline, context resolution, output validation, engine coordination |
| `dashboard/service.py` | 1,411 | Monolithic service with 15+ API endpoints inline |
| `store.py` | 1,233 | SQLite store mixing query building, schema management, consumption tracking |

#### 2. **Scattered Component Implementations**

Components are distributed across multiple locations without clear organization:
- Built-in components in `orchestrator_component.py`
- Utilities in `agent.py`
- Custom components mixed with core framework code
- No clear "component library" structure

#### 3. **Code Duplication** (12+ patterns)

- Type resolution logic repeated 8+ times
- Visibility deserialization repeated 5+ times
- Lock acquisition pattern repeated 15+ times
- Component hook execution duplicated 6 times
- Artifact validation pattern repeated 3+ times

#### 4. **Complex Nested Logic**

- 5-level nested conditionals in MCP config parsing
- 4-level nesting in signature field generation
- 7+ nested conditions in subscription matching
- Multiple if/elif chains in filter building

#### 5. **Inconsistent Patterns**

- Error handling: Some explicit, others broad exception swallows
- Async patterns: Mix of create_task(), await, asynccontextmanager
- Configuration: TypedDict vs dataclass vs ABC
- Logging: Inconsistent usage of loggers

#### 6. **Poor Project Structure**

```
Current Structure (Scattered):
src/flock/
├── agent.py                    # 1,578 LOC god class
├── orchestrator.py             # 1,746 LOC god class
├── components.py               # Base classes only
├── orchestrator_component.py   # Built-in components
├── engines/
│   └── dspy_engine.py         # 1,797 LOC god class
├── dashboard/
│   └── service.py             # 1,411 LOC monolith
├── store.py                    # 1,233 LOC
└── ... (scattered utilities)
```

---

## Target State: Beautiful Flock

### Design Principles

1. **Component-First Architecture** - Everything is a component where it makes sense
2. **Bounded Context** - Each module has a single, clear responsibility
3. **Composition Over Inheritance** - Favor small, composable pieces
4. **Explicit Over Implicit** - Clear naming and obvious behavior
5. **Consistency** - Same patterns for same problems throughout
6. **Developer Experience** - Easy to find, understand, and extend code

### Target Project Structure

```
src/flock/
├── core/                       # Core abstractions & interfaces
│   ├── __init__.py
│   ├── agent.py               # Agent interface (<300 LOC)
│   ├── orchestrator.py        # Orchestrator interface (<300 LOC)
│   ├── component.py           # Component base classes
│   ├── engine.py              # Engine interface
│   ├── store.py               # Store interface
│   └── types.py               # Core type definitions
│
├── agent/                      # Agent implementation
│   ├── __init__.py
│   ├── lifecycle.py           # Lifecycle management
│   ├── execution.py           # Execution pipeline
│   ├── output_processor.py    # Output validation & publishing
│   ├── context_resolver.py    # Context provider integration
│   └── builder.py             # AgentBuilder fluent API
│
├── orchestrator/               # Orchestrator implementation
│   ├── __init__.py
│   ├── orchestrator.py        # Main orchestrator (<400 LOC)
│   ├── scheduler.py           # Scheduling engine
│   ├── component_runner.py    # Component hook execution
│   ├── artifact_manager.py    # Publishing & persistence
│   └── mcp_manager.py         # MCP server management
│
├── components/                 # Component library
│   ├── __init__.py
│   ├── agent/                 # AgentComponent implementations
│   │   ├── __init__.py
│   │   ├── caching.py
│   │   ├── rate_limiting.py
│   │   ├── metrics.py
│   │   ├── validation.py
│   │   └── output_utility.py
│   │
│   └── orchestrator/          # OrchestratorComponent implementations
│       ├── __init__.py
│       ├── circuit_breaker.py
│       ├── deduplication.py
│       ├── collection.py      # AND gates, correlation, batching
│       └── scheduling/
│           ├── __init__.py
│           ├── correlation_engine.py
│           └── batch_engine.py
│
├── engines/                    # Evaluation engines
│   ├── __init__.py
│   ├── dspy/                  # DSPy engine (modular)
│   │   ├── __init__.py
│   │   ├── engine.py          # Main engine (~400 LOC)
│   │   ├── signature_builder.py
│   │   ├── streaming_executor.py
│   │   ├── artifact_materializer.py
│   │   └── formatting.py
│   │
│   └── base.py                # EngineComponent base
│
├── storage/                    # Storage backends
│   ├── __init__.py
│   ├── base.py                # BlackboardStore interface
│   ├── memory.py              # In-memory implementation
│   ├── sqlite/
│   │   ├── __init__.py
│   │   ├── store.py           # SQLite store (~400 LOC)
│   │   ├── query_builder.py   # SQL query construction
│   │   └── schema.py          # Schema management
│   │
│   └── utils/
│       ├── filter_builder.py
│       └── serialization.py
│
├── context/                    # Context providers
│   ├── __init__.py
│   ├── base.py                # BaseContextProvider
│   ├── bound_provider.py      # BoundContextProvider (security)
│   ├── providers/
│   │   ├── all_artifacts.py
│   │   ├── recent_artifacts.py
│   │   └── correlated_artifacts.py
│   │
│   └── resolver.py            # Context resolution logic
│
├── subscriptions/              # Subscription system
│   ├── __init__.py
│   ├── subscription.py        # Subscription model
│   ├── matcher.py             # Subscription matching logic
│   └── specs.py               # JoinSpec, BatchSpec
│
├── types/                      # Type system
│   ├── __init__.py
│   ├── registry.py            # Type registry
│   ├── artifacts.py           # Artifact models
│   ├── visibility.py          # Visibility models
│   └── utils.py               # Type utilities
│
├── mcp/                        # MCP integration
│   ├── __init__.py
│   ├── manager.py             # MCP server lifecycle
│   ├── integration.py         # Agent/orchestrator integration
│   └── config_parser.py       # Server configuration parsing
│
├── dashboard/                  # Dashboard & API
│   ├── __init__.py
│   ├── service.py             # FastAPI app setup (~200 LOC)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── control.py         # Control endpoints
│   │   ├── themes.py          # Theme endpoints
│   │   ├── traces.py          # Trace endpoints
│   │   └── websocket.py       # WebSocket endpoints
│   │
│   └── assembly/
│       ├── graph.py           # Graph assembly
│       └── themes.py          # Theme assembly
│
├── utils/                      # Shared utilities
│   ├── __init__.py
│   ├── async_utils.py         # Async helpers (@async_lock_required)
│   ├── type_resolution.py     # TypeRegistry.safe_resolve()
│   ├── visibility.py          # Visibility deserialization
│   └── validation.py          # Common validation
│
└── logging/                    # Logging (existing)
    └── ...
```

### Key Improvements

#### 1. **Modular Components**

Each major class is broken into focused modules:

**Before:** `orchestrator.py` (1,746 LOC)
```python
class Flock:
    def __init__(...): ...          # Initialization
    def add_agent(...): ...         # Agent management
    def publish(...): ...           # Publishing
    def _schedule_artifact(...): ... # Scheduling
    def _run_component_hook(...): ... # Component execution
    def add_mcp_server(...): ...    # MCP management
    # ... 50+ more methods
```

**After:** Distributed responsibilities
```python
# core/orchestrator.py (300 LOC)
class Flock:
    def __init__(self, scheduler, artifact_manager, mcp_manager, component_runner):
        self._scheduler = scheduler
        self._artifacts = artifact_manager
        self._mcp = mcp_manager
        self._components = component_runner

    async def publish(self, artifact):
        await self._artifacts.persist_and_schedule(artifact)

    def add_agent(self, agent):
        self._scheduler.register_agent(agent)

# orchestrator/scheduler.py (400 LOC)
class AgentScheduler:
    async def schedule_artifact(self, artifact): ...
    async def match_subscriptions(self, artifact): ...

# orchestrator/artifact_manager.py (300 LOC)
class ArtifactManager:
    async def persist_and_schedule(self, artifact): ...
    async def publish_outputs(self, agent, artifacts): ...

# orchestrator/mcp_manager.py (300 LOC)
class MCPManager:
    async def add_server(self, config): ...
    async def get_tools(self, agent): ...

# orchestrator/component_runner.py (200 LOC)
class ComponentRunner:
    async def run_hook(self, hook_name, components, *args): ...
```

#### 2. **Component Library Organization**

**Before:** Components scattered in multiple files
- `orchestrator_component.py` - Built-in orchestrator components
- `agent.py` - Utilities mixed with agent logic
- Custom components in random locations

**After:** Clear component library
```python
# components/agent/metrics.py
class MetricsComponent(AgentComponent):
    """Tracks agent execution metrics."""
    ...

# components/agent/rate_limiting.py
class RateLimitComponent(AgentComponent):
    """Rate limits agent execution."""
    ...

# components/orchestrator/circuit_breaker.py
class CircuitBreakerComponent(OrchestratorComponent):
    """Prevents runaway agent loops."""
    ...
```

**Usage becomes intuitive:**
```python
from flock.components.agent import MetricsComponent, RateLimitComponent
from flock.components.orchestrator import CircuitBreakerComponent

agent = (AgentBuilder()
    .with_utilities(MetricsComponent(), RateLimitComponent())
    .agent())

orchestrator = Flock()
orchestrator.add_component(CircuitBreakerComponent())
```

#### 3. **Extract Duplication into Utilities**

**Before:** Type resolution repeated 8+ times
```python
# In agent.py, store.py, orchestrator.py, context_provider.py, etc.
try:
    canonical = type_registry.resolve_name(type_name)
except KeyError:
    canonical = type_name
```

**After:** Single utility
```python
# utils/type_resolution.py
class TypeResolutionHelper:
    @staticmethod
    def safe_resolve(type_registry, type_name: str) -> str:
        """Safely resolve type name to canonical form."""
        try:
            return type_registry.resolve_name(type_name)
        except KeyError:
            return type_name

# Usage everywhere
from flock.utils.type_resolution import TypeResolutionHelper
canonical = TypeResolutionHelper.safe_resolve(registry, type_name)
```

**Before:** Component hook execution duplicated 6 times
```python
# In orchestrator.py - repeated for each hook
for component in self._components:
    comp_name = component.name or component.__class__.__name__
    self._logger.debug(f"Running {hook}: component={comp_name}, ...")
    try:
        result = await component.on_initialize(...)
    except Exception as e:
        self._logger.exception(...)
        raise
```

**After:** Single generic runner
```python
# orchestrator/component_runner.py
class ComponentRunner:
    async def run_hook(self, hook_name: str, components: list, *args, **kwargs):
        """Generic component hook execution with logging and error handling."""
        for component in components:
            comp_name = component.name or component.__class__.__name__
            self._logger.debug(f"Running {hook_name}: component={comp_name}")
            try:
                hook_method = getattr(component, hook_name)
                result = await hook_method(*args, **kwargs)
                yield component, result
            except Exception as e:
                self._logger.exception(f"Component {comp_name} failed in {hook_name}")
                raise

# Usage
async for component, result in self._components.run_hook("on_initialize", components, orchestrator):
    # Handle result
    pass
```

#### 4. **Simplify Complex Logic**

**Before:** 5-level nested MCP config parsing (agent.py:1249-1297)
```python
if isinstance(mcp_servers, dict):
    for name, config in mcp_servers.items():
        if isinstance(config, dict):
            if "command" in config:
                if isinstance(config["command"], str):
                    # ... more nesting
```

**After:** Strategy pattern with config parser
```python
# mcp/config_parser.py
class MCPConfigParser:
    def parse(self, config: MCPServerConfigInput) -> list[MCPServerConfig]:
        """Parse MCP server configuration from various formats."""
        if isinstance(config, dict):
            return self._parse_dict_config(config)
        elif isinstance(config, list):
            return self._parse_list_config(config)
        else:
            return self._parse_string_config(config)

    def _parse_dict_config(self, config: dict) -> list[MCPServerConfig]:
        # Single level logic
        ...

# Usage in agent
parser = MCPConfigParser()
servers = parser.parse(mcp_servers_input)
```

#### 5. **Consistent Patterns**

**Error Handling:** Standardize on explicit exception types
```python
# utils/async_utils.py
class AsyncLockRequired:
    """Decorator ensuring async lock acquisition."""
    def __init__(self, lock_attr: str = "_lock"):
        self.lock_attr = lock_attr

    def __call__(self, func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            lock = getattr(self, self.lock_attr)
            async with lock:
                return await func(self, *args, **kwargs)
        return wrapper

# Usage
class MyClass:
    def __init__(self):
        self._lock = asyncio.Lock()

    @AsyncLockRequired()
    async def my_method(self):
        # Lock automatically acquired
        ...
```

**Async Patterns:** Standardize on explicit patterns
```python
# Define clear patterns in documentation
# Pattern 1: Direct await for sequential operations
result = await operation()

# Pattern 2: create_task for fire-and-forget
task = asyncio.create_task(background_operation())

# Pattern 3: gather for parallel operations
results = await asyncio.gather(*[op1(), op2(), op3()])

# Pattern 4: asynccontextmanager for resources
async with resource_manager() as resource:
    await resource.use()
```

**Configuration:** Standardize on Pydantic
```python
# All config becomes Pydantic BaseModel
from pydantic import BaseModel, Field

class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)

class BatchSpec(BaseModel):
    max_size: int = Field(gt=0)
    timeout: timedelta = Field(default=timedelta(seconds=30))
```

---

## Component-First Refactoring Strategy

### When to Use Components

**AgentComponent** - Use for cross-cutting concerns during agent execution:
- ✅ Metrics collection
- ✅ Rate limiting
- ✅ Caching
- ✅ Input validation
- ✅ Output transformation
- ✅ Error recovery
- ❌ Core execution logic (stays in Agent)
- ❌ Business logic (stays in engines)

**OrchestratorComponent** - Use for system-wide policies:
- ✅ Circuit breaking
- ✅ Deduplication
- ✅ AND gates / correlation / batching
- ✅ Global rate limiting
- ✅ Artifact transformation
- ✅ Scheduling policies
- ❌ Core orchestration logic (stays in Flock)
- ❌ Storage (stays in BlackboardStore)

### Component Extraction Opportunities

#### 1. **Extract MCP Integration as Component**

**Before:** MCP logic embedded in Agent and Orchestrator
```python
# agent.py - lines 1249-1350
class Agent:
    def __init__(self, ..., mcp_servers=None):
        self._mcp_servers = self._parse_mcp_servers(mcp_servers)

    async def _get_mcp_tools(self):
        # Complex MCP tool fetching logic
        ...
```

**After:** MCP as AgentComponent
```python
# components/agent/mcp_integration.py
class MCPIntegrationComponent(AgentComponent):
    """Integrates MCP server tools into agent execution."""

    def __init__(self, servers: list[MCPServerConfig]):
        self.servers = servers

    async def on_pre_evaluate(self, agent, ctx, inputs):
        # Fetch MCP tools and inject into context
        tools = await self._fetch_tools(agent)
        ctx.mcp_tools = tools
        return inputs

# Usage
agent = (AgentBuilder()
    .with_utilities(MCPIntegrationComponent(servers=[...]))
    .agent())
```

**Benefits:**
- MCP is optional (no component = no MCP)
- Testing is easier (mock the component)
- Can swap implementations (e.g., cached MCP component)

#### 2. **Extract Output Processing as Component**

**Before:** Output validation logic in Agent
```python
# agent.py - lines 500-650
class Agent:
    async def _make_outputs(self, outputs, output_group):
        # Complex output validation, filtering, visibility logic
        ...
```

**After:** Validation as AgentComponent
```python
# components/agent/output_validator.py
class OutputValidatorComponent(AgentComponent):
    """Validates and filters agent outputs."""

    async def on_post_evaluate(self, agent, ctx, outputs, output_group):
        validated = []
        for output in outputs:
            if self._validate_output(output, output_group):
                validated.append(output)
        return validated

# Usage (automatically applied to all agents)
orchestrator = Flock(default_agent_components=[
    OutputValidatorComponent()
])
```

#### 3. **Extract Context Resolution as Component**

**Before:** Context resolution embedded in agent execution
```python
# agent.py - lines 350-450
class Agent:
    async def _resolve_context(self, subscription, artifacts):
        # Complex context provider logic
        ...
```

**After:** Context resolution as component
```python
# components/agent/context_resolver.py
class ContextResolverComponent(AgentComponent):
    """Resolves context providers for agent execution."""

    async def on_pre_consume(self, agent, ctx, inputs):
        # Resolve context provider and populate ctx.artifacts
        provider = agent.context_provider or orchestrator.default_provider
        ctx.artifacts = await provider.get_artifacts(ctx.request)
        return inputs
```

---

## Breaking Changes (Allowed)

### API Changes

#### 1. **Import Paths**

**Before:**
```python
from flock import Agent, Flock, AgentBuilder
from flock.components import AgentComponent, OrchestratorComponent
from flock.orchestrator_component import CircuitBreakerComponent
```

**After:**
```python
# Core abstractions
from flock.core import Agent, Flock, AgentBuilder
from flock.core.component import AgentComponent, OrchestratorComponent

# Components
from flock.components.agent import MetricsComponent, RateLimitComponent
from flock.components.orchestrator import CircuitBreakerComponent
```

**Migration:**
```python
# flock/__init__.py
from flock.core import Agent, Flock, AgentBuilder
from flock.core.component import AgentComponent, OrchestratorComponent
# ... etc

__all__ = ["Agent", "Flock", "AgentBuilder", ...]
```

#### 2. **Constructor Signatures**

Some constructors may change as responsibilities are extracted:

**Before:**
```python
orchestrator = Flock(
    store=sqlite_store,
    log_level="INFO"
)
```

**After:**
```python
orchestrator = Flock(
    store=sqlite_store,
    scheduler=AgentScheduler(),  # New: explicit scheduler
    log_level="INFO"
)
```

**Migration:** Provide sensible defaults
```python
class Flock:
    def __init__(
        self,
        store: BlackboardStore,
        scheduler: Optional[AgentScheduler] = None,  # Default to built-in
        log_level: str = "INFO"
    ):
        self.scheduler = scheduler or AgentScheduler()
```

#### 3. **Component Registration**

Components become more explicit:

**Before:**
```python
# Circuit breaker added automatically
orchestrator = Flock()
```

**After:**
```python
from flock.components.orchestrator import CircuitBreakerComponent, DeduplicationComponent

orchestrator = Flock(
    default_components=[  # Explicit default components
        CircuitBreakerComponent(),
        DeduplicationComponent()
    ]
)
```

**Migration:** Provide sensible defaults
```python
def _get_default_components():
    return [
        CircuitBreakerComponent(),
        DeduplicationComponent(),
        # ... other built-ins
    ]

class Flock:
    def __init__(self, default_components: Optional[list] = None):
        self.components = default_components or _get_default_components()
```

---

## Non-Negotiables (Regression Prevention)

### Feature Preservation

All existing features MUST continue working:

✅ **Agent Execution**
- All lifecycle hooks execute in correct order
- Context providers filter correctly
- Output validation behaves identically

✅ **Orchestration**
- Subscription matching produces same results
- AND gates collect artifacts correctly
- Correlation windows work identically
- Batching behavior unchanged

✅ **Components**
- All existing components work without modification
- Hook execution order preserved
- Priority ordering maintained

✅ **Storage**
- SQLite queries return same results
- In-memory store behaves identically
- Consumption tracking unchanged

✅ **MCP Integration**
- Tool fetching works correctly
- Server lifecycle identical
- Configuration parsing compatible

✅ **Dashboard**
- All API endpoints functional
- WebSocket streaming works
- Graph assembly unchanged

✅ **Testing**
- All existing tests pass
- Test coverage maintained or improved
- Performance benchmarks maintained

### Testing Strategy

**Phase Completion Criteria:**
```bash
# Every phase must pass:
1. pytest tests/              # All unit tests pass
2. pytest tests/integration/  # All integration tests pass
3. ruff check src/           # No linting errors
4. mypy src/                 # Type checking passes
5. Performance benchmarks    # No regression >10%
```

**Test-Driven Refactoring:**
1. **Before refactoring:** Run full test suite, document baseline
2. **During refactoring:** Run tests after each significant change
3. **After refactoring:** Verify 100% test pass rate

**New Tests Required:**
- Unit tests for each extracted module
- Integration tests for component interactions
- Regression tests for breaking changes

---

## Performance Considerations

### Potential Performance Impacts

#### 1. **Increased Indirection**

**Issue:** More classes = more method calls = potential overhead

**Mitigation:**
- Profile before/after each phase
- Use `__slots__` for frequently instantiated classes
- Cache lookups (e.g., type resolution)
- Avoid premature optimization

**Benchmark:**
```python
# Benchmark: Agent execution throughput
# Before: 1000 agents/sec
# After: ≥900 agents/sec (max 10% regression allowed)
```

#### 2. **Import Overhead**

**Issue:** More modules = more imports

**Mitigation:**
- Use lazy imports where appropriate
- Consolidate frequently used imports in `__init__.py`
- Profile import time in critical paths

#### 3. **Memory Footprint**

**Issue:** More class instances = more memory

**Mitigation:**
- Share immutable components across agents
- Use component pooling for expensive components
- Profile memory usage during refactoring

### Performance Goals

| Metric | Current | Target | Max Regression |
|--------|---------|--------|----------------|
| Agent execution throughput | Baseline | ≥90% | 10% |
| Import time | Baseline | ≤110% | 10% |
| Memory per agent | Baseline | ≤110% | 10% |
| Test suite duration | Baseline | ≤120% | 20% |

---

## Migration Path for Users

### For Framework Users (When Released)

**Scenario 1: Simple Usage**
```python
from flock import Agent, Flock, AgentBuilder

agent = AgentBuilder().consumes(...).publishes(...).agent()
orchestrator = Flock()
orchestrator.add_agent(agent)
```

**Scenario 2: Component Usage**
```python
# Import from new locations
from flock.components.orchestrator import CircuitBreakerComponent
```

**Scenario 3: Custom Components**
```python
# Update imports to new locations
from flock.core import Agent
```

### Migration Guide

Provide comprehensive migration guide:

```markdown
# Migration Guide: v0.x to v1.0

## Import Path Changes

| Old Import | New Import | Status |
|------------|------------|--------|
| `from flock import Agent` | `from flock.core import Agent` | Via __init__.py |
| `from flock.orchestrator_component import CircuitBreakerComponent` | `from flock.components.orchestrator import CircuitBreakerComponent` | Breaking |

## Constructor Changes

- `Flock()`: New optional `scheduler` parameter (default provided)
- `Agent()`: MCP servers now via `MCPIntegrationComponent`

## Deprecations

- `orchestrator_component.py` deprecated (use `components.orchestrator.*`)
- Direct MCP server config in Agent (use component instead)
```

---

## Success Metrics

### Code Quality Metrics

**Before Refactor:**
- Large classes (>1000 LOC): 5
- Code duplication: 12+ patterns
- Nested conditionals (5+ levels): 4
- Inconsistent patterns: 8+
- Test coverage: Current %

**After Refactor Targets:**
- Large classes (>1000 LOC): 0
- Code duplication: <3 patterns
- Nested conditionals (5+ levels): 0
- Inconsistent patterns: 0
- Test coverage: ≥Current % (maintain or improve)

### Developer Experience Metrics

- **Time to find code:** Reduced by 50% (clear module structure)
- **Time to add component:** Reduced by 60% (clear patterns)
- **Onboarding time:** Reduced by 40% (better organization)
- **PR review time:** Reduced by 30% (smaller, focused modules)

### Maintainability Metrics

- **Average module size:** <400 LOC
- **Cyclomatic complexity:** <10 per method
- **Class coupling:** Low (clear interfaces)
- **Module cohesion:** High (single responsibility)

---

## Risks & Mitigation

### Risk 1: Regression Introduction

**Probability:** Medium
**Impact:** Critical
**Mitigation:**
- Comprehensive test suite before starting
- Run tests after every change
- Phase-based approach (catch issues early)
- Automated CI/CD verification

### Risk 2: Performance Degradation

**Probability:** Low
**Impact:** High
**Mitigation:**
- Benchmark before/after each phase
- Profile critical paths
- Set performance budgets
- Rollback if regression >10%

### Risk 3: Scope Creep

**Probability:** High
**Impact:** Medium
**Mitigation:**
- Strict phase boundaries
- No feature additions during refactor
- Focus on structure, not functionality
- Regular progress reviews

### Risk 4: Breaking User Code

**Probability:** Low (framework not released)
**Impact:** None (no users yet)
**Mitigation:**
- Clean, modern import structure
- Comprehensive migration guide
- Clear breaking changes documentation

---

## Next Steps

1. **Review & Approve:** Get stakeholder approval on design
2. **Create Implementation Plan:** Break into concrete phases (see IMPLEMENTATION_PLAN.md)
3. **Setup Baseline:** Document current test results, performance benchmarks
4. **Execute Phase 1:** Begin with highest-impact, lowest-risk changes
5. **Iterate:** Complete phases sequentially, validating after each

---

## Appendix: Design Decisions

### Why Component-First?

**Decision:** Leverage AgentComponent/OrchestratorComponent extensively

**Rationale:**
- Framework already has excellent component infrastructure
- Components provide clear extension points
- Reduces coupling between core and features
- Makes testing easier (mock components)
- Enables plugin ecosystem

### Why Not Microservices Architecture?

**Decision:** Keep monolithic structure, just better organized

**Rationale:**
- Framework is a library, not a service
- Microservices add complexity without benefit here
- Monolith easier to test and debug
- Better performance (no network overhead)

### Why Pydantic Everywhere?

**Decision:** Standardize on Pydantic BaseModel for all configuration

**Rationale:**
- Type safety at runtime
- Automatic validation
- JSON serialization built-in
- Great IDE support
- Consistent pattern across codebase

### Why Not Use ABC for Everything?

**Decision:** Use ABC for interfaces, concrete classes for implementation

**Rationale:**
- ABCs add complexity without always adding value
- Concrete classes easier to test
- Duck typing works well in Python
- Only use ABC when multiple implementations expected

---

## Glossary

- **AgentComponent:** Lifecycle interceptor for agent execution (utilities)
- **OrchestratorComponent:** System-wide orchestration hooks
- **EngineComponent:** Evaluation strategy (inputs → outputs)
- **God Class:** Anti-pattern where a class does too many things
- **Bounded Context:** DDD concept - module with single, clear responsibility
- **Breaking Change:** API change that requires user code updates
- **Regression:** Bug introduced by changing working code

---

**Document Status:** READY FOR REVIEW
**Next:** Create IMPLEMENTATION_PLAN.md with phased execution strategy
