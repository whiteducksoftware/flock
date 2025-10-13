# Flock Framework: Comprehensive ID Audit Report

**Generated:** 2025-10-13
**Scope:** Complete inventory of all identifier types used in the Flock framework
**Purpose:** Understand ID semantics, relationships, overlaps, and potential issues

---

## Executive Summary

The Flock framework uses **11 distinct ID types** across 6 major categories for tracking artifacts, executions, agents, correlations, storage, and external integrations. This audit identified:

- ✅ **Well-designed separation** between artifact identity (`artifact.id`) and workflow correlation (`correlation_id`)
- ✅ **Strong tracing foundation** with OpenTelemetry `trace_id` and `span_id`
- ⚠️ **Naming inconsistency**: `task_id` (str) vs `correlation_id` (UUID) - both track execution but different types
- ⚠️ **Potential confusion**: Multiple "agent" identifiers (`agent.name`, `agent_id`, `agent.identity`)
- ⚠️ **Unclear scoping**: `run_id` vs `task_id` - appear to serve same purpose

---

## Category 1: Artifact Identification

### 1.1 `artifact.id` (UUID)
**File:** `src/flock/artifacts.py:18`

```python
id: UUID = Field(default_factory=uuid4)
```

**Purpose:** Unique identifier for a single artifact instance on the blackboard

**Semantics:**
- **What it identifies:** A specific artifact (message/data object) published to the blackboard
- **Scope:** Global - unique across all artifacts in the system
- **Lifetime:** Persistent - stored in blackboard and database
- **Generation:** Framework-generated (uuid4) on artifact creation
- **Mutability:** Immutable once created (except Phase 6 pre-generation for streaming)

**Usage Examples:**
```python
# Creation (artifacts.py:18)
artifact = Artifact(type="Task", payload={...})  # id auto-generated

# Lookup (store.py:130)
async def get(self, artifact_id: UUID) -> Artifact | None

# Storage (store.py:1059, 1100)
CREATE TABLE artifacts (artifact_id TEXT PRIMARY KEY, ...)
CREATE TABLE artifact_consumptions (artifact_id TEXT NOT NULL, ...)
```

**Special Case - Phase 6 Pre-generation:**
```python
# engines/dspy_engine.py:193
pre_generated_artifact_id = uuid4()  # Generated BEFORE artifact creation

# Used for streaming message preview (dspy_engine.py:643)
metadata["artifact_id"] = str(pre_generated_artifact_id)

# Preserved through agent publish (agent.py:83)
artifact_id=metadata.get("artifact_id")  # Reuse engine's ID
```

**Key Relationships:**
- Referenced in `ConsumptionRecord.artifact_id` (tracks which agents consumed this artifact)
- Used in dashboard for graph nodes (`GraphArtifact.artifact_id`)
- Stored in SQLite/DuckDB with indexes for fast lookup

---

### 1.2 `correlation_id` (UUID | None)
**File:** `src/flock/artifacts.py:22`

```python
correlation_id: UUID | None = None
```

**Purpose:** Groups related artifacts across a distributed workflow or conversation

**Semantics:**
- **What it identifies:** A workflow/trace/session that spans multiple artifacts and agents
- **Scope:** Workflow-wide - all artifacts in same conversation/request share this ID
- **Lifetime:** Persistent - stored with each artifact
- **Generation:**
  - Framework: `uuid4()` on first publish (orchestrator.py:700)
  - User: Can be provided externally for request tracing
  - Inherited: Propagated through agent execution chains (runtime.py:250, orchestrator.py:1005)
- **Mutability:** Set once, never changed

**Usage Examples:**
```python
# Auto-generation on publish (orchestrator.py:700)
artifact = Artifact(
    type=type_name,
    correlation_id=correlation_id or uuid4()  # Generate if not provided
)

# Context propagation (orchestrator.py:1005)
ctx = Context(
    correlation_id=artifacts[0].correlation_id,  # Inherit from input
)

# Filtering (store.py:292-294)
if filters.correlation_id and (
    artifact.correlation_id is None
    or str(artifact.correlation_id) != filters.correlation_id
):
    return False  # Skip artifacts not in this workflow
```

