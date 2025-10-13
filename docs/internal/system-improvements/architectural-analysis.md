# Flock Framework - Comprehensive Architectural Analysis

**Analysis Date**: 2025-10-13
**Analyst**: System Architect
**Purpose**: Deep dive into Flock's core architecture to identify patterns, strengths, and improvement opportunities

---

## Executive Summary

Flock is a **blackboard-based multi-agent orchestration framework** with event-driven coordination. The architecture demonstrates excellent separation of concerns, extensibility, and thoughtful design patterns. Key strengths include:

- Clean event-driven architecture with subscription-based routing
- Modular component system enabling cross-cutting concerns
- Strong abstraction layers (storage, visibility, correlation)
- Advanced coordination primitives (AND gates, batching, correlation)

The analysis reveals opportunities for:
- Enhanced dependency injection
- Clearer orchestrator responsibilities
- Improved testability through interface segregation
- Better lifecycle management

---

## 1. Architectural Overview

### 1.1 Core Architecture Pattern

**Primary Pattern**: **Blackboard Architecture** (Event-driven coordination)

```
┌─────────────────────────────────────────────────────────┐
│                    Flock Orchestrator                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │          Blackboard (Artifact Store)             │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐ │   │
│  │  │ TypeA  │  │ TypeB  │  │ TypeC  │  │ TypeD  │ │   │
│  │  └────────┘  └────────┘  └────────┘  └────────┘ │   │
│  └──────────────────────────────────────────────────┘   │
│                         ▲                                │
│                         │ publish/consume                │
│  ┌──────────┬───────────┴────────┬───────────┬────────┐ │
│  │ Agent A  │  Agent B (waiting) │  Agent C  │ Agent D│ │
│  │ .consume(│  .consumes(TypeA,  │ .consumes(│.consume│ │
│  │  TypeA)  │   TypeB) - AND gate│  TypeC)   │ (TypeD)│ │
│  └──────────┴────────────────────┴───────────┴────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Key Characteristics**:
- **Knowledge Sources**: Agents publish artifacts to shared blackboard
- **Control**: Subscription-based routing (type + predicate matching)
- **Coordination**: AND gates, JoinSpec correlation, BatchSpec batching
- **Decoupling**: Agents don't know about each other

---

## 2. Component-by-Component Analysis

### 2.1 Orchestrator (`orchestrator.py`)

**Location**: `src/flock/orchestrator.py` (1107 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Facade** | `Flock` class unifies agent, store, MCP, batch/correlation engines | Lines 60-1106 |
| **Strategy** | Pluggable `BlackboardStore` | Line 121 |
| **Observer** | Subscription-based event notification | Lines 877-980 |
| **Builder** | `AgentBuilder` for fluent agent construction | Lines 153-184 |
| **Handle** | `BoardHandle` for controlled blackboard access | Lines 44-58 |

#### Responsibilities

**PRIMARY (Well-defined)**:
1. **Agent Lifecycle Management** (Lines 153-196)
   - Registration, retrieval, builder creation
   - Prevents duplicate agent names

2. **Event Scheduling** (Lines 872-1008)
   - Artifact routing via `_schedule_artifact`
   - Subscription matching (type, visibility, predicates)
   - Circuit breaker enforcement (Lines 886-890)
   - AND gate/JoinSpec/BatchSpec coordination

3. **MCP Integration** (Lines 200-326)
   - Server registration, lazy connection
   - Tool namespace management

4. **Tracing Infrastructure** (Lines 328-439)
   - Unified workflow traces via `traced_run`
   - Span management and context propagation

**SECONDARY (Could be extracted)**:
5. **Batch Management** (Lines 1031-1068)
   - Timeout checking, flush coordination
   - Tightly coupled to orchestrator event loop

6. **Dashboard Integration** (Lines 557-638)
   - Event collector injection
   - Launcher management
   - UI-specific concerns leaking into orchestrator

#### Architectural Strengths

✅ **Strong Separation of Concerns**:
- Agent management isolated from execution (lines 186-196)
- Storage abstraction prevents vendor lock-in (line 121)
- MCP lazy initialization reduces startup cost (lines 315-326)

✅ **Excellent Extensibility**:
- `BoardHandle` provides safe, controlled blackboard access (lines 44-58)
- `AgentBuilder` enables fluent configuration (lines 441-450)
- Multiple publish methods: `publish()`, `invoke()`, `publish_many()` (lines 641-840)

✅ **Scalability Considerations**:
- Circuit breaker prevents runaway loops (lines 886-890, 1000 iterations default)
- Async task management with `asyncio.create_task` (line 983)
- Store abstraction enables distributed backends (line 121)

#### Architectural Smells

⚠️ **God Object Tendency**:
- Orchestrator manages 6+ subsystems (agents, store, MCP, batch, correlation, dashboard)
- 1107 lines - approaching complexity threshold
- Example: Dashboard concerns (lines 557-638) could be external service

⚠️ **Hidden Dependencies**:
```python
# Line 487: Context creation buries dependency on BoardHandle
ctx = Context(
    board=BoardHandle(self),  # Tight coupling to orchestrator
    orchestrator=self,         # Circular reference
    task_id=str(uuid4())
)
```
Better: Dependency injection via constructor

⚠️ **Mixed Abstraction Levels**:
```python
# Lines 877-980: _schedule_artifact mixes high-level routing with low-level details
async def _schedule_artifact(self, artifact: Artifact) -> None:
    for agent in self.agents:
        # High-level: iterate agents
        identity = agent.identity
        for subscription in agent.subscriptions:
            # High-level: check subscriptions
            if not subscription.accepts_events():
                continue
            # Low-level: circuit breaker logic
            if self._agent_iteration_count.get(agent.name, 0) >= self.max_agent_iterations:
                continue
            # Low-level: visibility checking
            if not self._check_visibility(artifact, identity):
                continue
            # Low-level: JoinSpec correlation logic
            if subscription.join is not None:
                completed_group = self._correlation_engine.add_artifact(...)
            # Low-level: Batch accumulator logic
            if subscription.batch is not None:
                should_flush = self._batch_engine.add_artifact_group(...)
```

Could extract routing logic into `SubscriptionRouter` class.

#### Recommendations

**HIGH IMPACT**:
1. **Extract Dashboard Service** (Lines 557-638)
   ```python
   # orchestrator.py (before)
   async def serve(self, *, dashboard: bool = False):
       if dashboard:
           # 80 lines of dashboard setup

   # Proposed: dashboard_service.py
   class DashboardService:
       def __init__(self, orchestrator: Flock):
           self.orchestrator = orchestrator

       async def serve(self, host: str, port: int):
           # Dashboard-specific logic isolated
   ```

2. **Introduce SubscriptionRouter** (Lines 877-980)
   ```python
   # Proposed: subscription_router.py
   class SubscriptionRouter:
       def __init__(self,
                    correlation_engine: CorrelationEngine,
                    batch_engine: BatchEngine,
                    artifact_collector: ArtifactCollector):
           self.correlation_engine = correlation_engine
           self.batch_engine = batch_engine
           self.artifact_collector = artifact_collector

       async def route(self, artifact: Artifact, agents: list[Agent]) -> list[(Agent, list[Artifact])]:
           """Return (agent, artifacts) tuples ready for execution."""
           # Encapsulates routing logic
   ```

**MEDIUM IMPACT**:
3. **Use Dependency Injection for Context** (Line 487)
   ```python
   # Current: tight coupling
   ctx = Context(board=BoardHandle(self), orchestrator=self, task_id=str(uuid4()))

   # Proposed: inject dependencies
   class ContextFactory:
       def __init__(self, board_handle: BoardHandle, orchestrator: Flock):
           self.board_handle = board_handle
           self.orchestrator = orchestrator

       def create(self, task_id: str) -> Context:
           return Context(
               board=self.board_handle,
               orchestrator=self.orchestrator,
               task_id=task_id
           )
   ```

---

### 2.2 Agent (`agent.py`)

**Location**: `src/flock/agent.py` (1093 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Builder** | `AgentBuilder` for fluent configuration | Lines 441-1028 |
| **Template Method** | Agent execution lifecycle hooks | Lines 128-148 |
| **Chain of Responsibility** | Utility/engine processing pipeline | Lines 229-352 |
| **Semaphore** | Concurrency control via `asyncio.Semaphore` | Lines 104, 129 |

#### Responsibilities

**PRIMARY**:
1. **Subscription Management** (Lines 472-564)
   - Type declarations, predicates, JoinSpec, BatchSpec
   - Validation (prevent feedback loops - lines 936-958)

2. **Lifecycle Execution** (Lines 128-148)
   ```python
   async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
       async with self._semaphore:  # Concurrency control
           self._resolve_engines()
           self._resolve_utilities()
           await self._run_initialize(ctx)          # Phase 1
           processed_inputs = await self._run_pre_consume(ctx, artifacts)  # Phase 2
           eval_inputs = EvalInputs(artifacts=processed_inputs, state=dict(ctx.state))
           eval_inputs = await self._run_pre_evaluate(ctx, eval_inputs)    # Phase 3
           result = await self._run_engines(ctx, eval_inputs)              # Phase 4
           result = await self._run_post_evaluate(ctx, eval_inputs, result)  # Phase 5
           outputs = await self._make_outputs(ctx, result)                 # Phase 6
           await self._run_post_publish(ctx, outputs)                      # Phase 7
           if self.calls_func:
               await self._invoke_call(ctx, outputs or processed_inputs)   # Phase 8
           return outputs
   ```
   - 8-phase execution pipeline
   - Clear extension points for components

3. **MCP Tool Integration** (Lines 150-221)
   - Lazy tool loading from assigned servers
   - Graceful degradation on failure
   - Tool namespacing (`{server}__{tool}`)

4. **Best-of-N Evaluation** (Lines 276-288)
   - Parallel execution with `asyncio.TaskGroup`
   - Scoring function for result selection

#### Architectural Strengths

✅ **Excellent Lifecycle Design**:
- Clear phases with well-defined responsibilities
- Easy to inject custom behavior (utilities, engines)
- Clean separation: utilities transform, engines evaluate

✅ **Fluent Builder Pattern**:
```python
agent = (flock.agent("analyzer")
    .description("Analyzes data quality")
    .consumes(DataSet, where=lambda d: d.size > 1000)
    .publishes(QualityReport)
    .with_utilities(RateLimiter(max_calls=10))
    .with_engines(CustomEngine(model="gpt-4o"))
    .best_of(n=3, score=lambda r: r.metrics.get("confidence", 0))
)
```
- Readable, self-documenting configuration
- Type-safe (returns `AgentBuilder`)

✅ **MCP Graceful Degradation**:
```python
# Lines 150-221
async def _get_mcp_tools(self, ctx: Context) -> list[Callable]:
    try:
        manager = self._orchestrator.get_mcp_manager()
        tools_dict = await manager.get_tools_for_agent(...)
        return dspy_tools
    except Exception as e:
        logger.error(f"Failed to load MCP tools: {e}")
        return []  # Agent continues with native tools
