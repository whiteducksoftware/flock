# Correlation ID Behavior in JoinSpec: Analysis & Recommendations

**Date**: 2025-10-13
**Question**: When an agent produces an artifact from correlated inputs, which correlation_id does it get?
**Answer**: The correlation_id from the **FIRST** input artifact in the correlated group.

---

## 🎯 Executive Summary

### The Question

In the medical diagnostics example (`examples/01-cli/13_medical_diagnostics_joinspec.py`):

```python
# Two artifacts are correlated by patient_id:
XRayImage(patient_id="A-001") → correlation_id=uuid1
LabResults(patient_id="A-001") → correlation_id=uuid2

# Agent produces output:
DiagnosticReport → correlation_id=???
```

**Which correlation_id does the DiagnosticReport get?**

### The Answer

**DiagnosticReport gets `correlation_id=uuid1`** (from the XRayImage - the first input)

---

### The Problem

**Lost Data Lineage**: The LabResults artifact (uuid2) is NOT linked to the DiagnosticReport!

```python
# This works:
report.correlation_id == xray.id  # ✅ True

# This doesn't:
report.correlation_id == lab.id  # ❌ False - Lost lineage!
```

---

## 🆔 Complete ID Inventory in Flock

**Purpose**: Before diving into the correlation_id issue, let's understand ALL identifier types used in Flock. This helps clarify the relationships and potential overlaps.

### Quick Summary

Flock uses **11 distinct ID types** across 6 categories:

| Category | IDs | Purpose |
|----------|-----|---------|
| **Artifact Identification** | `artifact.id`, `correlation_id`, `partition_key` | Identify & group artifacts |
| **Execution Tracking** | `task_id`, `run_id` | Track agent executions |
| **Agent/Component** | `agent.name`, `agent_id`, `tenant_id` | Identify agents & tenants |
| **Correlation & Grouping** | `correlation_key` | Business-level grouping |
| **External Systems** | `trace_id`, `span_id` | OpenTelemetry tracing |

---

### Category 1: Artifact Identification

#### `artifact.id` (UUID)
**File**: `src/flock/artifacts.py:18`

```python
id: UUID = Field(default_factory=uuid4)
```

- **What**: Unique identifier for a single artifact instance
- **Scope**: Global - unique across all artifacts
- **Lifetime**: Persistent (stored in blackboard)
- **Generated**: Framework (`uuid4()`)
- **Example**: Used for lookups, ConsumptionRecord references

---

#### `correlation_id` (UUID | None)
**File**: `src/flock/artifacts.py:22`

```python
correlation_id: UUID | None = None
```

- **What**: Groups related artifacts across a distributed workflow
- **Scope**: Workflow-wide - spans multiple artifacts and agents
- **Lifetime**: Persistent (stored with artifact)
- **Generated**: Framework (`uuid4()`) or user-provided
- **Inheritance**: Propagated through agent execution chains
- **Example**: `artifacts[0].correlation_id` becomes context's correlation_id

**⚠️ THIS IS THE ID WE'RE INVESTIGATING IN THIS DOCUMENT**

---

#### `partition_key` (str | None)
**File**: `src/flock/artifacts.py:23`

```python
partition_key: str | None = None
```

- **What**: Sharding/routing key for distributed deployments
- **Scope**: Infrastructure-level
- **Lifetime**: Persistent
- **Generated**: User-provided
- **Current Status**: Future-proofing placeholder, not actively used

---

### Category 2: Execution Tracking

#### `task_id` (str)
**File**: `src/flock/runtime.py:251`

```python
task_id: str
```

- **What**: Unique identifier for a single agent execution
- **Scope**: Agent run - unique per invocation
- **Lifetime**: Ephemeral (runtime) but recorded in ConsumptionRecord
- **Generated**: Framework (`str(uuid4())`)
- **Example**: Created on each `_run_agent_task()` call

---

#### `run_id` (str | None)
**File**: `src/flock/store.py:86`

```python
run_id: str | None = None
```

- **What**: Same as `task_id` - tracks agent execution
- **Scope**: Same as task_id
- **Lifetime**: Persistent (stored in ConsumptionRecord)
- **Generated**: Copied from `ctx.task_id`

**⚠️ NAMING INCONSISTENCY**: `task_id` in Context but `run_id` in storage - **same concept, different names**

---

### Category 3: Agent/Component Identification

#### `agent.name` (str)
**File**: `src/flock/agent.py:94`

- **What**: Primary identifier for agents
- **Scope**: Orchestrator-wide - must be unique
- **Lifetime**: Persistent (lifetime of Flock instance)
- **Generated**: User-provided via `flock.agent(name)`
- **Usage**: Used as `produced_by` in Artifact, `consumer` in ConsumptionRecord

---

#### `agent_id` (str)
**Usage**: Parameter name in various methods

- **What**: Alias for `agent.name`
- **Scope**: Same as agent.name
- **Generated**: Just a parameter naming convention

**⚠️ NOT A SEPARATE ID**: Just `agent.name` called by different parameter name - creates confusion

---