**Key Relationships:**
- Stored in `Context.correlation_id` (runtime.py:250) for execution context
- Stored in `ConsumptionRecord.correlation_id` (store.py:87) for consumption tracking
- Used in dashboard filters (`GraphFilters.correlation_id`)
- Used by `JoinSpec` correlation engine for correlated AND gates

**Comparison with business correlation keys:**
- Framework `correlation_id`: UUID for distributed tracing
- Business `correlation_key`: Extracted from payload by `JoinSpec.by` lambda (e.g., `patient_id`, `order_id`)

---

### 1.3 `partition_key` (str | None)
**File:** `src/flock/artifacts.py:23`

```python
partition_key: str | None = None
```

**Purpose:** Sharding/routing key for distributed deployments (future-proofing)

**Semantics:**
- **What it identifies:** A partition/shard for load balancing or multi-tenancy
- **Scope:** Infrastructure-level - used for routing decisions
- **Lifetime:** Persistent - stored with artifact
- **Generation:** User-provided (not auto-generated)
- **Mutability:** Immutable

**Usage Examples:**
```python
# Publishing with partition key (orchestrator.py:647)
await flock.publish(task, partition_key="tenant-123")

# Storage (store.py:480, 1094)
"partition_key": artifact.partition_key
CREATE INDEX idx_artifacts_partition ON artifacts(partition_key)
```

**Current Status:** Infrastructure placeholder - not actively used for routing logic yet

---

## Category 2: Execution Tracking

### 2.1 `task_id` (str)
**File:** `src/flock/runtime.py:251`

```python
task_id: str
```

**Purpose:** Unique identifier for a single agent execution/run

**Semantics:**
- **What it identifies:** One execution of one agent (agent activation + processing + output)
- **Scope:** Agent run - unique per agent invocation
- **Lifetime:** Ephemeral (runtime only) but recorded in ConsumptionRecord for history
- **Generation:** Framework-generated: `str(uuid4())` (orchestrator.py:487, 825, 1004)
- **Mutability:** Immutable per execution

**Usage Examples:**
```python
# Creation on agent execution (orchestrator.py:1004)
ctx = Context(
    board=BoardHandle(self),
    orchestrator=self,
    task_id=str(uuid4()),  # New ID for this execution
)

# Consumption tracking (orchestrator.py:1017)
ConsumptionRecord(
    artifact_id=artifact.id,
    consumer=agent.name,
    run_id=ctx.task_id,  # Track which execution consumed this
)

# Dashboard tracking (dashboard/collector.py:169)
event = DashboardRunStartEvent(
    run_id=ctx.task_id,  # Display this run in dashboard
)
```

**Key Relationships:**
- Stored in `ConsumptionRecord.run_id` (note naming: task_id → run_id)
- Used by dashboard for run tracking (`GraphRun.run_id`)
- Used by MCP manager for connection isolation (`agent_id, run_id`)

**Naming Issue:** Called `task_id` in Context but stored/used as `run_id` elsewhere

---

### 2.2 `run_id` (str | None)
**File:** `src/flock/store.py:86`

```python
run_id: str | None = None
```

**Purpose:** Same as `task_id` - tracks agent execution

**Semantics:**
- **What it identifies:** A specific agent run (identical to task_id)
- **Scope:** Agent run
- **Lifetime:** Persistent (stored in ConsumptionRecord)
- **Generation:** Copied from `ctx.task_id`
- **Mutability:** Immutable

**Usage Examples:**
```python
# Storage in consumption record (store.py:86)
@dataclass
class ConsumptionRecord:
    artifact_id: UUID
    consumer: str
    run_id: str | None = None  # Stores ctx.task_id

# Querying (dashboard/collector.py:309)
run = self._runs.get(run_id=ctx.task_id)
```

**Naming Inconsistency:** This is actually the same as `task_id`, just renamed when stored

---

## Category 3: Agent/Component Identification

### 3.1 `agent.name` (str)
**File:** `src/flock/agent.py:94`

```python
self.name = name
```

**Purpose:** Primary identifier for agents - used everywhere

**Semantics:**
- **What it identifies:** A specific agent in the orchestrator
- **Scope:** Orchestrator-wide - must be unique within Flock instance
- **Lifetime:** Persistent (lifetime of Flock instance)
- **Generation:** User-provided via `flock.agent(name)`
- **Mutability:** Immutable after registration

