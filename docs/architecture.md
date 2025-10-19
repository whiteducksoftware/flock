# Flock Architecture Overview

This document provides a comprehensive overview of the Flock framework's architecture, component organization, and extension points.

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Module Structure](#module-structure)
3. [Core Architecture](#core-architecture)
4. [Component System](#component-system)
5. [Orchestrator Architecture](#orchestrator-architecture)
6. [Agent Architecture](#agent-architecture)
7. [Storage Architecture](#storage-architecture)
8. [Engine Architecture](#engine-architecture)
9. [Extension Points](#extension-points)
10. [Data Flow](#data-flow)

---

## High-Level Architecture

Flock is a **blackboard-based multi-agent orchestration framework** that enables event-driven coordination between LLM agents.

### Core Concepts

```
┌──────────────────────────────────────────────────────────────┐
│                         BLACKBOARD                           │
│  (Shared memory for artifact publishing and subscription)    │
│                                                               │
│  Artifacts: Typed data published by agents                   │
│  Store: Persistent storage (SQLite or In-Memory)             │
│  Visibility: Access control for multi-tenant isolation       │
└──────────────────────────────────────────────────────────────┘
                              ▲  │
                              │  │
                 publish()    │  │  subscribe/schedule
                              │  ▼
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR (Flock)                    │
│                                                               │
│  • Agent Scheduler - Matches artifacts to subscriptions      │
│  • Component Runner - Executes lifecycle hooks               │
│  • Artifact Manager - Handles publishing and persistence     │
│  • MCP Manager - Manages tool connections                    │
│  • Context Builder - Creates execution contexts              │
│  • Tracing Manager - OpenTelemetry spans                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │  schedules
                              ▼
                    ┌──────────────────┐
                    │   Agent Tasks    │
                    │  (async tasks)   │
                    └──────────────────┘
                              │
                              ▼
┌────────────┐    ┌────────────┐    ┌────────────┐
│   Agent    │    │   Agent    │    │   Agent    │
│            │    │            │    │            │
│ Components │    │ Components │    │ Components │
│  Engines   │    │  Engines   │    │  Engines   │
└────────────┘    └────────────┘    └────────────┘
      │                 │                 │
      │  publishes      │                 │
      └─────────────────┴─────────────────┘
                        │
                        ▼
               Back to Blackboard
```

### System Responsibilities

| Component | Responsibility | Examples |
|-----------|---------------|----------|
| **Flock** | Orchestration, scheduling, lifecycle | Agent scheduling, MCP management, tracing |
| **Agent** | Consume artifacts, execute logic, publish outputs | LLM evaluation, data transformation |
| **Store** | Persist artifacts, query history | SQLite, in-memory storage |
| **Components** | Extend behavior via hooks | Circuit breaker, deduplication, metrics |
| **Engine** | Execute agent logic (LLM or custom) | DSPy, rule-based engines |

---

## Module Structure

### Directory Layout

```
src/flock/
├── __init__.py              # Public API exports
├── core/                    # Core orchestration and agents
│   ├── __init__.py
│   ├── orchestrator.py      # Flock orchestrator
│   └── agent.py            # Agent and AgentBuilder
│
├── orchestrator/           # Orchestrator modules (Phase 3+5A)
│   ├── __init__.py
│   ├── scheduler.py        # Agent scheduling
│   ├── artifact_manager.py # Publishing and persistence
│   ├── component_runner.py # Component hook execution
│   ├── mcp_manager.py      # MCP server management
│   ├── context_builder.py  # Context creation
│   ├── event_emitter.py    # Dashboard events
│   ├── lifecycle_manager.py # Batch/correlation lifecycle
│   ├── initialization.py   # Orchestrator initialization
│   ├── server_manager.py   # HTTP/Dashboard server
│   └── tracing.py          # OpenTelemetry tracing
│
├── agent/                  # Agent modules (Phase 4)
│   ├── __init__.py
│   ├── output_processor.py      # Output artifact creation
│   ├── mcp_integration.py       # MCP tool access
│   ├── component_lifecycle.py   # Component hook execution
│   ├── builder_validator.py     # Builder validation
│   └── builder_helpers.py       # Pipeline, RunHandle
│
├── components/             # Component library
│   ├── __init__.py
│   ├── agent/              # Agent components
│   │   ├── __init__.py
│   │   ├── base.py         # AgentComponent base
│   │   └── output_utility.py # Output streaming
│   └── orchestrator/       # Orchestrator components
│       ├── __init__.py
│       ├── base.py         # OrchestratorComponent base
│       ├── circuit_breaker.py  # Runaway loop prevention
│       ├── deduplication.py    # Duplicate artifact filtering
│       └── collection.py       # Batch and join logic
│
├── engines/                # Engine implementations
│   ├── __init__.py
│   ├── base.py            # EngineComponent base
│   ├── dspy_engine.py     # DSPy LLM engine
│   └── dspy/              # DSPy engine modules
│       ├── __init__.py
│       ├── streaming_executor.py  # Streaming execution
│       ├── tool_executor.py       # Tool/function calling
│       └── prompt_builder.py      # DSPy prompt construction
│
├── storage/                # Storage backends
│   ├── __init__.py
│   ├── sqlite/             # SQLite implementation
│   │   ├── __init__.py
│   │   └── sqlite_store.py
│   └── in_memory/          # In-memory implementation
│       ├── __init__.py
│       └── memory_store.py
│
├── dashboard/              # Real-time dashboard
│   ├── __init__.py
│   ├── service.py          # FastAPI app
│   ├── websocket.py        # WebSocket manager
│   ├── events.py           # Event models
│   ├── collector.py        # State collection
│   ├── graph_builder.py    # Visualization graph
│   └── routes/             # API routes (Phase 7)
│       ├── __init__.py
│       ├── control.py      # Control endpoints
│       ├── traces.py       # Tracing/telemetry
│       ├── themes.py       # UI themes
│       ├── websocket.py    # WebSocket endpoint
│       └── helpers.py      # Helper functions
│
├── mcp/                    # MCP (Model Context Protocol)
│   ├── __init__.py
│   ├── client.py           # MCP client
│   ├── manager.py          # Connection management
│   └── servers/            # Server implementations
│
├── utils/                  # Utility modules (Phase 1)
│   ├── __init__.py
│   ├── validation.py       # Input validation
│   ├── formatting.py       # String formatting
│   ├── conversion.py       # Type conversion
│   └── json_utils.py       # JSON handling
│
├── artifacts.py            # Artifact models
├── subscription.py         # Subscription and matching
├── visibility.py           # Access control
├── registry.py             # Type registry
├── runtime.py              # Context, EvalInputs, EvalResult
├── store.py                # Store abstraction
└── cli.py                  # CLI commands
```

### Core vs Components vs Utils

- **Core** (`core/`): Essential runtime (orchestrator, agent)
- **Modules** (`orchestrator/`, `agent/`): Extracted subsystems
- **Components** (`components/`): Pluggable extensions
- **Utils** (`utils/`): Shared helper functions
- **Storage** (`storage/`): Pluggable backends
- **Engines** (`engines/`): Pluggable evaluation logic

---

## Core Architecture

### The Flock Orchestrator

**File:** `src/flock/core/orchestrator.py`

The orchestrator is the central coordinator for all agent execution. It manages the blackboard, schedules agents, and coordinates components.

**Key Responsibilities:**

1. **Agent Management** - Register and retrieve agents
2. **Artifact Publishing** - Persist and schedule artifacts
3. **Subscription Matching** - Find agents interested in artifacts
4. **Component Coordination** - Execute orchestrator component hooks
5. **MCP Management** - Manage tool server connections
6. **Lifecycle Management** - Start, run, shutdown
7. **Tracing** - OpenTelemetry instrumentation

**Initialization Pattern:**

```python
# From src/flock/core/orchestrator.py (line 89)
def __init__(
    self,
    model: str | None = None,
    *,
    store: BlackboardStore | None = None,
    max_agent_iterations: int = 1000,
    context_provider: Any = None,
) -> None:
    # Phase 3: Use OrchestratorInitializer for setup
    components = OrchestratorInitializer.initialize_components(
        store=store,
        context_provider=context_provider,
        max_agent_iterations=max_agent_iterations,
        logger=self._logger,
        model=model,
    )

    # Assign components
    self.store = components["store"]
    self._correlation_engine = components["correlation_engine"]
    self._batch_engine = components["batch_engine"]
    # ... more components
```

**Delegation Pattern:**

The orchestrator delegates to specialized modules:

```python
# Artifact management
await self._artifact_manager.publish(artifact)

# Agent scheduling
await self._scheduler.schedule_artifact(artifact)

# Context building
ctx = await self._context_builder.build_execution_context(...)

# Component hooks
await self._component_runner.run_before_schedule(...)
```

### The Agent

**File:** `src/flock/core/agent.py`

Agents consume artifacts, execute logic via engines, and publish outputs.

**Key Responsibilities:**

1. **Subscription Management** - What artifacts to consume
2. **Output Definition** - What artifacts to publish
3. **Engine Execution** - Run LLM or custom logic
4. **Component Lifecycle** - Execute agent component hooks
5. **MCP Tool Access** - Get tools from MCP servers
6. **Output Processing** - Create output artifacts

**Agent Lifecycle:**

```python
# From src/flock/core/agent.py (line 244)
async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
    """Execute agent with full lifecycle."""
    async with self._semaphore:  # Concurrency control
        try:
            # 1. Setup
            self._resolve_engines()
            self._resolve_utilities()

            # 2. Lifecycle hooks (sequential)
            await self._run_initialize(ctx)
            processed = await self._run_pre_consume(ctx, artifacts)
            inputs = await self._run_pre_evaluate(ctx, processed)

            # 3. Engine execution (per output group)
            all_outputs = []
            for output_group in self.output_groups:
                result = await self._run_engines(ctx, inputs, output_group)
                result = await self._run_post_evaluate(ctx, inputs, result)
                outputs = await self._make_outputs_for_group(ctx, result, output_group)
                all_outputs.extend(outputs)

            # 4. Post-publish hooks
            await self._run_post_publish(ctx, all_outputs)

            return all_outputs
        except Exception as exc:
            await self._run_error(ctx, exc)
            raise
        finally:
            await self._run_terminate(ctx)
```

---

## Component System

Components extend behavior via lifecycle hooks without modifying core code.

### Component Types

**1. OrchestratorComponent** - Extends orchestrator behavior

**File:** `src/flock/components/orchestrator/base.py`

**Lifecycle Hooks:**

```python
class OrchestratorComponent:
    priority: int = 50  # Lower = runs earlier

    async def on_initialize(self, orchestrator: Flock) -> None:
        """Called when orchestrator initializes."""
        pass

    async def on_artifact_published(
        self, orchestrator: Flock, artifact: Artifact
    ) -> Artifact | None:
        """Transform or block published artifacts."""
        return artifact

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription
    ) -> ScheduleDecision:
        """Decide if agent should be scheduled."""
        return ScheduleDecision.CONTINUE

    async def on_collect_artifacts(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription
    ) -> CollectionResult:
        """Collect artifacts for batching/correlation."""
        return CollectionResult(complete=True, artifacts=[artifact])

    async def on_orchestrator_idle(self, orchestrator: Flock) -> None:
        """Called when orchestrator has no pending work."""
        pass

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Called during shutdown."""
        pass
```

**Built-in Orchestrator Components:**

| Component | Priority | Purpose | File |
|-----------|----------|---------|------|
| **CircuitBreakerComponent** | 10 | Prevent runaway loops | `circuit_breaker.py` |
| **DeduplicationComponent** | 20 | Skip duplicate artifacts | `deduplication.py` |
| **CollectionComponent** | 30 | Batch and join logic | `collection.py` |

**Example: Circuit Breaker**

```python
# From src/flock/components/orchestrator/circuit_breaker.py
class CircuitBreakerComponent(OrchestratorComponent):
    priority: int = 10  # Run early
    name: str = "circuit_breaker"
    max_iterations: int = 1000

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
    ) -> ScheduleDecision:
        """Prevent infinite loops."""
        current = self._iteration_counts.get(agent.name, 0)
        if current >= self.max_iterations:
            return ScheduleDecision.SKIP  # Block scheduling

        self._iteration_counts[agent.name] = current + 1
        return ScheduleDecision.CONTINUE

    async def on_orchestrator_idle(self, orchestrator: Flock) -> None:
        """Reset counters when idle."""
        self._iteration_counts.clear()
```

**2. AgentComponent** - Extends agent behavior

**File:** `src/flock/components/agent/base.py`

**Lifecycle Hooks:**

```python
class AgentComponent:
    priority: int = 50

    async def on_initialize(self, agent: Agent, ctx: Context) -> None:
        """Setup before execution."""
        pass

    async def on_pre_consume(
        self, agent: Agent, ctx: Context, inputs: list[Artifact]
    ) -> list[Artifact]:
        """Transform input artifacts."""
        return inputs

    async def on_pre_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
        """Prepare inputs for engine."""
        return inputs

    async def on_post_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """Transform engine outputs."""
        return result

    async def on_post_publish(
        self, agent: Agent, ctx: Context, artifacts: Sequence[Artifact]
    ) -> None:
        """React to published artifacts."""
        pass

    async def on_error(self, agent: Agent, ctx: Context, error: Exception) -> None:
        """Handle execution errors."""
        pass

    async def on_terminate(self, agent: Agent, ctx: Context) -> None:
        """Cleanup after execution."""
        pass
```

**Built-in Agent Components:**

| Component | Purpose | File |
|-----------|---------|------|
| **OutputUtilityComponent** | Stream outputs to CLI | `output_utility.py` |

---

## Orchestrator Architecture

### Modules (Phase 3 & 5A Extractions)

The orchestrator delegates to these specialized modules:

**1. AgentScheduler** (`orchestrator/scheduler.py`)

**Responsibilities:**
- Match artifacts to agent subscriptions
- Execute component hooks (before_schedule, collect_artifacts)
- Create agent execution tasks
- Track processed artifacts

```python
# From orchestrator/scheduler.py
class AgentScheduler:
    async def schedule_artifact(self, artifact: Artifact) -> None:
        """Match artifact to subscriptions and schedule agents."""
        for agent in self._orchestrator.agents:
            for subscription in agent.subscriptions:
                # 1. Check subscription match
                if not subscription.matches(artifact):
                    continue

                # 2. Component hook - before schedule
                decision = await self._component_runner.run_before_schedule(...)
                if decision == ScheduleDecision.SKIP:
                    continue

                # 3. Component hook - collect artifacts
                collection = await self._component_runner.run_collect_artifacts(...)
                if not collection.complete:
                    continue  # Still collecting

                # 4. Schedule agent task
                task = self.schedule_task(agent, collection.artifacts)
```

**2. ArtifactManager** (`orchestrator/artifact_manager.py`)

**Responsibilities:**
- Publish artifacts to blackboard
- Normalize input formats (BaseModel, dict, Artifact)
- Persist artifacts to store
- Schedule matching agents

**3. ComponentRunner** (`orchestrator/component_runner.py`)

**Responsibilities:**
- Sort components by priority
- Execute lifecycle hooks
- Handle hook errors gracefully
- Track initialization state

**4. MCPManager** (`orchestrator/mcp_manager.py`)

**Responsibilities:**
- Register MCP servers
- Create FlockMCPClientManager
- Manage server connections
- Handle MCP cleanup

**5. ContextBuilder** (`orchestrator/context_builder.py`)

**Responsibilities:**
- Create execution contexts
- Implement security boundary (visibility filtering)
- Resolve context providers
- Build MCP tool lists

**6. EventEmitter** (`orchestrator/event_emitter.py`)

**Responsibilities:**
- Emit WebSocket events for dashboard
- Track correlation group updates
- Track batch accumulation

**7. LifecycleManager** (`orchestrator/lifecycle_manager.py`)

**Responsibilities:**
- Start/stop background tasks
- Check batch timeouts
- Clean up expired correlations
- Manage watchdog loops

**8. TracingManager** (`orchestrator/tracing.py`)

**Responsibilities:**
- Create OpenTelemetry spans
- Manage workflow span context
- Clear traces from DuckDB

---

## Agent Architecture

### Modules (Phase 4 Extractions)

**1. OutputProcessor** (`agent/output_processor.py`)

**Responsibilities:**
- Create output artifacts from EvalResult
- Match engine outputs to declared outputs
- Apply visibility rules
- Handle fan-out (multiple artifacts per output)

**2. MCPIntegration** (`agent/mcp_integration.py`)

**Responsibilities:**
- Configure MCP servers for agent
- Validate server registration
- Get MCP tools from FlockMCPClientManager
- Filter tools by whitelist

**3. ComponentLifecycle** (`agent/component_lifecycle.py`)

**Responsibilities:**
- Execute component hooks (initialize, pre_consume, etc.)
- Sort components by priority
- Handle component errors

**4. BuilderValidator** (`agent/builder_validator.py`)

**Responsibilities:**
- Validate builder configurations
- Normalize JoinSpec/BatchSpec
- Detect self-trigger risks

**5. BuilderHelpers** (`agent/builder_helpers.py`)

**Responsibilities:**
- PublishBuilder - Conditional publishing
- Pipeline - Agent chaining
- RunHandle - Execution handle

---

## Storage Architecture

### Store Abstraction

**File:** `src/flock/store.py`

**Interface:**

```python
class BlackboardStore(ABC):
    """Abstract storage backend for artifacts."""

    @abstractmethod
    async def persist(self, artifact: Artifact) -> None:
        """Save artifact to storage."""
        pass

    @abstractmethod
    async def get(self, artifact_id: str) -> Artifact | None:
        """Retrieve artifact by ID."""
        pass

    @abstractmethod
    async def list(
        self,
        *,
        filter: ArtifactFilter | None = None,
        limit: int | None = None
    ) -> list[Artifact]:
        """Query artifacts with optional filtering."""
        pass

    @abstractmethod
    async def record_consumptions(
        self, records: list[ConsumptionRecord]
    ) -> None:
        """Track which agents consumed which artifacts."""
        pass
```

### Built-in Implementations

**1. SQLiteStore** (`storage/sqlite/sqlite_store.py`)

**Features:**
- Persistent storage using SQLite
- Full-text search support
- Consumption tracking
- OpenTelemetry tracing integration (DuckDB)

**2. InMemoryStore** (`storage/in_memory/memory_store.py`)

**Features:**
- Fast in-memory storage
- No persistence
- Ideal for testing

**Usage:**

```python
# SQLite (production)
from flock.storage.sqlite import SQLiteStore
store = SQLiteStore(db_path=".flock/artifacts.sqlite")
flock = Flock("openai/gpt-4.1", store=store)

# In-memory (testing)
from flock.storage.in_memory import InMemoryStore
store = InMemoryStore()
flock = Flock("test", store=store)
```

---

## Engine Architecture

### Engine Abstraction

**File:** `src/flock/engines/base.py`

**Interface:**

```python
class EngineComponent(AgentComponent):
    """Base class for agent engines (LLM or custom logic)."""

    async def on_pre_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
        """Prepare inputs before evaluation."""
        return inputs

    @abstractmethod
    async def evaluate(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs,
        output_group: OutputGroup
    ) -> EvalResult:
        """Execute agent logic and return outputs.

        Auto-detects batch/fan-out from ctx and output_group:
        - ctx.is_batch: Batch processing mode
        - output_group.outputs[0].count > 1: Fan-out mode
        """
        raise NotImplementedError

    async def on_post_evaluate(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs,
        result: EvalResult
    ) -> EvalResult:
        """Transform outputs after evaluation."""
        return result
```

### Built-in Engines

**1. DSPyEngine** (`engines/dspy_engine.py`)

**Features:**
- LLM-based evaluation via DSPy
- Function/tool calling
- Streaming support
- Multi-modal inputs
- Chain-of-thought prompting

**Modules (Phase 5):**
- `dspy/streaming_executor.py` - Streaming execution
- `dspy/tool_executor.py` - Tool/function calling
- `dspy/prompt_builder.py` - DSPy prompt construction

**Usage:**

```python
from flock.engines import DSPyEngine

agent = (
    flock.agent("analyst")
    .consumes(Data)
    .publishes(Report)
    .with_engines(DSPyEngine(
        model="openai/gpt-4o",
        instructions="Analyze data and generate insights"
    ))
)
```

**2. Custom Engines**

Create custom engines for non-LLM logic:

```python
class RuleBasedEngine(EngineComponent):
    """Rule-based decision engine."""

    async def evaluate(
        self, agent, ctx, inputs, output_group
    ) -> EvalResult:
        # Custom logic
        result = apply_business_rules(inputs.artifacts)

        return EvalResult(
            artifacts=[
                Artifact(
                    type="Decision",
                    payload={"decision": result},
                    produced_by=agent.name
                )
            ],
            state={},
        )
```

---

## Extension Points

### 1. Custom Components

**Orchestrator Components:**

```python
from flock.components.orchestrator import OrchestratorComponent, ScheduleDecision

class RateLimitComponent(OrchestratorComponent):
    """Limit agent execution rate."""

    priority = 15
    max_per_minute = 10

    async def on_before_schedule(
        self, orchestrator, artifact, agent, subscription
    ) -> ScheduleDecision:
        if self._exceeds_rate_limit(agent):
            return ScheduleDecision.DEFER  # Try again later
        return ScheduleDecision.CONTINUE

flock.add_component(RateLimitComponent())
```

**Agent Components:**

```python
from flock.components.agent import AgentComponent

class LoggingComponent(AgentComponent):
    """Log all agent executions."""

    priority = 5

    async def on_pre_consume(self, agent, ctx, inputs):
        logger.info("Agent %s consuming %s artifacts", agent.name, len(inputs))
        return inputs

    async def on_post_publish(self, agent, ctx, artifacts):
        logger.info("Agent %s published %s artifacts", agent.name, len(artifacts))

agent.with_utilities(LoggingComponent())
```

### 2. Custom Engines

Implement `EngineComponent.evaluate()` for custom logic:

```python
class DatabaseEngine(EngineComponent):
    """Query database for answers."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        query = inputs.artifacts[0].payload["query"]
        results = await self.db.execute(query)

        return EvalResult(artifacts=[
            Artifact(
                type="QueryResult",
                payload={"results": results},
                produced_by=agent.name
            )
        ])
```

### 3. Custom Context Providers

Control artifact visibility per agent:

```python
from flock.context import DefaultContextProvider

class TenantContextProvider(DefaultContextProvider):
    """Filter artifacts by tenant."""

    async def get_context(
        self, agent: Agent, visibility_filter: Callable
    ) -> list[Artifact]:
        # Get artifacts for agent's tenant only
        artifacts = await self._store.list(
            filter=ArtifactFilter(tenant_id=agent.tenant_id)
        )
        # Apply visibility filtering
        return [a for a in artifacts if visibility_filter(a)]

flock = Flock(
    "openai/gpt-4.1",
    context_provider=TenantContextProvider(store)
)
```

### 4. Custom Storage Backends

Implement `BlackboardStore` interface:

```python
from flock.store import BlackboardStore

class PostgresStore(BlackboardStore):
    """PostgreSQL storage backend."""

    async def persist(self, artifact: Artifact) -> None:
        await self.pool.execute(
            "INSERT INTO artifacts (id, type, payload) VALUES ($1, $2, $3)",
            str(artifact.id), artifact.type, artifact.payload
        )

    async def get(self, artifact_id: str) -> Artifact | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM artifacts WHERE id = $1", artifact_id
        )
        return self._row_to_artifact(row) if row else None

flock = Flock("openai/gpt-4.1", store=PostgresStore())
```

---

## Data Flow

### Event-Driven Publishing

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PUBLISH                                                   │
│    await flock.publish(Task(name="analyze"))                 │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ARTIFACT MANAGER                                          │
│    • Normalize input (BaseModel → Artifact)                  │
│    • Persist to store                                        │
│    • Schedule matching agents                                │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. AGENT SCHEDULER                                           │
│    For each agent:                                           │
│      • Check subscription match                              │
│      • Run component hooks (circuit breaker, dedup)          │
│      • Collect artifacts (batch/join logic)                  │
│      • Create agent task (asyncio.create_task)               │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. AGENT EXECUTION (async task)                              │
│    • Build context (security boundary)                       │
│    • Run lifecycle hooks (initialize, pre_consume, etc.)     │
│    • Execute engine (LLM or custom logic)                    │
│    • Create output artifacts                                 │
│    • Return artifacts to orchestrator                        │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. ORCHESTRATOR PUBLISHES OUTPUTS                            │
│    For each output artifact:                                 │
│      • Validate artifact                                     │
│      • Persist to store                                      │
│      • Schedule matching agents (cascade)                    │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. CASCADE CONTINUES                                         │
│    • More agents consume published artifacts                 │
│    • Process continues until idle (no pending tasks)         │
└─────────────────────────────────────────────────────────────┘
```

### Direct Invocation

```
┌─────────────────────────────────────────────────────────────┐
│ 1. DIRECT INVOKE                                             │
│    await flock.invoke(agent, Task(name="test"))              │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ORCHESTRATOR                                              │
│    • Create artifact (not published to blackboard yet)       │
│    • Build execution context                                 │
│    • Execute agent directly (bypass subscription matching)   │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. AGENT EXECUTION                                           │
│    • Same as event-driven flow                               │
│    • Returns outputs to caller                               │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. OPTIONAL CASCADE                                          │
│    If publish_outputs=True:                                  │
│      • Publish outputs to blackboard                         │
│      • Allow cascade to other agents                         │
│    If publish_outputs=False:                                 │
│      • Return outputs without cascade                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

**Key Architectural Principles:**

1. **Blackboard Pattern** - Shared artifact storage for loose coupling
2. **Event-Driven** - Publish/subscribe for reactive coordination
3. **Component System** - Extend behavior without modifying core code
4. **Delegation** - Orchestrator delegates to specialized modules
5. **Abstraction** - Pluggable storage, engines, and components
6. **Security Boundary** - Context providers enforce visibility filtering
7. **Lifecycle Hooks** - Predictable extension points for customization

**Design Goals:**

- ✅ **Modularity** - Components are independent and replaceable
- ✅ **Extensibility** - Easy to add custom behavior via components
- ✅ **Testability** - Isolated modules with clear contracts
- ✅ **Performance** - Parallel agent execution, efficient scheduling
- ✅ **Observability** - OpenTelemetry tracing throughout
- ✅ **Maintainability** - Clear separation of concerns, <500 LOC per module

**For More Information:**

- **Error Handling Patterns** - See `docs/patterns/error_handling.md`
- **Async Patterns** - See `docs/patterns/async_patterns.md`
- **Breaking Changes** - See `docs/refactor/breaking_changes.md`
- **Migration Guide** - See `docs/migration.md` (coming soon)
- **Contributing** - See `docs/contributing.md` (coming soon)
