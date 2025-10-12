<p align="center">
  <img alt="Flock Banner" src="docs/assets/images/flock.png" width="800">
</p>
<p align="center">
  <a href="https://docs.flock.whiteduck.de" target="_blank"><img alt="Documentation" src="https://img.shields.io/badge/docs-online-blue?style=for-the-badge&logo=readthedocs"></a>
  <a href="https://pypi.org/project/flock-core/" target="_blank"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/flock-core?style=for-the-badge&logo=pypi&label=pip%20version"></a>
  <img alt="Python Version" src="https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python">
  <a href="LICENSE" target="_blank"><img alt="License" src="https://img.shields.io/pypi/l/flock-core?style=for-the-badge"></a>
  <a href="https://whiteduck.de" target="_blank"><img alt="Built by white duck" src="https://img.shields.io/badge/Built%20by-white%20duck%20GmbH-white?style=for-the-badge&labelColor=black"></a>
  <img alt="Test Coverage" src="https://img.shields.io/badge/coverage-77%25-green?style=for-the-badge">
  <img alt="Tests" src="https://img.shields.io/badge/tests-743%20passing-brightgreen?style=for-the-badge">
</p>

---

# Flock 0.5: Declarative Blackboard Multi-Agent Orchestration

> **Stop engineering prompts. Start declaring contracts.**

Flock is a production-focused framework for orchestrating AI agents through **declarative type contracts** and **blackboard architecture**—proven patterns from distributed systems, decades of experience with microservice architectures, and classical AI—now applied to modern LLMs.