**Usage Examples:**
```python
# Registration (orchestrator.py:183)
if name in self._agents:
    raise ValueError(f"Agent '{name}' already registered.")

# Artifact production (artifacts.py:21)
produced_by: str  # Uses agent.name

# Subscription matching (subscription.py:114)
self.agent_name = agent_name

# Visibility checks (visibility.py:47)
return agent.name in self.agents
```

**Key Relationships:**
- Used as `produced_by` in Artifact (string, not object reference)
- Used as `consumer` in ConsumptionRecord
- Used as key in orchestrator agent registry
- Part of `AgentIdentity` (visibility.py:19)

---

### 3.2 `agent_id` (str)
**File:** Multiple locations (used as parameter name)

```python
# Example: dashboard/collector.py:196
agent_id=agent.name
```

**Purpose:** Alias for `agent.name` in certain contexts

**Semantics:**
- **What it identifies:** Same as agent.name
- **Scope:** Same as agent.name
- **Generation:** Just a parameter name convention
- **Mutability:** N/A (parameter)

**Usage Contexts:**
```python
# MCP connection pooling (mcp/manager.py:72)
async def get_client(self, server_name: str, agent_id: str, run_id: str)

# Store methods (store.py:204, 389)
async def record_consumptions(self, agent_id: str, ...)
async def agent_history_summary(self, agent_id: str, ...)
```

**Naming Confusion:** Not a separate ID - just `agent.name` called by different parameter name

---

### 3.3 `agent.identity` (AgentIdentity)
**File:** `src/flock/agent.py:119`

```python
@property
def identity(self) -> AgentIdentity:
    return AgentIdentity(
        name=self.name,
        labels=self.labels,
        tenant_id=self.tenant_id
    )
```

**Purpose:** Structured identity object for visibility checks

**Semantics:**
- **What it identifies:** Agent identity including name, labels, and tenant
- **Scope:** Agent-specific
- **Lifetime:** Created on-demand (property)
- **Generation:** Framework-composed from agent attributes
- **Mutability:** Reflects current agent state

**Usage Examples:**
```python
# Visibility checks (orchestrator.py:879)
identity = agent.identity
if not self._check_visibility(artifact, identity):
    continue
```

**Not a separate ID:** Composite object containing `agent.name` + metadata

---

### 3.4 `tenant_id` (str | None)
**File:** `src/flock/visibility.py:21`

```python
tenant_id: str | None = None
```

**Purpose:** Multi-tenancy isolation identifier

**Semantics:**
- **What it identifies:** A tenant/customer/organization in multi-tenant deployments
- **Scope:** Cross-system - isolates data between tenants
- **Lifetime:** Persistent (set on agent, stored in visibility)
- **Generation:** User-provided via `agent.tenant(tenant_id)`
- **Mutability:** Set once per agent

**Usage Examples:**
```python
# Agent configuration (agent.py:895)
def tenant(self, tenant_id: str) -> AgentBuilder:
    self._agent.tenant_id = tenant_id

# Visibility enforcement (visibility.py:62-65)
def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
    if self.tenant_id is None:
        return True
    return agent.tenant_id == self.tenant_id
```

**Key Relationships:**
- Part of `AgentIdentity` for visibility checks
- Used in `TenantVisibility` policy
- Stored in dashboard specs (`AgentSpec.tenant_id`)

---

## Category 4: Correlation & Grouping

### 4.1 `correlation_key` (Any)
**File:** `src/flock/correlation_engine.py:33`

```python
correlation_key: Any
```

**Purpose:** Business-level correlation key for JoinSpec AND gates

**Semantics:**
- **What it identifies:** Related artifacts by business logic (e.g., same patient, order, session)
- **Scope:** Workflow/business process
- **Lifetime:** Ephemeral (only used during correlation window)
- **Generation:** Extracted from artifact payload using `JoinSpec.by` lambda
- **Mutability:** N/A (extracted value)

**Usage Examples:**
```python
# Extraction from payload (correlation_engine.py:156)
correlation_key = join_spec.by(payload_instance)
# Example: join_spec.by = lambda x: x.patient_id

# Grouping (correlation_engine.py:164)
groups = self.correlation_groups[pool_key]
if correlation_key not in groups:
    groups[correlation_key] = CorrelationGroup(...)
```