#### `tenant_id` (str | None)
**File**: `src/flock/visibility.py:21`

- **What**: Multi-tenancy isolation identifier
- **Scope**: Cross-system - isolates data between tenants
- **Lifetime**: Persistent
- **Generated**: User-provided
- **Usage**: Part of AgentIdentity, used in TenantVisibility policy

---

### Category 4: Correlation & Grouping

#### `correlation_key` (Any)
**File**: `src/flock/correlation_engine.py:33`

- **What**: Business-level correlation key (NOT framework correlation_id!)
- **Scope**: Business process (e.g., same patient, order, session)
- **Lifetime**: Ephemeral (only during correlation window)
- **Generated**: Extracted from payload using `JoinSpec.by` lambda
- **Example**: `lambda x: x.patient_id` extracts patient_id as correlation_key

**CRITICAL DISTINCTION**:
```python
# Framework correlation_id (UUID): Distributed tracing
artifact.correlation_id  # uuid1

# Business correlation_key (Any): Grouping logic
join_spec.by(artifact)  # "P123" (patient_id)
```

---

### Category 5: External Systems (OpenTelemetry)

#### `trace_id` (str - hex formatted)
**File**: `src/flock/logging/logging.py:54-60`

```python
def get_current_trace_id() -> str:
    span_context = trace.get_current_span().get_span_context()
    return format(span_context.trace_id, "032x")
```

- **What**: OpenTelemetry distributed tracing identifier
- **Scope**: Workflow-wide (similar to correlation_id but for observability)
- **Lifetime**: Ephemeral (tracing session)
- **Generated**: OpenTelemetry framework
- **Usage**: Logging, telemetry databases, trace queries

**⚠️ OVERLAPPING WITH correlation_id**: Both track workflows but serve different purposes:
- `correlation_id`: Business workflow tracking (persistent, query blackboard)
- `trace_id`: Technical tracing (ephemeral, debugging)

---

#### `span_id` (str - hex formatted)
**File**: `src/flock/logging/telemetry_exporter/sqlite_exporter.py:42`

- **What**: OpenTelemetry span identifier (sub-operation within trace)
- **Scope**: Operation-level
- **Lifetime**: Ephemeral
- **Generated**: OpenTelemetry framework
- **Usage**: Forms parent-child hierarchy, flame graphs

---

### Comparison Matrix: All IDs

| ID Name | Type | Scope | Lifetime | Generated By | Purpose |
|---------|------|-------|----------|--------------|---------|
| `artifact.id` | UUID | Global | Persistent | Framework | Unique artifact identity |
| `correlation_id` | UUID\|None | Workflow | Persistent | Framework/User | Workflow tracing |
| `partition_key` | str\|None | Infrastructure | Persistent | User | Sharding (future) |
| `task_id` | str | Agent run | Ephemeral | Framework | Execution tracking |
| `run_id` | str\|None | Agent run | Persistent | Framework | Same as task_id (storage) |
| `agent.name` | str | Orchestrator | Persistent | User | Agent identifier |
| `agent_id` | str | N/A | N/A | User | Alias for agent.name |
| `tenant_id` | str\|None | Cross-system | Persistent | User | Multi-tenancy |
| `correlation_key` | Any | Business | Ephemeral | User lambda | Business grouping |
| `trace_id` | str (hex) | Workflow | Ephemeral | OpenTelemetry | Observability |
| `span_id` | str (hex) | Operation | Ephemeral | OpenTelemetry | Sub-operation tracing |

---

### Key Issues Identified in ID System

#### Issue #1: Naming Inconsistency (task_id vs run_id)
**Problem**: Same concept, different names
```python
Context.task_id  # In runtime
ConsumptionRecord.run_id  # In storage (but = ctx.task_id)
```

---

#### Issue #2: Type Inconsistency
**Problem**: Both track execution but different types
```python
correlation_id: UUID  # Workflow-level
task_id: str  # Execution-level (but internally str(uuid4()))
```

---

#### Issue #3: Multiple "Agent" Identifiers
**Problem**: Three related concepts creating confusion
- `agent.name` - primary identifier
- `agent_id` - just a parameter name (not separate ID)
- `agent.identity` - composite object (not separate ID)

---

#### Issue #4: Overlapping Concepts (correlation_id vs trace_id)
**Problem**: Both track workflows but different purposes
- `correlation_id`: Business workflow (persistent, blackboard queries)
- `trace_id`: Technical observability (ephemeral, debugging)

**Currently**: Independent, not linked
**Potential confusion**: Users might expect alignment

---

### Recommendations from ID Audit

**Priority 1**: Rename `task_id` → `run_id` everywhere for consistency

**Priority 2**: Document ID glossary with clear relationships

**Priority 3**: Consider linking `trace_id` and `correlation_id` (optional)

**Priority 4**: Clarify that `agent_id` is just parameter naming, not separate ID

---

**For complete ID audit report, see**: `ID_AUDIT_REPORT.md` in this directory

---

## 📋 Code Flow Analysis

### Step 1: Artifact Creation at Publish

**File**: `src/flock/orchestrator.py:689-731`

