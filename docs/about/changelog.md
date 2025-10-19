---
title: Changelog
description: Recent changes, updates, and release history for Flock
tags:
  - changelog
  - releases
  - history
search:
  boost: 1.2
---

# Changelog

## [0.5.2] - 2025-10-19

### 🎉 New Features

#### 🌟 Fan-Out Publishing
**Produce multiple outputs from a single agent execution:**

```python
# Generate 10 diverse product ideas from one brief
idea_generator = (
    flock.agent("generator")
    .consumes(ProductBrief)
    .publishes(ProductIdea, fan_out=10)  # Produces 10 ideas!
)

# Multi-output fan-out: Generate 3 of EACH type in ONE LLM call!
multi_master = (
    flock.agent("multi_master")
    .consumes(Idea)
    .publishes(Movie, MovieScript, MovieCampaign, fan_out=3)
)
# = 9 total artifacts (3 movies + 3 scripts + 3 campaigns) in one execution!
```

**Features:**
- Single execution produces N artifacts per type
- Quality filtering with `where` parameter
- Validation with `validate` parameter
- Dynamic visibility control per artifact
- Massive efficiency: 1 LLM call → multiple validated outputs

**Use cases:**
- Content generation with diversity
- A/B testing variants
- Code review with multiple bug reports
- Multi-perspective analysis

#### 📦 BatchSpec - Cost Optimization
**Process multiple artifacts efficiently:**

```python
# Process 25 transactions in one batch = 96% cost reduction!
payment_processor = flock.agent("payments").consumes(
    Transaction,
    batch=BatchSpec(size=25, timeout=timedelta(seconds=30))
)

# Hybrid batching: by size OR timeout
analyzer = flock.agent("analyzer").consumes(
    LogEntry,
    batch=BatchSpec(size=100, timeout=timedelta(minutes=5))
)
```

**Features:**
- Size-based batching (flush when N artifacts accumulated)
- Timeout-based batching (flush after T seconds)
- Hybrid mode (whichever comes first)
- Automatic batch coordination

**Benefits:**
- 90%+ API cost reduction for bulk operations
- Efficient processing of high-volume streams
- Natural aggregation patterns

#### 🔗 JoinSpec - Data Correlation
**Correlate related artifacts within time windows:**

```python
# Match orders + shipments by order_id within 24 hours
customer_service = flock.agent("notifications").consumes(
    Order,
    Shipment,
    join=JoinSpec(by=lambda x: x.order_id, within=timedelta(hours=24))
)

# IoT sensor correlation
quality_control = flock.agent("qc").consumes(
    TemperatureSensor,
    PressureSensor,
    join=JoinSpec(by=lambda x: x.device_id, within=timedelta(seconds=30)),
    batch=BatchSpec(size=5)  # Combine with batching!
)
```

**Features:**
- Correlation by custom key (e.g., order_id, user_id, device_id)
- Time window enforcement
- Multi-type correlation support
- Composable with BatchSpec for multi-stage pipelines

**Use cases:**
- Order + shipment tracking
- Multi-modal data fusion (scans + labs + history)
- IoT sensor correlation
- Financial trade matching

#### 🧠 Semantic Subscriptions - Intelligence Beyond Keywords
**Match artifacts by MEANING, not keywords:**

```python
# Install semantic extras
pip install flock-core[semantic]

# Agents route based on semantic similarity
security_team = (
    flock.agent("security_team")
    .consumes(SupportTicket, semantic_match="security vulnerability exploit")
    .publishes(SecurityAlert)
)

billing_team = (
    flock.agent("billing_team")
    .consumes(SupportTicket, semantic_match="payment charge refund billing")
    .publishes(BillingResponse)
)

# "SQL injection" → Security Team (no "security" keyword needed!)
# "charged twice" → Billing Team (semantic understanding!)
```

**Advanced semantic filtering:**
```python
# Custom threshold (0.0-1.0, default 0.4)
.consumes(Ticket, semantic_match="urgent", semantic_threshold=0.7)  # Strict

# Multiple criteria (ALL must match - AND logic)
.consumes(Doc, semantic_match=["security", "compliance"])

# Field-specific matching
.consumes(Article, semantic_match={
    "query": "machine learning",
    "threshold": 0.6,
    "field": "abstract"  # Only match this field
})
```