```

#### Architectural Smells

⚠️ **Builder Ambiguity**:
```python
# Line 442: AgentBuilder serves dual purpose
class AgentBuilder:
    """Fluent builder that also acts as the runtime agent handle."""
```
- Violates Single Responsibility Principle
- Builder pattern implies immutability, but this mutates agent
- Confusion: Is it configuration or execution handle?

Better: Separate `AgentBuilder` (configuration) from `AgentHandle` (execution)

⚠️ **Tight Coupling to Orchestrator**:
```python
# Lines 93, 445-448
def __init__(self, name: str, *, orchestrator: Flock) -> None:
    self._orchestrator = orchestrator  # Direct dependency

class AgentBuilder:
    def __init__(self, orchestrator: Flock, name: str) -> None:
        self._orchestrator = orchestrator  # Agent references orchestrator
        self._agent = Agent(name, orchestrator=orchestrator)
        orchestrator.register_agent(self._agent)  # Side effect during construction
```
- Agent can access entire orchestrator state
- Hard to test in isolation
- Circular reference: orchestrator -> agent -> orchestrator

Better: Inject minimal interface (e.g., `MCPManager`, `Store`)

⚠️ **Mixed Concerns in `_select_payload`** (Lines 412-438):
```python
def _select_payload(self, output_decl: AgentOutput, result: EvalResult) -> dict[str, Any] | None:
    # Try to find artifact by type
    for artifact in result.artifacts:
        if artifact.type == output_decl.spec.type_name:
            return artifact.payload

    # FALLBACK: Search state dictionary (WHY?)
    maybe_data = result.state.get(output_decl.spec.type_name)
    if isinstance(maybe_data, dict):
        return maybe_data
    return None
```
- Inconsistent data sources (artifacts vs state)
- No clear precedence rules documented

#### Recommendations

**HIGH IMPACT**:
1. **Separate Builder from Handle** (Lines 441-1028)
   ```python
   # Proposed: agent_builder.py
   class AgentBuilder:
       """Immutable configuration builder."""
       def build(self) -> Agent:
           """Construct and register agent."""
           agent = Agent(name=self._name, config=self._config)
           self._orchestrator.register_agent(agent)
           return agent

   # Proposed: agent.py
   class Agent:
       """Runtime execution handle."""
       async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
           # Execution logic
   ```

2. **Inject Minimal Interfaces** (Lines 93, 445)
   ```python
   # Current: tight coupling
   def __init__(self, name: str, *, orchestrator: Flock):
       self._orchestrator = orchestrator

   # Proposed: interface segregation
   class AgentDependencies:
       mcp_manager: MCPManager
       store: BlackboardStore
       model: str

   def __init__(self, name: str, *, deps: AgentDependencies):
       self._deps = deps  # Only what agent needs
   ```

**MEDIUM IMPACT**:
3. **Document Payload Selection Rules** (Lines 412-438)
   ```python
   def _select_payload(self, output_decl: AgentOutput, result: EvalResult) -> dict[str, Any] | None:
       """Select payload for output declaration.

       Selection precedence:
       1. Artifact with matching type (primary output)
       2. State dictionary entry (for engines that only update state)
       3. None (agent didn't produce this type)
       """
   ```

---

### 2.3 Component System (`components.py`)

**Location**: `src/flock/components.py` (190 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Template Method** | Lifecycle hooks with default no-op implementations | Lines 60-89 |
| **Strategy** | Pluggable components for agent behavior | Lines 51-90 |
| **Hook Pattern** | 8 lifecycle extension points | Lines 60-89 |

#### Architecture

```
┌─────────────────────────────────────────────────────┐
│            AgentComponent (Base Class)               │
│  ┌──────────────────────────────────────────────┐   │
│  │ Lifecycle Hooks (Override in subclass):      │   │
│  │  • on_initialize(agent, ctx)                 │   │
│  │  • on_pre_consume(agent, ctx, inputs)        │   │
│  │  • on_pre_evaluate(agent, ctx, eval_inputs)  │   │
│  │  • on_post_evaluate(agent, ctx, inputs, res) │   │
│  │  • on_post_publish(agent, ctx, artifact)     │   │
│  │  • on_error(agent, ctx, error)               │   │
│  │  • on_terminate(agent, ctx)                  │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
         ▲                              ▲
         │                              │
┌────────┴────────┐           ┌────────┴────────┐
│ AgentComponent  │           │ EngineComponent │
│  (Utilities)    │           │  (Evaluation)   │
├─────────────────┤           ├─────────────────┤
│ • RateLimiter   │           │ • DSPyEngine    │
│ • TokenBudget   │           │ • CustomEngine  │
│ • CacheLayer    │           │ • ChainEngine   │
│ • Metrics       │           │                 │
└─────────────────┘           └─────────────────┘
```

#### Responsibilities

**AgentComponent** (Lines 51-90):
- Cross-cutting concerns (rate limiting, metrics, caching)
- Transform artifacts and evaluation inputs
- No evaluation logic

**EngineComponent** (Lines 92-183):
- Evaluation logic (LLM calls, rules, computations)
- Conversation context management (lines 112-182)
- Produces `EvalResult` with artifacts

#### Architectural Strengths

✅ **Clean Separation of Concerns**:
- Utilities: cross-cutting (logging, rate limiting)
- Engines: evaluation (LLM, rule-based)
- Clear responsibility boundaries

✅ **Excellent Extension Points**:
```python
class MyComponent(AgentComponent):
    async def on_pre_consume(self, agent: Agent, ctx: Context, inputs: list[Artifact]) -> list[Artifact]:
        # Transform artifacts before evaluation
        filtered = [a for a in inputs if a.payload.get("priority") > 5]
        return filtered
```

✅ **Auto-Tracing Built-in**:
```python
# Lines 24-29
class TracedModelMeta(ModelMetaclass, AutoTracedMeta):
    """Combined metaclass for Pydantic models with auto-tracing."""

class AgentComponent(BaseModel, metaclass=TracedModelMeta):
    # All methods automatically traced via OpenTelemetry
```

#### Architectural Smells

⚠️ **Context Fetching in EngineComponent** (Lines 112-182):
```python
async def fetch_conversation_context(self, ctx: Context, correlation_id: UUID | None = None) -> list[dict]:
    all_artifacts = await ctx.board.list()  # Fetches ALL artifacts from blackboard
    context_artifacts = [a for a in all_artifacts if a.correlation_id == target_correlation_id]
    # Filters in memory
```
- Performance issue: fetches entire blackboard, filters in memory
- Should use store query with correlation_id filter
- Violates Law of Demeter (reaches through ctx.board.list())

⚠️ **Mixed Abstraction in Config** (Lines 32-48):
```python
class AgentComponentConfig(BaseModel):
    enabled: bool = True
    model: str | None = None  # Why is "model" in generic config?

    @classmethod
    def with_fields(cls, **field_definitions) -> type[Self]:
        return create_model(f"Dynamic{cls.__name__}", __base__=cls, **field_definitions)
```
- `model` field is engine-specific, not generic component config
- Dynamic model creation (`with_fields`) adds complexity

#### Recommendations

**HIGH IMPACT**:
1. **Optimize Context Fetching** (Lines 112-182)
   ```python
   # Current: inefficient
   async def fetch_conversation_context(self, ctx: Context, correlation_id: UUID) -> list[dict]:
       all_artifacts = await ctx.board.list()  # Fetches ALL
       context_artifacts = [a for a in all_artifacts if a.correlation_id == target_correlation_id]

   # Proposed: delegate to store
   async def fetch_conversation_context(self, ctx: Context, correlation_id: UUID) -> list[dict]:
       # Let store do efficient filtering
       filters = FilterConfig(correlation_id=str(correlation_id))
       artifacts, _ = await ctx.orchestrator.store.query_artifacts(
           filters=filters,
           limit=self.context_max_artifacts or 100
       )
       return [self._artifact_to_context(a) for a in artifacts]
   ```

2. **Move Engine-specific Config** (Lines 32-48)
   ```python
   # Proposed: engine_config.py
   class EngineComponentConfig(AgentComponentConfig):
       model: str | None = None  # Engine-specific
       temperature: float = 0.7
       max_tokens: int = 1000
   ```

---

### 2.4 Subscription System (`subscription.py`)

**Location**: `src/flock/subscription.py` (175 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Specification** | `Subscription` encapsulates matching rules | Lines 94-166 |
| **Value Object** | `JoinSpec`, `BatchSpec`, `TextPredicate` immutable specs | Lines 22-92 |
| **Composite** | Multiple predicates combined with AND logic | Lines 154-160 |

#### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Subscription                          │
├─────────────────────────────────────────────────────────┤
│ Type Matching:   type_names: set[str]                   │
│                  type_counts: dict[str, int]  (AND gate)│
│ Producer Filter: from_agents: set[str]                  │
│ Channel Filter:  channels: set[str]                     │
│ Predicates:      where: list[Callable[[BaseModel], bool]]│
│ Text Similarity: text_predicates: list[TextPredicate]   │
│ Correlation:     join: JoinSpec | None                  │
│ Batching:        batch: BatchSpec | None                │
│ Delivery:        delivery: "exclusive" | "broadcast"    │
│ Mode:            mode: "events" | "direct" | "both"     │
│ Priority:        priority: int                          │
└─────────────────────────────────────────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
┌────────┴────────┐  ┌────────┴────────┐  ┌───────┴──────┐
│   JoinSpec      │  │   BatchSpec     │  │TextPredicate │
├─────────────────┤  ├─────────────────┤  ├──────────────┤
│ by: Callable    │  │ size: int?      │  │ text: str    │
│ within: Δt | int│  │ timeout: Δt?    │  │ min_p: float │
└─────────────────┘  └─────────────────┘  └──────────────┘
```