```python
async def publish(obj: BaseModel, correlation_id: str | None = None) -> Artifact:
    artifact = Artifact(
        type=type_registry.get_name(type(obj)),
        payload=obj.model_dump(),
        correlation_id=correlation_id or uuid4(),  # NEW UUID if not provided
        produced_by="external",
        ...
    )
    await self.store.put(artifact)
    await self._schedule_artifact(artifact)
    return artifact
```

**Key behavior**: Each published artifact gets a **NEW UUID** as `correlation_id` if not explicitly provided.

---

### Step 2: Correlation Engine Processing

**File**: `src/flock/correlation_engine.py:130-202`

```python
async def add_artifact(
    self,
    artifact: Artifact,
    agent: Agent,
    sub_idx: int,
    join_spec: JoinSpec,
) -> list[Artifact] | None:
    # Extract business correlation key using JoinSpec.by lambda
    correlation_key = join_spec.by(payload_instance)  # e.g., "A-001"

    # Group artifacts by business key
    group = self.correlation_groups[(agent, sub_idx)][correlation_key]
    group.add_artifact(type_name, artifact)

    # When all required types present, return group
    if group.is_complete(self.required_types, self.required_counts):
        return group.get_artifacts()  # [XRayImage_artifact, LabResults_artifact]

    return None
```

**Key insight**: The correlation engine:
- Groups artifacts by **business key** (patient_id="A-001")
- Does NOT modify or merge framework `correlation_id` values
- Returns artifacts as a list (order matters!)

---

### Step 3: Agent Task Execution

**File**: `src/flock/orchestrator.py:998-1008`

```python
async def _run_agent_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
    correlation_id = artifacts[0].correlation_id if artifacts else uuid4()  # ⚠️ FIRST ONLY!

    timestamp = datetime.now(timezone.utc)
    ctx = Context(
        board=BoardHandle(self),
        orchestrator=self,
        task_id=str(uuid4()),
        correlation_id=correlation_id,  # Passed to context
    )

    # Record consumptions (ALL artifacts tracked here)
    records = [
        ConsumptionRecord(
            artifact_id=artifact.id,
            consumer=agent.name,
            run_id=ctx.task_id,
            correlation_id=str(correlation_id),  # Still first artifact's ID
            consumed_at=timestamp,
        )
        for artifact in artifacts
    ]
    await self.store.record_consumptions(records)

    # Execute agent
    await agent.execute(ctx, artifacts)
```

**CRITICAL LINE**: `correlation_id = artifacts[0].correlation_id`

**Key insight**:
- Context gets correlation_id from **first artifact only**
- ConsumptionRecords track ALL inputs, but with first artifact's correlation_id
- This is where lineage information starts to degrade

---

### Step 4: Output Creation

**File**: `src/flock/agent.py:298-322`

```python
async def _make_outputs(self, ctx: Context, result: EvalResult) -> list[Artifact]:
    produced: list[Artifact] = []
    for output_decl in self.outputs:
        payload = self._select_payload(output_decl, result)
        if payload is None:
            continue

        metadata = {
            "correlation_id": ctx.correlation_id,  # ⚠️ From context (first input only)
        }

        artifact = output_decl.apply(payload, produced_by=self.name, metadata=metadata)
        produced.append(artifact)
        await ctx.board.publish(artifact)

    return produced
```

**Key insight**: Output artifacts inherit `correlation_id` from context, which came from the first input artifact.

---

## 🔍 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: PUBLISH PHASE                                        │
└──────────────────────────────────────────────────────────────┘

User publishes XRayImage:
    XRayImage(patient_id="A-001")
        ↓
    Orchestrator.publish() assigns: correlation_id=uuid1
        ↓
    Stored: Artifact{type="XRayImage", correlation_id=uuid1,
                     payload={patient_id: "A-001"}}

User publishes LabResults:
    LabResults(patient_id="A-001")
        ↓
    Orchestrator.publish() assigns: correlation_id=uuid2
        ↓
    Stored: Artifact{type="LabResults", correlation_id=uuid2,
                     payload={patient_id: "A-001"}}


┌──────────────────────────────────────────────────────────────┐
│ STEP 2: CORRELATION ENGINE                                   │
└──────────────────────────────────────────────────────────────┘

JoinSpec.by(x) extracts business key:
    XRayImage → patient_id="A-001"
    LabResults → patient_id="A-001"
        ↓
    CorrelationEngine groups by business key "A-001"
        ↓
    When complete, returns: [XRayImage_artifact, LabResults_artifact]
        (Order: XRay first, Lab second)
        (Each retains original correlation_id: uuid1, uuid2)


┌──────────────────────────────────────────────────────────────┐
│ STEP 3: AGENT EXECUTION (_run_agent_task)                    │
└──────────────────────────────────────────────────────────────┘