**Distinction from `correlation_id`:**
- `correlation_id` (UUID): Framework-level distributed tracing
- `correlation_key` (Any): Business-level grouping extracted from payload

**Example Scenario:**
```python
# Patient diagnosis workflow
xray = XRay(patient_id="P123", image_url="...")
lab = LabResults(patient_id="P123", blood_type="A+")

# JoinSpec extracts patient_id as correlation_key
agent.consumes(
    XRay, LabResults,
    join={"by": lambda x: x.patient_id, "within": timedelta(minutes=10)}
)
# Both artifacts have correlation_key="P123"
# Agent triggers when both types arrive for same patient
```

---

## Category 5: Storage & Indexing

### 5.1 `artifact_id` (in ConsumptionRecord)
**File:** `src/flock/store.py:84`

```python
artifact_id: UUID
```

**Purpose:** Foreign key reference to consumed artifact

**Semantics:**
- **What it identifies:** The artifact that was consumed
- **Scope:** Same as artifact.id
- **Lifetime:** Persistent in consumption history
- **Generation:** Copied from `artifact.id`
- **Mutability:** Immutable

**Usage Examples:**
```python
# Recording consumption (orchestrator.py:1014-1020)
records = [
    ConsumptionRecord(
        artifact_id=artifact.id,  # Reference to artifact
        consumer=agent.name,
        run_id=ctx.task_id,
    )
]

# Querying consumptions (store.py:742)
WHERE artifact_id IN ({placeholders})
```

**Not a new ID:** Just a reference to existing `artifact.id`

---

### 5.2 Database Primary Keys
**Files:** `src/flock/store.py` (SQLite schema)

```sql
-- Artifacts table (store.py:1059)
CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,  -- Maps to artifact.id
    ...
)

-- Consumption table (store.py:1100-1105)
CREATE TABLE artifact_consumptions (
    artifact_id TEXT NOT NULL,
    consumer TEXT NOT NULL,
    consumed_at TEXT NOT NULL,
    PRIMARY KEY (artifact_id, consumer, consumed_at)  -- Composite key
)
```

**Purpose:** Database-level uniqueness constraints

**Not separate IDs:** Use existing IDs (`artifact.id`, `agent.name`) as keys

---

## Category 6: External Systems (MCP & Tracing)

### 6.1 `server_name` (str)
**File:** `src/flock/mcp/manager.py` (used as key)

```python
# Registration (orchestrator.py:237)
if name in self._mcp_configs:
    raise ValueError(f"MCP server '{name}' is already registered.")

# Tool namespacing (mcp/manager.py:208)
namespaced_name = f"{server_name}__{tool.name}"
```

**Purpose:** Unique identifier for MCP servers

**Semantics:**
- **What it identifies:** An MCP server instance (filesystem, github, etc.)
- **Scope:** Orchestrator-wide
- **Lifetime:** Persistent (lifetime of Flock instance)
- **Generation:** User-provided via `flock.add_mcp(name, ...)`
- **Mutability:** Immutable after registration

**Not a UUID:** Just a string name (e.g., "filesystem", "github")

---

### 6.2 `trace_id` (str - hex formatted)
**File:** `src/flock/logging/logging.py:54-60`

```python
def get_current_trace_id() -> str:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return "no-trace"
    # Format the trace_id as hex (if valid)
    return format(span_context.trace_id, "032x")
```

**Purpose:** OpenTelemetry distributed tracing identifier

**Semantics:**
- **What it identifies:** A complete trace across all operations (spans)
- **Scope:** Workflow-wide (similar to correlation_id but for observability)
- **Lifetime:** Ephemeral (tracing session)
- **Generation:** OpenTelemetry framework (auto-generated or propagated)
- **Mutability:** Immutable per trace

**Usage Examples:**
```python
# Logging (logging/logging.py:171, 194)
trace_id = record["extra"].get("trace_id", "no-trace")
f"<cyan>[trace_id: {trace_id}]</cyan> | "

# Storage (telemetry_exporter/duckdb_exporter.py:154)
"trace_id": format(context.trace_id, "032x")
```

**Key Relationships:**
- Can be set explicitly via `flock.traced_run()` context manager
- Stored in telemetry databases (DuckDB, SQLite)
- Indexed for trace queries

---

### 6.3 `span_id` (str - hex formatted)
**File:** `src/flock/logging/telemetry_exporter/sqlite_exporter.py:42`

