<p align="center">
  <img alt="Flock Banner" src="docs/assets/images/flock.png" width="800">
</p>
<p align="center">
  <a href="https://whiteducksoftware.github.io/flock/" target="_blank"><img alt="Documentation" src="https://img.shields.io/badge/docs-online-blue?style=for-the-badge&logo=readthedocs"></a>
  <a href="https://pypi.org/project/flock-core/" target="_blank"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/flock-core?style=for-the-badge&logo=pypi&label=pip%20version"></a>
  <img alt="Python Version" src="https://img.shields.io/badge/python-3.12%2B-blue?style=for-the-badge&logo=python">
  <a href="LICENSE" target="_blank"><img alt="License" src="https://img.shields.io/github/license/whiteducksoftware/flock?style=for-the-badge"></a>
  <a href="https://whiteduck.de" target="_blank"><img alt="Built by white duck" src="https://img.shields.io/badge/Built%20by-white%20duck%20GmbH-white?style=for-the-badge&labelColor=black"></a>
  <a href="https://codecov.io/gh/whiteducksoftware/flock" target="_blank"><img alt="Test Coverage" src="https://codecov.io/gh/whiteducksoftware/flock/branch/main/graph/badge.svg?token=YOUR_TOKEN_HERE&style=for-the-badge"></a>
  <img alt="Tests" src="https://img.shields.io/badge/tests-1400+-brightgreen?style=for-the-badge">
</p>

---

# Flock 0.5: Declarative Blackboard Multi-Agent Orchestration

> **Stop engineering prompts. Start declaring contracts.**

Flock is a production-focused framework for orchestrating AI agents through **declarative type contracts** and **blackboard architecture**—proven patterns from distributed systems, decades of microservice experience, and classical AI—now applied to modern LLMs.