Receives: artifacts=[XRayImage_artifact, LabResults_artifact]
    ↓
    Select correlation_id = artifacts[0].correlation_id  # uuid1 ⚠️
    ↓
    Create Context with correlation_id=uuid1
    ↓
    Record consumptions:
        ConsumptionRecord{artifact_id=xray.id, correlation_id=uuid1}
        ConsumptionRecord{artifact_id=lab.id, correlation_id=uuid1}  # ⚠️ Lost uuid2!
    ↓
    Agent.execute(ctx, [XRayImage, LabResults])


┌──────────────────────────────────────────────────────────────┐
│ STEP 4: OUTPUT CREATION (_make_outputs)                      │
└──────────────────────────────────────────────────────────────┘

Agent produces DiagnosticReport
    ↓
    _make_outputs() uses ctx.correlation_id (uuid1)
    ↓
    Create Artifact{type="DiagnosticReport",
                    correlation_id=uuid1,  # From first input only
                    produced_by="radiologist",
                    payload={patient_id: "A-001", diagnosis: "..."}}
    ↓
    Publish to blackboard


┌──────────────────────────────────────────────────────────────┐
│ FINAL STATE                                                   │
└──────────────────────────────────────────────────────────────┘

Artifacts in store:
    1. XRayImage:
       - id=xray_id
       - correlation_id=uuid1
       - payload={patient_id: "A-001"}

    2. LabResults:
       - id=lab_id
       - correlation_id=uuid2  # ⚠️ Not linked to output!
       - payload={patient_id: "A-001"}

    3. DiagnosticReport:
       - id=report_id
       - correlation_id=uuid1  # Only links to XRay
       - payload={patient_id: "A-001", diagnosis: "..."}

Data lineage:
    DiagnosticReport (uuid1) ← XRayImage (uuid1) ✅
                             ← LabResults (uuid2) ❌ LOST!
```

---

## ⚠️ Issues Identified

### Issue #1: Lost Data Lineage for Non-First Artifacts

**Severity**: HIGH
**Impact**: Cannot trace outputs back to all inputs

**Example**:
```python
# Scenario: Find all DiagnosticReports influenced by a specific lab result

lab_result = await store.get(lab_result_id)  # uuid2
print(lab_result.correlation_id)  # uuid2

# Try to find reports that used this lab result
reports = await store.get_by_type(DiagnosticReport)
for report in reports:
    if report.correlation_id == lab_result.correlation_id:  # uuid2 == uuid2?
        print("Found!")  # ❌ Never prints! correlation_id is uuid1, not uuid2

# The lineage is lost!
```

**Workaround** (complex):
```python
# Must use ConsumptionRecords (indirect query)
# 1. Find all runs that consumed the lab result
consumptions = await store.get_consumptions_by_artifact_id(lab_result_id)

# 2. For each run, find outputs produced
for consumption in consumptions:
    run_id = consumption.run_id
    # Now need to query: "Which artifacts were produced by run_id?"
    # This requires additional tracking not currently in the system!
```

---

### Issue #2: Terminology Confusion

**Severity**: MEDIUM
**Impact**: Developer confusion about two different "correlation" concepts

**Problem**: The term "correlation" is overloaded:

1. **Framework correlation_id** (UUID): For distributed tracing (tracking a request across services)
2. **Business correlation key** (e.g., patient_id): For joining artifacts based on business logic

**Confusion examples**:
```python
# Developer sees:
artifact.correlation_id  # Framework UUID for tracing

# But thinks:
"Ah, this must be the patient_id!"  # ❌ Wrong! That's the business key

# Actual business key is:
artifact.payload["patient_id"]  # ✅ Correct
```

**Industry standard**: OpenTelemetry uses `trace_id` and `span_id` for distributed tracing, reserving "correlation" for business concepts.

---

### Issue #3: No Explicit Parent Artifact Tracking

**Severity**: HIGH
**Impact**: Cannot directly query artifact lineage

**Current Artifact model**:
```python
class Artifact(BaseModel):
    id: UUID
    type: str
    correlation_id: UUID | None  # Only links to first input
    produced_by: str  # Agent name, not artifact IDs
    # Missing: Which artifacts produced this one?
```

**Limitation**: To find parent artifacts, you must:
1. Query ConsumptionRecords by artifact_id
2. Find the run_id that produced the artifact
3. Query all consumptions for that run_id
4. Fetch parent artifacts by ID

**This is unnecessarily complex for a fundamental operation.**

---

### Issue #4: ConsumptionRecords Don't Fully Solve the Problem

**Current ConsumptionRecord**:
```python
@dataclass
class ConsumptionRecord:
    artifact_id: UUID  # Input artifact
    consumer: str  # Agent name
    run_id: str  # Execution ID
    correlation_id: str  # Still just first artifact's ID
    consumed_at: datetime
```

**What's missing**: Link from output artifacts back to their run_id!

**Current flow**:
```
Input artifacts → ConsumptionRecords → run_id
                                        ↓
                                     Agent execution
                                        ↓
                                     Output artifacts (NO run_id stored!)
