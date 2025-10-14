# Flock Extensibility & Plugin Architecture Analysis

**Date:** 2025-10-13
**Version:** 0.5.0
**Status:** Comprehensive Review

---

## Executive Summary

This document provides a comprehensive analysis of Flock's extensibility mechanisms, identifies gaps in the plugin architecture, and proposes a roadmap for third-party ecosystem development.

**Key Findings:**
- ✅ **Strengths**: Clean component lifecycle, flexible engine abstraction, strong type registry
- ⚠️ **Gaps**: No formal plugin discovery, inconsistent extension patterns, missing orchestrator-level hooks
- 🎯 **Priority**: Establish plugin registry pattern, document extension points, create marketplace guidelines

---

## Table of Contents

1. [Extension Point Inventory](#extension-point-inventory)
2. [Component System Analysis](#component-system-analysis)
3. [Engine System Analysis](#engine-system-analysis)
4. [Storage Backend Analysis](#storage-backend-analysis)
5. [MCP Integration Analysis](#mcp-integration-analysis)
6. [Visibility System Analysis](#visibility-system-analysis)
7. [Subscription System Analysis](#subscription-system-analysis)
8. [Plugin Architecture Proposals](#plugin-architecture-proposals)
9. [Third-Party Ecosystem Roadmap](#third-party-ecosystem-roadmap)
10. [Comparison to Other Frameworks](#comparison-to-other-frameworks)

---

## Extension Point Inventory

### Current Extension Points (What Exists)

| System | Extension Point | Status | Ease of Use | Documentation |
|--------|----------------|--------|-------------|---------------|
| **Components** | AgentComponent lifecycle hooks | ✅ Excellent | ⭐⭐⭐⭐⭐ | ⚠️ Limited |
| **Engines** | EngineComponent.evaluate() | ✅ Good | ⭐⭐⭐⭐ | ⚠️ Limited |
| **Storage** | BlackboardStore interface | ✅ Good | ⭐⭐⭐ | ⚠️ None |
| **Type Registry** | flock_type decorator | ✅ Excellent | ⭐⭐⭐⭐⭐ | ✅ Good |
| **Function Registry** | flock_tool decorator | ✅ Excellent | ⭐⭐⭐⭐⭐ | ✅ Good |
| **Visibility** | Custom Visibility classes | ✅ Good | ⭐⭐⭐⭐ | ⚠️ Limited |
| **Subscription** | Predicate functions | ✅ Excellent | ⭐⭐⭐⭐⭐ | ✅ Good |
| **MCP Servers** | ServerParameters interface | ✅ Good | ⭐⭐⭐ | ✅ Good |

### Missing Extension Points (Gaps)

| System | Missing Extension Point | Impact | Priority |
|--------|------------------------|--------|----------|
| **Orchestrator** | OrchestratorComponent lifecycle | High | 🔴 Critical |
| **Plugin Registry** | Centralized discovery mechanism | High | 🔴 Critical |
| **Store Factory** | String-based store instantiation | Medium | 🟡 Important |
| **Engine Factory** | Model string parsing extensions | Medium | 🟡 Important |
| **Dashboard** | Custom dashboard modules | Low | 🟢 Nice-to-have |
| **Metrics** | Custom metrics collectors | Medium | 🟡 Important |
| **Tracing** | Custom trace exporters | Low | 🟢 Nice-to-have |

---

## Component System Analysis

**File:** `C:\workspace\whiteduck\flock\src\flock\components.py`

### Current Design

```python
class AgentComponent(BaseModel, metaclass=TracedModelMeta):
    """Base class for agent components with lifecycle hooks."""

    name: str | None = None
    config: AgentComponentConfig = Field(default_factory=AgentComponentConfig)

    # 7 lifecycle hooks:
    async def on_initialize(self, agent: Agent, ctx: Context) -> None: ...
    async def on_pre_consume(self, agent: Agent, ctx: Context, inputs: list[Artifact]) -> list[Artifact]: ...
    async def on_pre_evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs) -> EvalInputs: ...
    async def on_post_evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs, result: EvalResult) -> EvalResult: ...
    async def on_post_publish(self, agent: Agent, ctx: Context, artifact: Artifact) -> None: ...
    async def on_error(self, agent: Agent, ctx: Context, error: Exception) -> None: ...
    async def on_terminate(self, agent: Agent, ctx: Context) -> None: ...
```

### Strengths

✅ **Clean Lifecycle Model**
- 7 well-defined hooks cover the entire agent execution lifecycle
- Clear separation of concerns (pre/post, consume/evaluate/publish)
- Async-native design for I/O-heavy operations

✅ **Flexible Configuration**
- `AgentComponentConfig.with_fields()` enables dynamic config schemas
- Pydantic validation ensures type safety
- Example:
  ```python
  RateLimiterConfig = AgentComponentConfig.with_fields(
      max_calls=Field(default=10, description="Max calls per window"),
      window=Field(default=60, description="Time window in seconds")
  )
  ```

✅ **Automatic Tracing**
- `TracedModelMeta` metaclass auto-instruments all public methods
- Zero-overhead when tracing disabled
- Full OpenTelemetry integration

### Gaps & Weaknesses

⚠️ **No Discovery Mechanism**
```python
# Current (manual import required):
from my_package import RateLimiter
agent.with_utilities(RateLimiter(max_calls=10))

# Desired (plugin registry):
agent.with_utilities("rate_limiter", max_calls=10)
# OR
agent.with_utilities({"type": "rate_limiter", "max_calls": 10})
```

⚠️ **No Component Validation**
- Components can break core functionality if poorly written
- No safeguards for infinite loops or resource leaks
- Missing timeout enforcement

⚠️ **Limited Error Handling**
- `on_error()` is called but not enforced
- No retry/recovery strategy hooks
- Component errors can crash entire agent

⚠️ **No Inter-Component Communication**
- Components cannot easily share state
- No message bus for component coordination
- Context is read-only for most components

### Recommendations

1. **Add Component Registry**
   ```python
   from flock.plugins import register_component

   @register_component("rate_limiter")
   class RateLimiter(AgentComponent):
       max_calls: int = 10
       window: int = 60

   # Usage:
   agent.with_utilities("rate_limiter", max_calls=5)
   ```

2. **Add Component Validation Hooks**
   ```python
   class AgentComponent(BaseModel):
       def validate_safety(self) -> list[str]:
           """Return list of safety warnings."""
           return []

       def estimate_overhead(self) -> float:
           """Return estimated performance overhead (0.0-1.0)."""
           return 0.01
   ```

3. **Add Component Isolation**
   ```python
   class AgentComponent(BaseModel):
       max_execution_time: float = 30.0  # seconds
       error_strategy: Literal["fail", "log", "ignore"] = "log"
   ```

---

## Engine System Analysis

**File:** `C:\workspace\whiteduck\flock\src\flock\engines\dspy_engine.py`

### Current Design

```python
class EngineComponent(AgentComponent):
    """Base class for engine components."""

    # Context fetching configuration
    enable_context: bool = True
    context_max_artifacts: int | None = None
    context_exclude_types: set[str] = Field(default_factory=set)

    async def evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        """Override this method in your engine implementation."""
        raise NotImplementedError
```

### Strengths

✅ **Clean Abstraction**
- Single `evaluate()` method hides implementation complexity
- Built-in conversation context support
- Helper methods for context fetching

✅ **DSPy Integration**
- Full DSPy program support (Predict, ReAct, ChainOfThought)
- Streaming with Rich formatting
- WebSocket integration for dashboard

✅ **Flexible Model Resolution**
- Environment variable fallback (`TRELLIS_MODEL`, `OPENAI_MODEL`)
- Per-agent model override
- Model string parsing (`openai/gpt-4.1`)

### Gaps & Weaknesses

⚠️ **No Engine Registry**
```python
# Current (hardcoded imports):
from flock.engines import DSPyEngine
agent.with_engines(DSPyEngine(model="openai/gpt-4o"))

# Desired (string-based):
agent.with_engines("dspy", model="openai/gpt-4o")
# OR
agent.with_engines({"engine": "dspy", "model": "openai/gpt-4o"})
```

⚠️ **No Engine Composition**
- Can't easily chain multiple engines
- No retry/fallback engine patterns
- Missing router engines (based on input type)

⚠️ **Vendor Lock-in Risk**
- Heavy DSPy dependency throughout codebase
- No abstraction for non-DSPy engines
- Difficult to add LangChain/LlamaIndex engines

⚠️ **No Engine Validation**
- Engines can return invalid EvalResult
- No output schema validation
- Missing cost/latency tracking

### Recommendations

1. **Add Engine Registry**
   ```python
   from flock.plugins import register_engine

   @register_engine("openai_native")
   class OpenAIEngine(EngineComponent):
       async def evaluate(self, agent, ctx, inputs):
           # Direct OpenAI API calls (no DSPy)
           ...

   # Usage:
   agent.with_engines("openai_native", model="gpt-4o")
   ```

2. **Add Engine Composition**
   ```python
   class RouterEngine(EngineComponent):
       """Route to different engines based on input."""
       routes: dict[str, EngineComponent]

       async def evaluate(self, agent, ctx, inputs):
           input_type = inputs.artifacts[0].type
           engine = self.routes.get(input_type, self.default_engine)
           return await engine.evaluate(agent, ctx, inputs)

   # Usage:
   agent.with_engines(RouterEngine(
       routes={
           "CodeSubmission": DSPyEngine(model="gpt-4o"),
           "TextData": DSPyEngine(model="gpt-4o-mini")
       }
   ))
   ```

3. **Add Engine Validation**
   ```python
   class EngineComponent(AgentComponent):
       validate_outputs: bool = True
       max_cost_per_call: float | None = None
       max_latency_ms: int | None = None

       async def evaluate(self, agent, ctx, inputs) -> EvalResult:
           result = await self._evaluate_impl(agent, ctx, inputs)

           if self.validate_outputs:
               self._validate_result(result, agent.outputs)

           return result
   ```

---

## Storage Backend Analysis

**File:** `C:\workspace\whiteduck\flock\src\flock\store.py`

### Current Design

```python
class BlackboardStore:
    """Abstract base class for storage backends."""

    async def publish(self, artifact: Artifact) -> None: ...
    async def get(self, artifact_id: UUID) -> Artifact | None: ...
    async def list(self) -> list[Artifact]: ...
    async def list_by_type(self, type_name: str) -> list[Artifact]: ...
    async def get_by_type(self, artifact_type: type[T]) -> list[T]: ...
    async def record_consumptions(self, records: Iterable[ConsumptionRecord]) -> None: ...
    async def query_artifacts(self, filters: FilterConfig | None = None, *, limit: int = 50, offset: int = 0, embed_meta: bool = False) -> tuple[list[Artifact | ArtifactEnvelope], int]: ...
    async def summarize_artifacts(self, filters: FilterConfig | None = None) -> dict[str, Any]: ...
    async def agent_history_summary(self, agent_id: str, filters: FilterConfig | None = None) -> dict[str, Any]: ...
    async def upsert_agent_snapshot(self, snapshot: AgentSnapshotRecord) -> None: ...
    async def load_agent_snapshots(self) -> list[AgentSnapshotRecord]: ...
    async def clear_agent_snapshots(self) -> None: ...
```

### Strengths

✅ **Clean Interface**
- Well-defined contract with 13 methods
- Supports filtering, pagination, aggregation
- Type-safe retrieval with `get_by_type()`

✅ **Two Implementations**
- `InMemoryBlackboardStore`: Fast, simple, no dependencies
- `SQLiteBlackboardStore`: Persistent, production-ready, indexed

✅ **Rich Metadata**
- `FilterConfig` supports type, producer, correlation, tags, visibility, time range
- `ArtifactEnvelope` includes consumption records for lineage tracking
- `AgentSnapshotRecord` captures agent metadata for dashboard

### Gaps & Weaknesses

⚠️ **No Store Registry**
```python
# Current (manual instantiation):
from flock.store import SQLiteBlackboardStore
store = SQLiteBlackboardStore(".flock/blackboard.db")
await store.ensure_schema()
flock = Flock("openai/gpt-4.1", store=store)

# Desired (string-based):
flock = Flock("openai/gpt-4.1", store="sqlite://.flock/blackboard.db")
# OR
flock = Flock("openai/gpt-4.1", store={"type": "sqlite", "path": ".flock/blackboard.db"})
```

⚠️ **No Store Composition**
- Can't chain stores (e.g., cache + database)
- No read-through/write-through patterns
- Missing store middleware (logging, metrics, compression)

⚠️ **Limited Store Features**
- No transactions or ACID guarantees
- No optimistic locking
- Missing change data capture (CDC)
- No replication support

⚠️ **No Store Validation**
- Stores can silently fail
- No health checks
- Missing performance metrics

### Recommendations

1. **Add Store Registry**
   ```python
   from flock.plugins import register_store

   @register_store("redis")
   class RedisBlackboardStore(BlackboardStore):
       def __init__(self, host: str = "localhost", port: int = 6379, **kwargs):
           self.redis = aioredis.from_url(f"redis://{host}:{port}")

       async def publish(self, artifact: Artifact) -> None:
           await self.redis.set(f"artifact:{artifact.id}", artifact.model_dump_json())

   # Usage:
   flock = Flock("openai/gpt-4.1", store="redis://localhost:6379")
   ```

2. **Add Store Composition**
   ```python
   class CachedStore(BlackboardStore):
       """Cache reads, write-through to backing store."""

       def __init__(self, cache: BlackboardStore, backing: BlackboardStore):
           self.cache = cache
           self.backing = backing

       async def get(self, artifact_id: UUID) -> Artifact | None:
           # Try cache first
           artifact = await self.cache.get(artifact_id)
           if artifact:
               return artifact

           # Fallback to backing store
           artifact = await self.backing.get(artifact_id)
           if artifact:
               await self.cache.publish(artifact)  # Populate cache
           return artifact

       async def publish(self, artifact: Artifact) -> None:
           # Write-through
           await self.backing.publish(artifact)
           await self.cache.publish(artifact)

   # Usage:
   flock = Flock("openai/gpt-4.1", store=CachedStore(
       cache=InMemoryBlackboardStore(),
       backing=SQLiteBlackboardStore(".flock/blackboard.db")
   ))
   ```

3. **Add Store Middleware**
   ```python
   class MetricsStoreMiddleware(BlackboardStore):
       """Wrap any store to collect metrics."""

       def __init__(self, store: BlackboardStore):
           self.store = store
           self.metrics = {"reads": 0, "writes": 0, "latency_ms": []}

       async def get(self, artifact_id: UUID) -> Artifact | None:
           start = time.time()
           result = await self.store.get(artifact_id)
           self.metrics["reads"] += 1
           self.metrics["latency_ms"].append((time.time() - start) * 1000)
           return result
   ```

---

## MCP Integration Analysis

**File:** `C:\workspace\whiteduck\flock\src\flock\mcp\__init__.py`

### Current Design

**Architecture Decisions (from docstring):**
- **AD001:** Two-Level Architecture (orchestrator + agent)
- **AD003:** Tool Namespacing (`{server}__{tool}`)
- **AD004:** Per-(agent_id, run_id) Connection Isolation
- **AD005:** Lazy Connection Establishment
- **AD007:** Graceful Degradation on MCP Failures

### Strengths

✅ **Well-Architected**
- Two-level design separates concerns (orchestrator registers, agents consume)
- Connection pooling with lazy initialization
- Tool namespacing prevents collisions

✅ **Flexible Server Support**
- Supports 4 transport types (stdio, websockets, SSE, streamable HTTP)
- Custom `ServerParameters` interface for extensions
- Per-server feature configuration (tools, prompts, sampling, roots)

✅ **Agent-Level Control**
- Agents can mount specific filesystem roots
- Tool whitelisting for security
- Graceful fallback when MCP unavailable

### Gaps & Weaknesses

⚠️ **No MCP Plugin Registry**
```python
# Current (manual server registration):
from flock.mcp import StdioServerParameters
orchestrator.add_mcp(
    name="filesystem",
    connection_params=StdioServerParameters(
        command="uvx",
        args=["mcp-server-filesystem", "/tmp"]
    )
)

# Desired (plugin discovery):
orchestrator.add_mcp("filesystem", path="/tmp")  # Auto-discovers mcp-server-filesystem
```

⚠️ **Tight Coupling to Orchestrator**
- MCP manager stored in orchestrator (`_mcp_manager`)
- Agents can't use MCP without orchestrator
- Hard to test MCP in isolation

⚠️ **Limited Transport Extensibility**
- 4 hardcoded transport types
- No easy way to add custom transports
- Missing transport middleware (logging, retries, auth)

⚠️ **No MCP Tool Caching**
- Tools fetched on every agent run
- No schema caching
- Unnecessary network overhead

### Recommendations

1. **Add MCP Plugin Discovery**
   ```python
   from flock.mcp.discovery import discover_mcp_servers

   # Auto-discover MCP servers from:
   # 1. Environment variables (MCP_SERVERS)
   # 2. Config file (.flock/mcp.toml)
   # 3. Installed packages (mcp-server-* pattern)

   discovered = discover_mcp_servers()
   for name, params in discovered.items():
       orchestrator.add_mcp(name, params)
   ```

2. **Add Transport Middleware**
   ```python
   class RetryTransport:
       """Wrap any transport to add retry logic."""

       def __init__(self, transport: Transport, max_retries: int = 3):
           self.transport = transport
           self.max_retries = max_retries

       async def call_tool(self, name: str, args: dict) -> Any:
           for attempt in range(self.max_retries):
               try:
                   return await self.transport.call_tool(name, args)
               except TransientError:
                   if attempt == self.max_retries - 1:
                       raise
                   await asyncio.sleep(2 ** attempt)
   ```

3. **Add MCP Tool Caching**
   ```python
   class MCPToolCache:
       """Cache MCP tool schemas."""

       def __init__(self, ttl: int = 3600):
           self.cache: dict[str, dict] = {}
           self.ttl = ttl

       async def get_tools(self, server_name: str, client: FlockMCPClient) -> dict:
           if server_name in self.cache:
               cached_at, tools = self.cache[server_name]
               if time.time() - cached_at < self.ttl:
                   return tools

           tools = await client.list_tools()
           self.cache[server_name] = (time.time(), tools)
           return tools
   ```

---

## Visibility System Analysis

**File:** `C:\workspace\whiteduck\flock\src\flock\visibility.py`

### Current Design

```python
class Visibility(BaseModel):
    """Base visibility contract."""
    kind: Literal["Public", "Private", "Labelled", "Tenant", "After"]

    def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
        raise NotImplementedError

# 5 built-in visibility types:
class PublicVisibility(Visibility): ...
class PrivateVisibility(Visibility): ...
class LabelledVisibility(Visibility): ...
class TenantVisibility(Visibility): ...
class AfterVisibility(Visibility): ...
```

### Strengths

✅ **Polymorphic Design**
- Clean base class with single `allows()` method
- Easy to extend with custom policies
- Pydantic validation ensures type safety

✅ **5 Built-in Policies**
- Cover common use cases (public, private, RBAC, multi-tenancy, embargoes)
- Composable (e.g., `AfterVisibility` can wrap any other policy)
- Well-documented with clear semantics

✅ **Lightweight**
- Minimal overhead (simple boolean check)
- No database queries or external dependencies
- Works with in-memory and persistent stores

### Gaps & Weaknesses

⚠️ **No Policy Composition Helpers**
```python
# Current (manual composition):
artifact.visibility = AfterVisibility(
    ttl=timedelta(hours=24),
    then=PrivateVisibility(agents={"admin", "auditor"})
)

# Desired (fluent builder):
artifact.visibility = (
    Visibility.after(hours=24)
    .then_private(agents={"admin", "auditor"})
)
```

⚠️ **No Policy Registry**
```python
# Current (hardcoded imports):
from flock.visibility import LabelledVisibility
agent.publishes(Report, visibility=LabelledVisibility(required_labels={"clearance:secret"}))

# Desired (string-based):
agent.publishes(Report, visibility="labelled:clearance:secret")
# OR
agent.publishes(Report, visibility={"type": "labelled", "required_labels": ["clearance:secret"]})
```

⚠️ **Limited Policy Types**
- No geographic restrictions (e.g., "EU-only")
- No dynamic policies (e.g., based on artifact content)
- No policy inheritance (e.g., "inherit from parent")

⚠️ **No Policy Auditing**
- Can't track who accessed what
- No policy violation logging
- Missing compliance reports

### Recommendations

1. **Add Visibility Registry**
   ```python
   from flock.plugins import register_visibility

   @register_visibility("geographic")
   class GeographicVisibility(Visibility):
       kind: Literal["Geographic"] = "Geographic"
       allowed_regions: set[str]

       def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
           return agent.region in self.allowed_regions

   # Usage:
   agent.publishes(Data, visibility="geographic:EU,US")
   ```

2. **Add Fluent Builders**
   ```python
   class Visibility(BaseModel):
       @staticmethod
       def after(*, days: int = 0, hours: int = 0, minutes: int = 0) -> AfterVisibility:
           return AfterVisibility(ttl=timedelta(days=days, hours=hours, minutes=minutes))

       @staticmethod
       def private(*agent_names: str) -> PrivateVisibility:
           return PrivateVisibility(agents=set(agent_names))

       @staticmethod
       def labelled(*labels: str) -> LabelledVisibility:
           return LabelledVisibility(required_labels=set(labels))

   # Usage:
   artifact.visibility = Visibility.after(hours=24).then_private("admin")
   ```

3. **Add Visibility Auditing**
   ```python
   class AuditedVisibility(Visibility):
       """Wrap any visibility to add audit logging."""

       wrapped: Visibility
       audit_log: list[tuple[datetime, str, bool]] = []

       def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
           allowed = self.wrapped.allows(agent, now=now)
           self.audit_log.append((datetime.now(), agent.name, allowed))
           return allowed
   ```

---

## Subscription System Analysis

**File:** `C:\workspace\whiteduck\flock\src\flock\subscription.py`

### Current Design

```python
class Subscription:
    """Defines how an agent consumes artifacts from the blackboard."""

    def __init__(
        self, *,
        agent_name: str,
        types: Sequence[type[BaseModel]],
        where: Sequence[Predicate] | None = None,
        text_predicates: Sequence[TextPredicate] | None = None,
        from_agents: Iterable[str] | None = None,
        channels: Iterable[str] | None = None,
        join: JoinSpec | None = None,
        batch: BatchSpec | None = None,
        delivery: str = "exclusive",
        mode: str = "both",
        priority: int = 0,
    ): ...
```

### Strengths

✅ **Rich Subscription Language**
- Type-based matching (AND/OR gates)
- Predicate filtering (lambda functions)
- Text-based semantic filtering
- Producer filtering (`from_agents`)
- Channel-based routing (`channels`)
- Correlation joins (`JoinSpec`)
- Batching (`BatchSpec`)

✅ **Flexible Matching**
- Multiple types = AND gate
- Multiple `.consumes()` calls = OR gate
- Count-based gates (e.g., "wait for 3 Orders")
- Predicate chaining (all must pass)

✅ **Production Features**
- Priority-based scheduling
- Exclusive vs. broadcast delivery
- Direct vs. streaming mode

### Gaps & Weaknesses

⚠️ **No Subscription Validation**
```python
# Current (runtime errors possible):
agent.consumes(Order, Order, Order, where=lambda o: o.total > invalid_field)  # Crashes at runtime

# Desired (validation):
agent.consumes(Order, where=lambda o: o.total > 100).validate()  # Warns at build time
```

⚠️ **No Subscription Composition**
```python
# Current (manual composition):
premium_orders = lambda o: o.tier == "premium" and o.total > 100
urgent_orders = lambda o: o.priority == "urgent" and o.total > 50

agent.consumes(Order, where=[premium_orders])
agent.consumes(Order, where=[urgent_orders])

# Desired (fluent composition):
from flock.subscriptions import Predicates

premium = Predicates.field("tier").equals("premium")
high_value = Predicates.field("total").greater_than(100)
urgent = Predicates.field("priority").equals("urgent")
medium_value = Predicates.field("total").greater_than(50)

agent.consumes(Order, where=premium.and_(high_value).or_(urgent.and_(medium_value)))
```

⚠️ **Limited Subscription Debugging**
- Hard to debug why agent didn't trigger
- No subscription match tracing
- Missing subscription metrics (match rate, false positives)

⚠️ **No Dynamic Subscriptions**
- Subscriptions fixed at agent creation time
- Can't add/remove subscriptions at runtime
- No conditional subscriptions (e.g., "only during business hours")

### Recommendations

1. **Add Subscription Validation**
   ```python
   class Subscription:
       def validate(self, type_models: list[type[BaseModel]]) -> list[str]:
           """Return list of validation warnings."""
           warnings = []

           for predicate in self.where:
               # Check if predicate references valid fields
               try:
                   test_instance = type_models[0]()
                   predicate(test_instance)
               except AttributeError as e:
                   warnings.append(f"Predicate references invalid field: {e}")

           return warnings
   ```

2. **Add Fluent Predicate Builder**
   ```python
   class PredicateBuilder:
       @staticmethod
       def field(field_name: str) -> FieldPredicate:
           return FieldPredicate(field_name)

   class FieldPredicate:
       def __init__(self, field_name: str):
           self.field_name = field_name

       def equals(self, value: Any) -> Callable:
           return lambda obj: getattr(obj, self.field_name) == value

       def greater_than(self, value: Any) -> Callable:
           return lambda obj: getattr(obj, self.field_name) > value

       def and_(self, other: Callable) -> Callable:
           return lambda obj: self(obj) and other(obj)

   # Usage:
   agent.consumes(
       Order,
       where=Predicates.field("total").greater_than(100).and_(
           Predicates.field("status").equals("pending")
       )
   )
   ```

3. **Add Subscription Debugging**
   ```python
   class DebugSubscription(Subscription):
       """Wrap subscription to add debugging."""

       match_history: list[tuple[datetime, Artifact, bool]] = []

       def matches(self, artifact: Artifact) -> bool:
           result = super().matches(artifact)
           self.match_history.append((datetime.now(), artifact, result))
           return result

       def explain_mismatch(self, artifact: Artifact) -> list[str]:
           """Explain why artifact didn't match."""
           reasons = []

           if artifact.type not in self.type_names:
               reasons.append(f"Type mismatch: {artifact.type} not in {self.type_names}")

           if self.from_agents and artifact.produced_by not in self.from_agents:
               reasons.append(f"Producer mismatch: {artifact.produced_by} not in {self.from_agents}")

           # Check predicates
           for i, predicate in enumerate(self.where):
               try:
                   if not predicate(artifact.payload):
                       reasons.append(f"Predicate {i} failed")
               except Exception as e:
                   reasons.append(f"Predicate {i} error: {e}")

           return reasons
   ```

---

## Plugin Architecture Proposals

### 1. Plugin Registry Pattern

**Goal:** Centralized discovery and instantiation of extensions.

**Design:**

```python
# C:\workspace\whiteduck\flock\src\flock\plugins\registry.py

from typing import Any, Callable, TypeVar
from collections.abc import Mapping

T = TypeVar("T")

class PluginRegistry:
    """Centralized registry for all Flock plugins."""

    def __init__(self):
        self._components: dict[str, type[AgentComponent]] = {}
        self._engines: dict[str, type[EngineComponent]] = {}
        self._stores: dict[str, type[BlackboardStore]] = {}
        self._visibility: dict[str, type[Visibility]] = {}
        self._factories: dict[str, Callable] = {}

    # Component registration
    def register_component(self, name: str, component_cls: type[AgentComponent]) -> None:
        """Register an agent component."""
        self._components[name] = component_cls

    def get_component(self, name: str, **kwargs) -> AgentComponent:
        """Instantiate a registered component."""
        if name not in self._components:
            raise PluginNotFoundError(f"Component '{name}' not registered")
        return self._components[name](**kwargs)

    # Engine registration
    def register_engine(self, name: str, engine_cls: type[EngineComponent]) -> None:
        """Register an engine."""
        self._engines[name] = engine_cls

    def get_engine(self, name: str, **kwargs) -> EngineComponent:
        """Instantiate a registered engine."""
        if name not in self._engines:
            raise PluginNotFoundError(f"Engine '{name}' not registered")
        return self._engines[name](**kwargs)

    # Store registration
    def register_store(self, name: str, store_cls: type[BlackboardStore]) -> None:
        """Register a blackboard store."""
        self._stores[name] = store_cls

    def get_store(self, connection_string: str) -> BlackboardStore:
        """Instantiate a store from a connection string.

        Examples:
            sqlite://.flock/blackboard.db
            redis://localhost:6379
            postgres://user:pass@localhost/db
            memory://
        """
        if "://" not in connection_string:
            raise ValueError(f"Invalid store connection string: {connection_string}")

        protocol, params = connection_string.split("://", 1)

        if protocol not in self._stores:
            raise PluginNotFoundError(f"Store protocol '{protocol}' not registered")

        return self._stores[protocol].from_connection_string(connection_string)

    # Visibility registration
    def register_visibility(self, name: str, visibility_cls: type[Visibility]) -> None:
        """Register a visibility policy."""
        self._visibility[name] = visibility_cls

    def get_visibility(self, spec: str | dict) -> Visibility:
        """Instantiate a visibility policy from a string or dict.

        Examples:
            "public"
            "private:agent1,agent2"
            "labelled:clearance:secret"
            {"type": "geographic", "regions": ["EU", "US"]}
        """
        if isinstance(spec, dict):
            type_name = spec.pop("type")
            if type_name not in self._visibility:
                raise PluginNotFoundError(f"Visibility '{type_name}' not registered")
            return self._visibility[type_name](**spec)

        # Parse string format
        parts = spec.split(":", 1)
        type_name = parts[0]

        if type_name not in self._visibility:
            raise PluginNotFoundError(f"Visibility '{type_name}' not registered")

        # Type-specific parsing
        if type_name == "private":
            agents = parts[1].split(",") if len(parts) > 1 else []
            return PrivateVisibility(agents=set(agents))
        elif type_name == "labelled":
            labels = parts[1].split(",") if len(parts) > 1 else []
            return LabelledVisibility(required_labels=set(labels))
        else:
            return self._visibility[type_name]()

    # Factory registration (for custom instantiation logic)
    def register_factory(self, name: str, factory: Callable) -> None:
        """Register a custom factory function."""
        self._factories[name] = factory

    def list_components(self) -> list[str]:
        """List all registered components."""
        return list(self._components.keys())

    def list_engines(self) -> list[str]:
        """List all registered engines."""
        return list(self._engines.keys())

    def list_stores(self) -> list[str]:
        """List all registered store protocols."""
        return list(self._stores.keys())

    def list_visibility(self) -> list[str]:
        """List all registered visibility types."""
        return list(self._visibility.keys())

# Global plugin registry instance
plugin_registry = PluginRegistry()

# Decorator helpers
def register_component(name: str):
    """Decorator to register an agent component."""
    def decorator(cls: type[AgentComponent]):
        plugin_registry.register_component(name, cls)
        return cls
    return decorator

def register_engine(name: str):
    """Decorator to register an engine."""
    def decorator(cls: type[EngineComponent]):
        plugin_registry.register_engine(name, cls)
        return cls
    return decorator

def register_store(protocol: str):
    """Decorator to register a blackboard store."""
    def decorator(cls: type[BlackboardStore]):
        plugin_registry.register_store(protocol, cls)
        return cls
    return decorator

def register_visibility(name: str):
    """Decorator to register a visibility policy."""
    def decorator(cls: type[Visibility]):
        plugin_registry.register_visibility(name, cls)
        return cls
    return decorator
```

**Usage Examples:**

```python
# 1. Component Plugin (flock-rate-limiter package)
from flock.plugins import register_component
from flock.components import AgentComponent

@register_component("rate_limiter")
class RateLimiter(AgentComponent):
    max_calls: int = 10
    window: int = 60

    async def on_pre_evaluate(self, agent, ctx, inputs):
        # Rate limiting logic
        ...
        return inputs

# Usage:
agent.with_utilities("rate_limiter", max_calls=5)

# 2. Store Plugin (flock-redis-store package)
from flock.plugins import register_store
from flock.store import BlackboardStore

@register_store("redis")
class RedisBlackboardStore(BlackboardStore):
    @classmethod
    def from_connection_string(cls, conn_str: str):
        # Parse redis://host:port/db
        ...
        return cls(host=host, port=port, db=db)

    async def publish(self, artifact):
        # Redis implementation
        ...

# Usage:
flock = Flock("openai/gpt-4.1", store="redis://localhost:6379")

# 3. Engine Plugin (flock-langchain-engine package)
from flock.plugins import register_engine
from flock.components import EngineComponent

@register_engine("langchain")
class LangChainEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs):
        # LangChain implementation
        ...

# Usage:
agent.with_engines("langchain", model="openai/gpt-4o")

# 4. Visibility Plugin (flock-geographic-visibility package)
from flock.plugins import register_visibility
from flock.visibility import Visibility

@register_visibility("geographic")
class GeographicVisibility(Visibility):
    kind: Literal["Geographic"] = "Geographic"
    regions: set[str]

    def allows(self, agent, *, now=None):
        return agent.region in self.regions

# Usage:
agent.publishes(Data, visibility="geographic:EU,US")
```

### 2. Plugin Discovery Mechanism

**Goal:** Auto-discover plugins from installed packages.

**Design:**

```python
# C:\workspace\whiteduck\flock\src\flock\plugins\discovery.py

import importlib
import importlib.metadata
from pathlib import Path

def discover_plugins(entry_point_group: str = "flock.plugins"):
    """Discover and load plugins from entry points.

    Plugins declare entry points in pyproject.toml:

    [project.entry-points."flock.plugins"]
    rate_limiter = "flock_rate_limiter:RateLimiter"
    redis_store = "flock_redis_store:RedisBlackboardStore"
    """
    discovered = []

    for entry_point in importlib.metadata.entry_points().select(group=entry_point_group):
        try:
            plugin = entry_point.load()
            discovered.append({
                "name": entry_point.name,
                "module": entry_point.value.split(":")[0],
                "plugin": plugin
            })
        except Exception as e:
            # Log but don't crash on plugin load errors
            logger.warning(f"Failed to load plugin {entry_point.name}: {e}")

    return discovered

def auto_register_plugins():
    """Auto-register all discovered plugins."""
    plugins = discover_plugins()

    for plugin_info in plugins:
        plugin = plugin_info["plugin"]
        name = plugin_info["name"]

        # Auto-detect plugin type and register
        if issubclass(plugin, AgentComponent):
            plugin_registry.register_component(name, plugin)
        elif issubclass(plugin, EngineComponent):
            plugin_registry.register_engine(name, plugin)
        elif issubclass(plugin, BlackboardStore):
            # Extract protocol from name (e.g., "redis_store" -> "redis")
            protocol = name.split("_")[0]
            plugin_registry.register_store(protocol, plugin)
        elif issubclass(plugin, Visibility):
            plugin_registry.register_visibility(name, plugin)

# Auto-register on import
auto_register_plugins()
```

**Third-Party Plugin Template:**

```toml
# flock-redis-store/pyproject.toml

[project]
name = "flock-redis-store"
version = "0.1.0"
description = "Redis backend for Flock blackboard"
dependencies = [
    "flock-core>=0.5.0",
    "aioredis>=2.0.0"
]

[project.entry-points."flock.plugins"]
redis_store = "flock_redis_store:RedisBlackboardStore"

[project.urls]
Homepage = "https://github.com/user/flock-redis-store"
Documentation = "https://flock-redis-store.readthedocs.io"
```

### 3. Plugin Metadata & Validation

**Goal:** Ensure plugin quality and compatibility.

**Design:**

```python
# C:\workspace\whiteduck\flock\src\flock\plugins\metadata.py

from pydantic import BaseModel
from typing import Literal

class PluginMetadata(BaseModel):
    """Metadata for Flock plugins."""

    name: str
    version: str
    description: str
    author: str
    license: str

    # Compatibility
    min_flock_version: str = "0.5.0"
    max_flock_version: str | None = None

    # Classification
    plugin_type: Literal["component", "engine", "store", "visibility", "other"]
    tags: list[str] = []

    # Quality indicators
    test_coverage: float | None = None  # 0.0-1.0
    has_documentation: bool = False
    has_examples: bool = False

    # Performance hints
    estimated_overhead: float | None = None  # 0.0-1.0
    memory_intensive: bool = False
    io_intensive: bool = False

    # Security
    requires_network: bool = False
    requires_filesystem: bool = False
    requires_credentials: bool = False

class PluginValidator:
    """Validate plugin quality and compatibility."""

    def validate(self, plugin_cls, metadata: PluginMetadata) -> list[str]:
        """Return list of validation warnings."""
        warnings = []

        # Version compatibility check
        from packaging import version
        flock_version = version.parse(get_flock_version())
        min_version = version.parse(metadata.min_flock_version)

        if flock_version < min_version:
            warnings.append(f"Plugin requires Flock {metadata.min_flock_version}+, found {flock_version}")

        if metadata.max_flock_version:
            max_version = version.parse(metadata.max_flock_version)
            if flock_version > max_version:
                warnings.append(f"Plugin may not be compatible with Flock {flock_version}")

        # Type-specific validation
        if metadata.plugin_type == "component":
            if not issubclass(plugin_cls, AgentComponent):
                warnings.append("Component plugin must inherit from AgentComponent")

        elif metadata.plugin_type == "engine":
            if not issubclass(plugin_cls, EngineComponent):
                warnings.append("Engine plugin must inherit from EngineComponent")

            # Check for required methods
            if not hasattr(plugin_cls, "evaluate"):
                warnings.append("Engine must implement evaluate() method")

        elif metadata.plugin_type == "store":
            if not issubclass(plugin_cls, BlackboardStore):
                warnings.append("Store plugin must inherit from BlackboardStore")

            # Check for required methods
            required_methods = ["publish", "get", "list", "query_artifacts"]
            for method in required_methods:
                if not hasattr(plugin_cls, method):
                    warnings.append(f"Store must implement {method}() method")

        # Quality checks
        if metadata.test_coverage is not None and metadata.test_coverage < 0.7:
            warnings.append(f"Low test coverage ({metadata.test_coverage:.0%})")

        if not metadata.has_documentation:
            warnings.append("Plugin has no documentation")

        return warnings
```

### 4. OrchestratorComponent Lifecycle

**Current Gap:** No orchestrator-level components for cross-agent concerns.

**Proposal:**

```python
# C:\workspace\whiteduck\flock\src\flock\orchestrator_component.py

from flock.components import AgentComponent
from flock.runtime import Context
from flock.artifacts import Artifact

class OrchestratorComponent(BaseModel, metaclass=TracedModelMeta):
    """Base class for orchestrator-level components.

    Unlike AgentComponent (scoped to individual agents), OrchestratorComponent
    operates at the blackboard level, intercepting all artifacts and agent executions.

    Use cases:
    - Global rate limiting across all agents
    - Cross-agent metrics and monitoring
    - Circuit breakers for system-wide failures
    - Cost tracking and budgets
    - Audit logging for compliance
    """

    name: str | None = None

    # Orchestrator lifecycle hooks
    async def on_startup(self, orchestrator: Flock) -> None:
        """Called when orchestrator starts."""
        pass

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Called when orchestrator shuts down."""
        pass

    # Artifact interception
    async def on_before_publish(self, artifact: Artifact, orchestrator: Flock) -> Artifact | None:
        """Intercept artifact before publishing. Return None to block."""
        return artifact

    async def on_after_publish(self, artifact: Artifact, orchestrator: Flock) -> None:
        """Called after artifact is published."""
        pass

    # Agent execution hooks
    async def on_before_agent_execute(self, agent: Agent, ctx: Context, artifacts: list[Artifact]) -> list[Artifact] | None:
        """Intercept agent execution. Return None to block."""
        return artifacts

    async def on_after_agent_execute(self, agent: Agent, ctx: Context, outputs: list[Artifact]) -> None:
        """Called after agent execution completes."""
        pass

    # System health
    async def check_health(self, orchestrator: Flock) -> dict[str, Any]:
        """Return health status (for monitoring endpoints)."""
        return {"status": "healthy"}

# Usage in orchestrator:
class Flock:
    def __init__(self, ...):
        ...
        self._orchestrator_components: list[OrchestratorComponent] = []

    def with_orchestrator_components(self, *components: OrchestratorComponent) -> Flock:
        """Add orchestrator-level components."""
        self._orchestrator_components.extend(components)
        return self

    async def _persist_and_schedule(self, artifact: Artifact) -> None:
        # Run before-publish hooks
        for component in self._orchestrator_components:
            artifact = await component.on_before_publish(artifact, self)
            if artifact is None:
                return  # Blocked by component

        # Existing publish logic
        await self.store.publish(artifact)
        self.metrics["artifacts_published"] += 1

        # Run after-publish hooks
        for component in self._orchestrator_components:
            await component.on_after_publish(artifact, self)

        # Schedule agents
        await self._schedule_artifact(artifact)
```

**Example OrchestratorComponent:**

```python
# flock-cost-tracker package
from flock.orchestrator_component import OrchestratorComponent

class CostTracker(OrchestratorComponent):
    """Track LLM costs across all agents."""

    max_cost_per_hour: float = 10.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hourly_cost = 0.0
        self.last_reset = datetime.now()

    async def on_after_agent_execute(self, agent, ctx, outputs):
        # Estimate cost from context state
        if "dspy" in ctx.state:
            model = ctx.state["dspy"]["model"]
            # Estimate token count and cost
            input_tokens = estimate_tokens(ctx.state["dspy"]["input"])
            output_tokens = estimate_tokens(ctx.state["dspy"]["output"])
            cost = calculate_cost(model, input_tokens, output_tokens)

            self.hourly_cost += cost

            # Reset hourly counter
            if datetime.now() - self.last_reset > timedelta(hours=1):
                self.hourly_cost = 0.0
                self.last_reset = datetime.now()

    async def on_before_agent_execute(self, agent, ctx, artifacts):
        # Circuit breaker: block if hourly cost exceeded
        if self.hourly_cost > self.max_cost_per_hour:
            raise CostLimitExceeded(f"Hourly cost limit ${self.max_cost_per_hour} exceeded")
        return artifacts

    async def check_health(self, orchestrator):
        return {
            "status": "healthy",
            "hourly_cost": self.hourly_cost,
            "cost_limit": self.max_cost_per_hour,
            "utilization": self.hourly_cost / self.max_cost_per_hour
        }

# Usage:
flock = Flock("openai/gpt-4.1").with_orchestrator_components(
    CostTracker(max_cost_per_hour=5.0)
)
```

---

## Third-Party Ecosystem Roadmap

### Phase 1: Foundation (v0.6.0 - Q1 2025)

**Goals:**
- Establish plugin registry pattern
- Document extension points
- Create plugin template repository

**Deliverables:**
1. `flock.plugins` module with registry
2. Plugin discovery mechanism (entry points)
3. Plugin metadata and validation
4. Developer documentation:
   - "Creating Your First Plugin"
   - "Component Plugin Guide"
   - "Engine Plugin Guide"
   - "Store Plugin Guide"
   - "Testing Your Plugin"

**Example First-Party Plugins:**
- `flock-rate-limiter` - Reference component plugin
- `flock-sqlite-store` (already exists, extract to plugin)
- `flock-metrics-prometheus` - Orchestrator component

### Phase 2: Ecosystem (v0.7.0 - Q2 2025)

**Goals:**
- Enable third-party plugin development
- Create plugin marketplace guidelines
- Build community

**Deliverables:**
1. Plugin marketplace website (flock-plugins.io)
2. Plugin submission process
3. Quality badges (test coverage, documentation, examples)
4. Featured plugins showcase
5. Plugin search and discovery

**Example Community Plugins:**
- `flock-redis-store` - High-performance distributed store
- `flock-postgres-store` - Production-grade persistence
- `flock-langchain-engine` - LangChain integration
- `flock-llamaindex-engine` - LlamaIndex integration
- `flock-anthropic-engine` - Native Claude API (no DSPy)
- `flock-google-engine` - Native Gemini API
- `flock-openai-engine` - Native OpenAI API (no DSPy)
- `flock-cost-tracker` - Cost monitoring component
- `flock-audit-logger` - Compliance logging component
- `flock-semantic-cache` - Embedding-based cache

### Phase 3: Marketplace (v0.8.0 - Q3 2025)

**Goals:**
- Mature plugin ecosystem
- Commercial plugin support
- Enterprise integrations

**Deliverables:**
1. Plugin versioning and deprecation policy
2. Plugin security scanning
3. Commercial plugin marketplace
4. Enterprise support tier

**Example Enterprise Plugins:**
- `flock-azure-store` - Azure Cosmos DB backend
- `flock-aws-store` - AWS DynamoDB backend
- `flock-gcp-store` - GCP Firestore backend
- `flock-kafka-events` - Event streaming integration
- `flock-oauth2-auth` - Authentication component
- `flock-saml-auth` - Enterprise SSO
- `flock-kubernetes-operator` - K8s deployment
- `flock-datadog-monitoring` - Enterprise observability

### Phase 4: Platform (v1.0.0 - Q4 2025)

**Goals:**
- Flock as a platform ecosystem
- Plugin certification program
- Revenue sharing model

**Deliverables:**
1. Certified plugin program
2. Plugin revenue sharing
3. Enterprise plugin marketplace
4. Plugin training and certification

---

## Comparison to Other Frameworks

### LangChain

**Extensibility Model:**
- Heavy inheritance-based design
- Many base classes (BaseLoader, BaseRetriever, BaseTool, etc.)
- Duck typing for compatibility

**Strengths:**
- Mature ecosystem (1000+ integrations)
- Well-documented extension patterns
- Strong community support

**Weaknesses:**
- Inheritance hierarchy complexity
- Breaking changes across versions
- Tight coupling between components

**Flock Advantage:**
- Simpler base classes (AgentComponent vs. 50+ LangChain bases)
- Composition over inheritance
- Plugin registry reduces import complexity

### CrewAI

**Extensibility Model:**
- Tool-focused architecture
- Simple agent + task + tool model
- LangChain integration for tools

**Strengths:**
- Simple mental model
- Easy tool creation
- Good documentation

**Weaknesses:**
- Limited orchestration patterns
- No native type safety
- LangChain dependency for advanced features

**Flock Advantage:**
- Richer orchestration (AND gates, joins, batches)
- Native type safety (Pydantic)
- No heavy framework dependencies

### AutoGen

**Extensibility Model:**
- Conversable agent pattern
- Python function registration
- Execution modes (code, functions, default)

**Strengths:**
- Simple function-as-tool pattern
- Human-in-the-loop support
- Research-driven design

**Weaknesses:**
- Limited production features
- No native persistence
- Conversation-centric (hard to parallelize)

**Flock Advantage:**
- Parallel execution by default
- Production-grade observability
- Blackboard > conversation for complex workflows

### DSPy

**Extensibility Model:**
- Module-based design (like PyTorch)
- Signature-based I/O
- LM-agnostic abstractions

**Strengths:**
- Clean abstractions
- Optimization-friendly
- Strong typing

**Weaknesses:**
- Limited multi-agent support
- No orchestration layer
- Single-agent focus

**Flock Advantage:**
- Built on DSPy but adds orchestration
- Multi-agent by design
- Retains DSPy's strengths (signatures, optimization)

### Summary Matrix

| Framework | Extension Model | Ease of Use | Ecosystem Size | Type Safety | Production Ready |
|-----------|----------------|-------------|----------------|-------------|------------------|
| **Flock** | Component + Registry | ⭐⭐⭐⭐ | ⭐⭐ (growing) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **LangChain** | Inheritance | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **CrewAI** | Tools | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **AutoGen** | Functions | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **DSPy** | Modules | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## Best Practices for Extension Developers

### 1. Component Development

**DO:**
- ✅ Keep components stateless when possible
- ✅ Use `async` for all I/O operations
- ✅ Return modified inputs (don't mutate in place)
- ✅ Handle errors gracefully (log, don't crash)
- ✅ Add type hints everywhere
- ✅ Document configuration options
- ✅ Write tests for all lifecycle hooks

**DON'T:**
- ❌ Block the event loop (no `time.sleep()`)
- ❌ Mutate agent or context state unexpectedly
- ❌ Raise exceptions in `on_error()` hook
- ❌ Store secrets in config (use environment variables)
- ❌ Depend on execution order of other components

**Example:**

```python
@register_component("token_counter")
class TokenCounter(AgentComponent):
    """Count tokens used by agents."""

    def __init__(self):
        super().__init__()
        self.total_tokens = 0

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        # Extract token count from DSPy result
        if "dspy" in result.state:
            model = result.state["dspy"]["model"]
            output = result.state["dspy"]["raw"]

            # Estimate tokens
            tokens = estimate_tokens(output)
            self.total_tokens += tokens

            # Add to result metrics
            result.metrics["tokens_used"] = tokens

        return result
```

### 2. Engine Development

**DO:**
- ✅ Implement `evaluate()` method
- ✅ Return `EvalResult` with validated outputs
- ✅ Support conversation context (if applicable)
- ✅ Add cost/latency metrics
- ✅ Handle rate limits gracefully
- ✅ Support streaming (if possible)

**DON'T:**
- ❌ Assume DSPy availability
- ❌ Hardcode API keys
- ❌ Return None from evaluate()
- ❌ Ignore output schema validation
- ❌ Block indefinitely on API calls

**Example:**

```python
@register_engine("anthropic_native")
class AnthropicEngine(EngineComponent):
    """Native Claude API (no DSPy)."""

    model: str = "claude-3-5-sonnet-20241022"
    api_key: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))

    async def evaluate(self, agent, ctx, inputs):
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # Build messages from inputs
        messages = []
        for artifact in inputs.artifacts:
            messages.append({
                "role": "user",
                "content": json.dumps(artifact.payload)
            })

        # Call Claude API
        response = await client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=messages
        )

        # Parse response
        output_text = response.content[0].text
        output_data = json.loads(output_text)

        # Validate against output schema
        output_model = agent.outputs[0].spec.model
        validated_output = output_model(**output_data)

        # Create artifacts
        artifact = Artifact(
            type=agent.outputs[0].spec.type_name,
            payload=validated_output.model_dump(),
            produced_by=agent.name
        )

        return EvalResult(
            artifacts=[artifact],
            state=inputs.state,
            metrics={
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                "cost_usd": calculate_cost(self.model, response.usage)
            }
        )
```

### 3. Store Development

**DO:**
- ✅ Implement all BlackboardStore methods
- ✅ Support `FilterConfig` properly
- ✅ Add connection pooling
- ✅ Handle connection failures gracefully
- ✅ Implement health checks
- ✅ Add indexes for performance
- ✅ Support pagination

**DON'T:**
- ❌ Return `NotImplementedError` for core methods
- ❌ Silently drop data
- ❌ Block on network I/O
- ❌ Leak connections
- ❌ Ignore transaction safety (if applicable)

**Example:**

```python
@register_store("postgres")
class PostgresBlackboardStore(BlackboardStore):
    """Production-grade PostgreSQL backend."""

    @classmethod
    def from_connection_string(cls, conn_str: str):
        # Parse postgres://user:pass@host:port/db
        parsed = urlparse(conn_str)
        return cls(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/"),
            user=parsed.username,
            password=parsed.password
        )

    def __init__(self, host, port, database, user, password):
        self.pool = None
        self.config = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password
        }

    async def _get_pool(self):
        if self.pool is None:
            import asyncpg
            self.pool = await asyncpg.create_pool(**self.config)
        return self.pool

    async def publish(self, artifact: Artifact) -> None:
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO artifacts (id, type, payload, produced_by, created_at, visibility, tags)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE SET
                    type = EXCLUDED.type,
                    payload = EXCLUDED.payload,
                    produced_by = EXCLUDED.produced_by,
                    created_at = EXCLUDED.created_at,
                    visibility = EXCLUDED.visibility,
                    tags = EXCLUDED.tags
            """,
                str(artifact.id),
                artifact.type,
                json.dumps(artifact.payload),
                artifact.produced_by,
                artifact.created_at,
                json.dumps(artifact.visibility.model_dump()),
                list(artifact.tags)
            )

    async def get(self, artifact_id: UUID) -> Artifact | None:
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, type, payload, produced_by, created_at, visibility, tags
                FROM artifacts
                WHERE id = $1
            """, str(artifact_id))

            if not row:
                return None

            return Artifact(
                id=UUID(row["id"]),
                type=row["type"],
                payload=json.loads(row["payload"]),
                produced_by=row["produced_by"],
                created_at=row["created_at"],
                visibility=_deserialize_visibility(json.loads(row["visibility"])),
                tags=set(row["tags"])
            )

    # ... implement other methods ...
```

### 4. Testing Your Plugin

**Structure:**

```
flock-my-plugin/
├── src/
│   └── flock_my_plugin/
│       ├── __init__.py
│       └── my_component.py
├── tests/
│   ├── test_basic.py
│   ├── test_integration.py
│   └── test_edge_cases.py
├── examples/
│   └── basic_usage.py
├── docs/
│   ├── index.md
│   └── api.md
├── pyproject.toml
└── README.md
```

**Test Examples:**

```python
# tests/test_basic.py
import pytest
from flock import Flock, flock_type
from flock_my_plugin import MyComponent

@flock_type
class TestInput(BaseModel):
    value: int

@flock_type
class TestOutput(BaseModel):
    result: int

@pytest.mark.asyncio
async def test_component_basic():
    """Test component in isolation."""
    flock = Flock("openai/gpt-4o-mini")

    agent = (
        flock.agent("test")
        .consumes(TestInput)
        .publishes(TestOutput)
        .with_utilities(MyComponent(config="value"))
    )

    # Test component is registered
    assert any(isinstance(u, MyComponent) for u in agent.agent.utilities)

    # Test component processes data correctly
    result = await flock.arun(agent, TestInput(value=42))
    assert len(result) == 1
    assert result[0].type == "TestOutput"

@pytest.mark.asyncio
async def test_component_error_handling():
    """Test component handles errors gracefully."""
    flock = Flock("openai/gpt-4o-mini")

    agent = (
        flock.agent("test")
        .consumes(TestInput)
        .publishes(TestOutput)
        .with_utilities(MyComponent(config="invalid"))
    )

    # Component should log error but not crash
    result = await flock.arun(agent, TestInput(value=42))
    # Assert expected behavior
```

### 5. Documentation Requirements

**Minimum Documentation:**

1. **README.md:**
   - What the plugin does
   - Installation instructions
   - Quick start example
   - Configuration options
   - Requirements (Python version, dependencies)

2. **API Documentation:**
   - Docstrings on all public methods
   - Type hints on all parameters
   - Example usage for each method

3. **Examples:**
   - At least one working example
   - Cover common use cases
   - Show integration with Flock

4. **Changelog:**
   - Version history
   - Breaking changes
   - Migration guides

**Example README.md:**

```markdown
# flock-rate-limiter

Rate limiting component for Flock agents.

## Installation

```bash
pip install flock-rate-limiter
```

## Quick Start

```python
from flock import Flock
from flock_rate_limiter import RateLimiter

flock = Flock("openai/gpt-4.1")

agent = (
    flock.agent("analyzer")
    .consumes(Task)
    .publishes(Analysis)
    .with_utilities(RateLimiter(max_calls=10, window=60))
)
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_calls` | `int` | `10` | Maximum calls per window |
| `window` | `int` | `60` | Time window in seconds |
| `strategy` | `str` | `"sliding"` | Rate limiting strategy |

## Advanced Usage

See [examples/](examples/) for more examples.

## Requirements

- Python 3.10+
- flock-core >= 0.5.0

## License

MIT
```

---

## Action Items

### Immediate (v0.5.1 - Next 2 Weeks)

1. **Document Current Extension Points**
   - Write "Extensibility Guide" documentation
   - Add examples for each extension type
   - Create plugin template repository

2. **Add Plugin Registry Foundation**
   - Implement `PluginRegistry` class
   - Add `register_*` decorators
   - Add string-based instantiation for stores

3. **Extract First Plugin**
   - Move `SQLiteBlackboardStore` to separate package
   - Test plugin development workflow
   - Document lessons learned

### Short-Term (v0.6.0 - Q1 2025)

1. **Implement OrchestratorComponent**
   - Add lifecycle hooks
   - Document use cases
   - Create example components (cost tracker, metrics)

2. **Add Plugin Discovery**
   - Implement entry point loading
   - Add auto-registration
   - Test with external plugins

3. **Create Plugin Marketplace**
   - Build plugin website
   - Add submission process
   - Feature first community plugins

### Medium-Term (v0.7.0 - Q2 2025)

1. **Mature Plugin Ecosystem**
   - 10+ community plugins
   - Commercial plugin support
   - Enterprise integrations

2. **Add Plugin Validation**
   - Metadata schema
   - Quality badges
   - Security scanning

3. **Document Best Practices**
   - Testing guide
   - Security guide
   - Performance guide

### Long-Term (v1.0.0 - Q4 2025)

1. **Plugin Certification Program**
   - Certification criteria
   - Training materials
   - Revenue sharing

2. **Enterprise Plugin Marketplace**
   - Commercial plugins
   - Support tiers
   - SLA guarantees

---

## Conclusion

**Current State:**
- ✅ Solid foundation with 7-hook component lifecycle
- ✅ Clean engine and store abstractions
- ⚠️ Missing plugin registry and discovery
- ⚠️ No orchestrator-level extension points
- ⚠️ Limited documentation for extension developers

**Recommendations:**
1. Prioritize plugin registry pattern (critical for ecosystem)
2. Add OrchestratorComponent for cross-agent concerns
3. Document extension points comprehensively
4. Extract first plugin to validate workflow
5. Build plugin marketplace to foster community

**Competitive Position:**
- Flock's component system is simpler than LangChain's inheritance hierarchy
- Plugin registry will enable easier third-party development than current competitors
- Type safety and Pydantic validation give plugin developers confidence
- Blackboard architecture enables compositional plugins (vs. rigid graph-based systems)

**Timeline to Healthy Ecosystem:**
- **v0.6.0 (Q1 2025):** Foundation in place
- **v0.7.0 (Q2 2025):** 10+ community plugins
- **v1.0.0 (Q4 2025):** Mature plugin marketplace

The path forward is clear: formalize the plugin architecture, document extension points, and build the community. Flock's clean abstractions and type safety position it well for a thriving third-party ecosystem.