#### Responsibilities

**Subscription** (Lines 94-166):
1. **Matching Logic** (Lines 143-160)
   - Type matching, producer filtering, channel filtering
   - Predicate evaluation on typed payloads
   - Handles exceptions gracefully (returns False)

2. **Count-based AND Gates** (Lines 118-125)
   ```python
   # Example: .consumes(Task, Task, Alert) → {Task: 2, Alert: 1}
   type_name_list = [type_registry.register(t) for t in types]
   self.type_names: set[str] = set(type_name_list)
   self.type_counts: dict[str, int] = {}
   for type_name in type_name_list:
       self.type_counts[type_name] = self.type_counts.get(type_name, 0) + 1
   ```
   - Allows `.consumes(A, A, B)` → wait for 2 As and 1 B

**JoinSpec** (Lines 29-57):
- Correlated AND gates with time/count windows
- Example: Join X-ray + Lab results by patient_id within 5 minutes

**BatchSpec** (Lines 60-92):
- Size-based batching (e.g., 25 orders)
- Timeout-based batching (e.g., every 30 seconds)
- Whichever comes first wins

#### Architectural Strengths

✅ **Immutable Value Objects**:
- JoinSpec, BatchSpec, TextPredicate are `@dataclass` (immutable)
- No hidden state mutations
- Easy to reason about and test

✅ **Flexible Predicate Composition**:
```python
agent.consumes(
    Order,
    where=[
        lambda o: o.total > 100,
        lambda o: o.status == "pending",
        lambda o: o.customer_tier == "premium"
    ]
)
# All predicates evaluated with AND logic
```

✅ **Clear Separation of Coordination Primitives**:
- `where`: Filtering (stateless)
- `join`: Correlation (stateful, keyed)
- `batch`: Accumulation (stateful, time/size)

#### Architectural Smells

⚠️ **Exception Swallowing** (Lines 154-160):
```python
for predicate in self.where:
    try:
        if not predicate(payload):
            return False
    except Exception:  # Too broad
        return False  # Silent failure
```
- Any exception (AttributeError, TypeError, KeyError) silently fails
- No logging or debugging feedback
- Hard to diagnose predicate errors

Better: Log exception, re-raise in debug mode

⚠️ **Inconsistent Validation**:
- `BatchSpec.__post_init__` validates configuration (lines 89-91)
- `JoinSpec` has no validation (what if `within` is negative?)
- `Subscription` validates types but not predicates

#### Recommendations

**HIGH IMPACT**:
1. **Add Predicate Error Handling** (Lines 154-160)
   ```python
   # Current: silent failure
   for predicate in self.where:
       try:
           if not predicate(payload):
               return False
       except Exception:
           return False

   # Proposed: log and optionally raise
   for predicate in self.where:
       try:
           if not predicate(payload):
               return False
       except Exception as e:
           logger.warning(f"Predicate failed for {artifact.type}: {e}", exc_info=True)
           if os.getenv("FLOCK_STRICT_PREDICATES") == "true":
               raise  # Fail fast in dev/test
           return False
   ```

2. **Add JoinSpec Validation** (Lines 29-57)
   ```python
   @dataclass
   class JoinSpec:
       by: Callable[[BaseModel], Any]
       within: timedelta | int

       def __post_init__(self):
           if isinstance(self.within, int) and self.within <= 0:
               raise ValueError("Count window must be positive")
           if isinstance(self.within, timedelta) and self.within <= timedelta(0):
               raise ValueError("Time window must be positive")
   ```

---

### 2.5 Artifact Model (`artifacts.py`)