```

**Challenge**: Given an output artifact, how do you find which run_id produced it?
- No field on Artifact stores the run_id
- Must search ConsumptionRecords to find runs that might have produced it
- Ambiguous if multiple runs produce same artifact type

---

## 💡 Recommendations

### Recommendation #1: Add Parent Artifact Tracking

**Priority**: HIGH
**Effort**: Medium
**Impact**: Resolves Issues #1, #3, #4

#### Proposed Changes

**A. Extend Artifact Model**

**File**: `src/flock/artifacts.py`

```python
class Artifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: str
    payload: dict[str, Any]
    produced_by: str
    correlation_id: UUID | None = None  # Keep for backward compatibility
    parent_artifact_ids: list[UUID] = Field(default_factory=list)  # 🆕 NEW!
    run_id: str | None = None  # 🆕 NEW! Links to execution that produced this
    partition_key: str | None = None
    tags: set[str] = Field(default_factory=set)
    visibility: Visibility = Field(default_factory=lambda: PublicVisibility())
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
```

---

**B. Update Context to Track Inputs**

**File**: `src/flock/runtime.py`

```python
class Context(BaseModel):
    board: Any
    orchestrator: Any
    correlation_id: UUID | None = None
    task_id: str
    input_artifacts: list[Artifact] = Field(default_factory=list)  # 🆕 NEW!
    state: dict[str, Any] = Field(default_factory=dict)
```

---

**C. Update _run_agent_task to Populate Context**

**File**: `src/flock/orchestrator.py:998-1008`

```python
async def _run_agent_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
    correlation_id = artifacts[0].correlation_id if artifacts else uuid4()

    timestamp = datetime.now(timezone.utc)
    ctx = Context(
        board=BoardHandle(self),
        orchestrator=self,
        task_id=str(uuid4()),
        correlation_id=correlation_id,
        input_artifacts=artifacts,  # 🆕 NEW! Pass all input artifacts
    )

    # ... rest of method
```

---

**D. Update _make_outputs to Track Parents**

**File**: `src/flock/agent.py:298-322`

```python
async def _make_outputs(self, ctx: Context, result: EvalResult) -> list[Artifact]:
    produced: list[Artifact] = []
    for output_decl in self.outputs:
        payload = self._select_payload(output_decl, result)
        if payload is None:
            continue

        metadata = {
            "correlation_id": ctx.correlation_id,
            "parent_artifact_ids": [a.id for a in ctx.input_artifacts],  # 🆕 NEW!
            "run_id": ctx.task_id,  # 🆕 NEW!
        }

        artifact = output_decl.apply(payload, produced_by=self.name, metadata=metadata)
        produced.append(artifact)
        await ctx.board.publish(artifact)

    return produced
```

---

#### Example Usage After Implementation

```python
# Publish inputs
xray = await flock.publish(XRayImage(patient_id="A-001"))
# xray.parent_artifact_ids = []  # No parents (external input)

lab = await flock.publish(LabResults(patient_id="A-001"))
# lab.parent_artifact_ids = []  # No parents (external input)

# Agent processes
await flock.run_until_idle()

# Get output
reports = await flock.store.get_by_type(DiagnosticReport)
report = reports[0]

# ✅ Full lineage tracking!
print(report.parent_artifact_ids)  # [xray.id, lab.id]
print(xray.id in report.parent_artifact_ids)  # True
print(lab.id in report.parent_artifact_ids)  # True ✅ Not lost anymore!