```python
span_id TEXT
```

**Purpose:** OpenTelemetry span identifier (sub-operation within trace)

**Semantics:**
- **What it identifies:** A single operation within a trace (e.g., agent execution, tool call)
- **Scope:** Operation-level
- **Lifetime:** Ephemeral (tracing session)
- **Generation:** OpenTelemetry framework
- **Mutability:** Immutable per span

**Usage Examples:**
```python
# Extraction (telemetry_exporter/duckdb_exporter.py:155)
"span_id": format(context.span_id, "016x")

# Parent relationship (telemetry_exporter/file_exporter.py:70-71)
if span.parent and span.parent.span_id != 0:
    result["parent_id"] = format(span.parent.span_id, "016x")
```

**Key Relationships:**
- Child of `trace_id` (many spans per trace)
- Forms parent-child hierarchy via `parent_id`
- Used for flame graphs and performance analysis

---

## Category 7: Dashboard & Events

### 7.1 Graph Node/Edge IDs
**File:** `src/flock/dashboard/models/graph.py:69, 79`

```python
class GraphNode(BaseModel):
    id: str  # Composite: "agent-{name}" or "artifact-{uuid}"

class GraphEdge(BaseModel):
    id: str  # Composite: "{source}-{target}"
```

**Purpose:** React Flow graph visualization identifiers

**Semantics:**
- **What it identifies:** UI nodes/edges in dashboard graph
- **Scope:** Dashboard rendering
- **Lifetime:** Ephemeral (UI session)
- **Generation:** Composed from agent.name or artifact.id
- **Mutability:** Regenerated per render

**Not separate IDs:** Composite of existing IDs for UI purposes

---

## Complete ID Comparison Matrix

| ID Name | Type | Scope | Lifetime | Generated By | Purpose | File:Line |
|---------|------|-------|----------|--------------|---------|-----------|
| `artifact.id` | UUID | Global | Persistent | Framework (uuid4) | Unique artifact identity | artifacts.py:18 |
| `correlation_id` | UUID\|None | Workflow | Persistent | Framework/User | Distributed workflow tracing | artifacts.py:22 |
| `partition_key` | str\|None | Infrastructure | Persistent | User | Sharding/routing (future) | artifacts.py:23 |
| `task_id` | str | Agent run | Ephemeral | Framework (uuid4) | Execution tracking | runtime.py:251 |
| `run_id` | str\|None | Agent run | Persistent | Framework (copied) | Same as task_id (storage) | store.py:86 |
| `agent.name` | str | Orchestrator | Persistent | User | Primary agent identifier | agent.py:94 |
| `agent_id` | str | N/A | N/A | User | Alias for agent.name | (parameter) |
| `tenant_id` | str\|None | Cross-system | Persistent | User | Multi-tenancy isolation | visibility.py:21 |
| `correlation_key` | Any | Business process | Ephemeral | User lambda | Business-level grouping | correlation_engine.py:33 |
| `trace_id` | str (hex) | Workflow | Ephemeral | OpenTelemetry | Observability tracing | logging/logging.py:54 |
| `span_id` | str (hex) | Operation | Ephemeral | OpenTelemetry | Sub-operation tracing | logging/telemetry_exporter/sqlite_exporter.py:42 |

---

## Issues Identified

### 1. Naming Inconsistency: task_id vs run_id ⚠️

**Problem:** Same concept, different names in different contexts

**Evidence:**
- `Context.task_id` (runtime.py:251) - execution identifier
- `ConsumptionRecord.run_id` (store.py:86) - same identifier, different name
- Used interchangeably: `run_id=ctx.task_id` (orchestrator.py:1017)

**Impact:**
- Confusing for developers
- Harder to grep/search codebase
- Documentation ambiguity

**Recommendation:**
```python
# Option 1: Standardize on "run_id"
class Context(BaseModel):
    run_id: str  # Was: task_id

# Option 2: Standardize on "task_id"
class ConsumptionRecord:
    task_id: str  # Was: run_id

# Preferred: "run_id" (shorter, clearer)
```

---

### 2. Type Inconsistency: correlation_id (UUID) vs task_id (str) ⚠️

**Problem:** Both track execution/workflow but have different types

