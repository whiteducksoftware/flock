# Complete Security Flow Analysis

## Overview

This document explains the complete security flow in Flock from when an artifact is published through agent execution to output publishing, including all filtering and visibility controls.

---

## 🎯 Critical Concept: Visibility Controls BOTH Triggering AND Context Access

**Visibility has a dual purpose by design:**

### 1. Visibility Controls Triggering (Phase 1 - Scheduling)

When an artifact is published, visibility filtering happens **BEFORE** subscription matching:

```python
# Only agent_a triggers
flock.publish(
    ClassifiedDoc(...),
    visibility=PrivateVisibility(agents={"agent_a"})
)

# agent_a.consumes(ClassifiedDoc)  ✅ Triggers (can see it)
# agent_b.consumes(ClassifiedDoc)  ❌ Does NOT trigger (can't see it)
```

**Why this is correct:**
- ✅ **Security**: No information leakage (agent_b doesn't know artifact exists)
- ✅ **Efficiency**: Don't waste compute running agents that can't access data
- ✅ **Consistency**: If you can't see it, you shouldn't be triggered by it

**Location**: `orchestrator.py:1007` - Filter 3 in scheduling flow

---

### 2. Visibility Controls Context Access (Phase 2 - Execution)

When an agent runs and requests historical context, visibility filtering happens again:

```python
# Agent requests context
context = await engine.fetch_conversation_context(ctx)

# Context Provider filters by visibility AGAIN
# Agent only sees artifacts it's allowed to see
```

**Why we filter AGAIN:**
- ✅ **Defense in depth**: Even if triggering bypassed (shouldn't happen), context is still filtered
- ✅ **Historical context**: Agent may request artifacts from before it existed
- ✅ **Cross-correlation**: Agent may query artifacts outside its correlation_id

**Location**: `context_provider.py:132-136` - Visibility filtering in DefaultContextProvider

---

### 3. The Two-Layer Model

| Layer | Purpose | When It Applies | Location |
|-------|---------|-----------------|----------|
| **Visibility Filtering** | Security boundary (who can see what) | Phase 1 (triggering) + Phase 2 (context access) | `orchestrator.py:1007` + `context_provider.py:132-136` |
| **Subscription Filtering** | Routing logic (which types/tags to process) | Phase 1 (triggering only) | `subscription.py:143-160` |
| **Context Provider Filtering** | Context scope (what historical data to show) | Phase 2 (context access only) | `context_provider.py:92-158` |

**Key Insight:**
- **Visibility** = Security (enforced at framework level, cannot be bypassed)
- **Subscription filters** = Routing (developer-controlled, type/tag matching)
- **Context Providers** = Context shaping (developer-controlled, historical data filtering)

---

### 4. Why Visibility ≠ Context Provider

**Common Confusion:** "If visibility controls context access, why do we need Context Providers?"

**Answer:** They serve different purposes!

**Visibility:**
```python
# Security boundary: "Can this agent see this artifact AT ALL?"
flock.publish(
    Secret(...),
    visibility=PrivateVisibility(agents={"admin"})
)
# non_admin_agent CANNOT see it (triggering or context)
```

**Context Provider:**
```python
# Context shaping: "When agent runs, what historical artifacts should it see?"
flock = Flock(context_provider=FilteredContextProvider(
    FilterConfig(tags={"urgent"})  # Only show urgent artifacts in context
))
# Agent still triggers on ALL matching artifacts
# But only SEES urgent artifacts when it requests historical context
```

**Example:**

```python
# Publish mix of artifacts
await flock.publish(Task(name="docs"), tags={"normal"})    # Public
await flock.publish(Task(name="bug"), tags={"urgent"})     # Public
await flock.publish(Secret(key="xyz"), visibility=PrivateVisibility(agents={"admin"}))

# Agent configuration
agent.consumes(Task)  # Subscribes to ALL tasks
flock = Flock(context_provider=FilteredContextProvider(FilterConfig(tags={"urgent"})))

# What happens:
# 1. agent TRIGGERS twice (docs + bug) - visibility allows both
# 2. agent DOES NOT trigger for Secret - visibility denies
# 3. When agent runs, it SEES only "bug" in context - context provider filters
```

**The layers work together:**
1. **Visibility** (security): Filters what agents CAN see (triggering + context)
2. **Subscription** (routing): Filters what types/tags trigger agent
3. **Context Provider** (context shaping): Filters what historical data agent sees in context

---

## Phase 1: Artifact Publication → Agent Triggering

### 1.1 Entry Point: `orchestrator.publish(obj, *, visibility, tags, ...)`

**Location**: `orchestrator.py:507-593`

When you publish an artifact:
```python
await flock.publish(
    Task(name="foo", priority=5),
    visibility=PrivateVisibility(agents={"admin"}),  # Optional
    tags={"urgent", "backend"},  # Optional (yes, should be renamed from tags!)
    correlation_id=uuid4()  # Optional
)
```

**What happens:**
1. Artifact is created with:
   - `type`: Registered type name from type_registry
   - `payload`: obj.model_dump()
   - `produced_by`: "external" (or agent name if from agent)
   - `visibility`: Defaults to `PublicVisibility()` if not specified
   - `tags`: Empty set if not specified
   - `correlation_id`: Generated UUID if not specified

2. Artifact is persisted to store: `orchestrator.py:717-720`
3. Scheduling begins: `_schedule_artifact(artifact)`

---

### 1.2 Scheduling: `orchestrator._schedule_artifact()`

**Location**: `orchestrator.py:981-1041`

**Flow:**
```
FOR EACH agent in flock.agents:
    FOR EACH subscription in agent.subscriptions:

        ┌─────────────────────────────────────────┐
        │ FILTER 1: Subscription Mode Check      │
        │ - Skip if subscription.mode != "events" │
        └─────────────────────────────────────────┘

        ┌─────────────────────────────────────────┐
        │ FILTER 2: Self-Trigger Prevention      │
        │ - Skip if artifact.produced_by == agent.name │
        │   AND agent.prevent_self_trigger == True    │
        └─────────────────────────────────────────┘

        ┌──────────────────────────────────────────────┐
        │ FILTER 3: VISIBILITY CHECK (SECURITY!)      │
        │ Location: orchestrator.py:1007              │
        │ Method: _check_visibility(artifact, agent.identity) │
        │                                             │
        │ Returns: artifact.visibility.allows(agent.identity) │
        │                                             │
        │ This is the PRIMARY SECURITY CHECKPOINT!   │
        │ Agent is SKIPPED if visibility denies access │
        └──────────────────────────────────────────────┘

        ┌─────────────────────────────────────────┐
        │ FILTER 4: Subscription Match            │
        │ Location: subscription.py:143-160       │
        │ Checks (ALL must pass):                 │
        │   a. Type match: artifact.type in subscription.type_names │
        │   b. Producer filter: artifact.produced_by in subscription.from_agents (if specified) │
        │   c. Channel/Tag filter: artifact.tags intersects subscription.tags (if specified) │
        │   d. WHERE predicates: All subscription.where predicates return True │
        └─────────────────────────────────────────┘

        If ALL filters pass → Agent is scheduled for execution
```

---

## Filter Details

### Filter 3: Visibility Check (CRITICAL SECURITY)

**Location**: `orchestrator.py:1339-1343`

```python
def _check_visibility(self, artifact: Artifact, identity: AgentIdentity) -> bool:
    return artifact.visibility.allows(identity)
```

**Visibility Types** (from `visibility.py`):

1. **PublicVisibility**: Everyone can see it
   ```python
   def allows(self, agent_identity: AgentIdentity) -> bool:
       return True
   ```

2. **PrivateVisibility**: Allowlist-based (specific agents only)
   ```python
   def allows(self, agent_identity: AgentIdentity) -> bool:
       return agent_identity.name in self.agents
   ```

3. **TenantVisibility**: Multi-tenant isolation
   ```python
   def allows(self, agent_identity: AgentIdentity) -> bool:
       return agent_identity.tenant_id == self.tenant_id
   ```

4. **LabelledVisibility**: Role-based access control
   ```python
   def allows(self, agent_identity: AgentIdentity) -> bool:
       # Agent must have ALL required labels
       return self.labels.issubset(agent_identity.labels)
   ```

**Agent Identity** (`agent.py:167-168`):
```python
@property
def identity(self) -> AgentIdentity:
    return AgentIdentity(
        name=self.name,
        labels=self.labels,
        tenant_id=self.tenant_id
    )
```

---

### Filter 4: Subscription Matching

**Location**: `subscription.py:143-160`

```python
def matches(self, artifact: Artifact) -> bool:
    # 4a. Type check
    if artifact.type not in self.type_names:
        return False

    # 4b. Producer filter (from_agents)
    if self.from_agents and artifact.produced_by not in self.from_agents:
        return False

    # 4c. Channel/Tag filter (tags) - YES, should be renamed to "tags"!
    if self.tags and not artifact.tags.intersection(self.tags):
        return False

    # 4d. WHERE predicates
    model_cls = type_registry.resolve(artifact.type)
    payload = model_cls(**artifact.payload)
    for predicate in self.where:
        try:
            if not predicate(payload):
                return False
        except Exception:
            return False

    return True  # All checks passed!
```

**Subscription Filters Available** (`subscription.py:97-111`):
```python
subscription = Subscription(
    types=[Task, Event],              # Type matching
    where=[lambda x: x.priority > 5], # Predicate filtering
    from_agents={"analyzer"},         # Producer filtering
    tags={"urgent", "backend"},   # Tag filtering (SHOULD BE "tags")
    join=JoinSpec(...),              # Correlation/AND gates
    batch=BatchSpec(...)             # Batching
)
```

**Filter Ordering** (ALL filters):
```
1. Subscription mode check (events vs direct)
2. Self-trigger prevention
3. ✅ VISIBILITY (SECURITY - cannot be bypassed)
4. ✅ Subscription.matches():
   - Type matching
   - from_agents filter
   - tags/tags filter (YES - needs renaming!)
   - WHERE predicates
```

---

## Phase 2: Agent Execution (What Engines Can See)

### 2.1 Context Creation: `orchestrator._run_agent_task()`

**Location**: `orchestrator.py:1063-1087`

```python
async def _run_agent_task(self, agent, artifacts, is_batch=False):
    # Get provider (per-agent > global > default)
    inner_provider = (
        agent.context_provider or
        self._default_context_provider or
        DefaultContextProvider()
    )

    # SECURITY: Wrap with BoundContextProvider
    # This binds the provider to agent.identity (trusted source from orchestrator)
    provider = BoundContextProvider(inner_provider, agent.identity)

    # Create frozen Context (immutable)
    ctx = Context(
        provider=provider,              # Bound provider (ignores fake identities)
        store=self.store,               # Store reference for provider queries
        agent_identity=agent.identity,  # Informational (real security is in provider)
        task_id=str(uuid4()),
        correlation_id=correlation_id,
        is_batch=is_batch
    )

    # Execute agent
    outputs = await agent.execute(ctx, artifacts)

    # Orchestrator publishes outputs (Phase 6 security fix)
    for output in outputs:
        await self._persist_and_schedule(output)
```

---

### 2.2 What Engines Can Access

**Engines receive** (`agent.py:410`):
```python
result = await engine.evaluate(self, ctx, inputs, output_group)
```

**What's in `ctx` (Context)**:
```python
class Context(BaseModel):
    model_config = ConfigDict(frozen=True)  # IMMUTABLE!

    provider: Any         # BoundContextProvider (security boundary)
    store: Any           # Store reference (for provider queries only)
    agent_identity: Any  # Agent's identity (INFORMATIONAL - provider ignores this)
    correlation_id: UUID
    task_id: str
    state: dict[str, Any]
    is_batch: bool
```

**What engines CANNOT access** (removed in Phase 1):
- ❌ `ctx.board` - REMOVED (would bypass visibility)
- ❌ `ctx.orchestrator` - REMOVED (god mode access)

---

### 2.3 How Engines Fetch Context

**Location**: `components.py:156-259`

```python
class EngineComponent:
    async def fetch_conversation_context(
        self,
        ctx: Context,
        agent: Agent | None = None,
        correlation_id: UUID | None = None,
        max_artifacts: int | None = None,
        exclude_ids: set[UUID] | None = None,
    ) -> list[dict[str, Any]]:
        # SECURITY: Uses ctx.provider (BoundContextProvider)
        # This enforces visibility filtering at the security boundary

        # Create ContextRequest
        request = ContextRequest(
            agent=agent,
            correlation_id=correlation_id or ctx.correlation_id,
            store=ctx.store,
            agent_identity=ctx.agent_identity,  # From trusted source (orchestrator)
            exclude_ids=exclude_ids
        )

        # Provider returns FILTERED context (visibility already enforced)
        context_items = await ctx.provider(request)

        # Apply engine-level filtering (type exclusions)
        if self.context_exclude_types:
            context_items = [
                item for item in context_items
                if item["type"] not in self.context_exclude_types
            ]

        return context_items
```

---

### 2.4 Provider Security Flow

**BoundContextProvider** (`context_provider.py:249-304`):

```python
class BoundContextProvider:
    """SECURITY: Binds provider to trusted agent identity.

    Prevents engines from:
    1. Mutating ctx.agent_identity (Context is frozen)
    2. Creating fake Context with fake agent_identity (provider ignores it)
    """

    def __init__(self, inner_provider, bound_agent_identity):
        self._inner = inner_provider
        self._bound_identity = bound_agent_identity  # From orchestrator (TRUSTED)

    async def __call__(self, request: ContextRequest):
        # SECURITY: Replace untrusted agent_identity with trusted bound identity
        secure_request = ContextRequest(
            agent=request.agent,
            correlation_id=request.correlation_id,
            store=request.store,
            agent_identity=self._bound_identity,  # Use BOUND identity (trusted)
            exclude_ids=request.exclude_ids
        )
        return await self._inner(secure_request)
```

**DefaultContextProvider** (`context_provider.py:92-158`):

```python
async def __call__(self, request: ContextRequest):
    # Step 1: Query by correlation_id
    artifacts, _ = await request.store.query_artifacts(
        FilterConfig(correlation_id=str(request.correlation_id)),
        limit=-1
    )

    # Step 2: CRITICAL SECURITY - Filter by visibility
    # This is the FIX for Vulnerability #1 (READ BYPASS)
    visible_artifacts = [
        artifact for artifact in artifacts
        if artifact.visibility.allows(request.agent_identity)
    ]

    # Step 3: Exclude specific artifacts (e.g., input artifacts)
    if request.exclude_ids:
        visible_artifacts = [
            artifact for artifact in visible_artifacts
            if artifact.id not in request.exclude_ids
        ]

    # Step 4: Return serialized context
    return [serialize(artifact) for artifact in visible_artifacts]
```

**Security Properties:**
- ✅ Engines can ONLY see artifacts visible to their agent
- ✅ Engines CANNOT bypass visibility (no direct store access)
- ✅ Engines CANNOT fake identities (provider is bound at orchestrator level)
- ✅ Context is immutable (engines cannot mutate security-critical fields)

---

## Phase 3: Output Publishing (How Agents Set Visibility)

### 3.1 Declaring Outputs

**Location**: `agent.py:589-678`

```python
agent = (
    flock.agent("processor")
    .consumes(Task)
    .publishes(
        Report,
        visibility=PrivateVisibility(agents={"admin"}),  # Static visibility
        fan_out=3,  # Publish 3 reports
        where=lambda r: r.score > 0.5,  # Filter outputs
        validate=lambda r: r.score > 0  # Validate outputs
    )
)
```

**Visibility Options:**

1. **Static visibility** (set at declaration):
   ```python
   .publishes(Report, visibility=PrivateVisibility(agents={"admin"}))
   ```

2. **Dynamic visibility** (computed from artifact content):
   ```python
   def compute_visibility(report: Report) -> Visibility:
       if report.confidential:
           return PrivateVisibility(agents={"admin"})
       return PublicVisibility()

   .publishes(Report, visibility=compute_visibility)
   ```

3. **Sugar syntax** (only_for):
   ```python
   .publishes(Report).only_for("admin", "manager")
   # Equivalent to: visibility=PrivateVisibility(agents={"admin", "manager"})
   ```

---

### 3.2 Output Creation Flow

**Location**: `agent.py:177-299`

When engine returns artifacts:

```python
async def _make_outputs_for_group(self, ctx, result, output_group):
    produced = []

    for output_decl in output_group.outputs:
        # 1. Find matching artifacts from engine
        matching_artifacts = [
            a for a in result.artifacts
            if a.type == output_decl.spec.type_name
        ]

        # 2. STRICT VALIDATION: Engine must produce expected count
        expected_count = output_decl.count
        actual_count = len(matching_artifacts)
        if actual_count != expected_count:
            raise ValueError(
                f"Engine contract violation: Expected {expected_count}, "
                f"got {actual_count}"
            )

        # 3. Apply WHERE filtering (reduces published artifacts)
        if output_decl.filter_predicate:
            model_cls = type_registry.resolve(output_decl.spec.type_name)
            filtered = []
            for a in matching_artifacts:
                model_instance = model_cls(**a.payload)
                if output_decl.filter_predicate(model_instance):
                    filtered.append(a)
            matching_artifacts = filtered

        # 4. Apply VALIDATE checks (fail-fast on validation errors)
        if output_decl.validate_predicate:
            for artifact in matching_artifacts:
                model_instance = model_cls(**artifact.payload)
                if not output_decl.validate_predicate(model_instance):
                    raise ValueError("Validation failed")

        # 5. Apply visibility and create final artifacts
        for artifact_from_engine in matching_artifacts:
            # Determine visibility (static or dynamic)
            visibility = output_decl.default_visibility
            if callable(visibility):
                # Dynamic visibility based on content
                model_instance = model_cls(**artifact_from_engine.payload)
                visibility = visibility(model_instance)

            # Create artifact with agent metadata
            metadata = {
                "correlation_id": ctx.correlation_id,
                "artifact_id": artifact_from_engine.id,  # Preserve engine's ID
                "visibility": visibility  # Set visibility here!
            }

            artifact = output_decl.apply(
                artifact_from_engine.payload,
                produced_by=self.name,
                metadata=metadata
            )
            produced.append(artifact)

    return produced
```

**AgentOutput.apply()** (`agent.py:83-100`):
```python
def apply(self, data, *, produced_by, metadata):
    return self.spec.build(
        produced_by=produced_by,
        data=data,
        visibility=metadata.get("visibility", self.default_visibility),
        correlation_id=metadata.get("correlation_id"),
        partition_key=metadata.get("partition_key"),
        tags=metadata.get("tags"),
        version=metadata.get("version", 1),
        artifact_id=metadata.get("artifact_id")
    )
```

---

### 3.3 Publishing (Phase 6 Security Fix)

**Location**: `orchestrator.py:1090-1096`

```python
# Phase 6: Execute agent (returns artifacts, doesn't publish)
outputs = await agent.execute(ctx, artifacts)

# Phase 6: Orchestrator publishes outputs (security fix)
# This fixes Vulnerability #2 (WRITE Bypass)
for output in outputs:
    await self._persist_and_schedule(output)
```

**What changed:**
- ❌ OLD (vulnerable): Agents published directly via `ctx.board.publish()`
- ✅ NEW (secure): Agents return artifacts, orchestrator validates and publishes

**Security properties:**
- ✅ Agents CANNOT bypass validation (orchestrator validates all outputs)
- ✅ Agents CANNOT forge metadata (produced_by is set by agent.name)
- ✅ Agents CANNOT publish arbitrary artifacts (must match declared output types)

---

## Complete Security Summary

### Input Security (Who Can Trigger Agents)

**Filter Order:**
1. Subscription mode check
2. Self-trigger prevention (`prevent_self_trigger`)
3. **VISIBILITY CHECK** ← PRIMARY SECURITY
4. **Subscription matching**:
   - Type matching
   - `from_agents` filter
   - `tags`/`tags` filter (RENAME to `tags`!)
   - `where` predicates

**Security guarantees:**
- ✅ Agents can ONLY be triggered by artifacts they're allowed to see (visibility)
- ✅ Agents can filter by producer, tags, and custom predicates
- ✅ Visibility cannot be bypassed (enforced before subscription matching)

---

### Context Security (What Engines Can See)

**Architecture:**
```
Engine → fetch_conversation_context()
         ↓
       ContextRequest (with agent_identity)
         ↓
       BoundContextProvider (uses BOUND identity, ignores request)
         ↓
       DefaultContextProvider
         ↓
       query_artifacts(correlation_id)
         ↓
       filter by visibility.allows(bound_identity)
         ↓
       Return FILTERED artifacts
```

**Security guarantees:**
- ✅ Engines can ONLY see artifacts visible to their agent (via visibility filtering)
- ✅ Engines CANNOT bypass visibility (no direct store access, ctx.board removed)
- ✅ Engines CANNOT fake identities (BoundContextProvider ignores fake identities)
- ✅ Context is immutable (engines cannot mutate security fields)

---

### Output Security (How Agents Set Visibility)

**Flow:**
1. Agent declares outputs with visibility (static or dynamic)
2. Engine produces artifacts
3. Agent validates count, applies WHERE/VALIDATE filters
4. Agent applies visibility (static or computed from content)
5. Orchestrator validates and publishes

**Security guarantees:**
- ✅ Agents CANNOT bypass validation (orchestrator validates outputs)
- ✅ Agents CANNOT forge metadata (orchestrator sets produced_by)
- ✅ Agents CANNOT publish arbitrary types (must match declarations)
- ✅ Visibility is set at agent level (static or dynamic based on content)

---

## Terminology Issues

### "tags" Should Be "tags"

**Current naming** (`subscription.py:105, 130, 149`):
```python
# Declaration
agent.consumes(Task, tags={"urgent", "backend"})

# Storage
subscription.tags = set(tags or [])

# Matching
if self.tags and not artifact.tags.intersection(self.tags):
    return False
```

**The confusion:**
- Subscription uses `tags` parameter
- Artifact has `tags` field
- Matching checks `artifact.tags.intersection(subscription.tags)`

**Recommendation:** Rename `tags` → `tags` everywhere for consistency:
```python
# Should be:
agent.consumes(Task, tags={"urgent", "backend"})
subscription.tags = set(tags or [])
if self.tags and not artifact.tags.intersection(self.tags):
    return False
```

---

## Trust Boundaries

### Trusted Code (Cannot Be Bypassed)
1. **Orchestrator**: Enforces visibility, validates outputs, publishes artifacts
2. **Context Providers**: Enforce visibility filtering (security boundary)
3. **Visibility Classes**: Define access control rules
4. **BoundContextProvider**: Binds provider to trusted agent identity

### Untrusted Code (Business Logic)
1. **Engines**: Business logic that processes artifacts (untrusted)
2. **Custom Predicates**: User-defined where/validate functions (untrusted)
3. **Custom Providers**: Developer responsibility (trusted configuration)

### Developer Responsibility
1. **Custom Context Providers**: Must enforce visibility (documented requirement)
2. **Visibility Configuration**: Must be set correctly on artifacts
3. **Agent Declarations**: Must declare correct types and filters