# Find all reports influenced by this lab result
reports_using_lab = [
    r for r in await store.get_by_type(DiagnosticReport)
    if lab.id in r.parent_artifact_ids
]
```

---

### Recommendation #2: Rename correlation_id to trace_id

**Priority**: MEDIUM
**Effort**: High (requires migration)
**Impact**: Resolves Issue #2

#### Rationale

- **Industry standard**: OpenTelemetry uses `trace_id` and `span_id`
- **Clear semantics**: "trace" clearly means distributed tracing, not business correlation
- **Aligns with patterns**: Separates framework concerns from domain concepts

#### Proposed Changes

**File**: `src/flock/artifacts.py`

```python
class Artifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: str
    trace_id: UUID | None = None  # 🔄 RENAMED from correlation_id
    parent_artifact_ids: list[UUID] = Field(default_factory=list)
    run_id: str | None = None
    ...

    # Backward compatibility property (deprecation period)
    @property
    def correlation_id(self) -> UUID | None:
        import warnings
        warnings.warn(
            "correlation_id is deprecated, use trace_id instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.trace_id

    @correlation_id.setter
    def correlation_id(self, value: UUID | None):
        self.trace_id = value
```

#### Migration Strategy

**Phase 1** (v0.X): Add deprecation warnings
- Keep `correlation_id` property as alias to `trace_id`
- Update documentation to use `trace_id`
- Convert internal code to use `trace_id`

**Phase 2** (v0.Y): Loud warnings
- Add runtime warnings whenever `correlation_id` is accessed
- Update all examples and tests

**Phase 3** (v1.0): Breaking change
- Remove `correlation_id` property entirely
- Only `trace_id` remains

---

### Recommendation #3: Add Lineage Query Helpers

**Priority**: MEDIUM
**Effort**: Medium
**Impact**: Improves developer experience

#### Proposed API

**File**: `src/flock/store.py`

```python
from dataclasses import dataclass


@dataclass
class ArtifactLineage:
    """Represents the lineage tree of an artifact."""
    artifact: Artifact
    parents: list["ArtifactLineage"]  # Recursive structure


class BlackboardStore:
    # ... existing methods ...

    async def get_lineage(
        self,
        artifact_id: UUID,
        max_depth: int | None = None
    ) -> ArtifactLineage:
        """
        Get full lineage tree for an artifact.

        Args:
            artifact_id: The artifact to trace
            max_depth: Maximum depth to traverse (None = unlimited)

        Returns:
            ArtifactLineage with recursive parent structure

        Example:
            >>> lineage = await store.get_lineage(report_id)
            >>> print(f"Report produced from {len(lineage.parents)} inputs")
            >>> for parent_lineage in lineage.parents:
            >>>     print(f"  - {parent_lineage.artifact.type}")
        """
        artifact = await self.get(artifact_id)

        if max_depth == 0:
            return ArtifactLineage(artifact=artifact, parents=[])

        # Get parents recursively
        parents = []
        for parent_id in artifact.parent_artifact_ids:
            next_depth = None if max_depth is None else max_depth - 1
            parent_lineage = await self.get_lineage(parent_id, max_depth=next_depth)
            parents.append(parent_lineage)

        return ArtifactLineage(artifact=artifact, parents=parents)

    async def get_descendants(
        self,
        artifact_id: UUID,
        max_depth: int | None = None
    ) -> list[Artifact]:
        """
        Get all artifacts that were derived from this artifact.

        Args:
            artifact_id: The source artifact
            max_depth: Maximum depth to traverse (None = unlimited)

        Returns:
            List of descendant artifacts (breadth-first order)

        Example:
            >>> lab_result = await store.get(lab_result_id)
            >>> descendants = await store.get_descendants(lab_result_id)
            >>> print(f"Lab result influenced {len(descendants)} artifacts:")
            >>> for desc in descendants:
            >>>     print(f"  - {desc.type} (id={desc.id})")
        """
        if max_depth == 0:
            return []

        # Find all artifacts where parent_artifact_ids contains artifact_id
        # Implementation depends on storage backend
        # For memory store:
        all_artifacts = await self.get_all()
        descendants = [
            a for a in all_artifacts
            if artifact_id in a.parent_artifact_ids
        ]

        # Recursively get descendants of descendants
        if max_depth is None or max_depth > 1:
            next_depth = None if max_depth is None else max_depth - 1
            for desc in list(descendants):
                sub_descendants = await self.get_descendants(desc.id, max_depth=next_depth)
                descendants.extend(sub_descendants)

        return descendants

    async def get_lineage_path(
        self,
        from_artifact_id: UUID,
        to_artifact_id: UUID
    ) -> list[Artifact] | None:
        """
        Find the path from one artifact to another through lineage.

        Args:
            from_artifact_id: Source artifact
            to_artifact_id: Target artifact

        Returns:
            List of artifacts forming the path, or None if no path exists

        Example:
            >>> path = await store.get_lineage_path(xray_id, treatment_plan_id)
            >>> if path:
            >>>     print(" → ".join(a.type for a in path))
            >>>     # Output: "XRayImage → DiagnosticReport → TreatmentPlan"
        """
        # Breadth-first search through lineage
        from collections import deque

        queue = deque([(from_artifact_id, [from_artifact_id])])
        visited = set()

        while queue:
            current_id, path = queue.popleft()

            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id == to_artifact_id:
                # Found path!
                return [await self.get(aid) for aid in path]

            # Explore descendants
            current = await self.get(current_id)
            descendants = await self.get_descendants(current_id, max_depth=1)

            for desc in descendants:
                if desc.id not in visited:
                    queue.append((desc.id, path + [desc.id]))

        return None  # No path found
```

---

#### Example Usage

```python
# Get full lineage tree
lineage = await store.get_lineage(diagnostic_report_id)
print(f"DiagnosticReport produced from {len(lineage.parents)} inputs:")
for parent_lineage in lineage.parents:
    print(f"  - {parent_lineage.artifact.type} (id={parent_lineage.artifact.id})")

# Find all artifacts influenced by a lab result
lab_result = await store.get(lab_result_id)
descendants = await store.get_descendants(lab_result_id)
print(f"Lab result influenced {len(descendants)} artifacts:")
for desc in descendants:
    print(f"  - {desc.type} (id={desc.id})")

# Trace path from X-ray to treatment plan
path = await store.get_lineage_path(xray_id, treatment_plan_id)
if path:
    print("Lineage path:")
    print(" → ".join(a.type for a in path))
    # Output: "XRayImage → DiagnosticReport → TreatmentPlan"
```

---

### Recommendation #4: Document the Distinction

**Priority**: HIGH
**Effort**: Low
**Impact**: Reduces developer confusion

#### Proposed Documentation

**File**: `docs/concepts/correlation-and-lineage.md`

```markdown
# Correlation and Lineage in Flock

## Overview

Flock uses three related but distinct concepts for tracking artifacts:

1. **Business Correlation** (JoinSpec) - Grouping artifacts by business key
2. **Distributed Tracing** (trace_id) - Tracking requests across agents
3. **Data Lineage** (parent_artifact_ids) - Tracking which artifacts produced which

## 1. Business Correlation (JoinSpec)

### What It Is

Grouping artifacts by a business-specific key (e.g., patient_id, order_id, user_id).

### How It Works

```python
radiologist = (
    flock.agent("radiologist")
    .consumes(
        XRayImage,
        LabResults,
        join=JoinSpec(
            by=lambda x: x.patient_id,  # Business correlation key
            within=timedelta(minutes=5)
        )
    )
)
```

### When to Use

- When an agent needs MULTIPLE types of artifacts that share a common business key
- When artifacts must arrive within a time window
- When order of arrival doesn't matter

### Example

"Wait for both X-ray AND lab results for the SAME patient before diagnosing."

---

## 2. Distributed Tracing (trace_id)

### What It Is

A UUID that tracks a single request/workflow across multiple agents and services.

### How It Works

```python
# Publish with explicit trace_id
xray = await flock.publish(
    XRayImage(patient_id="A-001"),
    trace_id=trace_id  # Propagate from incoming request
)

# All derived artifacts inherit trace_id
report = reports[0]
print(report.trace_id == xray.trace_id)  # True
```

### When to Use

- Debugging distributed workflows
- Observability and monitoring (e.g., OpenTelemetry integration)
- SLA tracking (e.g., "How long did this request take end-to-end?")

### Example

"Trace all artifacts generated by a single diagnostic request from intake to billing."

---

## 3. Data Lineage (parent_artifact_ids)

### What It Is

Explicit parent-child relationships showing which artifacts produced which outputs.

### How It Works

```python
# Automatically tracked by framework
report = reports[0]
print(report.parent_artifact_ids)  # [xray.id, lab.id]

# Query lineage
lineage = await store.get_lineage(report.id)
for parent_lineage in lineage.parents:
    print(parent_lineage.artifact.type)  # "XRayImage", "LabResults"
```

### When to Use

- Debugging: "Which inputs produced this output?"
- Audit trails: "What data was used to make this decision?"
- Impact analysis: "If I fix this input, what outputs are affected?"
- Compliance: "Show me the data provenance for this diagnosis."

### Example

"Trace which X-ray and lab results were used to generate this specific diagnostic report."

---

## Comparison Table

| Concept | Purpose | Scope | Key Field | Example |
|---------|---------|-------|-----------|---------|
| **Business Correlation** | Group artifacts by business key | Within single agent subscription | `JoinSpec.by` | patient_id="A-001" |
| **Distributed Tracing** | Track requests across agents | Entire workflow | `Artifact.trace_id` | trace_id=uuid1 |
| **Data Lineage** | Track input→output relationships | Parent-child links | `Artifact.parent_artifact_ids` | [xray.id, lab.id] |

---

## Common Patterns

### Pattern 1: Trace a Specific Patient Workflow

```python
# Start with patient identifier
patient_id = "A-001"

# Find all artifacts for this patient (business correlation)
xrays = await store.get_by_type(XRayImage)
patient_xrays = [x for x in xrays if x.payload["patient_id"] == patient_id]

# Trace lineage from X-ray (data lineage)
for xray in patient_xrays:
    descendants = await store.get_descendants(xray.id)
    print(f"X-ray {xray.id} influenced {len(descendants)} artifacts")
```

### Pattern 2: Debug a Specific Request

```python
# Start with trace_id from incoming request
trace_id = request_headers["X-Trace-ID"]

# Find all artifacts in this trace (distributed tracing)
all_artifacts = await store.get_all()
trace_artifacts = [a for a in all_artifacts if a.trace_id == trace_id]

print(f"Request {trace_id} produced {len(trace_artifacts)} artifacts:")
for artifact in trace_artifacts:
    print(f"  - {artifact.type} at {artifact.created_at}")
```

### Pattern 3: Impact Analysis

```python
# "If I fix this lab result, what needs to be reprocessed?"
lab_result = await store.get(lab_result_id)

# Find all descendants (data lineage)
impacted = await store.get_descendants(lab_result_id)

print(f"Fixing lab result {lab_result_id} would affect:")
for artifact in impacted:
    print(f"  - {artifact.type} (id={artifact.id})")
```

---

## Best Practices

### DO:
- ✅ Use JoinSpec for business-driven correlation (patient_id, order_id)
- ✅ Propagate trace_id for observability and debugging
- ✅ Query parent_artifact_ids for data lineage and audit trails
- ✅ Combine all three for comprehensive workflow understanding

### DON'T:
- ❌ Use trace_id for business correlation (use JoinSpec instead)
- ❌ Use correlation_id (deprecated, use trace_id)
- ❌ Rely on framework internals for lineage (use parent_artifact_ids)
```

---

## 📊 Testing Strategy

### Test Case 1: Parent Artifact Tracking

```python
@pytest.mark.asyncio
async def test_parent_artifact_tracking_joinspec():
    """Test that outputs track ALL input artifacts from JoinSpec correlation."""
    flock = Flock()

    # Register types
    @flock_type("XRayImage")
    class XRayImage(BaseModel):
        patient_id: str

    @flock_type("LabResults")
    class LabResults(BaseModel):
        patient_id: str

    @flock_type("DiagnosticReport")
    class DiagnosticReport(BaseModel):
        patient_id: str
        diagnosis: str

    # Create agent
    radiologist = (
        flock.agent("radiologist")
        .consumes(
            XRayImage,
            LabResults,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5))
        )
        .publishes(DiagnosticReport)
    )

    # Publish inputs
    xray = await flock.publish(XRayImage(patient_id="A-001"))
    lab = await flock.publish(LabResults(patient_id="A-001"))

    # Process
    await flock.run_until_idle()

    # Get output
    reports = await flock.store.get_by_type(DiagnosticReport)
    assert len(reports) == 1
    report = reports[0]

    # Verify lineage (NEW BEHAVIOR)
    assert len(report.parent_artifact_ids) == 2
    assert xray.id in report.parent_artifact_ids
    assert lab.id in report.parent_artifact_ids  # ✅ Not lost!

    # Verify run_id is set
    assert report.run_id is not None