**Evidence:**
- `correlation_id: UUID | None` - workflow-level
- `task_id: str` - execution-level (but also UUID internally: `str(uuid4())`)

**Why task_id is str:**
- Converted to string immediately: `task_id=str(uuid4())` (orchestrator.py:1004)
- Stored as TEXT in database (store.py:1102)
- Used in string contexts (logging, dashboard)

**Impact:**
- Unnecessary type conversion overhead
- Potential for UUID parsing errors
- Inconsistent with correlation_id pattern

**Recommendation:**
```python
# Consider making task_id a UUID for consistency
class Context(BaseModel):
    run_id: UUID  # Not str
    correlation_id: UUID | None

# Or document why they differ (type choice rationale)
```

---

### 3. Multiple "Agent" Identifiers 🤔

**Problem:** Three related but distinct concepts: `agent.name`, `agent_id`, `agent.identity`

**Evidence:**
- `agent.name` - primary string identifier
- `agent_id` - just a parameter name (alias for agent.name)
- `agent.identity` - composite object (name + labels + tenant_id)

**Impact:**
- Unclear which to use when
- `agent_id` creates false impression of separate ID
- Documentation needs clarification

**Recommendation:**
```python
# Standardize parameter naming
# Instead of: agent_id, agent_name
# Use consistently: agent_name (when string needed)

# Document that agent.identity is for visibility checks
# Not a separate identifier
```

---

### 4. Overlapping Concepts: correlation_id vs trace_id 🤔

**Problem:** Both track distributed workflows but serve different purposes

**Evidence:**
- `correlation_id` (UUID) - business workflow tracking, persisted
- `trace_id` (hex string) - observability tracing, ephemeral

**Current Relationship:**
- Independent: Not linked or synchronized
- Can be set separately via different mechanisms
- Stored in different systems (blackboard vs telemetry DB)

**Potential Confusion:**
- Users might expect them to align
- Both describe "workflow" but at different levels

**Recommendation:**
```python
# Option 1: Keep separate (current) - RECOMMENDED
# Document clearly:
# - correlation_id: Business workflow (persistent, query blackboard)
# - trace_id: Technical tracing (ephemeral, debugging)

# Option 2: Link them (optional enhancement)
# Set trace_id = str(correlation_id) when workflow starts
# Benefit: Single unified ID for workflow + tracing
```

---

### 5. Pre-generated artifact_id (Phase 6 Streaming) 🎯

**Problem:** Complex ID lifecycle for streaming preview

**Evidence:**
```python
# Engine pre-generates ID (dspy_engine.py:193)
pre_generated_artifact_id = uuid4()

# Passes to metadata (dspy_engine.py:643)
artifact_id=str(pre_generated_artifact_id)

# Agent reuses ID (agent.py:83)
artifact_id=metadata.get("artifact_id")

# Final artifact gets same ID
```

**Why This Exists:**
- Streaming events need artifact ID before artifact is published
- Dashboard preview shows interim results with stable ID
- Final artifact must match preview ID

**Impact:**
- Breaks "artifact.id is framework-generated" rule
- Special case code path (if artifact_id is not None)
- Requires careful coordination

**Recommendation:**
```python
# Document this as a special case in artifacts.py
# Add explicit comment explaining streaming preview requirement
# Consider extracting to a StreamingArtifact builder pattern
```

---

## Recommendations

### Priority 1: Naming Standardization

**Action Items:**
1. **Rename `task_id` → `run_id` everywhere**
   - More intuitive (an agent "run")
   - Shorter, clearer
   - Aligns with dashboard terminology

2. **Eliminate `agent_id` parameter name**
   - Use `agent_name` consistently
   - Less confusion

3. **Document ID glossary**
   - Create `docs/IDENTIFIER_GUIDE.md`
   - Explain each ID type with examples
   - Clarify relationships

### Priority 2: Type Consistency

**Action Items:**
1. **Consider making `run_id` a UUID** (not str)
   - Aligns with correlation_id pattern
   - More efficient comparisons
   - Breaking change, so needs migration

2. **Document why task_id is str if keeping it**
   - Explain benefits (logging, readability)
   - Justify inconsistency

### Priority 3: Documentation

**Action Items:**
1. **Add ID relationship diagram**
   - Visual showing: artifact.id → consumptions → run_id → agent.name
   - Clarify workflow: correlation_id spans multiple artifacts