**📖 [Read the full documentation →](https://docs.flock.whiteduck.de)**

**Quick links:**
- **[Getting Started](https://docs.flock.whiteduck.de/getting-started/installation/)** - Installation and first steps
- **[Tutorials](https://docs.flock.whiteduck.de/tutorials/)** - Step-by-step learning path
- **[User Guides](https://docs.flock.whiteduck.de/guides/)** - In-depth feature documentation
- **[API Reference](https://docs.flock.whiteduck.de/reference/api/)** - Complete API documentation
- **[Roadmap](https://docs.flock.whiteduck.de/about/roadmap/)** - What's coming in v1.0

---

## The Problem With Current Approaches

Building production multi-agent systems today means dealing with:

**🔥 Prompt Engineering Hell**
```python

prompt = """You are an expert code reviewer. When you receive code, you should...
[498 more lines of instructions that the LLM ignores half the time]"""

# 500-line prompt that breaks when models update

# How do I know that there isn't an even better prompt? (you don't)
# -> proving 'best possible performance' is impossible
```

**🧪 Testing Nightmares**
```python
# How do you unit test this?
result = llm.invoke(prompt)  # Hope for valid JSON
data = json.loads(result.content)  # Crashes in production
```

**📐 Rigid topology and tight coupling**
```python
# Want to add a new agent? Rewrite the entire graph.
workflow.add_edge("agent_a", "agent_b")
workflow.add_edge("agent_b", "agent_c")
# Add agent_d? Start rewiring...
```

**💀 Single point of failure: Orchestrator dies? Everything dies.**
```python
# Orchestrator dies? Everything dies.
```

**🧠 God object anti-pattern:**
```python
# One orchestrator needs domain knowledge of 20+ agents to route correctly
# Orchestrator 'guesses' next agent based on a natural language description.
# Not suitable for critical systems.
```

These aren't framework limitations, they're **architectural choices** that don't scale.

These challenges are solvable—decades of experience with microservices have taught us hard lessons about decoupling, orchestration, and reliability. Let's apply those lessons!

---

## The Flock Approach

Flock takes a different path, combining two proven patterns:

### 1. Declarative Type Contracts (Not Prompts)

**Traditional approach:**
```python
prompt = """You are an expert software engineer and bug analyst. Your task is to analyze bug reports and provide structured diagnostic information.

INSTRUCTIONS:
1. Read the bug report carefully
2. Determine the severity level (must be exactly one of: Critical, High, Medium, Low)
3. Classify the bug category (e.g., "performance", "security", "UI", "data corruption")
4. Formulate a root cause hypothesis (minimum 50 characters)
5. Assign a confidence score between 0.0 and 1.0

OUTPUT FORMAT:
You MUST return valid JSON with this exact structure:
{
  "severity": "string (Critical|High|Medium|Low)",
  "category": "string",
  "root_cause_hypothesis": "string (minimum 50 characters)",
  "confidence_score": "number (0.0 to 1.0)"
}

VALIDATION RULES:
- severity: Must be exactly one of: Critical, High, Medium, Low (case-sensitive)
- category: Must be a single word or short phrase describing the bug type
- root_cause_hypothesis: Must be at least 50 characters long and explain the likely cause
- confidence_score: Must be a decimal number between 0.0 and 1.0 inclusive

EXAMPLES:
Input: "App crashes when user clicks submit button"
Output: {"severity": "Critical", "category": "crash", "root_cause_hypothesis": "Null pointer exception in form validation logic when required fields are empty", "confidence_score": 0.85}

Input: "Login button has wrong color"
Output: {"severity": "Low", "category": "UI", "root_cause_hypothesis": "CSS class override not applied correctly in the theme configuration", "confidence_score": 0.9}

IMPORTANT:
- Do NOT include any explanatory text before or after the JSON
- Do NOT use markdown code blocks (no ```json```)
- Do NOT add comments in the JSON
- Ensure the JSON is valid and parseable
- If you cannot determine something, use your best judgment
- Never return null values

Now analyze this bug report:
{bug_report_text}"""

result = llm.invoke(prompt)  # 500-line prompt that breaks when models update
# Then parse and hope it's valid JSON
data = json.loads(result.content)  # Crashes in production 🔥
```

**The Flock way:**
```python
@flock_type
class BugDiagnosis(BaseModel):
    severity: str = Field(pattern="^(Critical|High|Medium|Low)$")
    category: str = Field(description="Bug category")
    root_cause_hypothesis: str = Field(min_length=50)
    confidence_score: float = Field(ge=0.0, le=1.0)

# The schema IS the instruction. No 500-line prompt needed.
agent.consumes(BugReport).publishes(BugDiagnosis)
```

<p align="center">
  <img alt="Flock Banner" src="docs/assets/images/bug_diagnosis.png" width="1000">
</p>

**Why this matters:**
- ✅ **Survives model upgrades** - GPT-6 will still understand Pydantic schemas
- ✅ **Runtime validation** - Errors caught at parse time, not in production
- ✅ **Testable** - Mock inputs/outputs with concrete types
- ✅ **Self-documenting** - The code tells you what agents do

### 2. Blackboard Architecture (Not Directed Graphs)

**Graph-based approach:**
```python
# Explicit workflow with hardcoded edges
workflow.add_edge("radiologist", "diagnostician")
workflow.add_edge("lab_tech", "diagnostician")
# Add performance_analyzer? Rewrite the graph.
```

**The Flock way (blackboard):**
```python
# Agents subscribe to types, workflows emerge
radiologist = flock.agent("radiologist").consumes(Scan).publishes(XRayAnalysis)
lab_tech = flock.agent("lab_tech").consumes(Scan).publishes(LabResults)
diagnostician = flock.agent("diagnostician").consumes(XRayAnalysis, LabResults).publishes(Diagnosis)

# Add performance_analyzer? Just subscribe it:
performance = flock.agent("perf").consumes(Scan).publishes(PerfAnalysis)
# Done. No graph rewiring. Diagnostician can optionally consume it.
```

**What just happened:**
- ✅ **Parallel execution** - Radiologist and lab_tech run concurrently (automatic)
- ✅ **Dependency resolution** - Diagnostician waits for both inputs (automatic)
- ✅ **Loose coupling** - Agents don't know about each other, just data types
- ✅ **Scalable** - O(n) complexity, not O(n²) edges

**This is not a new idea.** Blackboard architecture has powered groundbreaking AI systems since the 1970s (Hearsay-II, HASP/SIAP, BB1). We're applying proven patterns to modern LLMs.

---

## Quick Start (60 Seconds)

```bash
pip install flock-core
export OPENAI_API_KEY="sk-..."
# Optional: export DEFAULT_MODEL (falls back to hard-coded default if unset)
export DEFAULT_MODEL="openai/gpt-4.1"
```

```python
import os
import asyncio
from pydantic import BaseModel, Field
from flock import Flock, flock_type

# 1. Define typed artifacts
@flock_type
class CodeSubmission(BaseModel):
    code: str
    language: str

@flock_type
class BugAnalysis(BaseModel):
    bugs_found: list[str]
    severity: str = Field(pattern="^(Critical|High|Medium|Low|None)$")
    confidence: float = Field(ge=0.0, le=1.0)

@flock_type
class SecurityAnalysis(BaseModel):
    vulnerabilities: list[str]
    risk_level: str = Field(pattern="^(Critical|High|Medium|Low|None)$")

@flock_type
class FinalReview(BaseModel):
    overall_assessment: str = Field(pattern="^(Approve|Approve with Changes|Reject)$")
    action_items: list[str]

# 2. Create the blackboard
flock = Flock(os.getenv("DEFAULT_MODEL", "openai/gpt-4.1"))

# 3. Agents subscribe to types (NO graph wiring!)
bug_detector = flock.agent("bug_detector").consumes(CodeSubmission).publishes(BugAnalysis)
security_auditor = flock.agent("security_auditor").consumes(CodeSubmission).publishes(SecurityAnalysis)

# This agent AUTOMATICALLY waits for both analyses
final_reviewer = flock.agent("final_reviewer").consumes(BugAnalysis, SecurityAnalysis).publishes(FinalReview)

# 4. Run with real-time dashboard
async def main():
    await flock.serve(dashboard=True)

asyncio.run(main())
```

**What happened:**
- Bug detector and security auditor ran **in parallel** (both consume CodeSubmission)
- Final reviewer **automatically waited** for both
- **Zero prompts written** - types defined the behavior
- **Zero graph edges** - subscriptions created the workflow
- **Full type safety** - Pydantic validates all outputs

---

## Persistent Blackboard History

The in-memory store is still great for local tinkering, but production teams now have a durable option. Plugging in `SQLiteBlackboardStore` turns the blackboard into a persistent event log with first-class ergonomics:

- **Long-lived artifacts** — every field (payload, tags, partition keys, visibility) is stored for replay, audits, and postmortems
- **Historical APIs** — `/api/v1/artifacts`, `/summary`, and `/agents/{agent_id}/history-summary` expose pagination, filtering, and consumption counts
- **Dashboard module** — the new **Historical Blackboard** experience preloads persisted history, enriches the graph with consumer metadata, and highlights retention windows
- **Operational tooling** — CLI helpers (`init-sqlite-store`, `sqlite-maintenance --delete-before ... --vacuum`) make schema setup and retention policies scriptable

Quick start:

```python
from flock import Flock
from flock.store import SQLiteBlackboardStore

store = SQLiteBlackboardStore(".flock/blackboard.db")
await store.ensure_schema()
flock = Flock("openai/gpt-4.1", store=store)
```

Run `examples/02-the-blackboard/01_persistent_pizza.py` to generate history, then launch `examples/03-the-dashboard/04_persistent_pizza_dashboard.py` and explore previous runs, consumption trails, and retention banners inside the dashboard.

---

## Core Concepts

### Typed Artifacts (The Vocabulary)

Every piece of data on the blackboard is a validated Pydantic model:

```python
@flock_type
class PatientDiagnosis(BaseModel):
    condition: str = Field(min_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_treatment: list[str] = Field(min_length=1)
    follow_up_required: bool
```

**Benefits:**
- Runtime validation ensures quality
- Field constraints prevent bad outputs
- Self-documenting data structures
- Version-safe (types survive model updates)

### Agent Subscriptions (The Rules)

Agents declare what they consume and produce:

```python
analyzer = (
    flock.agent("analyzer")
    .description("Analyzes patient scans")  # Optional: improves multi-agent coordination
    .consumes(PatientScan)                   # What triggers this agent
    .publishes(PatientDiagnosis)             # What it produces
)
```

**Advanced subscriptions:**

```python
# Conditional consumption - only high-severity cases
urgent_care = flock.agent("urgent").consumes(
    Diagnosis,
    where=lambda d: d.severity in ["Critical", "High"]
)

# Batch processing - wait for 10 items
batch_processor = flock.agent("batch").consumes(
    Event,
    batch=BatchSpec(size=10, timeout=timedelta(seconds=30))
)

# Join operations - wait for multiple types within time window
correlator = flock.agent("correlator").consumes(
    SignalA,
    SignalB,
    join=JoinSpec(within=timedelta(minutes=5))
)
```

### Visibility Controls (The Security)

**Unlike other frameworks, Flock has zero-trust security built-in:**

```python
# Multi-tenancy (SaaS isolation)
agent.publishes(CustomerData, visibility=TenantVisibility(tenant_id="customer_123"))

# Explicit allowlist (HIPAA compliance)
agent.publishes(MedicalRecord, visibility=PrivateVisibility(agents={"physician", "nurse"}))

# Role-based access control
agent.identity(AgentIdentity(name="analyst", labels={"clearance:secret"}))
agent.publishes(IntelReport, visibility=LabelledVisibility(required_labels={"clearance:secret"}))

# Time-delayed release (embargo periods)
artifact.visibility = AfterVisibility(ttl=timedelta(hours=24), then=PublicVisibility())

# Public (default)
agent.publishes(PublicReport, visibility=PublicVisibility())
```

**Why this matters:** Financial services, healthcare, defense, SaaS platforms all need this for compliance. Other frameworks make you build it yourself.

### Batching Pattern: Parallel Execution Control

**A key differentiator:** The separation of `publish()` and `run_until_idle()` enables parallel execution.

```python
# ✅ EFFICIENT: Batch publish, then run in parallel
for review in customer_reviews:
    await flock.publish(review)  # Just scheduling work

await flock.run_until_idle()  # All sentiment_analyzer agents run concurrently!

# Get all results
analyses = await flock.store.get_by_type(SentimentAnalysis)
# 100 analyses completed in ~1x single review processing time!
```

**Why this separation matters:**
- ⚡ **Parallel execution** - Process 100 customer reviews concurrently
- 🎯 **Batch control** - Publish multiple artifacts, execute once
- 🔄 **Multi-type workflows** - Publish different types, trigger different agents in parallel
- 📊 **Better performance** - Process 1000 items in the time it takes to process 1

**Comparison to other patterns:**
```python
# ❌ If run_until_idle() was automatic (like most frameworks):
for review in customer_reviews:
    await flock.publish(review)  # Would wait for completion each time!
# Total time: 100x single execution (sequential)

# ✅ With explicit batching:
for review in customer_reviews:
    await flock.publish(review)  # Fast: just queuing
await flock.run_until_idle()
# Total time: ~1x single execution (parallel)
```

### Production Safety Features

**Built-in safeguards prevent common production failures:**

```python
# Circuit breakers prevent runaway costs
flock = Flock("openai/gpt-4.1", max_agent_iterations=1000)

# Feedback loop protection
critic = (
    flock.agent("critic")
    .consumes(Essay)
    .publishes(Critique)
    .prevent_self_trigger(True)  # Won't trigger itself infinitely
)

# Best-of-N execution (run 5x, pick best)
agent.best_of(5, score=lambda result: result.metrics["confidence"])

# Configuration validation
agent.best_of(150, ...)  # ⚠️ Warns: "best_of(150) is very high - high LLM costs"
```

---

## Production-Ready Observability

### Real-Time Dashboard

**Start the dashboard with one line:**

```python
await flock.serve(dashboard=True)
```

The dashboard provides comprehensive real-time visibility into your agent system with professional UI/UX:

<p align="center">
  <img alt="Flock Agent View" src="docs/assets/images/flock_ui_agent_view.png" width="1000">
  <i>Agent View: See agent communication patterns and message flows in real-time</i>
</p>

**Key Features:**

- **Dual Visualization Modes:**
  - **Agent View** - Agents as nodes with message flows as edges
  - **Blackboard View** - Messages as nodes with data transformations as edges

<p align="center">
  <img alt="Flock Blackboard View" src="docs/assets/images/flock_ui_blackboard_view.png" width="1000">
  <i>Blackboard View: Track data lineage and transformations across the system</i>
</p>

- **Real-Time Updates:**
  - WebSocket streaming with 2-minute heartbeat
  - Live agent activation and message publication
  - Auto-layout with Dagre algorithm

- **Interactive Graph:**
  - Drag nodes, zoom, pan, and explore topology
  - Double-click nodes to open detail windows
  - Right-click for context menu with auto-layout options:
    - **5 Layout Algorithms**: Hierarchical (Vertical/Horizontal), Circular, Grid, and Random
    - **Smart Spacing**: Dynamic 200px minimum clearance based on node dimensions
    - **Viewport Centering**: Layouts always center around current viewport
  - Add modules dynamically from context menu

- **Advanced Filtering:**
  - Correlation ID tracking for workflow tracing
  - Time range filtering (last 5/10/60 minutes or custom)
  - Active filter pills with one-click removal
  - Autocomplete search with metadata preview

- **Control Panel:**
  - Publish artifacts from the UI
  - Invoke agents manually
  - Monitor system health

- **Keyboard Shortcuts:**
  - `Ctrl+M` - Toggle view mode
  - `Ctrl+F` - Focus filter
  - `Ctrl+/` - Show shortcuts help
  - WCAG 2.1 AA compliant accessibility

### Production-Grade Trace Viewer

The dashboard includes a **Jaeger-style trace viewer** with 7 powerful visualization modes:

<p align="center">
  <img alt="Trace Viewer" src="docs/assets/images/trace_1.png" width="1000">
  <i>Trace Viewer: Timeline view showing span hierarchies and execution flow</i>
</p>

**7 Trace Viewer Modes:**

1. **Timeline** - Waterfall visualization with parent-child relationships
2. **Statistics** - Sortable table view with durations and error tracking
3. **RED Metrics** - Rate, Errors, Duration monitoring for service health
4. **Dependencies** - Service-to-service communication analysis
5. **DuckDB SQL** - Interactive SQL query editor with CSV export
6. **Configuration** - Real-time service/operation filtering
7. **Guide** - Built-in documentation and query examples

**Additional Features:**

- **Full I/O Capture** - Complete input/output data for every operation
- **JSON Viewer** - Collapsible tree structure with expand all/collapse all
- **Multi-Trace Support** - Open and compare multiple traces simultaneously
- **Smart Sorting** - Sort by date, span count, or duration
- **CSV Export** - Download query results for offline analysis

<p align="center">
  <img alt="Trace Viewer" src="docs/assets/images/trace_2.png" width="1000">
  <i>Trace Viewer: Dependency Analysis</i>
</p>


### OpenTelemetry + DuckDB Tracing

**One environment variable enables comprehensive tracing:**

```bash
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true

python your_app.py
# Traces stored in .flock/traces.duckdb
```

**AI-queryable debugging:**

```python
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)

# Find bottlenecks
slow_ops = conn.execute("""
    SELECT name, AVG(duration_ms) as avg_ms, COUNT(*) as count
    FROM spans
    WHERE duration_ms > 1000
    GROUP BY name
    ORDER BY avg_ms DESC
""").fetchall()

# Find errors with full context
errors = conn.execute("""
    SELECT name, status_description,
           json_extract(attributes, '$.input') as input,
           json_extract(attributes, '$.output') as output
    FROM spans
    WHERE status_code = 'ERROR'
""").fetchall()
```

**Real debugging session:**
```
You: "My pizza agent is slow"
AI: [queries DuckDB]
    "DSPyEngine.evaluate takes 23s on average.
     Input size: 50KB of conversation history.
     Recommendation: Limit context to last 5 messages."
```

**Why DuckDB?** 10-100x faster than SQLite for analytical queries. Zero configuration. AI agents can debug your AI agents.

<p align="center">
  <img alt="Trace Viewer" src="docs/assets/images/trace_3.png" width="1000">
  <i>Trace Viewer: DuckDB Query</i>
</p>

---

## Framework Comparison

### Architectural Differences

Flock uses a fundamentally different coordination pattern than most multi-agent frameworks:

| Dimension | Graph-Based Frameworks | Chat-Based Frameworks | Flock (Blackboard) |
|-----------|------------------------|----------------------|-------------------|
| **Core Pattern** | Directed graph with explicit edges | Round-robin conversation | Blackboard subscriptions |
| **Coordination** | Manual edge wiring | Message passing | Type-based subscriptions |
| **Parallelism** | Manual (split/join nodes) | Sequential turn-taking | Automatic (concurrent consumers) |
| **Type Safety** | Varies (often TypedDict) | Text-based messages | Pydantic + runtime validation |
| **Coupling** | Tight (hardcoded successors) | Medium (conversation context) | Loose (type subscriptions only) |
| **Adding Agents** | Rewrite graph topology | Update conversation flow | Just subscribe to types |
| **Testing** | Requires full graph | Requires full group | Individual agent isolation |
| **Security Model** | DIY implementation | DIY implementation | Built-in (5 visibility types) |
| **Scalability** | O(n²) edge complexity | Limited by turn-taking | O(n) subscription complexity |

### When Flock Wins

**✅ Use Flock when you need:**

- **Parallel agent execution** - Agents consuming the same type run concurrently automatically
- **Type-safe outputs** - Pydantic validation catches errors at runtime
- **Minimal prompt engineering** - Schemas define behavior, not natural language
- **Dynamic agent addition** - Subscribe new agents without rewiring existing workflows
- **Testing in isolation** - Unit test individual agents with mock inputs
- **Built-in security** - 5 visibility types for compliance (HIPAA, SOC2, multi-tenancy)
- **10+ agents** - Linear complexity stays manageable at scale

### When Alternatives Win

**⚠️ Consider graph-based frameworks when:**
- You need extensive ecosystem integration with existing tools
- Your workflow is inherently sequential (no parallelism needed)
- You want battle-tested maturity (larger communities, more documentation)
- Your team has existing expertise with those frameworks

**⚠️ Consider chat-based frameworks when:**
- You prefer conversation-based development patterns
- Your use case maps naturally to turn-taking dialogue
- You need features specific to those ecosystems

### Honest Trade-offs

**You trade:**
- Ecosystem maturity (established frameworks have larger communities)
- Extensive documentation (we're catching up)
- Battle-tested age (newer architecture means less production history)

**You gain:**
- Better scalability (O(n) vs O(n²) complexity)
- Type safety (runtime validation vs hope)
- Cleaner architecture (loose coupling vs tight graphs)
- Production safety (circuit breakers, feedback prevention built-in)
- Security model (5 visibility types vs DIY)

**Different frameworks for different priorities. Choose based on what matters to your team.**

---

## Production Readiness

### What Works Today (v0.5.0)

**✅ Production-ready core:**
- More than 700 tests, with >75% coverage (>90% on critical paths)
- Blackboard orchestrator with typed artifacts
- Parallel + sequential execution (automatic)
- Zero-trust security (5 visibility types)
- Circuit breakers and feedback loop prevention
- OpenTelemetry distributed tracing with DuckDB storage
- Real-time dashboard with 7-mode trace viewer
- MCP integration (Model Context Protocol)
- Best-of-N execution, batch processing, join operations
- Type-safe retrieval API (`get_by_type()`)

**⚠️ What's missing for large-scale production:**
- **Advanced retry logic** - Basic only (exponential backoff planned)
- **Event replay** - No Kafka integration yet
- **Kubernetes-native deployment** - No Helm chart yet
- **OAuth/RBAC** - Dashboard has no auth

**✅ Available today:**
- **Persistent blackboard** - SQLiteBlackboardStore (see above)

All missing features planned for v1.0

### Recommended Use Cases Today

**✅ Good fit right now:**
- **Startups/MVPs** - Fast iteration, type safety, built-in observability
- **Internal tools** - Where in-memory blackboard is acceptable
- **Research/prototyping** - Rapid experimentation with clean architecture
- **Medium-scale systems** (10-50 agents, 1000s of artifacts)

**⚠️ Wait for 1.0 if you need:**
- **Enterprise persistence** (multi-region, high availability)
- **Compliance auditing** (immutable event logs)
- **Multi-tenancy SaaS** (with OAuth/SSO)
- **Mission-critical systems** with 99.99% uptime requirements

**Flock 0.5.0 is production-ready for the right use cases. Know your requirements.**

---

## Roadmap to 1.0

We're building enterprise infrastructure for AI agents and tracking the work publicly. Check [ROADMAP.md](ROADMAP.md) for deep dives and status updates.

### 0.5.0 Beta (In Flight)
- **Core data & governance:** [#271](https://github.com/whiteducksoftware/flock/issues/271), [#274](https://github.com/whiteducksoftware/flock/issues/274), [#273](https://github.com/whiteducksoftware/flock/issues/273), [#281](https://github.com/whiteducksoftware/flock/issues/281)
- **Execution patterns & scheduling:** [#282](https://github.com/whiteducksoftware/flock/issues/282), [#283](https://github.com/whiteducksoftware/flock/issues/283)
- **REST access & integrations:** [#286](https://github.com/whiteducksoftware/flock/issues/286), [#287](https://github.com/whiteducksoftware/flock/issues/287), [#288](https://github.com/whiteducksoftware/flock/issues/288), [#289](https://github.com/whiteducksoftware/flock/issues/289), [#290](https://github.com/whiteducksoftware/flock/issues/290), [#291](https://github.com/whiteducksoftware/flock/issues/291), [#292](https://github.com/whiteducksoftware/flock/issues/292), [#293](https://github.com/whiteducksoftware/flock/issues/293)
- **Docs & onboarding:** [#270](https://github.com/whiteducksoftware/flock/issues/270), [#269](https://github.com/whiteducksoftware/flock/issues/269)

### 1.0 Release Goals (Target Q4 2025)
- **Reliability & operations:** [#277](https://github.com/whiteducksoftware/flock/issues/277), [#278](https://github.com/whiteducksoftware/flock/issues/278), [#279](https://github.com/whiteducksoftware/flock/issues/279), [#294](https://github.com/whiteducksoftware/flock/issues/294)
- **Platform validation & quality:** [#275](https://github.com/whiteducksoftware/flock/issues/275), [#276](https://github.com/whiteducksoftware/flock/issues/276), [#284](https://github.com/whiteducksoftware/flock/issues/284), [#285](https://github.com/whiteducksoftware/flock/issues/285)
- **Security & access:** [#280](https://github.com/whiteducksoftware/flock/issues/280)

---

## Example: Multi-Modal Clinical Decision Support

```python
import os
from flock import Flock, flock_type
from flock.visibility import PrivateVisibility, TenantVisibility, LabelledVisibility
from flock.identity import AgentIdentity
from pydantic import BaseModel

@flock_type
class PatientScan(BaseModel):
    patient_id: str
    scan_type: str
    image_data: bytes

@flock_type
class XRayAnalysis(BaseModel):
    findings: list[str]
    confidence: float

@flock_type
class LabResults(BaseModel):
    markers: dict[str, float]

@flock_type
class Diagnosis(BaseModel):
    condition: str
    reasoning: str
    confidence: float

# Create HIPAA-compliant blackboard
flock = Flock(os.getenv("DEFAULT_MODEL", "openai/gpt-4.1"))

# Radiologist with privacy controls
radiologist = (
    flock.agent("radiologist")
    .consumes(PatientScan)
    .publishes(
        XRayAnalysis,
        visibility=PrivateVisibility(agents={"diagnostician"})  # HIPAA!
    )
)

# Lab tech with multi-tenancy
lab_tech = (
    flock.agent("lab_tech")
    .consumes(PatientScan)
    .publishes(
        LabResults,
        visibility=TenantVisibility(tenant_id="patient_123")  # Isolation!
    )
)

# Diagnostician with explicit access
diagnostician = (
    flock.agent("diagnostician")
    .identity(AgentIdentity(name="diagnostician", labels={"role:physician"}))
    .consumes(XRayAnalysis, LabResults)  # Waits for BOTH
    .publishes(
        Diagnosis,
        visibility=LabelledVisibility(required_labels={"role:physician"})
    )
)

# Run with tracing
async with flock.traced_run("patient_123_diagnosis"):
    await flock.publish(PatientScan(patient_id="123", ...))
    await flock.run_until_idle()

    # Get diagnosis (type-safe retrieval)
    diagnoses = await flock.store.get_by_type(Diagnosis)
    # Returns list[Diagnosis] directly - no .data access, no casting
```

**What this demonstrates:**
- Multi-modal data fusion (images + labs + history)
- Built-in access controls (HIPAA compliance)
- Parallel agent execution (radiology + labs run concurrently)
- Automatic dependency resolution (diagnostician waits for both)
- Full audit trail (traced_run + DuckDB storage)
- Type-safe data retrieval (no Artifact wrappers)

---

## Production Use Cases

Flock's architecture shines in production scenarios requiring parallel execution, security, and observability. Here are common patterns:

### Financial Services: Multi-Signal Trading

**The Challenge:** Analyze multiple market signals in parallel, correlate them within time windows, maintain SEC-compliant audit trails.

**The Solution:** 20+ signal analyzers run concurrently, join operations correlate signals, DuckDB provides complete audit trails.

```python
# Parallel signal analyzers
volatility = flock.agent("volatility").consumes(MarketData).publishes(VolatilityAlert)
sentiment = flock.agent("sentiment").consumes(NewsArticle).publishes(SentimentAlert)

# Trade execution waits for CORRELATED signals (within 5min window)
trader = flock.agent("trader").consumes(
    VolatilityAlert, SentimentAlert,
    join=JoinSpec(within=timedelta(minutes=5))
).publishes(TradeOrder)
```

### Healthcare: HIPAA-Compliant Diagnostics

**The Challenge:** Multi-modal data fusion with strict access controls, complete audit trails, zero-trust security.

**The Solution:** Built-in visibility controls for HIPAA compliance, automatic parallel execution, full data lineage tracking.

```python
# Privacy controls built-in
radiology.publishes(XRayAnalysis, visibility=PrivateVisibility(agents={"diagnostician"}))
lab.publishes(LabResults, visibility=TenantVisibility(tenant_id="patient_123"))

# Diagnostician waits for BOTH inputs with role-based access
diagnostician = flock.agent("diagnostician").consumes(XRayAnalysis, LabResults).publishes(Diagnosis)
```

### E-Commerce: 50-Agent Personalization

**The Challenge:** Analyze dozens of independent signals, support dynamic signal addition, process millions of events daily.

**The Solution:** O(n) scaling to 50+ analyzers, batch processing for efficiency, zero graph rewiring when adding signals.

```python
# 50+ signal analyzers (all run in parallel!)
for signal in ["browsing", "purchase", "cart", "reviews", "email", "social"]:
    flock.agent(f"{signal}_analyzer").consumes(UserEvent).publishes(Signal)

# Recommender batches signals for efficient LLM calls
recommender = flock.agent("recommender").consumes(Signal, batch=BatchSpec(size=50))
```

### Multi-Tenant SaaS: Content Moderation

**The Challenge:** Complete data isolation between tenants, multi-agent consensus, full audit trails.

**The Solution:** Tenant visibility ensures zero cross-tenant leakage, parallel checks provide diverse signals, traces show complete reasoning.

**See [USECASES.md](USECASES.md) for complete code examples and production metrics.**

---

## Getting Started

```bash
# Install
pip install flock-core

# Set API key
export OPENAI_API_KEY="sk-..."

# Try the examples
git clone https://github.com/whiteducksoftware/flock-flow.git
cd flock-flow

# CLI examples with detailed output
uv run python examples/01-cli/01_declarative_pizza.py

# Dashboard examples with visualization
uv run python examples/02-dashboard/01_declarative_pizza.py
```

**Learn by doing:**
- 📚 [Examples README](examples/README.md) - 12-step learning path from basics to advanced
- 🖥️ [CLI Examples](examples/01-cli/) - Detailed console output examples (01-12)
- 📊 [Dashboard Examples](examples/02-dashboard/) - Interactive visualization examples (01-12)
- 📖 [Documentation](https://docs.flock.whiteduck.de) - Complete online documentation
- 📘 [AGENTS.md](AGENTS.md) - Development guide

---

## Contributing

We're building Flock in the open. See **[Contributing Guide](https://docs.flock.whiteduck.de/about/contributing/)** for development setup, or check [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) locally.

**We welcome:**
- Bug reports and feature requests
- Documentation improvements
- Example contributions
- Architecture discussions

**Quality standards:**
- All tests must pass
- Coverage requirements met
- Code formatted with Ruff

---

## Why "0.5"?

We're calling this 0.5 to signal:

1. **Core is production-ready** - real-world client deployments, comprehensive features
2. **Ecosystem is evolving** - Documentation growing, community building, features maturing
3. **Architecture is proven** - Blackboard pattern is 50+ years old, declarative contracts are sound
4. **Enterprise features are coming** - Persistence, auth, Kubernetes deployment in roadmap

**1.0 will arrive** when we've delivered persistence, advanced error handling, and enterprise deployment patterns (targeting Q4 2025).

---

## The Bottom Line

**Flock is different because it makes different architectural choices:**

**Instead of:**
- ❌ Prompt engineering → ✅ Declarative type contracts
- ❌ Workflow graphs → ✅ Blackboard subscriptions
- ❌ Manual parallelization → ✅ Automatic concurrent execution
- ❌ Bolt-on security → ✅ Zero-trust visibility controls
- ❌ Hope-based debugging → ✅ AI-queryable distributed traces

**These aren't marketing slogans. They're architectural decisions with real tradeoffs.**

**You trade:**
- Ecosystem maturity (established frameworks have larger communities)
- Extensive documentation (we're catching up)
- Battle-tested age (newer architecture means less production history)

**You gain:**
- Better scalability (O(n) vs O(n²) complexity)
- Type safety (runtime validation vs hope)
- Cleaner architecture (loose coupling vs tight graphs)
- Production safety (circuit breakers, feedback prevention built-in)
- Security model (5 visibility types vs DIY)

**Different frameworks for different priorities. Choose based on what matters to your team.**

---

<div align="center">

**Built with ❤️ by white duck GmbH**

**"Declarative contracts eliminate prompt hell. Blackboard architecture eliminates graph spaghetti. Proven patterns applied to modern LLMs."**

[⭐ Star on GitHub](https://github.com/whiteducksoftware/flock-flow) | [📖 Documentation](https://docs.flock.whiteduck.de) | [🚀 Try Examples](examples/) | [💼 Enterprise Support](mailto:support@whiteduck.de)

</div>

---

**Last Updated:** October 13, 2025
**Version:** Flock 0.5.0 (Blackboard Edition)
**Status:** Production-Ready Core, Enterprise Features Roadmapped