```

---

### Test Case 2: Multi-Level Lineage

```python
@pytest.mark.asyncio
async def test_multi_level_lineage():
    """Test lineage tracking across multiple agent executions."""
    flock = Flock()

    # Level 1: Diagnostic from X-ray + Lab
    xray = await flock.publish(XRayImage(patient_id="A-001"))
    lab = await flock.publish(LabResults(patient_id="A-001"))

    await flock.run_until_idle()

    reports = await flock.store.get_by_type(DiagnosticReport)
    report = reports[0]

    # Level 2: Treatment plan from diagnostic
    doctor = (
        flock.agent("doctor")
        .consumes(DiagnosticReport)
        .publishes(TreatmentPlan)
    )

    await flock.run_until_idle()

    plans = await flock.store.get_by_type(TreatmentPlan)
    plan = plans[0]

    # Verify immediate parent
    assert report.id in plan.parent_artifact_ids

    # Verify full lineage query
    lineage = await flock.store.get_lineage(plan.id)
    assert lineage.artifact.id == plan.id
    assert len(lineage.parents) == 1  # DiagnosticReport
    assert len(lineage.parents[0].parents) == 2  # XRay + Lab

    # Verify descendants query
    descendants = await flock.store.get_descendants(xray.id)
    assert report.id in [d.id for d in descendants]
    assert plan.id in [d.id for d in descendants]