2. **Clarify correlation_id vs correlation_key**
   - Framework tracing vs business grouping
   - When to use each

3. **Document trace_id vs correlation_id**
   - Observability vs business tracking
   - Whether to link them (optional)

### Priority 4: Code Quality

**Action Items:**
1. **Extract Phase 6 streaming ID logic**
   - Create `StreamingArtifactBuilder` class
   - Encapsulate pre-generation complexity
   - Make special case explicit

2. **Add type hints everywhere**
   - `agent_name: str` (not just `agent_id`)
   - `run_id: str | UUID` (document which)

---

## ID Usage Patterns

### Pattern 1: Artifact Lifecycle
```python
# 1. Artifact created with auto-generated ID
artifact = Artifact(
    id=uuid4(),                    # Unique artifact identity
    correlation_id=ctx.correlation_id,  # Workflow tracking
    produced_by=agent.name,        # Producer identity
)

# 2. Published to blackboard
await store.publish(artifact)

# 3. Consumed by agent
record = ConsumptionRecord(
    artifact_id=artifact.id,       # Which artifact
    consumer=agent.name,           # Which agent consumed it
    run_id=ctx.run_id,            # Which execution consumed it
)

# 4. Queried by correlation
artifacts = await store.query_artifacts(
    filters=FilterConfig(correlation_id=str(ctx.correlation_id))
)
```

### Pattern 2: Agent Execution
```python
# 1. Agent activated
ctx = Context(
    run_id=str(uuid4()),          # Unique execution ID
    correlation_id=artifact.correlation_id,  # Inherit workflow
)

# 2. Agent processes
result = await agent.execute(ctx, [artifact])

# 3. Consumption recorded
ConsumptionRecord(
    artifact_id=artifact.id,
    consumer=agent.name,
    run_id=ctx.run_id,
)

# 4. Dashboard tracks
GraphRun(
    run_id=ctx.run_id,
    agent_name=agent.name,
    correlation_id=str(ctx.correlation_id),
)
```

### Pattern 3: Correlation (JoinSpec)
```python
# 1. Extract business key
correlation_key = join_spec.by(payload)  # e.g., patient.id

# 2. Group by key
group = CorrelationGroup(
    correlation_key=correlation_key,  # Business grouping
    required_types={"XRay", "LabResults"},
)

# 3. Complete when all types arrive
if group.is_complete():
    artifacts = group.get_artifacts()  # All have same correlation_key
```

### Pattern 4: MCP Connection Isolation
```python
# 1. Get client for agent run
client = await manager.get_client(
    server_name="filesystem",
    agent_id=agent.name,     # Which agent
    run_id=ctx.run_id,       # Which execution
)

# 2. Pool key: (agent_id, run_id)
key = (agent.name, ctx.run_id)
self._pool[key] = {"filesystem": client}

# 3. Cleanup after run
await manager.cleanup_run(agent.name, ctx.run_id)
```

---

## Conclusion

The Flock framework has a **well-architected ID system** with clear separation of concerns:

✅ **Strong Points:**
- Distinct artifact identity (`artifact.id`) vs workflow tracking (`correlation_id`)
- OpenTelemetry integration with `trace_id` and `span_id`
- Multi-tenancy support via `tenant_id`
- Business correlation via `correlation_key`

⚠️ **Areas for Improvement:**
- Naming consistency (`task_id` → `run_id`, eliminate `agent_id` parameter)
- Type consistency (`run_id` as UUID not str)
- Documentation (ID glossary, relationship diagram)
- Code clarity (extract streaming ID logic)

**Recommended Actions:**
1. Rename `task_id` to `run_id` throughout codebase
2. Create `docs/IDENTIFIER_GUIDE.md` with examples
3. Add ID relationship diagram to docs
4. Consider linking `trace_id` and `correlation_id` (optional enhancement)

**Impact Assessment:**
- Breaking changes: Minimal (mostly internal renames)
- Documentation effort: Medium (write guide + diagram)
- Code changes: Small (rename + extract helpers)
- Benefits: Major (clarity, consistency, maintainability)

---

**Report Complete** ✅

This audit provides a comprehensive inventory of all 11 ID types, their purposes, relationships, and potential improvements. Use this as a reference for code reviews, documentation, and future refactoring decisions.