**Location**: `src/flock/artifacts.py` (87 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Value Object** | Immutable artifact envelope | Lines 15-31 |
| **Builder** | `ArtifactSpec` for construction | Lines 33-72 |
| **Registry** | Type registry integration | Lines 40-42, 56 |

#### Architecture

```
┌──────────────────────────────────────────────────────┐
│                     Artifact                          │
├──────────────────────────────────────────────────────┤
│ Metadata:                                            │
│  • id: UUID                    (unique identifier)   │
│  • type: str                   (type name from registry)│
│  • produced_by: str            (agent name)          │
│  • created_at: datetime        (timestamp)           │
│  • version: int                (artifact version)    │
│                                                      │
│ Routing:                                             │
│  • correlation_id: UUID?       (conversation tracking)│
│  • partition_key: str?         (sharding hint)       │
│  • tags: set[str]              (channel routing)     │
│  • visibility: Visibility      (access control)      │
│                                                      │
│ Content:                                             │
│  • payload: dict[str, Any]     (serialized data)     │
└──────────────────────────────────────────────────────┘
```

#### Responsibilities

**Artifact** (Lines 15-31):
- Immutable envelope for blackboard data
- Rich metadata for routing and tracing
- Pydantic serialization for storage

**ArtifactSpec** (Lines 33-72):
- Factory for validated artifact construction
- Type registry integration
- Payload validation via Pydantic

#### Architectural Strengths

✅ **Clean Separation of Metadata and Content**:
- Metadata: routing, access control, tracing
- Content: domain-specific payload
- Easy to add new metadata without changing payloads

✅ **Immutable by Default**:
- All fields non-mutable after creation
- Prevents accidental state mutations
- Thread-safe sharing across agents

✅ **Streaming Support** (Line 54):
```python
def build(self, *, artifact_id: UUID | None = None, ...) -> Artifact:
    # Phase 6: Use pre-generated ID if provided (for streaming message preview)
    if artifact_id is not None:
        artifact_kwargs["id"] = artifact_id
```
- Allows engines to generate ID upfront
- Streaming events use same ID as final artifact
- Prevents duplicate artifact tracking

#### Architectural Smells

⚠️ **Nullable Visibility Default** (Line 25):
```python
visibility: Visibility = Field(default_factory=lambda: ensure_visibility(None))
```
- Why lambda instead of direct `PublicVisibility()`?
- Extra layer of indirection (`ensure_visibility`)
- Inconsistent: other fields use direct defaults

⚠️ **Mixed Concerns in ArtifactEnvelope** (Lines 75-79):
```python
class ArtifactEnvelope(BaseModel):
    """Envelope passed to components/engines during evaluation."""
    artifact: Artifact
    state: dict[str, Any] = Field(default_factory=dict)
```
- Name collision: `ArtifactEnvelope` also in `store.py` (lines 105-109)
- Different semantics: artifacts.py → evaluation, store.py → consumption records
- Confusing naming

#### Recommendations

**LOW IMPACT**:
1. **Simplify Visibility Default** (Line 25)
   ```python
   # Current: unnecessary lambda
   visibility: Visibility = Field(default_factory=lambda: ensure_visibility(None))

   # Proposed: direct default
   visibility: Visibility = Field(default_factory=PublicVisibility)
   ```

2. **Rename ArtifactEnvelope** (Lines 75-79)
   ```python
   # Current: name collision with store.py
   class ArtifactEnvelope(BaseModel):
       """Envelope passed to components/engines during evaluation."""

   # Proposed: more specific name
   class EvaluationEnvelope(BaseModel):
       """Evaluation context containing artifact and state."""
   ```

---

### 2.6 Storage Abstraction (`store.py`)

**Location**: `src/flock/store.py` (1215 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Strategy** | `BlackboardStore` abstract base class | Lines 126-221 |
| **Factory** | Multiple store implementations (InMemory, SQLite) | Lines 223-433, 443-1215 |
| **Repository** | Centralized data access | Lines 126-221 |
| **Specification** | `FilterConfig` for query composition | Lines 92-102 |

#### Architecture

```
┌───────────────────────────────────────────────────────┐
│          BlackboardStore (Abstract Base)              │
├───────────────────────────────────────────────────────┤
│ Core Operations:                                      │
│  • publish(artifact)                                  │
│  • get(artifact_id) -> Artifact?                      │
│  • list() -> list[Artifact]                           │
│  • list_by_type(type_name) -> list[Artifact]          │
│  • get_by_type(artifact_type) -> list[T]              │
│                                                       │
│ Consumption Tracking:                                 │
│  • record_consumptions(records)                       │
│  • query_artifacts(filters) -> (artifacts, total)     │
│  • fetch_graph_artifacts(filters) -> (envelopes, ...)│
│                                                       │
│ Analytics:                                            │
│  • summarize_artifacts(filters) -> stats              │
│  • agent_history_summary(agent_id) -> produced/consumed│
│                                                       │
│ Agent Metadata:                                       │
│  • upsert_agent_snapshot(snapshot)                    │
│  • load_agent_snapshots() -> list[AgentSnapshotRecord]│
└───────────────────────────────────────────────────────┘
         ▲                              ▲
         │                              │
┌────────┴────────────┐     ┌──────────┴────────────┐
│ InMemoryBlackboard  │     │ SQLiteBlackboardStore │
│      Store          │     │                       │
├─────────────────────┤     ├───────────────────────┤
│ • Dict storage      │     │ • aiosqlite backend   │
│ • Fast, ephemeral   │     │ • Persistent          │
│ • Testing/dev       │     │ • Indexing            │
└─────────────────────┘     └───────────────────────┘
```

#### Responsibilities

**BlackboardStore Interface** (Lines 126-221):
- CRUD operations for artifacts
- Consumption tracking (who consumed what)
- Query with filtering (type, producer, correlation_id, time range)
- Analytics and summaries

**InMemoryBlackboardStore** (Lines 223-433):
- Simple dict-based storage
- Fast, no dependencies
- Suitable for dev, testing, demos

**SQLiteBlackboardStore** (Lines 443-1215):
- Production-ready persistent storage
- Async with `aiosqlite`
- Query optimization (indexes on type, producer, correlation_id)
- Schema versioning (lines 446, 985-1146)

#### Architectural Strengths

✅ **Excellent Abstraction**:
- Clear interface separation (lines 126-221)
- Easy to swap implementations (in-memory ↔ SQLite ↔ future: PostgreSQL, Redis)
- No vendor lock-in

✅ **Query Optimization** (Lines 678-769):
```python
async def query_artifacts(self, filters: FilterConfig, ...) -> tuple[list, int]:
    # Efficient SQL with indexes
    where_clause, params = self._build_filters(filters)

    # Count query (uses indexes)
    count_query = f"SELECT COUNT(*) AS total FROM artifacts{where_clause}"

    # Paginated fetch
    query = f"SELECT ... FROM artifacts {where_clause} ORDER BY created_at LIMIT ? OFFSET ?"
```
- Pagination support (avoid loading all artifacts)
- Index-friendly queries (lines 1075-1125)
- Prepared statements (SQL injection prevention)

✅ **Consumption Tracking** (Lines 528-560):
```python
async def record_consumptions(self, records: Iterable[ConsumptionRecord]) -> None:
    # Track which agent consumed which artifact
    # Enables analytics: "Who processed this artifact?"
    # Foundation for lineage tracking
```

✅ **Schema Evolution** (Lines 985-1146):
```python
SCHEMA_VERSION = 3  # Line 446

async def _apply_schema(self, conn: aiosqlite.Connection) -> None:
    # Create schema_meta table
    # Track schema version
    # Future: migrations between versions
```

#### Architectural Smells

⚠️ **Inconsistent Error Handling**:
```python
# Lines 154-159: NotImplementedError allowed
async def record_consumptions(self, records: Iterable[ConsumptionRecord]) -> None:
    raise NotImplementedError  # Base class

# Lines 1023-1027: Exception swallowed
try:
    await self.store.record_consumptions(records)
except NotImplementedError:
    pass  # Silent failure
except Exception as exc:
    self._logger.exception("Failed to record consumption: %s", exc)
```
- Inconsistent: some stores may not implement consumptions
- No way to detect feature support before calling

⚠️ **InMemory Store Lacks Pagination** (Lines 269-325):
```python
async def query_artifacts(self, filters: FilterConfig, *, limit: int = 50, offset: int = 0) -> ...:
    async with self._lock:
        artifacts = list(self._by_id.values())  # Load ALL artifacts

    filtered = [artifact for artifact in artifacts if _matches(artifact)]  # Filter in memory

    # Then paginate
    page = filtered[offset : offset + limit]
```
- Performance issue: loads entire blackboard, then filters
- SQLite version is more efficient (lines 678-769)

⚠️ **Name Collision** (Lines 105-109):
```python
# store.py
@dataclass(slots=True)
class ArtifactEnvelope:
    """Wrapper returned when ``embed_meta`` is requested."""
    artifact: Artifact
    consumptions: list[ConsumptionRecord] = field(default_factory=list)

# artifacts.py (Lines 75-79)
class ArtifactEnvelope(BaseModel):
    """Envelope passed to components/engines during evaluation."""
    artifact: Artifact
    state: dict[str, Any] = Field(default_factory=dict)
```
- Same name, different semantics
- Import collision risk

#### Recommendations

**HIGH IMPACT**:
1. **Feature Detection Interface** (Lines 154-159)
   ```python
   # Proposed: blackboard_store.py
   class BlackboardStore:
       def supports_consumptions(self) -> bool:
           """Check if store tracks consumption records."""
           return True  # Override to return False in minimal stores

       async def record_consumptions(self, records: Iterable[ConsumptionRecord]) -> None:
           if not self.supports_consumptions():
               raise NotImplementedError("This store doesn't support consumption tracking")
   ```

2. **Optimize InMemory Filtering** (Lines 269-325)
   ```python
   # Current: loads all, then filters
   artifacts = list(self._by_id.values())
   filtered = [artifact for artifact in artifacts if _matches(artifact)]

   # Proposed: filter during iteration
   def _filter_artifacts(self, filters: FilterConfig) -> Iterator[Artifact]:
       # Early return optimizations
       if filters.type_names:
           # Use _by_type index
           for type_name in filters.type_names:
               for artifact in self._by_type[type_name]:
                   if _matches_other_filters(artifact, filters):
                       yield artifact
       else:
           # Iterate all artifacts
           for artifact in self._by_id.values():
               if _matches(artifact, filters):
                   yield artifact
   ```

**MEDIUM IMPACT**:
3. **Rename Store's ArtifactEnvelope** (Lines 105-109)
   ```python
   # Current: name collision
   class ArtifactEnvelope:
       artifact: Artifact
       consumptions: list[ConsumptionRecord]

   # Proposed: more specific name
   class ConsumptionEnvelope:
       artifact: Artifact
       consumptions: list[ConsumptionRecord]
   ```

---

### 2.7 Correlation Engine (`correlation_engine.py`)

**Location**: `src/flock/correlation_engine.py` (219 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **State Machine** | CorrelationGroup tracks incomplete → complete transitions | Lines 22-87 |
| **Registry** | Groups keyed by (agent, subscription, correlation_key) | Lines 122-124 |
| **Strategy** | Time window vs count window strategies | Lines 65-76 |

#### Architecture

```
┌──────────────────────────────────────────────────────┐
│              CorrelationEngine                        │
├──────────────────────────────────────────────────────┤
│ Global State:                                        │
│  • global_sequence: int (for count windows)          │
│  • correlation_groups: dict[(agent, sub_idx),        │
│                              dict[key, Group]]       │
│                                                      │
│ Operations:                                          │
│  • add_artifact() -> CorrelationGroup?               │
│    - Extract correlation key via JoinSpec.by         │
│    - Add to group's waiting pool                     │
│    - Check completion                                │
│    - Return group if complete, else None             │
│  • cleanup_expired()                                 │
└──────────────────────────────────────────────────────┘
         ▲
         │ manages
         │
┌────────┴────────────────────────────────────────────┐
│           CorrelationGroup                          │
├─────────────────────────────────────────────────────┤
│ Configuration:                                      │
│  • correlation_key: Any (e.g., patient_id)          │
│  • required_types: set[str] (e.g., {XRay, LabResult})│
│  • type_counts: dict[str, int] (e.g., {XRay: 1, ...})│
│  • window_spec: timedelta | int (5 minutes or 10 seq)│
│                                                     │
│ State:                                              │
│  • waiting_artifacts: dict[type, list[Artifact]]    │
│  • created_at_time: datetime (first artifact arrival)│
│  • created_at_sequence: int (global sequence number)│
│                                                     │
│ Methods:                                            │
│  • add_artifact(artifact)                           │
│  • is_complete() -> bool                            │
│  • is_expired(current_sequence) -> bool             │
│  • get_artifacts() -> list[Artifact]                │
└─────────────────────────────────────────────────────┘
```

#### Responsibilities

**CorrelationEngine** (Lines 89-216):
1. **Key Extraction** (Lines 150-160)
   - Parse artifact payload
   - Call `JoinSpec.by` lambda to extract correlation key
   - Handle extraction failures gracefully

2. **Group Management** (Lines 164-190)
   - Create/retrieve correlation groups per key
   - Handle window expiry (recreate group if expired)
   - Track global sequence for count windows

3. **Completion Detection** (Lines 195-199)
   - Check if all required types arrived
   - Remove completed group from tracking
   - Return artifacts for agent execution

**CorrelationGroup** (Lines 22-87):
1. **Artifact Accumulation** (Lines 52-57)
   - Store artifacts by type
   - Track arrival time for time windows

2. **Completion Logic** (Lines 59-63)
   - Check if all type counts satisfied
   - Example: `.consumes(A, B, join=...)` → wait for 1 A and 1 B

3. **Expiry Logic** (Lines 65-76)
   ```python
   def is_expired(self, current_sequence: int) -> bool:
       if isinstance(self.window_spec, int):
           # Count window: expire after N artifacts published
           return (current_sequence - self.created_at_sequence) > self.window_spec
       elif isinstance(self.window_spec, timedelta):
           # Time window: expire after duration elapsed
           elapsed = datetime.now() - self.created_at_time
           return elapsed > self.window_spec
   ```

#### Architectural Strengths

✅ **Clean State Machine**:
- Groups transition: waiting → complete (removed)
- Clear states: incomplete (collecting) vs complete (returned to orchestrator)
- No lingering state after completion

✅ **Dual Window Strategy**:
```python
# Time-based correlation (wait up to 5 minutes)
JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5))

# Count-based correlation (wait up to next 10 artifacts)
JoinSpec(by=lambda x: x.correlation_id, within=10)
```
- Time windows: real-world time constraints
- Count windows: relative artifact ordering

✅ **Graceful Key Extraction** (Lines 155-160):
```python
try:
    correlation_key = join_spec.by(payload_instance)
except Exception as e:
    # Key extraction failed - skip this artifact
    return None  # Agent won't be triggered
```
- Handles user-provided lambda failures
- Prevents orchestrator crashes from bad predicates

#### Architectural Smells

⚠️ **Global Sequence Not Persisted**:
```python
# Line 117
self.global_sequence = 0  # In-memory counter

# Lines 139-140
self.global_sequence += 1
current_sequence = self.global_sequence
```
- Count windows break on orchestrator restart
- No coordination across distributed orchestrators
- Should use blackboard-level sequence or timestamp

⚠️ **No Cleanup Trigger**:
```python
# Lines 204-215: cleanup_expired method exists but never called automatically
def cleanup_expired(self, agent_name: str, subscription_index: int) -> None:
    """Clean up expired correlation groups for a specific subscription."""
    # Manual cleanup - not triggered automatically
```
- Expired groups linger in memory until manually cleaned
- Memory leak risk for high-correlation workloads
- Should have periodic background task

⚠️ **Inconsistent Time Source**:
```python
# Line 54: uses datetime.now() (no timezone)
self.created_at_time = datetime.now()

# Line 74: uses datetime.now() again (no timezone)
elapsed = datetime.now() - self.created_at_time
```
- Should use `datetime.now(timezone.utc)` for consistency
- Time zone ambiguity

#### Recommendations

**HIGH IMPACT**:
1. **Add Automatic Cleanup** (Lines 204-215)
   ```python
   # Proposed: orchestrator.py
   class Flock:
       def __init__(self, ...):
           self._correlation_engine = CorrelationEngine()
           self._cleanup_task = None

       async def _start_cleanup_task(self):
           """Periodically clean up expired correlation groups."""
           while True:
               await asyncio.sleep(60)  # Check every minute
               for agent in self.agents:
                   for sub_idx, subscription in enumerate(agent.subscriptions):
                       if subscription.join:
                           self._correlation_engine.cleanup_expired(agent.name, sub_idx)
   ```

2. **Use Artifact-based Sequence** (Line 117)
   ```python
   # Current: in-memory sequence
   self.global_sequence = 0

   # Proposed: use artifact timestamps or store sequence
   async def _get_next_sequence(self) -> int:
       # Option 1: Use artifact count from store
       artifacts = await self.store.list()
       return len(artifacts)

       # Option 2: Use store-level sequence (if available)
       return await self.store.get_sequence()
   ```

**MEDIUM IMPACT**:
3. **Use UTC Timestamps** (Lines 54, 74)
   ```python
   # Current: no timezone
   self.created_at_time = datetime.now()

   # Proposed: explicit UTC
   from datetime import timezone
   self.created_at_time = datetime.now(timezone.utc)
   ```

---

### 2.8 Batch Accumulator (`batch_accumulator.py`)

**Location**: `src/flock/batch_accumulator.py` (253 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Accumulator** | Collects artifacts until threshold | Lines 23-72 |
| **Registry** | Batches keyed by (agent, subscription_index) | Line 104 |
| **Strategy** | Size vs timeout flushing strategies | Lines 42-63 |

#### Architecture

```
┌──────────────────────────────────────────────────────┐
│                 BatchEngine                           │
├──────────────────────────────────────────────────────┤
│ State:                                               │
│  • batches: dict[(agent, sub_idx), BatchAccumulator] │
│                                                      │
│ Operations:                                          │
│  • add_artifact() -> bool (flush?)                   │
│  • add_artifact_group() -> bool (for JoinSpec+Batch) │
│  • flush_batch() -> list[Artifact]?                  │
│  • check_timeouts() -> list[(agent, sub_idx)]        │
│  • flush_all() -> list[(agent, sub_idx, artifacts)]  │
└──────────────────────────────────────────────────────┘
         ▲
         │ manages
         │
┌────────┴────────────────────────────────────────────┐
│            BatchAccumulator                         │
├─────────────────────────────────────────────────────┤
│ Configuration:                                      │
│  • batch_spec: BatchSpec (size + timeout)           │
│  • created_at: datetime (first artifact)            │
│                                                     │
│ State:                                              │
│  • artifacts: list[Artifact]                        │
│                                                     │
│ Methods:                                            │
│  • add_artifact() -> bool (flush?)                  │
│  • is_timeout_expired() -> bool                     │
│  • get_artifacts() -> list[Artifact]                │
│  • clear()                                          │
└─────────────────────────────────────────────────────┘
```

#### Responsibilities

**BatchEngine** (Lines 74-250):
1. **Artifact Accumulation** (Lines 106-136)
   - Add artifacts to batch per (agent, subscription_index)
   - Check size threshold after each add
   - Return True if batch ready to flush

2. **Group Batching** (Lines 138-195)
   - Special handling for JoinSpec + BatchSpec
   - Example: "Batch 5 correlated pairs" (not 5 individual artifacts)
   - Track group count separately from artifact count

3. **Timeout Checking** (Lines 216-229)
   - Check all batches for timeout expiry
   - Return list of expired batch keys
   - Orchestrator responsible for flushing

4. **Shutdown Flush** (Lines 231-249)
   - Zero data loss: flush all partial batches
   - Called during orchestrator shutdown

**BatchAccumulator** (Lines 23-72):
1. **Size-based Flushing** (Lines 42-55)
   ```python
   def add_artifact(self, artifact: Artifact) -> bool:
       self.artifacts.append(artifact)
       if self.batch_spec.size is not None:
           if len(self.artifacts) >= self.batch_spec.size:
               return True  # Flush now
       return False
   ```

2. **Timeout Detection** (Lines 57-63)
   ```python
   def is_timeout_expired(self) -> bool:
       if self.batch_spec.timeout is None:
           return False
       elapsed = datetime.now() - self.created_at
       return elapsed >= self.batch_spec.timeout
   ```

#### Architectural Strengths

✅ **Zero Data Loss**:
```python
# Lines 231-249: flush_all ensures no artifacts lost
def flush_all(self) -> list[tuple[str, int, list[Artifact]]]:
    """Flush ALL partial batches (for shutdown)."""
    results = []
    for batch_key, accumulator in list(self.batches.items()):
        if accumulator.artifacts:
            artifacts = accumulator.get_artifacts()
            results.append((agent_name, subscription_index, artifacts))
    self.batches.clear()
    return results
```
- Called during orchestrator shutdown
- Ensures partial batches are processed

✅ **Flexible Batching Strategies**:
```python
# Size-only batching
BatchSpec(size=25)  # Flush when 25 artifacts accumulated

# Timeout-only batching
BatchSpec(timeout=timedelta(seconds=30))  # Flush every 30 seconds

# Hybrid (whichever comes first)
BatchSpec(size=100, timeout=timedelta(minutes=5))
```

✅ **JoinSpec + BatchSpec Composition** (Lines 138-195):
```python
# Complex coordination: batch correlated groups
agent.consumes(
    XRay, LabResult,
    join={"by": lambda x: x.patient_id, "within": timedelta(minutes=5)},
    batch={"size": 5, "timeout": timedelta(seconds=30)}
)
# Wait for correlated pairs, then batch 5 pairs together
```

#### Architectural Smells

⚠️ **Group Count Tracking Hack** (Lines 186-192):
```python
# HACK: Dynamic attribute for group counting
if not hasattr(accumulator, '_group_count'):
    accumulator._group_count = 0

accumulator._group_count += 1

if accumulator._group_count >= subscription.batch.size:
    return True  # Flush now
```
- Uses `hasattr` to check for dynamic attribute
- Not type-safe
- Should be explicit field in `BatchAccumulator`

⚠️ **No Timeout Triggering in Orchestrator**:
```python
# Lines 216-229: check_timeouts returns expired batches
def check_timeouts(self) -> list[tuple[str, int]]:
    """Check all batches for timeout expiry."""
    expired = []
    for batch_key, accumulator in list(self.batches.items()):
        if accumulator.is_timeout_expired():
            expired.append(batch_key)
    return expired

# But orchestrator never calls this automatically!
# Only called in tests: tests/test_batch_accumulator.py
```
- Timeout batching requires manual orchestrator integration
- Not documented
- Users may expect automatic timeout flushing

⚠️ **Time Source Inconsistency** (Line 128, 60):
```python
# Line 128: no timezone
created_at=datetime.now()

# Line 60: no timezone
elapsed = datetime.now() - self.created_at
```
- Should use `datetime.now(timezone.utc)`

#### Recommendations

**HIGH IMPACT**:
1. **Add Group Count Field** (Lines 186-192)
   ```python
   # Current: dynamic attribute hack
   if not hasattr(accumulator, '_group_count'):
       accumulator._group_count = 0

   # Proposed: batch_accumulator.py
   class BatchAccumulator:
       def __init__(self, *, batch_spec: BatchSpec, created_at: datetime):
           self.batch_spec = batch_spec
           self.created_at = created_at
           self.artifacts: list[Artifact] = []
           self.group_count: int = 0  # Explicit field

       def add_group(self, artifacts: list[Artifact]) -> bool:
           """Add a GROUP of artifacts (for JoinSpec+BatchSpec)."""
           self.artifacts.extend(artifacts)
           self.group_count += 1
           if self.batch_spec.size is not None:
               return self.group_count >= self.batch_spec.size
           return False
   ```

2. **Automatic Timeout Flushing** (Lines 216-229)
   ```python
   # Proposed: orchestrator.py
   class Flock:
       async def _start_batch_timeout_task(self):
           """Periodically flush expired batches."""
           while True:
               await asyncio.sleep(1)  # Check every second
               expired_batches = self._batch_engine.check_timeouts()
               for agent_name, subscription_index in expired_batches:
                   artifacts = self._batch_engine.flush_batch(agent_name, subscription_index)
                   if artifacts:
                       agent = self._agents[agent_name]
                       self._schedule_task(agent, artifacts)
   ```

**MEDIUM IMPACT**:
3. **Use UTC Timestamps** (Lines 128, 60)
   ```python
   # Current: no timezone
   created_at=datetime.now()

   # Proposed: explicit UTC
   from datetime import timezone
   created_at=datetime.now(timezone.utc)
   ```

---

### 2.9 Artifact Collector (`artifact_collector.py`)

**Location**: `src/flock/artifact_collector.py` (160 lines)

#### Architectural Patterns

| Pattern | Implementation | Location |
|---------|---------------|----------|
| **Waiting Pool** | Collects artifacts until AND gate complete | Lines 25-155 |
| **Registry** | Pools keyed by (agent, subscription_index) | Lines 46-48 |

#### Architecture

```
┌──────────────────────────────────────────────────────┐
│            ArtifactCollector                          │
├──────────────────────────────────────────────────────┤
│ State:                                               │
│  • _waiting_pools: dict[(agent, sub_idx),            │
│                         dict[type, list[Artifact]]]  │
│                                                      │
│ Example pool:                                        │
│  ("diagnostician", 0): {                             │
│      "XRay": [artifact1],                            │
│      "LabResult": []  # Waiting for lab result       │
│  }                                                   │
│                                                      │
│ Operations:                                          │
│  • add_artifact() -> (is_complete, artifacts)        │
│  • get_waiting_status() -> dict[type, list]          │
│  • clear_waiting_pool()                              │
│  • clear_all_pools()                                 │
└──────────────────────────────────────────────────────┘
```

#### Responsibilities

**ArtifactCollector** (Lines 25-157):
1. **AND Gate Logic** (Lines 50-115)
   ```python
   def add_artifact(self, agent: Agent, subscription: Subscription, artifact: Artifact) -> tuple[bool, list[Artifact]]:
       # Single-type: immediate trigger
       if len(subscription.type_names) == 1 and subscription.type_counts[artifact.type] == 1:
           return (True, [artifact])

       # Multi-type: collect until complete
       self._waiting_pools[pool_key][artifact.type].append(artifact)

       # Check completion
       is_complete = all(
           len(self._waiting_pools[pool_key][type_name]) >= required_count
           for type_name, required_count in subscription.type_counts.items()
       )

       if is_complete:
           # Collect all artifacts and clear pool
           artifacts = []
           for type_name, required_count in subscription.type_counts.items():
               artifacts.extend(self._waiting_pools[pool_key][type_name][:required_count])
           del self._waiting_pools[pool_key]
           return (True, artifacts)
       else:
           return (False, [])
   ```

2. **Count-based AND Gates** (Lines 98-109)
   - Example: `.consumes(Task, Task, Alert)` → wait for 2 Tasks + 1 Alert
   - Uses `subscription.type_counts` to track required counts

3. **Pool Management** (Lines 117-155)
   - Inspection: `get_waiting_status()` for debugging
   - Cleanup: `clear_waiting_pool()`, `clear_all_pools()`

#### Architectural Strengths

✅ **Simple, Correct AND Gate Logic**:
- Clear completion condition: all type counts satisfied
- Automatic cleanup after triggering
- No state leaks

✅ **Single-type Optimization** (Lines 75-76):
```python
if len(subscription.type_names) == 1 and subscription.type_counts[artifact.type] == 1:
    return (True, [artifact])  # Bypass waiting pool
```
- Most common case (single-type subscriptions) has O(1) path
- No unnecessary pool allocation

✅ **Count-based AND Gate Support** (Lines 98-109):
```python
# .consumes(Task, Task, Alert) → {"Task": 2, "Alert": 1}
is_complete = True
for type_name, required_count in subscription.type_counts.items():
    collected_count = len(self._waiting_pools[pool_key][type_name])
    if collected_count < required_count:
        is_complete = False
        break
```
- Handles duplicate types (e.g., wait for 2 Tasks)

#### Architectural Smells

⚠️ **No Expiry/Timeout**:
```python
# Line 93: artifacts added to pool indefinitely
self._waiting_pools[pool_key][artifact.type].append(artifact)

# No timeout mechanism
# Pool grows unbounded if not all types arrive
```
- If one type never arrives, pool leaks memory
- No way to expire incomplete AND gates
- Example: Wait for TypeA + TypeB, but TypeB never published

⚠️ **No Pool Size Limit**:
```python
# Line 93: unlimited artifact accumulation
self._waiting_pools[pool_key][artifact.type].append(artifact)
```
- If TypeA published 1000 times while waiting for TypeB, pool has 1000 TypeA artifacts
- Should limit pool size per type (e.g., keep only latest N)

⚠️ **Hardcoded to AND Logic**:
```python
# Lines 96-101: Only AND gate (all types required)
is_complete = True
for type_name, required_count in subscription.type_counts.items():
    if collected_count < required_count:
        is_complete = False
        break
```
- No support for OR gates (any type triggers)
- No support for M-of-N gates (e.g., any 2 of 3 types)

#### Recommendations

**HIGH IMPACT**:
1. **Add Pool Expiry** (Lines 50-115)
   ```python
   # Proposed: artifact_collector.py
   class PoolEntry:
       artifacts: list[Artifact]
       created_at: datetime
       ttl: timedelta

   class ArtifactCollector:
       def __init__(self, *, default_ttl: timedelta = timedelta(minutes=10)):
           self.default_ttl = default_ttl
           self._waiting_pools: dict[tuple[str, int], dict[str, PoolEntry]] = ...

       def add_artifact(self, ...) -> tuple[bool, list[Artifact]]:
           # Check expiry before adding
           pool = self._waiting_pools[pool_key]
           for type_name, entry in list(pool.items()):
               if datetime.now(timezone.utc) - entry.created_at > entry.ttl:
                   del pool[type_name]  # Expire old artifacts

           # Then add new artifact
           ...
   ```

2. **Add Pool Size Limit** (Line 93)
   ```python
   # Proposed: limit artifacts per type
   class ArtifactCollector:
       def __init__(self, *, max_pool_size_per_type: int = 100):
           self.max_pool_size_per_type = max_pool_size_per_type

       def add_artifact(self, ...) -> tuple[bool, list[Artifact]]:
           pool = self._waiting_pools[pool_key]
           type_artifacts = pool[artifact.type]

           # Keep only latest N artifacts per type
           if len(type_artifacts) >= self.max_pool_size_per_type:
               type_artifacts.pop(0)  # Remove oldest

           type_artifacts.append(artifact)
   ```

**MEDIUM IMPACT**:
3. **Support OR Gates** (Lines 96-101)
   ```python
   # Proposed: subscription.py
   @dataclass
   class GateSpec:
       logic: Literal["AND", "OR", "M_OF_N"]
       m: int | None = None  # For M-of-N gates

   class Subscription:
       gate: GateSpec = field(default=GateSpec(logic="AND"))

   # Proposed: artifact_collector.py
   def add_artifact(self, ...) -> tuple[bool, list[Artifact]]:
       if subscription.gate.logic == "OR":
           # Trigger immediately when ANY type arrives
           return (True, [artifact])
       elif subscription.gate.logic == "AND":
           # Current logic: wait for ALL types
           ...
       elif subscription.gate.logic == "M_OF_N":
           # Trigger when M of N types arrived
           ...
   ```

---

## 3. Cross-Cutting Architectural Concerns

### 3.1 Visibility System (`visibility.py`)

**Location**: `src/flock/visibility.py` (108 lines)

#### Pattern: Strategy with Polymorphism

```
┌──────────────────────────────────────────┐
│     Visibility (Abstract Base)           │
│  • allows(agent: AgentIdentity) -> bool  │
└──────────────────────────────────────────┘
         ▲
         │
┌────────┼────────┬────────┬────────┬──────────┐
│        │        │        │        │          │
Public  Private Labelled Tenant  After       ...
 (all)  (list)   (labels) (tenant)(temporal) (custom)
```

**Strengths**:
- Clean polymorphic design
- Easy to add new visibility policies (just subclass `Visibility`)
- Type-safe via Pydantic discriminated union

**Example Usage**:
```python
# Public: all agents can see
agent.publishes(Report, visibility=PublicVisibility())

# Private: only specific agents
agent.publishes(Secret, visibility=PrivateVisibility(agents={"admin", "auditor"}))

# Labelled: role-based access
agent.publishes(Invoice, visibility=LabelledVisibility(required_labels={"finance"}))

# Tenant: multi-tenant isolation
agent.publishes(Data, visibility=TenantVisibility(tenant_id="acme-corp"))

# Temporal: delayed visibility
agent.publishes(Draft, visibility=AfterVisibility(ttl=timedelta(hours=24), then=PublicVisibility()))
```

**Integration Point**:
```python
# orchestrator.py (Line 1090-1094)
def _check_visibility(self, artifact: Artifact, identity: AgentIdentity) -> bool:
    try:
        return artifact.visibility.allows(identity)
    except AttributeError:  # pragma: no cover - fallback for dict vis
        return True
```

---

### 3.2 Type Registry System (`registry.py`)

**Location**: `src/flock/registry.py` (149 lines)

#### Pattern: Registry with Bidirectional Mapping

```
┌──────────────────────────────────────────────────┐
│            TypeRegistry                          │
├──────────────────────────────────────────────────┤
│ _by_name: dict[str, type[BaseModel]]             │
│   "acme.models.Task" -> Task class               │
│                                                  │
│ _by_cls: dict[type[BaseModel], str]              │
│   Task class -> "acme.models.Task"               │
│                                                  │
│ Operations:                                      │
│  • register(model, name?) -> str                 │
│  • resolve(type_name) -> type[BaseModel]         │
│  • resolve_name(type_name) -> canonical_name     │
│  • name_for(model) -> str                        │
└──────────────────────────────────────────────────┘
```

**Strengths**:
- **Canonical Names**: Prevents type name collisions (lines 30-42)
- **Simple Name Resolution**: `"Task"` → `"__main__.Task"` (lines 50-79)
- **Automatic Registration**: Types registered on first use

**Ambiguity Handling**:
```python
# Lines 67-79
def resolve_name(self, type_name: str) -> str:
    # If already canonical, return as-is
    if type_name in self._by_name:
        return type_name

    # Search for models with matching simple name
    matches = [canonical for canonical, model in self._by_name.items()
               if model.__name__ == type_name]

    if len(matches) == 0:
        raise RegistryError(f"Unknown artifact type '{type_name}'.")
    if len(matches) == 1:
        return matches[0]
    raise RegistryError(f"Ambiguous type name '{type_name}'. Use qualified name.")
```

**Integration**:
- Used by `Subscription` for type matching (subscription.py:118)
- Used by `Agent` for payload deserialization (agent.py:336)
- Used by `Store` for canonical type storage (store.py:466)

---

### 3.3 Lifecycle Management

#### Agent Execution Lifecycle

```
┌──────────────────────────────────────────────────────┐
│              Agent.execute(ctx, artifacts)           │
└──────────────────────────────────────────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   PHASE 1: Initialize          │
      │   • utilities.on_initialize()  │
      │   • engines.on_initialize()    │
      └───────────────┬────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   PHASE 2: Pre-Consume         │
      │   • utilities.on_pre_consume() │
      │   • Transform artifacts        │
      └───────────────┬────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   PHASE 3: Pre-Evaluate        │
      │   • utilities.on_pre_evaluate()│
      │   • Transform eval inputs      │
      └───────────────┬────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   PHASE 4: Evaluate            │
      │   • engines.evaluate()         │
      │   • LLM calls, computations    │
      │   • Best-of-N if configured    │
      └───────────────┬────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   PHASE 5: Post-Evaluate       │
      │   • utilities.on_post_evaluate()│
      │   • Transform eval result      │
      └───────────────┬────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   PHASE 6: Make Outputs        │
      │   • _make_outputs()            │
      │   • Publish artifacts to board │
      └───────────────┬────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   PHASE 7: Post-Publish        │
      │   • utilities.on_post_publish()│
      │   • Notifications, metrics     │
      └───────────────┬────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   PHASE 8: Calls (Optional)    │
      │   • agent.calls_func()         │
      │   • User-defined callback      │
      └───────────────┬────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │   FINALLY: Terminate           │
      │   • utilities.on_terminate()   │
      │   • engines.on_terminate()     │
      │   • Cleanup resources          │
      └────────────────────────────────┘
```

**Error Handling**:
```python
# agent.py (Lines 128-148)
async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
    async with self._semaphore:  # Concurrency control
        try:
            # Phases 1-8
            ...
        except Exception as exc:
            await self._run_error(ctx, exc)  # Notify utilities/engines
            raise  # Propagate to orchestrator
        finally:
            await self._run_terminate(ctx)  # Always cleanup
```

---

### 3.4 Concurrency Model

#### Orchestrator Task Management

```python
# orchestrator.py (Lines 982-985)
def _schedule_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
    task = asyncio.create_task(self._run_agent_task(agent, artifacts))
    self._tasks.add(task)
    task.add_done_callback(self._tasks.discard)  # Auto-cleanup
```

**Characteristics**:
- **Fire-and-forget**: Agents run as independent tasks
- **No backpressure**: Unlimited task creation (potential memory issue)
- **Graceful shutdown**: `run_until_idle()` waits for all tasks

#### Agent Concurrency Control

```python
# agent.py (Lines 104, 121-123)
self._semaphore = asyncio.Semaphore(self.max_concurrency)

async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
    async with self._semaphore:  # Limit concurrent executions
        # Agent execution
```

**Characteristics**:
- **Per-agent concurrency**: Each agent has own semaphore
- **Default**: 2 concurrent executions per agent (line 103)
- **Configurable**: `.max_concurrency(n)` (line 706)

---

## 4. Data Flow Architecture

### 4.1 Event-Driven Artifact Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        USER/EXTERNAL                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │ flock.publish(obj)    │
              └───────────┬───────────┘
                          │
              ┌───────────▼──────────────────────────────────┐
              │ Orchestrator._persist_and_schedule(artifact) │
              ├──────────────────────────────────────────────┤
              │ 1. await store.publish(artifact)             │
              │ 2. await _schedule_artifact(artifact)        │
              └───────────┬──────────────────────────────────┘
                          │
    ┌─────────────────────┴─────────────────────┐
    │ _schedule_artifact (Routing Logic)        │
    ├───────────────────────────────────────────┤
    │ FOR EACH agent:                           │
    │   FOR EACH subscription:                  │
    │     ✓ Check event mode                    │
    │     ✓ Check prevent_self_trigger          │
    │     ✓ Check circuit breaker               │
    │     ✓ Check visibility                    │
    │     ✓ Check type/predicate match          │
    │     ✓ Check from_agents/channels          │
    │                                           │
    │     IF JoinSpec:                          │
    │       → CorrelationEngine (wait for all)  │
    │       → Return if incomplete              │
    │                                           │
    │     IF BatchSpec:                         │
    │       → BatchEngine (accumulate)          │
    │       → Return if not ready to flush      │
    │                                           │
    │     IF AND gate (multi-type):             │
    │       → ArtifactCollector (wait for all)  │
    │       → Return if incomplete              │
    │                                           │
    │     ✓ Mark artifacts as processed         │
    │     ✓ Schedule agent task                 │
    └───────────┬───────────────────────────────┘
                │
    ┌───────────▼───────────────────────────────┐
    │ _run_agent_task(agent, artifacts)         │
    ├───────────────────────────────────────────┤
    │ 1. Create Context (board handle, task_id) │
    │ 2. await agent.execute(ctx, artifacts)    │
    │ 3. Record consumption (store)             │
    └───────────┬───────────────────────────────┘
                │
    ┌───────────▼───────────────────────────────┐
    │ agent.execute(ctx, artifacts)             │
    ├───────────────────────────────────────────┤
    │ • 8-phase lifecycle (see Section 3.3)     │
    │ • Utilities transform artifacts           │
    │ • Engines evaluate                        │
    │ • Outputs published to blackboard         │
    └───────────┬───────────────────────────────┘
                │
    ┌───────────▼───────────────────────────────┐
    │ _make_outputs(ctx, result)                │
    ├───────────────────────────────────────────┤
    │ FOR EACH output_decl:                     │
    │   • Find matching artifact in result      │
    │   • Select payload (artifact or state)    │
    │   • Build Artifact with metadata          │
    │   • await ctx.board.publish(artifact)     │
    └───────────┬───────────────────────────────┘
                │
    ┌───────────▼───────────────────────────────┐
    │ BoardHandle.publish(artifact)             │
    │  → orchestrator._persist_and_schedule()   │
    └───────────────────────────────────────────┘
                ↓
          (CASCADE: New artifacts trigger other agents)
```

### 4.2 Bottlenecks and Performance Considerations

**1. Subscription Matching** (orchestrator.py:877-980)
- **O(N × M)** where N = agents, M = subscriptions per agent
- Every published artifact scanned against all subscriptions
- Mitigation: Could use type-based indexing

**2. Store Operations**
- InMemory: O(N) filtering (loads all artifacts)
- SQLite: O(log N) with indexes (efficient)
- Recommendation: Always use SQLite for production

**3. Correlation/Batch Engines**
- Correlation: O(G) where G = active correlation groups
- Batch: O(B) where B = active batches
- Both grow with subscription diversity

**4. Task Creation**
- Unlimited: `asyncio.create_task()` without backpressure
- Risk: Memory exhaustion with high artifact velocity
- Recommendation: Add orchestrator-level semaphore

---

## 5. Scalability Analysis

### 5.1 Horizontal Scalability Challenges

**Current Limitations**:

1. **In-Memory State** (Stateful Components)
   - CorrelationEngine: `global_sequence`, `correlation_groups`
   - BatchEngine: `batches`
   - ArtifactCollector: `_waiting_pools`
   - **Cannot distribute** across multiple orchestrator instances

2. **Circuit Breaker** (orchestrator.py:888-890)
   ```python
   iteration_count = self._agent_iteration_count.get(agent.name, 0)
   if iteration_count >= self.max_agent_iterations:
       continue  # Skip agent
   ```
   - Per-instance counter
   - Different orchestrators have different counts

3. **No Coordination Primitives**
   - No distributed locks
   - No leader election
   - No shared state management

**Proposed Architecture for Distribution**:

```
┌─────────────────────────────────────────────────────┐
│            Load Balancer (Sticky Sessions)          │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
┌──────────▼──────────┐    ┌──────────▼──────────┐
│ Orchestrator 1      │    │ Orchestrator 2      │
│ (Stateful)          │    │ (Stateful)          │
├─────────────────────┤    ├─────────────────────┤
│ • Agent A, B        │    │ • Agent C, D        │
│ • Local correlation │    │ • Local correlation │
│ • Local batching    │    │ • Local batching    │
└──────────┬──────────┘    └──────────┬──────────┘
           │                          │
           └──────────┬───────────────┘
                      │
         ┌────────────▼────────────┐
         │ Shared Storage Backend  │
         │ (PostgreSQL/Redis)      │
         └─────────────────────────┘
```

**Distribution Strategy**:
1. **Agent Partitioning**: Assign agents to specific orchestrator instances
2. **Sticky Sessions**: Route artifacts by `partition_key` to same orchestrator
3. **Shared Store**: All orchestrators read/write to shared database
4. **Independent Coordination**: Each orchestrator manages its own agents' correlation/batching

---

### 5.2 Vertical Scalability

**Strong Support**:
- Async I/O: Handles high concurrency
- Store abstraction: Swap in-memory for persistent store
- Configurable concurrency: Per-agent semaphores

**Recommendations**:
1. **Orchestrator-level Backpressure**
   ```python
   class Flock:
       def __init__(self, ..., max_concurrent_tasks: int = 1000):
           self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)

       def _schedule_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
           async def _run_with_backpressure():
               async with self._task_semaphore:
                   await self._run_agent_task(agent, artifacts)

           task = asyncio.create_task(_run_with_backpressure())
           self._tasks.add(task)
   ```

2. **Batch Artifact Publishing**
   - Current: `publish()` waits for store write + scheduling
   - Proposed: Batch N artifacts, write once, schedule in parallel

---

## 6. Testability

### 6.1 What's Testable

✅ **Excellent**:
- **Subscription Matching**: Pure logic, no I/O (subscription.py:143-160)
- **Correlation Logic**: CorrelationGroup is self-contained (correlation_engine.py:22-87)
- **Batch Logic**: BatchAccumulator is self-contained (batch_accumulator.py:23-72)
- **Visibility Policies**: Pure predicates (visibility.py:29-81)

✅ **Good**:
- **Agent Execution**: Mockable store, context (agent.py:128-148)
- **Store Implementations**: InMemory for fast tests, SQLite for integration

### 6.2 What's Hard to Test

⚠️ **Challenges**:

1. **Orchestrator Integration Tests**
   - Requires mocking: store, MCP manager, dashboard
   - Tight coupling: agent → orchestrator (agent.py:93)
   - Suggestion: Extract interfaces (e.g., `MCPManager`, `MetricsCollector`)

2. **Concurrency Edge Cases**
   - Circuit breaker race conditions (orchestrator.py:887)
   - Batch timeout edge cases (batch_accumulator.py:216-229)
   - Suggestion: Use deterministic time (mock `datetime.now()`)

3. **Lifecycle Hooks**
   - Hard to verify hook execution order (agent.py:128-148)
   - Suggestion: Add `LifecycleTracker` utility for testing

### 6.3 Recommended Testing Improvements

**HIGH IMPACT**:

1. **Dependency Injection for Orchestrator**
   ```python
   # Proposed: orchestrator.py
   class OrchestrationServices:
       store: BlackboardStore
       mcp_manager: MCPManager
       metrics_collector: MetricsCollector
       correlation_engine: CorrelationEngine
       batch_engine: BatchEngine
       artifact_collector: ArtifactCollector

   class Flock:
       def __init__(self, ..., services: OrchestrationServices | None = None):
           self.services = services or self._create_default_services()
   ```
   - Easy to inject mocks for testing
   - Clear dependencies

2. **Time Abstraction**
   ```python
   # Proposed: time_source.py
   class TimeSource(Protocol):
       def now(self) -> datetime:
           ...

   class SystemTimeSource:
       def now(self) -> datetime:
           return datetime.now(timezone.utc)

   class MockTimeSource:
       def __init__(self, fixed_time: datetime):
           self._time = fixed_time

       def now(self) -> datetime:
           return self._time

       def advance(self, delta: timedelta):
           self._time += delta
   ```
   - Deterministic batch timeout tests
   - Deterministic correlation window tests

---

## 7. Security Considerations

### 7.1 Current Security Posture

✅ **Good Practices**:

1. **SQL Injection Prevention** (store.py:678-769)
   - Parameterized queries throughout
   - `# nosec B608` annotations for safe string composition

2. **Visibility Access Control** (visibility.py)
   - Clear policy enforcement
   - Type-safe polymorphic design

3. **MCP Tool Namespacing** (agent.py:203-213)
   - Prevents tool name collisions
   - Format: `{server}__{tool}`

⚠️ **Potential Issues**:

1. **Predicate Code Injection** (subscription.py:154-160)
   ```python
   # User-provided lambda executed without sandboxing
   agent.consumes(Task, where=lambda t: eval(t.user_input))  # DANGER
   ```
   - No validation of user predicates
   - Arbitrary code execution risk
   - **Recommendation**: Document security implications, add opt-in sandboxing

2. **Dashboard Authentication** (orchestrator.py:557-638)
   - No authentication on dashboard endpoint
   - WebSocket connections not authenticated
   - **Recommendation**: Add authentication layer (API keys, JWT)

3. **MCP Server Trust** (agent.py:150-221)
   - Agents trust all tools from assigned MCP servers
   - No tool permission validation
   - **Recommendation**: Add tool capability declarations

### 7.2 Multi-Tenancy Support

✅ **Foundation in Place**:
- `TenantVisibility` (visibility.py:58-65)
- `partition_key` in artifacts (artifacts.py:23)
- Agent `tenant_id` (agent.py:108)

⚠️ **Gaps**:
- No tenant isolation at store level
- Agents can access any tenant's data via direct store access
- **Recommendation**: Add tenant-scoped store queries

---

## 8. Summary of Recommendations

### 8.1 HIGH IMPACT (Addresses Core Issues)

| # | Recommendation | File | Benefit |
|---|---------------|------|---------|
| 1 | Extract `SubscriptionRouter` | orchestrator.py:877-980 | Reduces orchestrator complexity, improves testability |
| 2 | Dependency Injection for `Context` | orchestrator.py:487 | Breaks circular dependencies, enables mocking |
| 3 | Separate `AgentBuilder` from `Agent` | agent.py:441-1028 | Clear configuration vs execution, reduces confusion |
| 4 | Interface Segregation for Agent | agent.py:93 | Reduces coupling, improves testability |
| 5 | Optimize Context Fetching | components.py:112-182 | Improves performance (avoid loading all artifacts) |
| 6 | Add Predicate Error Logging | subscription.py:154-160 | Improves debuggability, prevents silent failures |
| 7 | Feature Detection Interface | store.py:154-159 | Clear capability checking, prevents runtime errors |
| 8 | Automatic Correlation Cleanup | correlation_engine.py:204-215 | Prevents memory leaks |
| 9 | Artifact-based Sequence | correlation_engine.py:117 | Enables persistence, distribution |
| 10 | Group Count Field | batch_accumulator.py:186-192 | Removes hack, improves type safety |
| 11 | Automatic Batch Timeout Task | batch_accumulator.py:216-229 | Makes timeout batching actually work |
| 12 | Add Pool Expiry | artifact_collector.py:50-115 | Prevents memory leaks from incomplete AND gates |

### 8.2 MEDIUM IMPACT (Improves Quality)

| # | Recommendation | File | Benefit |
|---|---------------|------|---------|
| 13 | Extract Dashboard Service | orchestrator.py:557-638 | Separation of concerns |
| 14 | Move Engine Config | components.py:32-48 | Clearer abstraction |
| 15 | Add JoinSpec Validation | subscription.py:29-57 | Early error detection |
| 16 | Optimize InMemory Filtering | store.py:269-325 | Better performance |
| 17 | Rename Store Envelopes | store.py:105-109 | Prevents name collision |
| 18 | Use UTC Timestamps | Multiple files | Consistent time handling |
| 19 | Add Pool Size Limit | artifact_collector.py:93 | Prevents unbounded growth |
| 20 | Support OR Gates | artifact_collector.py:96-101 | More flexible coordination |

### 8.3 LOW IMPACT (Polish)

| # | Recommendation | File | Benefit |
|---|---------------|------|---------|
| 21 | Simplify Visibility Default | artifacts.py:25 | Code clarity |
| 22 | Rename EvaluationEnvelope | artifacts.py:75-79 | Prevents confusion |
| 23 | Document Payload Selection | agent.py:412-438 | Better documentation |

---

## 9. Conclusion

### What's Working Exceptionally Well

1. **Blackboard Architecture**: Clean event-driven coordination with clear separation
2. **Component System**: Excellent extension points for utilities and engines
3. **Subscription Model**: Flexible, composable subscription rules
4. **Storage Abstraction**: Easy to swap implementations (in-memory, SQLite, future: distributed)
5. **Advanced Coordination**: AND gates, JoinSpec, BatchSpec are powerful primitives

### Key Architectural Strengths

- **Extensibility**: Easy to add new agent behaviors, visibility policies, coordination primitives
- **Composability**: Features compose well (JoinSpec + BatchSpec works!)
- **Testability**: Most components are testable in isolation
- **Tracing**: Built-in OpenTelemetry support throughout

### Primary Growth Areas

1. **Orchestrator Complexity**: Too many responsibilities (agents, MCP, batch, correlation, dashboard)
2. **Tight Coupling**: Agent ↔ Orchestrator circular dependencies
3. **Lifecycle Management**: Missing automatic cleanup tasks (correlation, batch timeouts)
4. **Scalability**: In-memory state prevents distribution
5. **Time Handling**: Inconsistent (no timezone, no abstraction for testing)

### Architectural Vision for Future

**Short-term** (Next 6 months):
- Extract routing logic into `SubscriptionRouter`
- Add automatic cleanup tasks (correlation, batch)
- Implement dependency injection for testability

**Medium-term** (6-12 months):
- Extract dashboard as separate service
- Add distributed coordination primitives
- Improve multi-tenancy support

**Long-term** (12+ months):
- Distributed orchestrator architecture
- Advanced scheduling (priority queues, deadlines)
- Plugin system for custom coordination primitives

---

**Document Version**: 1.0
**Analysis Depth**: Comprehensive (9 core files, 4800+ LOC analyzed)
**Files Analyzed**:
- `src/flock/orchestrator.py` (1107 lines)
- `src/flock/agent.py` (1093 lines)
- `src/flock/components.py` (190 lines)
- `src/flock/subscription.py` (175 lines)
- `src/flock/artifacts.py` (87 lines)
- `src/flock/store.py` (1215 lines)
- `src/flock/correlation_engine.py` (219 lines)
- `src/flock/batch_accumulator.py` (253 lines)
- `src/flock/artifact_collector.py` (160 lines)
- Supporting files: `runtime.py`, `visibility.py`, `registry.py`