```

---

### Test Case 3: Lineage Path Finding

```python
@pytest.mark.asyncio
async def test_lineage_path():
    """Test finding path between artifacts through lineage."""
    flock = Flock()

    # Create workflow: XRay → DiagnosticReport → TreatmentPlan
    xray = await flock.publish(XRayImage(patient_id="A-001"))
    lab = await flock.publish(LabResults(patient_id="A-001"))

    await flock.run_until_idle()

    reports = await flock.store.get_by_type(DiagnosticReport)
    report = reports[0]

    doctor = (
        flock.agent("doctor")
        .consumes(DiagnosticReport)
        .publishes(TreatmentPlan)
    )

    await flock.run_until_idle()

    plans = await flock.store.get_by_type(TreatmentPlan)
    plan = plans[0]

    # Find path from X-ray to treatment plan
    path = await flock.store.get_lineage_path(xray.id, plan.id)

    assert path is not None
    assert len(path) == 3  # XRay → Report → Plan
    assert path[0].id == xray.id
    assert path[1].id == report.id
    assert path[2].id == plan.id
```

---

## 🎯 Summary

### Current Behavior

✅ **Works**: JoinSpec correlation by business key
✅ **Works**: Agents receive all correlated artifacts
⚠️ **Limited**: Outputs only link to first input via correlation_id
❌ **Missing**: Explicit parent-child artifact tracking

### Key Findings

1. **DiagnosticReport gets correlation_id from the FIRST input** (XRayImage)
2. LabResults correlation_id is NOT preserved in the output
3. Data lineage IS trackable via ConsumptionRecords, but indirectly

### Recommendations

| Recommendation | Priority | Effort | Impact |
|---------------|----------|--------|--------|
| **Add parent_artifact_ids** | HIGH | Medium | Resolves lost lineage |
| **Rename to trace_id** | MEDIUM | High | Reduces confusion |
| **Add lineage helpers** | MEDIUM | Medium | Improves DX |
| **Document distinction** | HIGH | Low | Education |

### Timeline

- **Phase 1** (Week 1): Add `parent_artifact_ids` and `run_id` fields
- **Phase 2** (Week 2): Implement lineage query helpers
- **Phase 3** (Week 3): Documentation and examples
- **Phase 4** (6+ months): Deprecate `correlation_id`, rename to `trace_id`

---

**Document Version**: 1.0
**Last Updated**: 2025-10-13
**Status**: Analysis Complete - Ready for Implementation