**Semantic Context Provider:**
```python
from flock.semantic import SemanticContextProvider

# Find similar historical incidents for context-aware decisions
provider = SemanticContextProvider(
    query_text="database connection timeout",
    threshold=0.4,
    limit=5,
    artifact_type=Incident,
    where=lambda a: a.payload["resolved"] is True
)
similar_incidents = await provider.get_context(store)
```

**Features:**
- Local embeddings with all-MiniLM-L6-v2 model (~90MB)
- No external API required
- Fast with LRU cache (10k entries, ~15ms per embedding)
- Threshold control for precision/recall tuning
- Field extraction for targeted matching
- Multiple predicates with AND logic

**Benefits:**
- No keyword brittleness ("SQL injection" matches "security vulnerability")
- Better recall (catches semantically similar content)
- Intelligent routing without complex rule systems
- Context-aware agents with historical similarity search

**Use cases:**
- Smart ticket routing to specialized teams
- Content recommendation based on meaning
- Incident response with historical context
- Document classification by topic

### 📚 Documentation

- Added comprehensive semantic subscriptions guide (`docs/semantic-subscriptions.md`)
- Added 4 runnable examples in `examples/08-semantic/`:
  - `00_verify_semantic_features.py` - Quick verification (no LLM)
  - `01_intelligent_ticket_routing.py` - Smart routing demo
  - `02_multi_criteria_filtering.py` - Advanced filtering patterns
- Updated README with semantic subscriptions feature
- Added API documentation for all new features

### 🔧 API Changes

**New Parameters:**
- `fan_out` parameter in `.publishes()` for multi-output generation
- `semantic_match` parameter in `.consumes()` for meaning-based matching (replaces `text`)
- `semantic_threshold` parameter in `.consumes()` for similarity control (replaces `min_p`)
- `batch` parameter in `.consumes()` accepts `BatchSpec` objects
- `join` parameter in `.consumes()` accepts `JoinSpec` objects

**Note:** The original `text` and `min_p` parameters have been renamed to `semantic_match` and `semantic_threshold` for clarity. This makes it obvious that matching is semantic (meaning-based), not keyword-based.

### ✅ Testing

- Added 39 semantic subscription tests (100% passing)
- Added fan-out publishing tests
- Added BatchSpec and JoinSpec integration tests
- All 1,435+ tests passing with zero regressions

### 🚀 Performance

- Semantic matching: ~15ms per embedding (CPU)
- Batch processing: ~4.5ms per text with batching
- Cache hit rate: 60-80% typical
- Fan-out efficiency: N outputs in 1 LLM call

---

# Flock 0.5.0 Complete Changelog & Migration Guide

> **Complete architectural rewrite from workflow orchestration to blackboard architecture**

