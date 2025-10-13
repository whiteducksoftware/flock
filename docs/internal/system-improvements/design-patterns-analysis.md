# Design Pattern Analysis: Flock Framework

**Date**: 2025-10-13
**Analyst**: Quality Architecture Review
**Framework Version**: Current main branch (feat/improving-examples)

---

## Executive Summary

This document analyzes the Flock blackboard-based agent orchestration framework to identify opportunities for applying Gang of Four (GoF) and modern Python design patterns. The analysis focuses on practical improvements to code quality, maintainability, extensibility, testability, and developer experience.

### Key Findings

- **Currently Well-Implemented Patterns**: Builder (AgentBuilder), Observer (pub-sub), Strategy (engines), Chain of Responsibility (subscription matching), Context Manager (tracing)
- **High-Impact Opportunities**: 10 pattern improvements identified
- **Quick Wins**: 4 low-complexity, high-impact improvements
- **Architectural Strengths**: Clean separation of concerns, extensible component architecture, robust subscription model

---

## Table of Contents

1. [Patterns Already in Use](#patterns-already-in-use)
2. [Creational Patterns](#creational-patterns)
3. [Structural Patterns](#structural-patterns)
4. [Behavioral Patterns](#behavioral-patterns)
5. [Modern Python Patterns](#modern-python-patterns)
6. [Prioritized Recommendations](#prioritized-recommendations)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Patterns Already in Use

### 1. Builder Pattern (AgentBuilder)
**Location**: `src/flock/agent.py:441-1028`

**Current Implementation**:
```python
agent = (
    flock.agent("pizza_master")
    .description("Creates pizza recipes")
    .consumes(Idea)
    .publishes(Pizza)
    .with_utilities(RateLimiter())
)
```

**Assessment**: Excellent implementation. Fluent API provides clear, composable agent configuration.

---

### 2. Strategy Pattern (EngineComponent)
**Location**: `src/flock/components.py:92-183`, `src/flock/engines/dspy_engine.py`

**Current Implementation**:
```python
class EngineComponent(AgentComponent):
    async def evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        raise NotImplementedError
```

**Assessment**: Clean strategy abstraction allows pluggable evaluation engines (DSPy, custom, hybrid).

---

### 3. Observer Pattern (Pub-Sub)
**Location**: `src/flock/orchestrator.py:872-980`

**Current Implementation**:
```python
async def publish(self, obj: BaseModel) -> Artifact:
    await self._persist_and_schedule(artifact)  # Notify subscribers

async def _schedule_artifact(self, artifact: Artifact) -> None:
    for agent in self.agents:
        for subscription in agent.subscriptions:
            if subscription.matches(artifact):
                self._schedule_task(agent, artifacts)
```

**Assessment**: Event-driven architecture with subscription filtering. Works well but could benefit from explicit Observer abstraction.

---

### 4. Chain of Responsibility (Subscription Matching)
**Location**: `src/flock/orchestrator.py:877-980`

**Current Implementation**: Sequential checking of visibility, type matching, predicates, correlation, batching.

**Assessment**: Implicit chain. Could benefit from explicit handler chain for extensibility.

---

### 5. Context Manager (Tracing)
**Location**: `src/flock/orchestrator.py:330-376`

**Current Implementation**:
```python
@asynccontextmanager
async def traced_run(self, name: str = "workflow") -> AsyncGenerator[Any, None]:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(name) as span:
        yield span
```

**Assessment**: Excellent use of async context managers for unified tracing.

---

## Creational Patterns

### 1. Abstract Factory for Storage Backends

**Impact**: High
**Complexity**: Medium
**Priority**: Should-Have

#### Problem
Storage backend instantiation is direct and inflexible:

```python
# orchestrator.py:121
self.store: BlackboardStore = store or InMemoryBlackboardStore()
```

Users need to manually instantiate specific backends, making configuration cumbersome.

#### Proposed Pattern: Abstract Factory

```python
# store_factory.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class BlackboardStoreFactory(ABC):
    """Abstract factory for creating storage backends."""

    @abstractmethod
    def create_store(self, **config: Any) -> BlackboardStore:
        """Create and configure a storage backend."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get factory name for registration."""
        pass


class InMemoryStoreFactory(BlackboardStoreFactory):
    def create_store(self, **config: Any) -> BlackboardStore:
        return InMemoryBlackboardStore()

    def get_name(self) -> str:
        return "memory"


class SQLiteStoreFactory(BlackboardStoreFactory):
    def create_store(self, **config: Any) -> BlackboardStore:
        db_path = config.get("db_path", ".flock/blackboard.db")
        timeout = config.get("timeout", 5.0)
        return SQLiteBlackboardStore(db_path, timeout=timeout)

    def get_name(self) -> str:
        return "sqlite"


class StoreRegistry:
    """Registry for storage backend factories."""

    def __init__(self):
        self._factories: Dict[str, BlackboardStoreFactory] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(InMemoryStoreFactory())
        self.register(SQLiteStoreFactory())

    def register(self, factory: BlackboardStoreFactory) -> None:
        self._factories[factory.get_name()] = factory

    def create(self, store_type: str, **config: Any) -> BlackboardStore:
        if store_type not in self._factories:
            raise ValueError(f"Unknown store type: {store_type}")
        return self._factories[store_type].create_store(**config)


# Global registry
store_registry = StoreRegistry()


# Usage in Flock
class Flock:
    def __init__(
        self,
        model: str | None = None,
        *,
        store: BlackboardStore | str | None = None,
        store_config: dict[str, Any] | None = None,
        max_agent_iterations: int = 1000,
    ):
        # Support both explicit instance and factory-based creation
        if isinstance(store, str):
            self.store = store_registry.create(store, **(store_config or {}))
        elif store is None:
            self.store = store_registry.create("memory")
        else:
            self.store = store
```

#### Benefits
1. **Simplified Configuration**: `Flock(store="sqlite", store_config={"db_path": "custom.db"})`
2. **Extensibility**: Users can register custom backends without modifying Flock
3. **Testability**: Easy to inject test doubles
4. **Consistency**: Centralized backend creation logic

#### Trade-offs
- **Complexity**: Adds factory layer
- **Indirection**: One more abstraction to understand

#### Files to Modify
- `src/flock/orchestrator.py:86-121` (Flock.__init__)
- `src/flock/store.py` (add factory classes)

---

### 2. Factory Method for Engine Selection

**Impact**: Medium
**Complexity**: Low
**Priority**: Should-Have

#### Problem
Engine resolution is tightly coupled:

```python
# agent.py:354-367
def _resolve_engines(self) -> list[EngineComponent]:
    if self.engines:
        return self.engines
    try:
        from flock.engines import DSPyEngine
    except Exception:
        return []

    default_engine = DSPyEngine(
        model=self._orchestrator.model or os.getenv("DEFAULT_MODEL", "openai/gpt-4.1"),
        instructions=self.description,
    )
    self.engines = [default_engine]
    return self.engines
```

#### Proposed Pattern: Factory Method

```python
# engines/factory.py
from typing import Dict, Type, Callable

class EngineFactory:
    """Factory for creating engine instances."""

    def __init__(self):
        self._builders: Dict[str, Callable[..., EngineComponent]] = {}
        self._register_defaults()

    def _register_defaults(self):
        def create_dspy(**kwargs):
            from flock.engines import DSPyEngine
            return DSPyEngine(**kwargs)

        self.register("dspy", create_dspy)

    def register(self, name: str, builder: Callable[..., EngineComponent]) -> None:
        """Register a custom engine builder."""
        self._builders[name] = builder

    def create(self, name: str, **config) -> EngineComponent:
        if name not in self._builders:
            raise ValueError(f"Unknown engine: {name}")
        return self._builders[name](**config)

    def create_default(self, model: str | None, instructions: str | None) -> EngineComponent:
        """Create the default engine (DSPy) with minimal config."""
        return self.create("dspy", model=model, instructions=instructions)


# Global factory
engine_factory = EngineFactory()


# Usage
class Agent:
    def _resolve_engines(self) -> list[EngineComponent]:
        if self.engines:
            return self.engines

        try:
            engine = engine_factory.create_default(
                model=self._orchestrator.model or os.getenv("DEFAULT_MODEL", "openai/gpt-4.1"),
                instructions=self.description,
            )
            self.engines = [engine]
            return self.engines
        except Exception:
            return []
```

#### Benefits
1. **Extensibility**: Easy to add custom engines without modifying agent.py
2. **Configuration**: Centralized engine creation
3. **Testing**: Mock engine injection

#### Trade-offs
- **Minimal**: Low complexity addition

#### Files to Modify
- `src/flock/agent.py:354-367`
- `src/flock/engines/__init__.py` (add factory)

---

### 3. Prototype Pattern for Artifact Cloning

**Impact**: Low
**Complexity**: Low
**Priority**: Nice-to-Have

#### Problem
No built-in way to clone artifacts with modifications:

```python
# User code workaround
original = await store.get(artifact_id)
modified = Artifact(
    type=original.type,
    payload={**original.payload, "status": "updated"},
    produced_by="updater",
    visibility=original.visibility,
    correlation_id=original.correlation_id,
    # ... tedious copying
)
```

#### Proposed Pattern: Prototype

```python
# artifacts.py
class Artifact(BaseModel):
    # ... existing fields ...

    def clone(
        self,
        *,
        payload: dict[str, Any] | None = None,
        produced_by: str | None = None,
        visibility: Visibility | None = None,
        tags: set[str] | None = None,
        regenerate_id: bool = True,
        **overrides
    ) -> Artifact:
        """Clone artifact with selective modifications.

        Args:
            payload: New payload (defaults to copy of original)
            produced_by: New producer (defaults to original)
            visibility: New visibility (defaults to original)
            tags: New tags (defaults to copy of original)
            regenerate_id: If True, generates new UUID (default), if False preserves ID
            **overrides: Any other field overrides

        Returns:
            New Artifact instance

        Example:
            updated = original.clone(
                payload={**original.payload, "status": "processed"},
                produced_by="processor"
            )
        """
        data = self.model_dump()

        if regenerate_id:
            data["id"] = uuid4()

        if payload is not None:
            data["payload"] = payload
        if produced_by is not None:
            data["produced_by"] = produced_by
        if visibility is not None:
            data["visibility"] = visibility
        if tags is not None:
            data["tags"] = tags

        data.update(overrides)
        return Artifact(**data)
```

#### Benefits
1. **Convenience**: Simplified artifact modification workflows
2. **Safety**: Prevents accidental field omissions
3. **Clarity**: Intent-revealing method

#### Trade-offs
- **Minor**: Adds one method

#### Files to Modify
- `src/flock/artifacts.py:15-31`

---

## Structural Patterns

### 4. Adapter Pattern for Storage Backends

**Impact**: Medium
**Complexity**: Medium
**Priority**: Should-Have

#### Problem
Storage backends have tight coupling to internal types. Adding external backends (Redis, PostgreSQL, S3) requires deep integration.

#### Current Interface
```python
# store.py:126-221
class BlackboardStore:
    async def publish(self, artifact: Artifact) -> None:
        raise NotImplementedError

    async def get(self, artifact_id: UUID) -> Artifact | None:
        raise NotImplementedError

    # ... 10+ methods tightly coupled to Artifact, ConsumptionRecord, FilterConfig
```

#### Proposed Pattern: Adapter

```python
# store_adapters.py
from abc import ABC, abstractmethod
from typing import Any, Dict

class StorageBackend(ABC):
    """Generic storage backend interface (decoupled from Flock types)."""

    @abstractmethod
    async def store(self, key: str, value: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def retrieve(self, key: str) -> Dict[str, Any] | None:
        pass

    @abstractmethod
    async def query(self, filters: Dict[str, Any], limit: int, offset: int) -> list[Dict[str, Any]]:
        pass


class BlackboardStoreAdapter(BlackboardStore):
    """Adapter that bridges BlackboardStore to generic StorageBackend."""

    def __init__(self, backend: StorageBackend):
        self._backend = backend

    async def publish(self, artifact: Artifact) -> None:
        # Convert Artifact to generic dict
        data = {
            "id": str(artifact.id),
            "type": artifact.type,
            "payload": artifact.payload,
            "produced_by": artifact.produced_by,
            "visibility": artifact.visibility.model_dump(mode="json"),
            "created_at": artifact.created_at.isoformat(),
            # ... serialize all fields
        }
        await self._backend.store(f"artifact:{artifact.id}", data)

    async def get(self, artifact_id: UUID) -> Artifact | None:
        data = await self._backend.retrieve(f"artifact:{artifact_id}")
        if data is None:
            return None

        # Deserialize dict to Artifact
        return self._deserialize_artifact(data)

    def _deserialize_artifact(self, data: Dict[str, Any]) -> Artifact:
        # Convert generic dict back to Artifact
        # ... parsing logic
        pass


# Concrete adapters for external backends
class RedisStorageBackend(StorageBackend):
    """Redis adapter using generic interface."""

    def __init__(self, redis_url: str):
        import redis.asyncio as redis
        self._redis = redis.from_url(redis_url)

    async def store(self, key: str, value: Dict[str, Any]) -> None:
        import json
        await self._redis.set(key, json.dumps(value))

    async def retrieve(self, key: str) -> Dict[str, Any] | None:
        import json
        data = await self._redis.get(key)
        return json.loads(data) if data else None

    async def query(self, filters: Dict[str, Any], limit: int, offset: int) -> list[Dict[str, Any]]:
        # Use Redis search/indexing
        pass


# Usage
flock = Flock(store=BlackboardStoreAdapter(RedisStorageBackend("redis://localhost")))
```

#### Benefits
1. **Extensibility**: Easy to add new backends (Redis, Postgres, S3, etc.)
2. **Decoupling**: Storage backends don't need to know about Artifact internals
3. **Reusability**: Generic StorageBackend can be used outside Flock
4. **Testing**: Mock backends trivial

#### Trade-offs
- **Serialization Overhead**: Conversion between Artifact and dict
- **Complexity**: Additional adapter layer

#### Files to Modify
- `src/flock/store.py` (add adapter base classes)
- New file: `src/flock/adapters/redis_adapter.py`, `src/flock/adapters/postgres_adapter.py`

---

### 5. Proxy Pattern for Store Caching

**Impact**: High
**Complexity**: Low
**Priority**: Must-Have (Quick Win)

#### Problem
Every artifact read hits the backend, even for frequently accessed artifacts. No caching layer.

```python
# orchestrator.py:53-54
async def get(self, artifact_id) -> Artifact | None:
    return await self._orchestrator.store.get(artifact_id)
```

#### Proposed Pattern: Proxy (Caching Proxy)

```python
# store_proxy.py
from functools import lru_cache
from typing import Dict, Any
import asyncio

class CachingStoreProxy(BlackboardStore):
    """Caching proxy for BlackboardStore with TTL and size limits."""

    def __init__(
        self,
        backend: BlackboardStore,
        max_size: int = 1000,
        ttl_seconds: float = 60.0,
    ):
        self._backend = backend
        self._cache: Dict[UUID, tuple[Artifact, float]] = {}  # id -> (artifact, expiry_time)
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    async def publish(self, artifact: Artifact) -> None:
        # Write-through: publish to backend first
        await self._backend.publish(artifact)

        # Update cache
        async with self._lock:
            self._cache[artifact.id] = (artifact, asyncio.get_event_loop().time() + self._ttl)
            self._evict_if_needed()

    async def get(self, artifact_id: UUID) -> Artifact | None:
        async with self._lock:
            # Check cache
            cached = self._cache.get(artifact_id)
            if cached:
                artifact, expiry = cached
                if asyncio.get_event_loop().time() < expiry:
                    # Cache hit
                    return artifact
                else:
                    # Expired - remove
                    del self._cache[artifact_id]

        # Cache miss - fetch from backend
        artifact = await self._backend.get(artifact_id)
        if artifact:
            async with self._lock:
                self._cache[artifact_id] = (artifact, asyncio.get_event_loop().time() + self._ttl)
                self._evict_if_needed()

        return artifact

    def _evict_if_needed(self):
        """LRU eviction when cache exceeds max_size."""
        if len(self._cache) > self._max_size:
            # Evict oldest entry
            oldest_id = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_id]

    async def list(self) -> list[Artifact]:
        # No caching for list operations (too many combinations)
        return await self._backend.list()

    # Delegate all other methods to backend
    async def list_by_type(self, type_name: str) -> list[Artifact]:
        return await self._backend.list_by_type(type_name)

    # ... delegate remaining methods ...


# Usage
backend = InMemoryBlackboardStore()
cached_store = CachingStoreProxy(backend, max_size=5000, ttl_seconds=120.0)
flock = Flock(store=cached_store)
```

#### Benefits
1. **Performance**: Massive speedup for read-heavy workloads
2. **Transparent**: No changes to user code
3. **Configurable**: TTL and size limits tunable per deployment
4. **Metrics**: Easy to add cache hit/miss tracking

#### Trade-offs
- **Memory**: Cache consumes memory
- **Consistency**: TTL means brief stale reads (acceptable for artifacts)

#### Files to Modify
- New file: `src/flock/store_proxy.py`
- `src/flock/orchestrator.py:86-121` (optionally enable by default)

---

### 6. Decorator Pattern for Artifact Enrichment

**Impact**: High
**Complexity**: Medium
**Priority**: Should-Have

#### Problem
No extensible way to enrich artifacts with metadata (timestamps, tags, security labels) during publication.

```python
# Users manually add metadata
artifact = Artifact(type="Task", payload=data, produced_by="agent")
artifact.tags.add("high-priority")  # Manual tagging
artifact.tags.add("production")
```

#### Proposed Pattern: Decorator (Artifact Enrichment Pipeline)

```python
# artifact_decorators.py
from abc import ABC, abstractmethod

class ArtifactDecorator(ABC):
    """Base decorator for artifact enrichment."""

    @abstractmethod
    async def enrich(self, artifact: Artifact, ctx: Context) -> Artifact:
        """Enrich artifact with additional metadata."""
        pass


class TimestampDecorator(ArtifactDecorator):
    """Add processing timestamps."""

    async def enrich(self, artifact: Artifact, ctx: Context) -> Artifact:
        enriched_payload = {
            **artifact.payload,
            "_enriched_at": datetime.now(timezone.utc).isoformat(),
            "_enriched_by": ctx.task_id,
        }
        return artifact.clone(payload=enriched_payload, regenerate_id=False)


class TagDecorator(ArtifactDecorator):
    """Auto-tag artifacts based on rules."""

    def __init__(self, rules: Dict[str, Callable[[Artifact], bool]]):
        self._rules = rules  # {"urgent": lambda a: a.payload.get("priority", 0) > 8}

    async def enrich(self, artifact: Artifact, ctx: Context) -> Artifact:
        new_tags = set(artifact.tags)
        for tag, predicate in self._rules.items():
            if predicate(artifact):
                new_tags.add(tag)
        return artifact.clone(tags=new_tags, regenerate_id=False)


class SecurityLabelDecorator(ArtifactDecorator):
    """Add security classifications."""

    def __init__(self, classifier: Callable[[Artifact], str]):
        self._classifier = classifier

    async def enrich(self, artifact: Artifact, ctx: Context) -> Artifact:
        classification = self._classifier(artifact)
        enriched_payload = {
            **artifact.payload,
            "_security_classification": classification,
        }
        return artifact.clone(payload=enriched_payload, regenerate_id=False)


class EnrichmentPipeline:
    """Chain of decorators applied during publish."""

    def __init__(self, decorators: list[ArtifactDecorator] | None = None):
        self._decorators = decorators or []

    def add(self, decorator: ArtifactDecorator) -> None:
        self._decorators.append(decorator)

    async def enrich(self, artifact: Artifact, ctx: Context) -> Artifact:
        """Apply all decorators in sequence."""
        enriched = artifact
        for decorator in self._decorators:
            enriched = await decorator.enrich(enriched, ctx)
        return enriched


# Integration with Flock
class Flock:
    def __init__(self, ..., enrichment_pipeline: EnrichmentPipeline | None = None):
        self._enrichment_pipeline = enrichment_pipeline or EnrichmentPipeline()

    async def publish(self, obj, ...) -> Artifact:
        # ... create artifact ...

        # Apply enrichment pipeline
        if self._enrichment_pipeline:
            artifact = await self._enrichment_pipeline.enrich(artifact, Context(...))

        await self._persist_and_schedule(artifact)
        return artifact


# Usage
pipeline = EnrichmentPipeline([
    TimestampDecorator(),
    TagDecorator(rules={
        "urgent": lambda a: a.payload.get("priority", 0) > 8,
        "ml": lambda a: "model" in a.payload,
    }),
    SecurityLabelDecorator(classifier=my_classifier),
])

flock = Flock(enrichment_pipeline=pipeline)
```

#### Benefits
1. **Extensibility**: Add custom enrichment logic without modifying Flock
2. **Composability**: Chain multiple enrichers
3. **Reusability**: Share decorators across projects
4. **Testability**: Test enrichers in isolation

#### Trade-offs
- **Performance**: Additional processing per artifact
- **Complexity**: More concepts to understand

#### Files to Modify
- New file: `src/flock/artifact_decorators.py`
- `src/flock/orchestrator.py:641-735` (publish method)

---

## Behavioral Patterns

### 7. Explicit Chain of Responsibility for Subscription Matching

**Impact**: Medium
**Complexity**: Medium
**Priority**: Should-Have

#### Problem
Subscription matching logic is monolithic and hard to extend:

```python
# orchestrator.py:877-980
async def _schedule_artifact(self, artifact: Artifact) -> None:
    for agent in self.agents:
        for subscription in agent.subscriptions:
            # Implicit chain of checks
            if not subscription.accepts_events():
                continue
            if agent.prevent_self_trigger and artifact.produced_by == agent.name:
                continue
            if iteration_count >= self.max_agent_iterations:
                continue
            if not self._check_visibility(artifact, identity):
                continue
            if not subscription.matches(artifact):
                continue
            if self._seen_before(artifact, agent):
                continue
            # ... more checks ...
```

Adding new matching logic (e.g., rate limiting, priority queues) requires modifying this method.

#### Proposed Pattern: Chain of Responsibility

```python
# subscription_handlers.py
from abc import ABC, abstractmethod

class SubscriptionHandler(ABC):
    """Base handler in subscription matching chain."""

    def __init__(self, next_handler: SubscriptionHandler | None = None):
        self._next = next_handler

    async def handle(
        self,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
        orchestrator: Flock,
    ) -> bool:
        """Check if artifact should trigger agent.

        Returns:
            True if should continue chain, False if should skip this agent.
        """
        if not await self._check(artifact, agent, subscription, orchestrator):
            return False  # Stop chain

        if self._next:
            return await self._next.handle(artifact, agent, subscription, orchestrator)

        return True  # End of chain - accept

    @abstractmethod
    async def _check(
        self,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription,
        orchestrator: Flock,
    ) -> bool:
        """Perform this handler's check."""
        pass


class EventModeHandler(SubscriptionHandler):
    """Check if subscription accepts events."""

    async def _check(self, artifact, agent, subscription, orchestrator) -> bool:
        return subscription.accepts_events()


class SelfTriggerHandler(SubscriptionHandler):
    """Check prevent_self_trigger flag."""

    async def _check(self, artifact, agent, subscription, orchestrator) -> bool:
        if agent.prevent_self_trigger and artifact.produced_by == agent.name:
            return False
        return True


class CircuitBreakerHandler(SubscriptionHandler):
    """Check iteration limit (circuit breaker)."""

    async def _check(self, artifact, agent, subscription, orchestrator) -> bool:
        iteration_count = orchestrator._agent_iteration_count.get(agent.name, 0)
        return iteration_count < orchestrator.max_agent_iterations


class VisibilityHandler(SubscriptionHandler):
    """Check artifact visibility."""

    async def _check(self, artifact, agent, subscription, orchestrator) -> bool:
        return orchestrator._check_visibility(artifact, agent.identity)


class TypeMatchHandler(SubscriptionHandler):
    """Check subscription type/predicate matching."""

    async def _check(self, artifact, agent, subscription, orchestrator) -> bool:
        return subscription.matches(artifact)


class DeduplicationHandler(SubscriptionHandler):
    """Check if artifact already processed."""

    async def _check(self, artifact, agent, subscription, orchestrator) -> bool:
        return not orchestrator._seen_before(artifact, agent)


# Build the chain
def build_subscription_chain() -> SubscriptionHandler:
    """Construct the default subscription matching chain."""
    return EventModeHandler(
        SelfTriggerHandler(
            CircuitBreakerHandler(
                VisibilityHandler(
                    TypeMatchHandler(
                        DeduplicationHandler()
                    )
                )
            )
        )
    )


# Usage in Flock
class Flock:
    def __init__(self, ..., subscription_chain: SubscriptionHandler | None = None):
        self._subscription_chain = subscription_chain or build_subscription_chain()

    async def _schedule_artifact(self, artifact: Artifact) -> None:
        for agent in self.agents:
            for subscription in agent.subscriptions:
                # Use chain
                should_schedule = await self._subscription_chain.handle(
                    artifact, agent, subscription, self
                )

                if not should_schedule:
                    continue

                # ... AND gate, JoinSpec, BatchSpec logic ...
                self._schedule_task(agent, artifacts)
```

#### Benefits
1. **Extensibility**: Add custom handlers without modifying orchestrator
2. **Testability**: Test each handler in isolation
3. **Clarity**: Explicit handler responsibilities
4. **Reordering**: Easy to change handler order

#### Trade-offs
- **Complexity**: More classes to understand
- **Performance**: Minor overhead from chain traversal

#### Files to Modify
- New file: `src/flock/subscription_handlers.py`
- `src/flock/orchestrator.py:877-980` (_schedule_artifact)

---

### 8. Command Pattern for Orchestrator Operations

**Impact**: Medium
**Complexity**: Medium
**Priority**: Nice-to-Have

#### Problem
No built-in undo, logging, or queuing for orchestrator operations. Operations execute immediately.

#### Proposed Pattern: Command

```python
# commands.py
from abc import ABC, abstractmethod
from typing import Any

class Command(ABC):
    """Encapsulated orchestrator operation."""

    @abstractmethod
    async def execute(self, orchestrator: Flock) -> Any:
        """Execute the command."""
        pass

    @abstractmethod
    async def undo(self, orchestrator: Flock) -> None:
        """Undo the command (if possible)."""
        pass

    def can_undo(self) -> bool:
        """Check if this command supports undo."""
        return True


class PublishCommand(Command):
    """Command to publish an artifact."""

    def __init__(self, obj: BaseModel, **kwargs):
        self.obj = obj
        self.kwargs = kwargs
        self.published_artifact: Artifact | None = None

    async def execute(self, orchestrator: Flock) -> Artifact:
        self.published_artifact = await orchestrator.publish(self.obj, **self.kwargs)
        return self.published_artifact

    async def undo(self, orchestrator: Flock) -> None:
        if self.published_artifact:
            # Remove from store (requires new store method)
            await orchestrator.store.delete(self.published_artifact.id)


class InvokeCommand(Command):
    """Command to invoke an agent."""

    def __init__(self, agent: Agent, obj: BaseModel, **kwargs):
        self.agent = agent
        self.obj = obj
        self.kwargs = kwargs

    async def execute(self, orchestrator: Flock) -> list[Artifact]:
        return await orchestrator.invoke(self.agent, self.obj, **self.kwargs)

    async def undo(self, orchestrator: Flock) -> None:
        # Agent execution can't be undone
        pass

    def can_undo(self) -> bool:
        return False


class CommandQueue:
    """Queue for batching and replaying commands."""

    def __init__(self):
        self._queue: list[Command] = []
        self._history: list[Command] = []

    def enqueue(self, command: Command) -> None:
        self._queue.append(command)

    async def execute_all(self, orchestrator: Flock) -> list[Any]:
        """Execute all queued commands."""
        results = []
        for command in self._queue:
            result = await command.execute(orchestrator)
            self._history.append(command)
            results.append(result)
        self._queue.clear()
        return results

    async def undo_last(self, orchestrator: Flock) -> None:
        """Undo the last executed command."""
        if not self._history:
            raise RuntimeError("No commands to undo")

        command = self._history.pop()
        if not command.can_undo():
            raise RuntimeError(f"Command {command} cannot be undone")

        await command.undo(orchestrator)


# Usage
queue = CommandQueue()
queue.enqueue(PublishCommand(task1))
queue.enqueue(PublishCommand(task2))
queue.enqueue(InvokeCommand(agent, idea))

# Execute batch
results = await queue.execute_all(flock)

# Undo last operation
await queue.undo_last(flock)
```

#### Benefits
1. **Undo/Redo**: Enable undo for debugging workflows
2. **Logging**: Automatic audit trail of commands
3. **Queuing**: Batch operations for efficiency
4. **Macro Recording**: Record and replay workflows

#### Trade-offs
- **Complexity**: Additional abstraction layer
- **Limited Undo**: Not all operations can be undone

#### Files to Modify
- New file: `src/flock/commands.py`

---

### 9. State Pattern for Orchestrator Lifecycle

**Impact**: Medium
**Complexity**: Medium
**Priority**: Nice-to-Have

#### Problem
Orchestrator lifecycle is implicit. No clear states (idle, running, shutting down, error).

```python
# orchestrator.py - implicit state
# No explicit state tracking
```

#### Proposed Pattern: State

```python
# orchestrator_states.py
from abc import ABC, abstractmethod
from enum import Enum

class OrchestratorState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    ERROR = "error"


class StateHandler(ABC):
    """Base handler for orchestrator state behavior."""

    @abstractmethod
    async def publish(self, orchestrator: Flock, obj: BaseModel, **kwargs) -> Artifact:
        pass

    @abstractmethod
    async def shutdown(self, orchestrator: Flock) -> None:
        pass

    @abstractmethod
    def can_transition_to(self, new_state: OrchestratorState) -> bool:
        pass


class IdleStateHandler(StateHandler):
    async def publish(self, orchestrator: Flock, obj: BaseModel, **kwargs) -> Artifact:
        # Transition to running
        orchestrator._set_state(OrchestratorState.RUNNING)
        artifact = await orchestrator._do_publish(obj, **kwargs)
        orchestrator._set_state(OrchestratorState.IDLE)
        return artifact

    async def shutdown(self, orchestrator: Flock) -> None:
        # Already idle - nothing to do
        pass

    def can_transition_to(self, new_state: OrchestratorState) -> bool:
        return new_state in {OrchestratorState.RUNNING, OrchestratorState.SHUTTING_DOWN}


class RunningStateHandler(StateHandler):
    async def publish(self, orchestrator: Flock, obj: BaseModel, **kwargs) -> Artifact:
        # Already running - just publish
        return await orchestrator._do_publish(obj, **kwargs)

    async def shutdown(self, orchestrator: Flock) -> None:
        orchestrator._set_state(OrchestratorState.SHUTTING_DOWN)
        await orchestrator._do_shutdown()
        orchestrator._set_state(OrchestratorState.IDLE)

    def can_transition_to(self, new_state: OrchestratorState) -> bool:
        return new_state in {OrchestratorState.IDLE, OrchestratorState.SHUTTING_DOWN, OrchestratorState.ERROR}


class ShuttingDownStateHandler(StateHandler):
    async def publish(self, orchestrator: Flock, obj: BaseModel, **kwargs) -> Artifact:
        raise RuntimeError("Cannot publish while shutting down")

    async def shutdown(self, orchestrator: Flock) -> None:
        # Already shutting down
        pass

    def can_transition_to(self, new_state: OrchestratorState) -> bool:
        return new_state in {OrchestratorState.IDLE, OrchestratorState.ERROR}


# Integration
class Flock:
    def __init__(self, ...):
        self._state = OrchestratorState.IDLE
        self._state_handlers = {
            OrchestratorState.IDLE: IdleStateHandler(),
            OrchestratorState.RUNNING: RunningStateHandler(),
            OrchestratorState.SHUTTING_DOWN: ShuttingDownStateHandler(),
        }

    def _set_state(self, new_state: OrchestratorState) -> None:
        current_handler = self._state_handlers[self._state]
        if not current_handler.can_transition_to(new_state):
            raise RuntimeError(f"Invalid state transition: {self._state} -> {new_state}")
        self._state = new_state

    async def publish(self, obj: BaseModel, **kwargs) -> Artifact:
        handler = self._state_handlers[self._state]
        return await handler.publish(self, obj, **kwargs)

    async def shutdown(self) -> None:
        handler = self._state_handlers[self._state]
        await handler.shutdown(self)
```

#### Benefits
1. **Clarity**: Explicit lifecycle states
2. **Safety**: Prevent invalid operations (e.g., publish during shutdown)
3. **Debugging**: Track state transitions
4. **Extensibility**: Add new states easily

#### Trade-offs
- **Complexity**: More state management code
- **Overkill**: Current implicit state works fine for most use cases

#### Files to Modify
- New file: `src/flock/orchestrator_states.py`
- `src/flock/orchestrator.py` (add state tracking)

---

## Modern Python Patterns

### 10. Protocol/ABC for Component Interfaces

**Impact**: High
**Complexity**: Low
**Priority**: Must-Have (Quick Win)

#### Problem
Components use ABC (inheritance), but Python 3.8+ Protocols (structural subtyping) are more flexible.

```python
# components.py:51-90 - current ABC approach
class AgentComponent(BaseModel, metaclass=TracedModelMeta):
    """Base class for agent components with lifecycle hooks."""

    async def on_initialize(self, agent: Agent, ctx: Context) -> None:
        return None
    # ... all methods must be overridden
```

Users must inherit from AgentComponent even for simple utilities.

#### Proposed Pattern: Protocol (Structural Subtyping)

```python
# components.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class AgentComponent(Protocol):
    """Protocol for agent components (structural subtyping).

    Any class implementing these methods can act as a component,
    without requiring inheritance from a base class.
    """

    async def on_initialize(self, agent: Agent, ctx: Context) -> None:
        ...

    async def on_pre_consume(
        self, agent: Agent, ctx: Context, inputs: list[Artifact]
    ) -> list[Artifact]:
        ...

    async def on_pre_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
        ...

    # ... remaining methods


# Concrete component (no inheritance required!)
class SimpleRateLimiter:
    """Rate limiter component - no inheritance needed."""

    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self._calls = 0

    async def on_initialize(self, agent, ctx):
        self._calls = 0

    async def on_pre_consume(self, agent, ctx, inputs):
        if self._calls >= self.max_calls:
            raise RuntimeError(f"Rate limit exceeded: {self.max_calls}")
        self._calls += 1
        return inputs

    # Don't need to implement all methods!
    # Only implement what you need - Protocol allows duck typing


# Type checking works
def use_component(comp: AgentComponent):
    # comp can be ANY object with the right methods
    pass

limiter = SimpleRateLimiter(10)
use_component(limiter)  # Type checker happy!
isinstance(limiter, AgentComponent)  # True (at runtime)
```

#### Benefits
1. **Flexibility**: No forced inheritance
2. **Composability**: Easier to add components to existing classes
3. **Testing**: Mock components without base class
4. **Modern Python**: Leverages Python 3.8+ structural subtyping

#### Trade-offs
- **Type Checking**: Requires runtime_checkable for isinstance
- **Documentation**: Protocol methods need clear docstrings

#### Files to Modify
- `src/flock/components.py:51-90` (convert ABC to Protocol)

---

### 11. Async Context Manager for Resource Lifecycle

**Impact**: Medium
**Complexity**: Low
**Priority**: Should-Have

#### Problem
No built-in context manager for agent lifecycle (initialize, execute, cleanup).

```python
# Current usage - manual lifecycle
agent = flock.agent("processor")
# ... no automatic cleanup
```

#### Proposed Pattern: Async Context Manager

```python
# agent.py
class Agent:
    @asynccontextmanager
    async def lifecycle(self, ctx: Context):
        """Async context manager for agent lifecycle.

        Example:
            async with agent.lifecycle(ctx) as agent_ctx:
                # Agent initialized
                await agent_ctx.process(artifacts)
                # Agent automatically cleaned up
        """
        # Initialize
        try:
            await self._run_initialize(ctx)
            yield self
        except Exception as exc:
            await self._run_error(ctx, exc)
            raise
        finally:
            # Always cleanup
            await self._run_terminate(ctx)


# Usage
async with agent.lifecycle(ctx) as agent_ctx:
    results = await agent_ctx.process(artifacts)
# Automatic cleanup, even if exception raised
```

#### Benefits
1. **Safety**: Guaranteed cleanup
2. **Clarity**: Explicit lifecycle scope
3. **Exception Handling**: Automatic error handling

#### Trade-offs
- **Minor API Change**: New usage pattern

#### Files to Modify
- `src/flock/agent.py:87-148` (add lifecycle context manager)

---

### 12. Descriptor for Lazy Loading

**Impact**: Low
**Complexity**: Medium
**Priority**: Nice-to-Have

#### Problem
MCP tools loaded eagerly, even if never used.

```python
# agent.py:150-221
async def _get_mcp_tools(self, ctx: Context) -> list[Callable]:
    # Loaded every time, even if not needed
```

#### Proposed Pattern: Descriptor (Lazy Loading)

```python
# lazy_loader.py
class LazyMCPTools:
    """Descriptor for lazy-loading MCP tools."""

    def __init__(self):
        self._cache_attr = "_mcp_tools_cache"

    def __get__(self, instance, owner):
        if instance is None:
            return self

        # Check cache
        if not hasattr(instance, self._cache_attr):
            # Load on first access
            import asyncio
            tools = asyncio.create_task(instance._load_mcp_tools())
            setattr(instance, self._cache_attr, tools)

        return getattr(instance, self._cache_attr)


# Usage in Agent
class Agent:
    mcp_tools = LazyMCPTools()

    async def _load_mcp_tools(self) -> list[Callable]:
        # Actual loading logic (expensive)
        ...


# Accessed lazily
tools = await agent.mcp_tools  # Only loads on first access
```

#### Benefits
1. **Performance**: Defer expensive operations
2. **Automatic**: Transparent to users

#### Trade-offs
- **Complexity**: Descriptors are advanced Python
- **Async Challenges**: Descriptors + async is tricky

#### Files to Modify
- New file: `src/flock/lazy_loader.py`
- `src/flock/agent.py:150-221`

---

## Prioritized Recommendations

### Must-Have (Quick Wins)
**High Impact + Low/Medium Complexity - Implement First**

1. **Proxy Pattern for Store Caching** (Structural)
   - **Impact**: High - Massive performance improvement for read-heavy workloads
   - **Complexity**: Low - Single class addition
   - **ROI**: Immediate
   - **Files**: New `src/flock/store_proxy.py`

2. **Protocol for Component Interfaces** (Modern Python)
   - **Impact**: High - More flexible, modern Python design
   - **Complexity**: Low - Convert ABC to Protocol
   - **ROI**: Improved testability and composability
   - **Files**: `src/flock/components.py:51-90`

### Should-Have
**High Impact - Implement Next Sprint**

3. **Abstract Factory for Storage Backends** (Creational)
   - **Impact**: High - Simplified configuration, extensibility
   - **Complexity**: Medium
   - **Files**: `src/flock/orchestrator.py:86-121`, `src/flock/store.py`

4. **Decorator Pattern for Artifact Enrichment** (Structural)
   - **Impact**: High - Enable extensible metadata pipelines
   - **Complexity**: Medium
   - **Files**: New `src/flock/artifact_decorators.py`, `src/flock/orchestrator.py:641-735`

5. **Adapter Pattern for Storage Backends** (Structural)
   - **Impact**: Medium - Enable Redis, Postgres, S3 backends
   - **Complexity**: Medium
   - **Files**: `src/flock/store.py`, new adapter files

6. **Chain of Responsibility for Subscription Matching** (Behavioral)
   - **Impact**: Medium - Extensible subscription logic
   - **Complexity**: Medium
   - **Files**: New `src/flock/subscription_handlers.py`, `src/flock/orchestrator.py:877-980`

7. **Factory Method for Engine Selection** (Creational)
   - **Impact**: Medium - Cleaner engine management
   - **Complexity**: Low
   - **Files**: `src/flock/agent.py:354-367`, `src/flock/engines/__init__.py`

### Nice-to-Have
**Polish & Advanced Features**

8. **Prototype Pattern for Artifact Cloning** (Creational)
   - **Impact**: Low - Convenience feature
   - **Complexity**: Low
   - **Files**: `src/flock/artifacts.py:15-31`

9. **Command Pattern for Orchestrator Operations** (Behavioral)
   - **Impact**: Medium - Undo/redo, logging
   - **Complexity**: Medium
   - **Files**: New `src/flock/commands.py`

10. **State Pattern for Orchestrator Lifecycle** (Behavioral)
    - **Impact**: Medium - Explicit state management
    - **Complexity**: Medium
    - **Files**: New `src/flock/orchestrator_states.py`

11. **Async Context Manager for Agent Lifecycle** (Modern Python)
    - **Impact**: Medium - Safety and clarity
    - **Complexity**: Low
    - **Files**: `src/flock/agent.py:87-148`

12. **Descriptor for Lazy Loading** (Modern Python)
    - **Impact**: Low - Performance optimization
    - **Complexity**: Medium
    - **Files**: New `src/flock/lazy_loader.py`, `src/flock/agent.py:150-221`

---

## Implementation Roadmap

### Phase 1: Quick Wins (Sprint 1)
**Goal**: High-impact, low-effort improvements

- [ ] **Week 1**: Implement Proxy Pattern for Store Caching
  - Create `src/flock/store_proxy.py`
  - Add tests with benchmarks
  - Document cache configuration

- [ ] **Week 2**: Convert Components to Protocols
  - Refactor `src/flock/components.py`
  - Update documentation
  - Create migration guide for existing components

### Phase 2: Extensibility (Sprint 2-3)
**Goal**: Enable user extensibility

- [ ] **Week 3-4**: Abstract Factory for Storage
  - Design factory interface
  - Create `StoreRegistry`
  - Add SQLite factory
  - Update `Flock.__init__`

- [ ] **Week 5-6**: Artifact Enrichment Pipeline
  - Create `artifact_decorators.py`
  - Implement timestamp, tag, security decorators
  - Integrate with `Flock.publish`
  - Add examples

### Phase 3: Backend Adapters (Sprint 4-5)
**Goal**: Production-ready storage options

- [ ] **Week 7-8**: Storage Adapter Pattern
  - Design `StorageBackend` protocol
  - Create `BlackboardStoreAdapter`
  - Implement Redis adapter
  - Add tests

- [ ] **Week 9-10**: Additional Backend Adapters
  - PostgreSQL adapter
  - S3 adapter (for artifact payloads)
  - Performance benchmarks

### Phase 4: Advanced Patterns (Sprint 6-7)
**Goal**: Polish and advanced features

- [ ] **Week 11-12**: Subscription Chain & Engine Factory
  - Implement Chain of Responsibility for subscriptions
  - Add Factory Method for engines
  - Update tests

- [ ] **Week 13-14**: Remaining Patterns
  - Prototype pattern for artifacts
  - Command pattern (optional)
  - State pattern (optional)
  - Async context managers

---

## Conclusion

The Flock framework demonstrates strong architectural foundations with excellent use of Builder, Strategy, Observer, and Context Manager patterns. The identified opportunities focus on:

1. **Extensibility**: Making it easier to add custom backends, enrichment logic, and subscription handlers
2. **Performance**: Caching proxy for read-heavy workloads
3. **Modern Python**: Leveraging Protocols for structural subtyping
4. **Safety**: Explicit lifecycle management and state tracking

### Immediate Next Steps

1. **Implement Caching Proxy** (1-2 days) - Immediate performance win
2. **Convert to Protocols** (1 day) - Modernize component architecture
3. **Plan Storage Factory** (1 week) - Foundation for extensibility

### Long-Term Vision

By implementing these patterns, Flock will evolve into an even more extensible, performant, and maintainable framework that empowers users to customize every aspect of the blackboard orchestration while maintaining clean, well-tested code.

---

**Document Prepared By**: Design Pattern Analysis Team
**Review Status**: Draft for Architecture Review
**Next Review**: After Phase 1 implementation