**📖 [Read the full documentation →](https://whiteducksoftware.github.io/flock)**

**Quick links:**
- **[Getting Started](https://whiteducksoftware.github.io/flock/getting-started/installation/)** - Installation and first steps
- **[Tutorials](https://whiteducksoftware.github.io/flock/tutorials/)** - Step-by-step learning path
- **[User Guides](https://whiteducksoftware.github.io/flock/guides/)** - In-depth feature documentation
- **[API Reference](https://whiteducksoftware.github.io/flock/reference/api/)** - Complete API documentation
- **[Roadmap](https://whiteducksoftware.github.io/flock/about/roadmap/)** - What's coming in v1.0
- **[Changelog](https://whiteducksoftware.github.io/flock/about/changelog/)** - Recent new features and version history

---

## The Problem With Current Approaches

Building production multi-agent systems today means dealing with:

**🔥 Prompt Engineering Hell**
```python
prompt = """You are an expert code reviewer. When you receive code, you should...
[498 more lines of instructions that the LLM ignores half the time]"""

# 500-line prompt that breaks when models update
# How do I know this is the best prompt? (you don't)
# Proving 'best possible performance' is impossible
```

**🧪 Testing Nightmares**
```python
# How do you unit test this?
result = llm.invoke(prompt)  # Hope for valid JSON
data = json.loads(result.content)  # Crashes in production
```

**📐 Rigid Topology & Tight Coupling**
```python
# Want to add a new agent? Rewrite the entire graph.
workflow.add_edge("agent_a", "agent_b")
workflow.add_edge("agent_b", "agent_c")
# Add agent_d? Start rewiring...
```

**💀 Single Point of Failure**
```python
# Orchestrator dies? Everything dies.
```

**🧠 God Object Anti-Pattern**
```python
# One orchestrator needs domain knowledge of 20+ agents to route correctly
# Orchestrator 'guesses' next agent based on natural language
# Not suitable for critical systems
```

These aren't framework limitations—they're **architectural choices** that don't scale. Decades of microservice experience have taught us about decoupling, orchestration, and reliability. Let's apply those lessons!

---

## The Flock Approach

Flock combines two proven patterns:

### 1. Declarative Type Contracts (Not Prompts)

**Traditional approach:**
```python
prompt = """You are an expert bug analyst. Analyze bug reports and provide structured diagnostics.

INSTRUCTIONS:
1. Read the bug report carefully
2. Determine severity (Critical|High|Medium|Low)
3. Classify bug category
4. Formulate root cause hypothesis (minimum 50 characters)
5. Assign confidence score (0.0-1.0)

OUTPUT FORMAT:
You MUST return valid JSON with this exact structure:
{
  "severity": "string (Critical|High|Medium|Low)",
  "category": "string",
  "root_cause_hypothesis": "string (minimum 50 characters)",
  "confidence_score": "number (0.0 to 1.0)"
}

VALIDATION RULES:
- severity: Must be exactly one of: Critical, High, Medium, Low
- category: Must be a single word or short phrase
- root_cause_hypothesis: Must be at least 50 characters
- confidence_score: Must be between 0.0 and 1.0

[...hundreds more lines...]"""

result = llm.invoke(prompt)  # 500-line prompt that breaks
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
  <img alt="Bug Diagnosis" src="docs/assets/images/bug_diagnosis.png" width="1000">
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

**This is not a new idea.** Blackboard architecture has powered AI systems since the 1970s (Hearsay-II, HASP/SIAP, BB1). We're applying proven patterns to modern LLMs.

---

## Quick Start (60 Seconds)

```bash
pip install flock-core
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4.1"  # Optional, has defaults
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

# AND gate: This agent AUTOMATICALLY waits for BOTH analyses
final_reviewer = flock.agent("final_reviewer").consumes(BugAnalysis, SecurityAnalysis).publishes(FinalReview)

# 4. Run with real-time dashboard
async def main():
    await flock.serve(dashboard=True)

asyncio.run(main())
```

**What happened:**
- Bug detector and security auditor ran **in parallel**
- Final reviewer **automatically waited** for both
- **Zero prompts written** - types defined the behavior
- **Zero graph edges** - subscriptions created the workflow
- **Full type safety** - Pydantic validates all outputs

---

## Core Features

### Typed Artifacts

Every piece of data is a validated Pydantic model:

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

### Agent Subscriptions with Logic Gates

**AND Gates - Wait for ALL types:**
```python
# Wait for BOTH types before triggering
diagnostician = flock.agent("diagnostician").consumes(XRayAnalysis, LabResults).publishes(Diagnosis)
```

**OR Gates - Trigger on ANY type:**
```python
# Trigger when EITHER type arrives (via chaining)
alert_handler = flock.agent("alerts").consumes(SystemAlert).consumes(UserAlert).publishes(Response)
```

**Count-Based AND Gates:**
```python
# Wait for THREE Orders
aggregator = flock.agent("aggregator").consumes(Order, Order, Order).publishes(BatchSummary)

# Wait for TWO Images AND ONE Metadata
validator = flock.agent("validator").consumes(Image, Image, Metadata).publishes(ValidationResult)
```

### 🧠 Semantic Subscriptions (New in 0.5!)

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

# Tickets route automatically based on MEANING!
# "SQL injection" → Security Team (no keyword "security" needed!)
# "charged twice" → Billing Team (semantic match to "payment")
```

**Advanced semantic filtering:**
```python
# Custom threshold (0.0-1.0, default 0.4)
.consumes(Ticket, semantic_match="urgent", semantic_threshold=0.7)  # Strict

# Multiple criteria (ALL must match)
.consumes(Doc, semantic_match=["security", "compliance"])  # AND logic

# Field-specific matching
.consumes(Article, semantic_match={
    "query": "machine learning",
    "threshold": 0.6,
    "field": "abstract"  # Only match this field
})
```

**Why this is revolutionary:**
- ✅ **No keyword brittleness** - "SQL injection" matches "security vulnerability"
- ✅ **Better recall** - Catches semantically similar content
- ✅ **Local embeddings** - all-MiniLM-L6-v2 model (~90MB), no external API
- ✅ **Fast & cached** - LRU cache with 10k entries, ~15ms per embedding

**📖 [Full Semantic Guide →](docs/semantic-subscriptions.md)**

### Advanced Subscription Patterns

<p align="center">
  <img alt="Event Join" src="docs/assets/images/join.png" width="800">
</p>

**Predicates - Smart Filtering:**
```python
# Only process critical cases
urgent_care = flock.agent("urgent").consumes(
    Diagnosis,
    where=lambda d: d.severity in ["Critical", "High"]
)
```

**BatchSpec - Cost Optimization:**
```python
# Process 25 at once = 96% cheaper API calls!
payment_processor = flock.agent("payments").consumes(
    Transaction,
    batch=BatchSpec(size=25, timeout=timedelta(seconds=30))
)
```

**JoinSpec - Data Correlation:**
```python
# Match orders + shipments by ID
customer_service = flock.agent("notifications").consumes(
    Order,
    Shipment,
    join=JoinSpec(by=lambda x: x.order_id, within=timedelta(hours=24))
)
```

**Combined - Production Pipelines:**
```python
# Correlate sensors, THEN batch for analysis
quality_control = flock.agent("qc").consumes(
    TemperatureSensor,
    PressureSensor,
    join=JoinSpec(by=lambda x: x.device_id, within=timedelta(seconds=30)),
    batch=BatchSpec(size=5, timeout=timedelta(seconds=45))
)
```

<p align="center">
  <img alt="Event Batch" src="docs/assets/images/batch.png" width="800">
</p>

### 🌟 Fan-Out Publishing

**Produce multiple outputs from a single execution:**

```python
# Generate 10 diverse product ideas from one brief
idea_generator = (
    flock.agent("generator")
    .consumes(ProductBrief)
    .publishes(ProductIdea, fan_out=10)
)

# With quality filtering
idea_generator = (
    flock.agent("generator")
    .consumes(ProductBrief)
    .publishes(
        ProductIdea,
        fan_out=20,  # Generate 20 candidates
        where=lambda idea: idea.score >= 8.0  # Only publish score >= 8
    )
)
```

**Multi-Output Fan-Out (The Mind-Blowing Part):**

```python
# Generate 3 of EACH type = 9 total artifacts in ONE LLM call!
multi_master = (
    flock.agent("multi_master")
    .consumes(Idea)
    .publishes(Movie, MovieScript, MovieCampaign, fan_out=3)
)

# Single execution produces:
# - 3 complete Movies (title, genre, cast, plot)
# - 3 complete MovieScripts (characters, scenes, pages)
# - 3 complete MovieCampaigns (taglines, posters)
# = 9 complex artifacts, 100+ fields, full validation, ONE LLM call!
```

**📖 [Full Fan-Out Guide →](https://whiteducksoftware.github.io/flock/guides/fan-out/)**

### 🔒 Zero-Trust Visibility Controls

**Built-in security (not bolt-on):**

```python
# Multi-tenancy (SaaS isolation)
agent.publishes(CustomerData, visibility=TenantVisibility(tenant_id="customer_123"))

# Explicit allowlist (HIPAA compliance)
agent.publishes(MedicalRecord, visibility=PrivateVisibility(agents={"physician", "nurse"}))

# Role-based access control
agent.identity(AgentIdentity(name="analyst", labels={"clearance:secret"}))
agent.publishes(IntelReport, visibility=LabelledVisibility(required_labels={"clearance:secret"}))

# Time-delayed release
artifact.visibility = AfterVisibility(ttl=timedelta(hours=24), then=PublicVisibility())
```

**Architecturally impossible to bypass:** Every context provider inherits from `BaseContextProvider`, which enforces visibility filtering automatically. You literally cannot create a provider that forgets to check permissions.

### Context Providers (Smart Filtering)

**Control what agents see:**

```python
from flock.context_provider import FilteredContextProvider, PasswordRedactorProvider

# Global filtering - all agents see only urgent items
flock = Flock(
    "openai/gpt-4.1",
    context_provider=FilteredContextProvider(FilterConfig(tags={"urgent"}))
)

# Per-agent overrides
error_agent.context_provider = FilteredContextProvider(FilterConfig(tags={"ERROR"}))

# Production-ready password filtering
flock = Flock(
    "openai/gpt-4.1",
    context_provider=PasswordRedactorProvider()  # Auto-redacts secrets!
)
```

**Built-in providers (all visibility-filtered):**
- `DefaultContextProvider` - Full blackboard access
- `CorrelatedContextProvider` - Workflow isolation
- `RecentContextProvider` - Token cost control
- `TimeWindowContextProvider` - Time-based filtering
- `SemanticContextProvider` - Similarity-based retrieval (New!)
- `EmptyContextProvider` - Stateless agents
- `FilteredContextProvider` - Custom filtering

**Semantic Context Provider:**
```python
from flock.semantic import SemanticContextProvider

# Find similar historical incidents
provider = SemanticContextProvider(
    query_text="database connection timeout",
    threshold=0.4,
    limit=5,
    artifact_type=Incident,
    where=lambda a: a.payload["resolved"] is True
)
similar = await provider.get_context(store)
```

**📖 [Context Providers Guide →](https://whiteducksoftware.github.io/flock/guides/context-providers/)**

### Persistent Blackboard

**Production durability with SQLite:**

```python
from flock.store import SQLiteBlackboardStore

store = SQLiteBlackboardStore(".flock/blackboard.db")
await store.ensure_schema()
flock = Flock("openai/gpt-4.1", store=store)
```

**What you get:**
- Long-lived artifacts with full history
- Historical APIs with pagination
- Dashboard integration with retention windows
- CLI tools for maintenance and retention policies

### Parallel Execution Control

**Batch-then-execute pattern:**

```python
# ✅ EFFICIENT: Batch publish, then run in parallel
for review in customer_reviews:
    await flock.publish(review)  # Just scheduling work

await flock.run_until_idle()  # All sentiment_analyzer agents run concurrently!

# Get all results
analyses = await flock.store.get_by_type(SentimentAnalysis)
# 100 analyses in ~1x single review time!
```

### Agent & Orchestrator Components

**Composable lifecycle hooks:**

```python
from flock.components import AgentComponent

class LoggingComponent(AgentComponent):
    async def on_pre_evaluate(self, agent, ctx, inputs):
        logger.info(f"Agent {agent.name} evaluating: {inputs}")
        return inputs

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        logger.info(f"Agent {agent.name} produced: {result}")
        return result

analyzer.with_utilities(LoggingComponent())
```

**Built-in components:** Rate limiting, caching, metrics, budget tracking, circuit breakers, deduplication

**📖 [Agent Components Guide →](https://whiteducksoftware.github.io/flock/guides/components/)**

### Production Safety

**Built-in safeguards:**

```python
# Circuit breakers (auto-added)
flock = Flock("openai/gpt-4.1")  # CircuitBreakerComponent(max_iterations=1000)

# Feedback loop protection
critic.prevent_self_trigger(True)  # Won't trigger itself infinitely

# Best-of-N execution
agent.best_of(5, score=lambda result: result.metrics["confidence"])
```

---

## Production Observability

### Real-Time Dashboard

**Start with one line:**

```python
await flock.serve(dashboard=True)
```

<p align="center">
  <img alt="Agent View" src="docs/assets/images/flock_ui_agent_view.png" width="1000">
  <i>Agent View: Real-time communication patterns</i>
</p>

**Features:**
- **Dual Modes:** Agent view & Blackboard view
- **Real-Time Updates:** WebSocket streaming with live activation
- **Interactive Graph:** Drag, zoom, pan, 5 auto-layout algorithms
- **Advanced Filtering:** Correlation ID tracking, time ranges, autocomplete
- **Control Panel:** Publish artifacts, invoke agents from UI
- **Keyboard Shortcuts:** WCAG 2.1 AA compliant

<p align="center">
  <img alt="Blackboard View" src="docs/assets/images/flock_ui_blackboard_view.png" width="1000">
  <i>Blackboard View: Data lineage and transformations</i>
</p>

### Production-Grade Trace Viewer

**Jaeger-style tracing with 7 modes:**

<p align="center">
  <img alt="Trace Viewer" src="docs/assets/images/trace_1.png" width="1000">
  <i>Timeline view with span hierarchies</i>
</p>

**7 Trace Modes:**
1. **Timeline** - Waterfall visualization
2. **Statistics** - Sortable duration/error tracking
3. **RED Metrics** - Rate, Errors, Duration monitoring
4. **Dependencies** - Service communication analysis
5. **DuckDB SQL** - Interactive query editor with CSV export
6. **Configuration** - Real-time filtering
7. **Guide** - Built-in documentation

<p align="center">
  <img alt="Dependencies" src="docs/assets/images/trace_2.png" width="1000">
  <i>Dependency analysis</i>
</p>

### OpenTelemetry + DuckDB Tracing

**One environment variable enables tracing:**

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

**Real debugging:**
```
You: "My pizza agent is slow"
AI: [queries DuckDB]
    "DSPyEngine.evaluate takes 23s on average.
     Input size: 50KB of conversation history.
     Recommendation: Limit context to last 5 messages."
```

<p align="center">
  <img alt="DuckDB Query" src="docs/assets/images/trace_3.png" width="1000">
  <i>DuckDB SQL query interface</i>
</p>

### REST API

**Production-ready HTTP endpoints:**

```python
await flock.serve(dashboard=True)  # API + Dashboard on port 8344
# API docs: http://localhost:8344/docs
```

**Key endpoints:**
- `POST /api/v1/artifacts` - Publish to blackboard
- `GET /api/v1/artifacts` - Query with filtering/pagination
- `POST /api/v1/agents/{name}/run` - Direct agent invocation
- `GET /api/v1/correlations/{id}/status` - Workflow tracking
- `GET /health` and `GET /metrics` - Monitoring

**Features:**
- ✅ OpenAPI 3.0 documentation at `/docs`
- ✅ Pydantic validation
- ✅ Correlation tracking
- ✅ Consumption metadata
- ✅ Prometheus-compatible metrics

---

## Framework Comparison

| Dimension | Graph-Based | Chat-Based | Flock (Blackboard) |
|-----------|------------|------------|-------------------|
| **Pattern** | Directed graph | Round-robin chat | Blackboard subscriptions |
| **Coordination** | Manual edges | Message passing | Type subscriptions |
| **Parallelism** | Manual split/join | Sequential | Automatic |
| **Type Safety** | Varies | Text messages | Pydantic + validation |
| **Coupling** | Tight | Medium | Loose |
| **Adding Agents** | Rewrite graph | Update flow | Just subscribe |
| **Testing** | Full graph | Full group | Individual isolation |
| **Security** | DIY | DIY | Built-in (5 types) |
| **Scalability** | O(n²) | Limited | O(n) |

### When Flock Wins

**✅ Use Flock when you need:**
- Parallel agent execution (automatic)
- Type-safe outputs (Pydantic validation)
- Minimal prompt engineering (schemas define behavior)
- Dynamic agent addition (no rewiring)
- Testing in isolation (unit test individual agents)
- Built-in security (HIPAA, SOC2, multi-tenancy)
- 10+ agents (linear complexity)
- Semantic routing (meaning-based matching)

### When Alternatives Win

**⚠️ Consider graph-based frameworks:**
- Extensive ecosystem integration needed
- Workflow is inherently sequential
- Battle-tested maturity required
- Team has existing expertise

**⚠️ Consider chat-based frameworks:**
- Conversation-based development preferred
- Turn-taking dialogue use case
- Specific ecosystem features needed

### Honest Trade-offs

**You trade:**
- Ecosystem maturity (smaller community)
- Extensive documentation (catching up)
- Battle-tested age (newer architecture)

**You gain:**
- Better scalability (O(n) vs O(n²))
- Type safety (validation vs hope)
- Cleaner architecture (loose coupling)
- Production safety (built-in circuit breakers)
- Security model (5 visibility types)
- Semantic intelligence (meaning-based routing)

**Different frameworks for different priorities. Choose based on what matters to your team.**

---

## Production Readiness

### What Works Today (v0.5.0)

**✅ Production-ready core:**
- 1300+ tests with >75% coverage (>90% on critical paths)
- Blackboard orchestrator with typed artifacts
- Parallel + sequential execution (automatic)
- Zero-trust security (5 visibility types)
- Semantic subscriptions with local embeddings
- Circuit breakers and feedback prevention
- OpenTelemetry + DuckDB tracing
- Real-time dashboard with 7-mode trace viewer
- MCP integration (Model Context Protocol)
- Best-of-N, batching, joins, fan-out
- Type-safe retrieval API
- SQLite persistent store

**⚠️ What's missing for large-scale:**
- Advanced retry logic (basic only)
- Event replay (no Kafka yet)
- Kubernetes-native deployment (no Helm)
- OAuth/RBAC (dashboard has no auth)

All missing features planned for v1.0 (Q4 2025)

### Recommended Use Cases Today

**✅ Good fit right now:**
- Startups/MVPs (fast iteration, type safety)
- Internal tools (in-memory acceptable)
- Research/prototyping (clean architecture)
- Medium-scale systems (10-50 agents, 1000s of artifacts)

**⚠️ Wait for 1.0 if you need:**
- Enterprise persistence (multi-region, HA)
- Compliance auditing (immutable logs)
- Multi-tenancy SaaS (OAuth/SSO)
- Mission-critical 99.99% uptime

**Flock 0.5.0 is production-ready for the right use cases. Know your requirements.**

---

## Getting Started

```bash
# Install
pip install flock-core

# With semantic features
pip install flock-core[semantic]

# Set API key
export OPENAI_API_KEY="sk-..."

# Try examples
git clone https://github.com/whiteducksoftware/flock-flow.git
cd flock-flow

# CLI examples
uv run python examples/01-cli/01_declarative_pizza.py

# Dashboard examples
uv run python examples/02-dashboard/01_declarative_pizza.py

# Semantic routing
uv run python examples/08-semantic/01_intelligent_ticket_routing.py
```

**Learn by doing:**
- 📚 [Examples README](examples/README.md) - Complete learning path
- 🖥️ [CLI Examples](examples/01-cli/) - Console output (01-12)
- 📊 [Dashboard Examples](examples/02-dashboard/) - Interactive visualization (01-12)
- 🧠 [Semantic Examples](examples/08-semantic/) - Meaning-based routing
- 📖 [Documentation](https://whiteducksoftware.github.io/flock) - Full docs

---

## Production Use Cases

### Financial Services: Multi-Signal Trading

**Challenge:** Analyze signals in parallel, correlate within time windows, maintain audit trails.

```python
# Parallel signal analyzers
volatility = flock.agent("volatility").consumes(MarketData).publishes(VolatilityAlert)
sentiment = flock.agent("sentiment").consumes(NewsArticle).publishes(SentimentAlert)

# Trade execution waits for CORRELATED signals
trader = flock.agent("trader").consumes(
    VolatilityAlert, SentimentAlert,
    join=JoinSpec(within=timedelta(minutes=5))
).publishes(TradeOrder)
```

### Healthcare: HIPAA-Compliant Diagnostics

**Challenge:** Multi-modal fusion with access controls, audit trails, zero-trust.

```python
# Privacy controls built-in
radiology.publishes(XRayAnalysis, visibility=PrivateVisibility(agents={"diagnostician"}))
lab.publishes(LabResults, visibility=TenantVisibility(tenant_id="patient_123"))

# Diagnostician waits for BOTH with role-based access
diagnostician = flock.agent("diagnostician").consumes(XRayAnalysis, LabResults).publishes(Diagnosis)
```

### E-Commerce: Intelligent Support Routing

**Challenge:** Route support tickets to specialized teams based on meaning.

```python
# Semantic routing (NO keyword matching!)
security_team.consumes(Ticket, semantic_match="security vulnerability exploit")
billing_team.consumes(Ticket, semantic_match="payment charge refund billing")
tech_support.consumes(Ticket, semantic_match="technical issue error bug")

# "SQL injection" → Security (no "security" keyword needed!)
# "charged twice" → Billing (semantic match!)
# "app crashes" → Tech Support (semantic understanding!)
```

**📖 [Full Use Cases →](USECASES.md)**

---

## Contributing

We're building Flock in the open. See **[Contributing Guide](https://whiteducksoftware.github.io/flock/about/contributing/)**.

**Before contributing:**
- [Architecture Overview](docs/architecture.md) - Codebase organization
- [Error Handling](docs/patterns/error_handling.md) - Required patterns
- [Async Patterns](docs/patterns/async_patterns.md) - Standards

**Quality standards:**
- All tests must pass
- Coverage requirements met
- Code formatted with Ruff

---

## Roadmap to 1.0

**Target: Q4 2025**

See [ROADMAP.md](ROADMAP.md) for detailed status and tracking.

**Key initiatives:**
- **Reliability:** Advanced retry, error recovery, distributed tracing
- **Persistence:** Multi-region stores, event replay, Kafka integration
- **Security:** OAuth/RBAC, audit logging, compliance tooling
- **Operations:** Kubernetes deployment, Helm charts, monitoring
- **Quality:** Performance benchmarks, stress testing, migration tools

---

## The Bottom Line

**Flock makes different architectural choices:**

**Instead of:**
- ❌ Prompt engineering → ✅ Declarative type contracts
- ❌ Workflow graphs → ✅ Blackboard subscriptions
- ❌ Keyword matching → ✅ Semantic intelligence
- ❌ Manual parallelization → ✅ Automatic concurrent execution
- ❌ Bolt-on security → ✅ Zero-trust visibility controls
- ❌ Hope-based debugging → ✅ AI-queryable distributed traces

**These are architectural decisions with real tradeoffs.**

**Different frameworks for different priorities. Choose based on what matters to your team.**

---

<div align="center">

**Built with ❤️ by white duck GmbH**

**"Declarative contracts eliminate prompt hell. Blackboard architecture eliminates graph spaghetti. Semantic intelligence eliminates keyword brittleness. Proven patterns applied to modern LLMs."**

[⭐ Star on GitHub](https://github.com/whiteducksoftware/flock-flow) | [📖 Documentation](https://whiteducksoftware.github.io/flock) | [🚀 Try Examples](examples/) | [💼 Enterprise Support](mailto:support@whiteduck.de)

</div>

---

**Last Updated:** October 19, 2025
**Version:** Flock 0.5.0 (Blackboard Edition)
**Status:** Production-Ready Core, Enterprise Features Roadmapped