**Release Date**: 12. Oct 2025
**Migration Effort**: 1-4 weeks depending on system size
**Backward Compatibility**: **NONE** - This is a ground-up rewrite

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architectural Changes](#architectural-changes)
3. [Breaking Changes](#breaking-changes)
4. [New Features](#new-features)
5. [Migration Guide](#migration-guide)
6. [Performance Improvements](#performance-improvements)
7. [Deprecations & Removals](#deprecations--removals)
8. [Known Limitations](#known-limitations)
9. [Upgrade Recommendations](#upgrade-recommendations)

---

## Executive Summary

### What Changed?

Flock 0.5.0 is **not an incremental update**—it's a complete reimplementation with a fundamentally different architecture:

| Aspect | Flock 0.4 | Flock 0.5 |
|--------|-----------|-----------|
| **Architecture** | Workflow orchestration (LangGraph-style) | Blackboard architecture (Hearsay-II-style) |
| **Communication** | Direct agent-to-agent handoffs | Publish-subscribe via blackboard |
| **Execution Model** | Sequential by default | Parallel by default |
| **Type System** | String-based signatures | Pure Pydantic models with `@flock_type` |
| **Routing** | Explicit routers with config | Type-based subscription matching |
| **State** | Mutable `FlockContext` | Immutable `Artifact` objects |
| **Orchestration** | Temporal.io workflows | Event-driven coordination |
| **Dependencies** | PyTorch + Temporal + Heavy stack | DuckDB + FastAPI + Lean stack |

### Why This Change?

**Workflow orchestration doesn't scale.** As agent systems grow:
- **O(n²) complexity**: Every new agent requires updating router configuration
- **Tight coupling**: Agents must know about each other
- **Sequential bottlenecks**: Parallelism requires manual configuration
- **Testing complexity**: Must mock entire workflow graph

**Blackboard architecture solves this:**
- **O(n) complexity**: Agents subscribe to types, routing is automatic
- **Loose coupling**: Agents only know about data types
- **Natural parallelism**: All matching agents execute concurrently
- **Testing simplicity**: Test agents in isolation with type fixtures

**Research validation**: Recent studies show blackboard + MCP architectures achieve **competitive performance with SOTA multi-agent systems while using fewer tokens** ([Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture, 2024](https://arxiv.org/abs/2507.01701)).

---

## Architectural Changes

### Core Architecture: Workflow → Blackboard

#### Flock 0.4: Workflow Orchestration
```
[Agent A] → Router → [Agent B] → Router → [Agent C]
                ↓
        Temporal.io Workflow
```

**Characteristics:**
- Explicit handoffs between agents
- Central orchestrator manages execution
- Sequential by default, parallel requires configuration
- Tight coupling through router configuration

#### Flock 0.5: Blackboard Architecture
```
          [Blackboard Store]
               ↑     ↓
    ┌─────────┼─────┼─────────┐
    ↓         ↓     ↓         ↓
[Agent A] [Agent B] [Agent C] [Agent D]
```

**Characteristics:**
- Publish-subscribe communication
- No central orchestrator (event-driven)
- Parallel by default, executes all matching agents
- Loose coupling through type system

### Communication Model

#### 0.4: Direct Handoffs
```python
# Flock 0.4
class MyAgent(Agent):
    async def execute(self, context: FlockContext):
        result = await self.process(context.data)
        context.set_result(result)
        return "next_agent"  # Explicit routing
```

#### 0.5: Publish-Subscribe
```python
# Flock 0.5
@flock.agent("my_agent")
    .consumes(InputType)
    .publishes(OutputType)
    .does(process)

async def process(input: InputType) -> OutputType:
    # Pure transformation, no routing logic
    return OutputType(...)
```

### Execution Model

#### 0.4: Imperative Execution
```python
# Flock 0.4
context = FlockContext(initial_data)
result = await flock.run(context, entry_agent="start")
# Sequential execution, manual parallelism
```

#### 0.5: Declarative Execution
```python
# Flock 0.5
await flock.publish(UserRequest(query="..."))
await flock.run_until_idle()
# Parallel execution, automatic coordination
```

---

## Breaking Changes

### 1. Agent Definition

#### Before (0.4)
```python
from flock import FlockFactory, Agent, FlockContext

class ResearchAgent(Agent):
    def __init__(self, name: str):
        super().__init__(name)
        self.input_signature = "query: str"
        self.output_signature = "findings: List[str]"

    async def execute(self, context: FlockContext) -> str:
        query = context.data.get("query")
        findings = await self.research(query)
        context.set_result({"findings": findings})
        return "summarizer_agent"  # Explicit routing

agent = FlockFactory.create_default_agent(
    name="researcher",
    description="Research agent",
    agent_class=ResearchAgent
)
```

#### After (0.5)
```python
from flock import flock, flock_type
from pydantic import BaseModel

@flock_type
class Query(BaseModel):
    text: str

@flock_type
class Findings(BaseModel):
    results: list[str]

async def research_handler(query: Query) -> Findings:
    findings = await do_research(query.text)
    return Findings(results=findings)

agent = (
    flock.agent("researcher")
    .consumes(Query)
    .publishes(Findings)
    .does(research_handler)
)
```

**Key Changes:**
- ❌ No `FlockFactory`, `Agent` base class, or `FlockContext`
- ✅ Fluent builder pattern: `flock.agent().consumes().publishes().does()`
- ✅ Pure Pydantic types with `@flock_type` decorator
- ✅ Functions instead of classes (simpler)
- ✅ No explicit routing (type-based)

---

### 2. Multi-Agent Coordination

#### Before (0.4): Explicit Routing
```python
from flock import Router

# Define explicit routing logic
router = Router()
router.add_route("researcher", "summarizer", lambda ctx: ctx.has_findings())
router.add_route("summarizer", "formatter", lambda ctx: ctx.has_summary())

flock = FlockFactory.create(
    agents=[researcher, summarizer, formatter],
    router=router,
    entry_agent="researcher"
)
```

#### After (0.5): Type-Driven Flow
```python
# No router needed! Flow emerges from type relationships

# Researcher consumes Query, publishes Findings
researcher = flock.agent("researcher").consumes(Query).publishes(Findings).does(research)

# Summarizer consumes Findings, publishes Summary
summarizer = flock.agent("summarizer").consumes(Findings).publishes(Summary).does(summarize)

# Formatter consumes Summary, publishes Report
formatter = flock.agent("formatter").consumes(Summary).publishes(Report).does(format)

# Flow: Query → researcher → Findings → summarizer → Summary → formatter → Report
# No explicit routing config needed!
```

**Key Changes:**
- ❌ No `Router` class or route configuration
- ✅ Type system defines flow automatically
- ✅ Add/remove agents without touching router
- ✅ Natural composition through type matching

---

### 3. Execution & Result Retrieval

#### Before (0.4): Direct Access
```python
# Flock 0.4
context = FlockContext({"query": "AI trends"})
result = await flock.run(context, entry_agent="researcher")

# Direct access to result
findings = result.data.get("findings")
```

#### After (0.5): Store Queries
```python
# Flock 0.5
from flock.store import FilterConfig

# Publish input
await flock.publish(Query(text="AI trends"))

# Wait for completion
await flock.run_until_idle()

# Query the blackboard store
findings_artifacts = await flock.store.query_artifacts(
    FilterConfig(type_names={"Findings"}),
    limit=10
)

findings = findings_artifacts[0].payload
```

**Key Changes:**
- ❌ No direct result access via return value
- ✅ Results stored in persistent blackboard
- ✅ Query by type, producer, tags, time range, etc.
- ✅ Full audit trail of all artifacts

---

### 4. Tools & External Integration

#### Before (0.4): Modules
```python
# Flock 0.4
from flock import Module

class WebSearchModule(Module):
    async def search(self, query: str) -> list[str]:
        # Implementation
        pass

flock = FlockFactory.create(
    agents=[...],
    modules=[WebSearchModule()]
)
```

#### After (0.5): MCP Servers & Custom Tools
```python
# Flock 0.5 - Custom Tools
from flock import flock_tool

@flock_tool
async def web_search(query: str) -> list[str]:
    """Search the web for information."""
    # Implementation
    pass

# Or use MCP servers (external processes)
flock.with_mcp_server(
    name="brave-search",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-brave-search"]
)
```

**Key Changes:**
- ❌ No `Module` concept
- ✅ Simple `@flock_tool` decorator for custom tools
- ✅ MCP (Model Context Protocol) for external tools
- ✅ Tools run in separate processes (better isolation)

---

### 5. Configuration & Setup

#### Before (0.4): Factory Pattern
```python
# Flock 0.4
from flock import FlockFactory, TemporalConfig

flock = FlockFactory.create(
    agents=[agent1, agent2],
    router=router,
    temporal_config=TemporalConfig(
        host="localhost:7233",
        namespace="default"
    ),
    entry_agent="agent1"
)
```

#### After (0.5): Fluent Builder
```python
# Flock 0.5
from flock import Flock

flock = (
    Flock.builder()
    .with_agent(agent1)
    .with_agent(agent2)
    .with_tool(custom_tool)
    .with_mcp_server(name="brave", command="npx", args=[...])
    .build()
)

# Or use default orchestrator
await flock.publish(initial_artifact)
await flock.run_until_idle()
```

**Key Changes:**
- ❌ No `FlockFactory`, `TemporalConfig`
- ✅ Fluent builder: `Flock.builder().with_agent().with_tool().build()`
- ✅ No Temporal.io configuration (removed dependency)
- ✅ Simpler default setup

---

## New Features

### 1. Real-Time Dashboard

**Location:** `http://localhost:3000` (when running `flock dashboard`)

**Features:**
- **Dual Visualization Modes:**
  - **Agent View**: Network graph showing agent relationships and message flows
  - **Blackboard View**: Data lineage graph showing artifact transformations
- **WebSocket Streaming**: Zero-lag updates as agents execute
- **Trace Viewer**: 7 visualization modes (Timeline, Waterfall, Gantt, Flamegraph, Sunburst, Icicle, Sankey)
- **SQL Query Interface**: AI-queryable telemetry via DuckDB
- **Agent Metrics**: Real-time message counts, execution status, streaming tokens
- **Artifact Inspector**: Inspect artifact payloads, metadata, consumption chains

**Example:**
```bash
# Terminal 1: Start dashboard
flock dashboard

# Terminal 2: Run your agents
python my_agent_system.py

# Browser: Open http://localhost:3000
# Watch agents execute in real-time!
```

---

### 2. Type-Safe Contracts with @flock_type

**Pure Pydantic models** replace string-based signatures:

```python
from flock import flock_type
from pydantic import BaseModel, Field
from datetime import datetime

@flock_type
class UserRequest(BaseModel):
    """User's research request."""
    query: str = Field(description="Search query")
    max_results: int = Field(default=10, ge=1, le=100)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

@flock_type
class ResearchFindings(BaseModel):
    """Research results."""
    query: str
    sources: list[str]
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
```

**Benefits:**
- ✅ **Compile-time validation**: Catch type errors before runtime
- ✅ **Auto-generated docs**: Pydantic models document themselves
- ✅ **IDE support**: Full autocomplete and type checking
- ✅ **Canonical names**: `__main__.UserRequest` with aliases for flexibility

---

### 3. Visibility Controls (Zero-Trust Security)

**5 Visibility Types** for multi-tenant systems:

#### Public Visibility
```python
from flock.core.visibility import PublicVisibility

@flock_type
class PublicAnnouncement(BaseModel):
    message: str
    visibility: PublicVisibility = PublicVisibility()
# Any agent can consume this
```

#### Private Visibility
```python
from flock.core.visibility import PrivateVisibility

@flock_type
class PrivateNote(BaseModel):
    content: str
    visibility: PrivateVisibility = PrivateVisibility(producer_id="agent-123")
# Only the producer can consume this
```

#### Tenant Visibility
```python
from flock.core.visibility import TenantVisibility

@flock_type
class PatientData(BaseModel):
    patient_id: str
    diagnosis: str
    visibility: TenantVisibility = TenantVisibility(tenant_id="hospital-abc")
# Only agents with tenant_id="hospital-abc" can consume
```

#### Labelled Visibility
```python
from flock.core.visibility import LabelledVisibility

@flock_type
class InternalReport(BaseModel):
    data: dict
    visibility: LabelledVisibility = LabelledVisibility(required_labels={"clearance:secret", "dept:engineering"})
# Only agents with BOTH labels can consume
```

#### After Visibility
```python
from flock.core.visibility import AfterVisibility
from datetime import datetime, timedelta

@flock_type
class ScheduledMessage(BaseModel):
    content: str
    visibility: AfterVisibility = AfterVisibility(
        available_after=datetime.utcnow() + timedelta(hours=1)
    )
# Only visible after the specified timestamp
```

---

### 4. Persistent Blackboard Store

**SQLite-backed storage** with full audit trail:

```python
from flock.store import SQLiteBlackboardStore

store = SQLiteBlackboardStore(db_path=".flock/blackboard.db")

# Query artifacts by type
from flock.store import FilterConfig

artifacts = await store.query_artifacts(
    FilterConfig(
        type_names={"UserRequest"},
        tags={"priority:high"},
        start=datetime(2024, 1, 1),
        end=datetime(2024, 12, 31)
    ),
    limit=100
)

# Get consumption history
consumptions = await store.get_consumptions(artifact_id="artifact-123")
```

**Features:**
- ✅ Every artifact persisted with metadata
- ✅ Consumption tracking (who consumed what, when)
- ✅ Tag-based filtering
- ✅ Time-range queries
- ✅ Correlation ID tracking for request chains

---

### 5. Production Safety Features

#### Circuit Breakers
```python
from flock import Flock

flock = (
    Flock.builder()
    .with_agent(agent)
    .with_circuit_breaker(
        failure_threshold=5,
        timeout_seconds=30,
        half_open_after_seconds=60
    )
    .build()
)
```

#### Feedback Prevention
```python
agent = (
    flock.agent("analyzer")
    .consumes(Report)
    .publishes(Analysis)
    .prevents_feedback()  # Prevents consuming its own output
    .does(analyze)
)
```

#### Execution Limits
```python
await flock.run_until_idle(
    max_cycles=100,  # Prevent infinite loops
    timeout_seconds=300  # 5 minute timeout
)
```

---

### 6. AI-Queryable Telemetry (DuckDB + OpenTelemetry)

**DuckDB storage** for traces:

```python
# Dashboard SQL interface allows queries like:
SELECT
    service_name,
    span_name,
    AVG(duration_ns / 1000000) as avg_duration_ms,
    COUNT(*) as call_count
FROM spans
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY service_name, span_name
ORDER BY avg_duration_ms DESC
LIMIT 10;
```

**Features:**
- ✅ **10-100x faster than SQLite** for analytical queries
- ✅ **Jaeger-compatible traces** (OpenTelemetry)
- ✅ **SQL interface** in dashboard
- ✅ **AI-queryable**: LLMs can write queries to analyze system behavior

---

### 7. MCP (Model Context Protocol) Integration

**Extensible tool ecosystem:**

```python
# Use community MCP servers
flock.with_mcp_server(
    name="brave-search",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-brave-search"],
    env={"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY")}
)

# Or build your own
@flock_tool
async def custom_tool(param: str) -> str:
    """Custom tool implementation."""
    return f"Processed: {param}"
```

**Benefits:**
- ✅ Tools run in separate processes (better isolation)
- ✅ Language-agnostic (write tools in any language)
- ✅ Community ecosystem (growing library of MCP servers)
- ✅ Hot-reload support (update tools without restarting)

---

## Migration Guide

### Step-by-Step Migration

#### Step 1: Update Dependencies

```bash
# Uninstall old version
pip uninstall flock-core

# Install new version
pip install flock-core==0.5.0
```

#### Step 2: Convert Types

**Before:**
```python
class MyAgent(Agent):
    def __init__(self):
        self.input_signature = "query: str, max_results: int"
        self.output_signature = "results: List[str], confidence: float"
```

**After:**
```python
from flock import flock_type
from pydantic import BaseModel

@flock_type
class Query(BaseModel):
    query: str
    max_results: int = 10

@flock_type
class Results(BaseModel):
    results: list[str]
    confidence: float
```

#### Step 3: Convert Agents

**Before:**
```python
class MyAgent(Agent):
    async def execute(self, context: FlockContext) -> str:
        data = context.data
        result = await self.process(data)
        context.set_result(result)
        return "next_agent"
```

**After:**
```python
async def my_handler(input: Query) -> Results:
    result = await process(input)
    return Results(results=result, confidence=0.9)

agent = (
    flock.agent("my_agent")
    .consumes(Query)
    .publishes(Results)
    .does(my_handler)
)
```

#### Step 4: Remove Router Configuration

**Before:**
```python
router = Router()
router.add_route("agent1", "agent2", condition)
router.add_route("agent2", "agent3", condition)
```

**After:**
```python
# No router needed! Define agents with type contracts:

agent1 = flock.agent("agent1").consumes(TypeA).publishes(TypeB).does(handler1)
agent2 = flock.agent("agent2").consumes(TypeB).publishes(TypeC).does(handler2)
agent3 = flock.agent("agent3").consumes(TypeC).publishes(TypeD).does(handler3)

# Flow emerges from type relationships: TypeA → TypeB → TypeC → TypeD
```

#### Step 5: Update Execution

**Before:**
```python
context = FlockContext({"query": "search term"})
result = await flock.run(context, entry_agent="researcher")
findings = result.data.get("findings")
```

**After:**
```python
from flock.store import FilterConfig

# Publish input
await flock.publish(Query(query="search term"))

# Wait for completion
await flock.run_until_idle()

# Query results
artifacts = await flock.store.query_artifacts(
    FilterConfig(type_names={"Results"}),
    limit=1
)
results = artifacts[0].payload  # Results object
```

#### Step 6: Replace Modules with Tools

**Before:**
```python
class SearchModule(Module):
    async def search(self, query: str) -> list[str]:
        # Implementation
```

**After:**
```python
@flock_tool
async def search(query: str) -> list[str]:
    """Search the web."""
    # Same implementation
```

---

### Complete Example Migration

#### Flock 0.4: Research Assistant
```python
# research_assistant_04.py (Flock 0.4)
from flock import FlockFactory, Agent, FlockContext, Router, Module

class WebSearchModule(Module):
    async def search(self, query: str) -> list[str]:
        # Web search implementation
        return ["result1", "result2"]

class ResearchAgent(Agent):
    def __init__(self):
        super().__init__("researcher")
        self.input_signature = "query: str"
        self.output_signature = "findings: List[str]"

    async def execute(self, context: FlockContext) -> str:
        query = context.data["query"]
        search = context.get_module(WebSearchModule)
        findings = await search.search(query)
        context.set_result({"findings": findings})
        return "summarizer"

class SummarizerAgent(Agent):
    def __init__(self):
        super().__init__("summarizer")
        self.input_signature = "findings: List[str]"
        self.output_signature = "summary: str"

    async def execute(self, context: FlockContext) -> str:
        findings = context.data["findings"]
        summary = " | ".join(findings)
        context.set_result({"summary": summary})
        return "END"

# Setup
router = Router()
router.add_route("researcher", "summarizer", lambda ctx: "findings" in ctx.data)

flock = FlockFactory.create(
    agents=[ResearchAgent(), SummarizerAgent()],
    modules=[WebSearchModule()],
    router=router,
    entry_agent="researcher"
)

# Execute
context = FlockContext({"query": "AI trends"})
result = await flock.run(context)
print(result.data["summary"])
```

#### Flock 0.5: Research Assistant
```python
# research_assistant_05.py (Flock 0.5)
from flock import Flock, flock, flock_type, flock_tool
from pydantic import BaseModel

# Types
@flock_type
class Query(BaseModel):
    text: str

@flock_type
class Findings(BaseModel):
    results: list[str]

@flock_type
class Summary(BaseModel):
    text: str

# Tools
@flock_tool
async def web_search(query: str) -> list[str]:
    """Search the web."""
    # Same implementation
    return ["result1", "result2"]

# Agents
async def research_handler(query: Query, tools) -> Findings:
    results = await tools.web_search(query.text)
    return Findings(results=results)

async def summarize_handler(findings: Findings) -> Summary:
    summary = " | ".join(findings.results)
    return Summary(text=summary)

researcher = flock.agent("researcher").consumes(Query).publishes(Findings).does(research_handler)
summarizer = flock.agent("summarizer").consumes(Findings).publishes(Summary).does(summarize_handler)

# Setup
orchestrator = (
    Flock.builder()
    .with_agent(researcher)
    .with_agent(summarizer)
    .with_tool(web_search)
    .build()
)

# Execute
from flock.store import FilterConfig

await orchestrator.publish(Query(text="AI trends"))
await orchestrator.run_until_idle()

# Get results
summaries = await orchestrator.store.query_artifacts(
    FilterConfig(type_names={"Summary"}),
    limit=1
)
print(summaries[0].payload.text)
```

**Key Differences:**
1. ❌ No `FlockFactory`, `FlockContext`, `Router`
2. ✅ Pydantic types with `@flock_type`
3. ✅ Simple functions instead of Agent classes
4. ✅ Fluent builder pattern
5. ✅ Store queries instead of direct access
6. ✅ Type-driven flow (no router config)

---

## Performance Improvements

### Resource Usage

| Metric | Flock 0.4 | Flock 0.5 | Improvement |
|--------|-----------|-----------|-------------|
| **Install Size** | ~3.2 GB | ~650 MB | **80% reduction** |
| **Dependencies** | 47 packages | 23 packages | **51% reduction** |
| **PyTorch** | Required | **Removed** | ✅ |
| **Agent Handoff** | ~100-500ms | <1ms | **100-500x faster** |
| **Routing Complexity** | O(n²) | O(n) | **Linear scaling** |

### Why So Much Faster?

1. **No PyTorch**: Removed 2.5GB dependency not needed for orchestration
2. **No Temporal.io**: Event-driven coordination is lightweight
3. **Zero-copy messaging**: Artifacts stored once, referenced by ID
4. **Parallel execution**: All matching agents run concurrently
5. **DuckDB**: 10-100x faster than SQLite for analytical queries

### Benchmark: 10-Agent Pipeline

| Metric | Flock 0.4 | Flock 0.5 |
|--------|-----------|-----------|
| **Sequential execution** | 5.2s | 0.8s |
| **With parallelism** | 3.1s | 0.2s |
| **Memory usage** | 450 MB | 90 MB |

---

## Deprecations & Removals

### Removed Components

#### Temporal.io Integration
- **Reason**: Heavy dependency, not needed for event-driven coordination
- **Migration**: Use `flock.publish()` + `run_until_idle()`

#### PyTorch Dependency
- **Reason**: Only needed for embeddings, not core orchestration
- **Migration**: Use external MCP servers for embeddings if needed

#### Router Class
- **Reason**: Type system provides automatic routing
- **Migration**: Define type contracts with `.consumes()` and `.publishes()`

#### FlockContext
- **Reason**: Mutable state doesn't fit event-driven model
- **Migration**: Use immutable `Artifact` objects, query store for results

#### Agent Base Class
- **Reason**: Functions are simpler than classes for agent logic
- **Migration**: Use async functions with `.does(handler)`

#### Module System
- **Reason**: MCP provides better tool isolation
- **Migration**: Use `@flock_tool` or MCP servers

#### String Signatures
- **Reason**: No type safety, error-prone
- **Migration**: Use Pydantic models with `@flock_type`

---

## Known Limitations

### Beta Features

1. **SQLiteBlackboardStore**: Marked as beta, may have performance issues at scale
2. **Dashboard OAuth**: No authentication yet (local use only)
3. **Redis Backend**: Not yet implemented (roadmap item)

### Not Yet Supported

1. **Kafka/RabbitMQ Integration**: Planned for 1.0
2. **Kubernetes-Native Deployment**: Planned for 1.0
3. **Multi-Tenant Dashboard**: Single tenant only
4. **Advanced Analytics**: Basic metrics only
5. **RBAC**: No role-based access control yet

### Migration Challenges

1. **No Backward Compatibility**: Complete rewrite required
2. **Async Everywhere**: Must use async/await throughout
3. **Learning Curve**: New patterns take time to internalize
4. **Example Dependencies**: Most examples require API keys

---

## Upgrade Recommendations

### When to Upgrade

#### ✅ **Upgrade Immediately If:**
- Starting a new project
- Need parallel agent execution (10+ agents)
- Require type safety and compile-time validation
- Want production observability (dashboard, traces)
- Building multi-tenant systems (need visibility controls)
- Resource constraints (80% reduction in dependencies)

#### ⏳ **Wait for 1.0 If You Need:**
- Enterprise persistence (Redis, Kafka)
- Kubernetes-native deployment
- OAuth/RBAC for dashboard
- Multi-tenant SaaS features
- Proven 99.99% uptime

#### ⚠️ **Stay on 0.4 If:**
- Heavily invested in Temporal.io workflows
- Sequential execution sufficient
- Production system is stable
- Migration cost > benefits
- Team has no bandwidth for rewrite

### Migration Timeline

| System Size | Agents | Est. Time | Complexity |
|-------------|--------|-----------|------------|
| **Small** | 1-5 | 1-2 days | Low |
| **Medium** | 6-20 | 1 week | Medium |
| **Large** | 21-50 | 2-3 weeks | High |
| **Enterprise** | 50+ | 4+ weeks | Very High |

**Factors affecting timeline:**
- Complexity of router logic
- Number of custom modules
- Amount of FlockContext usage
- Test coverage requirements
- Team familiarity with async/Pydantic

---

## FAQ

### Q: Is there ANY backward compatibility?

**A:** No. Flock 0.5 is a complete architectural rewrite with zero shared code.

### Q: Why not call this Flock 2.0?

**A:** The team considers 0.5 a "production-ready core" but reserves 1.0 for enterprise features (Kafka, K8s, OAuth, Redis). This follows semantic versioning where 0.x.x allows API evolution.

### Q: Can I run 0.4 and 0.5 side by side?

**A:** Yes, but not recommended. They use different package names internally, but share the `flock` namespace. Use separate virtual environments.

### Q: Where's the migration tooling?

**A:** No automated migration tools exist (yet). The architectural differences are too fundamental for code transformation.

### Q: What about Temporal workflows?

**A:** Temporal is completely removed. If you need durable workflows, consider staying on 0.4 or using Temporal separately.

### Q: How stable is the API?

**A:** Core API is stable. Minor changes may occur before 1.0, but no more ground-up rewrites.

### Q: Will you maintain 0.4?

**A:** Critical bug fixes only. No new features. Focus is on 0.5 → 1.0.

---

## Resources

- **API Documentation**: [docs.flock.io](https://docs.flock.io)
- **Examples**: [`examples/`](../../examples/) directory (34+ working examples)
- **Migration Support**: [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions)
- **Roadmap**: [ROADMAP.md](./ROADMAP.md)
- **Changelog**: This document
- **Release Notes**: [GitHub Releases](https://github.com/whiteducksoftware/flock/releases)

---

## Acknowledgments

This release represents **months of research** into production agent systems, blackboard architecture patterns, and modern multi-agent frameworks.

**Special thanks to:**
- The Hearsay-II team (1970s) for pioneering blackboard architecture
- LangGraph, AutoGen, and CrewAI for inspiring the original 0.4
- The MCP team for creating an extensible tool ecosystem
- Our early adopters who helped shape 0.5 through feedback

**Philosophy shift:**
> "Workflow orchestration made sense when we thought of agents as steps in a pipeline. But agents are more like microservices—they should communicate through events, not hardcoded calls."

The future of agent systems is **decentralized, type-safe, and observable**. Flock 0.5 gets us there.

---

*Built with ❤️ by the Flock team*
