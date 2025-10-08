<p align="center">
  <img alt="Flock Banner" src="https://raw.githubusercontent.com/whiteducksoftware/flock/master/docs/assets/images/flock.png" width="800">
</p>
<p align="center">
  <a href="https://pypi.org/project/flock-core/" target="_blank"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/flock-core?style=for-the-badge&logo=pypi&label=pip%20version"></a>
  <img alt="Python Version" src="https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python">
  <a href="https://github.com/whiteducksoftware/flock/blob/master/LICENSE" target="_blank"><img alt="License" src="https://img.shields.io/pypi/l/flock-core?style=for-the-badge"></a>
  <a href="https://whiteduck.de" target="_blank"><img alt="Built by white duck" src="https://img.shields.io/badge/Built%20by-white%20duck%20GmbH-white?style=for-the-badge&labelColor=black"></a>
</p>

---

# Flock 0.5: Declarative Multi-Agent Orchestration

> **Stop engineering prompts. Start declaring contracts.**

Flock is a production-focused framework for orchestrating AI agents through **declarative type contracts** and **blackboard architecture**—proven patterns from distributed systems and classical AI, now applied to modern LLMs.

**Version 0.5.0** • Production-Ready Core • 743 Tests • 77% Coverage

---

## The Problem With Current Frameworks

Building production multi-agent systems today means dealing with:

**🔥 Prompt Engineering Hell**
```python
# 500-line prompt that breaks when GPT-4 becomes GPT-5
prompt = """You are an expert code reviewer. When you receive code, you should...
[498 more lines of instructions that the LLM ignores half the time]"""
```

**🔥 Testing Nightmares**
```python
# How do you unit test this?
result = llm.invoke(prompt)  # Hope for valid JSON
data = json.loads(result.content)  # Crashes in production
```

**🔥 Rigid Workflow Graphs**
```python
# Want to add a new agent? Rewrite the entire graph.
workflow.add_edge("agent_a", "agent_b")
workflow.add_edge("agent_b", "agent_c")
# Add agent_d? Start rewiring...
```

**🔥 No Security Model**
```python
# Every agent sees everything. Good luck with HIPAA compliance.
```

These aren't framework limitations—they're **architectural choices** that don't scale.

---

## The Flock Approach

Flock takes a different path, combining two proven patterns:

### 1. Declarative Type Contracts (Not Prompts)

**The old way:**
```python
prompt = "Analyze this bug report and return JSON with severity, category, hypothesis..."
result = llm.invoke(prompt)  # Hope it works
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

**Why this matters:**
- ✅ **Survives model upgrades** - GPT-6 will still understand Pydantic schemas
- ✅ **Runtime validation** - Errors caught at parse time, not in production
- ✅ **Testable** - Mock inputs/outputs with concrete types
- ✅ **Self-documenting** - The code tells you what agents do

### 2. Blackboard Architecture (Not Directed Graphs)

**The old way (graph-based):**
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

**This is not a new idea.** Blackboard architecture powered groundbreaking AI systems since the 1970s (Hearsay-II, HASP/SIAP, BB1). We're applying proven patterns to modern LLMs.

---

## Quick Start (60 Seconds)

```bash
pip install flock-flow
export OPENAI_API_KEY="sk-..."
```

```python
import asyncio
from pydantic import BaseModel, Field
from flock.orchestrator import Flock
from flock.registry import flock_type

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
flock = Flock("openai/gpt-4.1")

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

### Real-Time Dashboard

```python
await flock.serve(dashboard=True)
```

- **Dual visualization modes:** Agent View vs Blackboard View
- **WebSocket streaming:** Live updates with 2-minute heartbeat
- **Control panel:** Publish artifacts and invoke agents from UI
- **7 trace viewer modes:** Timeline, Statistics, RED metrics, Dependencies, SQL, Config, Guide
- **Full I/O capture:** Complete input/output data with collapsible JSON viewer
- **Keyboard shortcuts:** WCAG 2.1 AA compliant accessibility

---

## Framework Comparison

### When Flock Wins

**✅ Use Flock when you need:**

| Requirement | Why Flock | Alternative Challenge |
|-------------|-----------|----------------------|
| **Parallel agent execution** | Automatic - agents consuming same type run concurrently | Graph frameworks require manual coordination; chat frameworks are typically sequential |
| **Type-safe outputs** | Pydantic validation at runtime | Most use TypedDict (no validation) or text-based outputs |
| **Zero prompt engineering** | Schemas define behavior | Most require extensive manual prompts |
| **Adding agents dynamically** | Just subscribe to types | Graph frameworks require rewiring; others need flow updates |
| **Testing in isolation** | Unit test individual agents | Most require full workflow setup for testing |
| **Security/access control** | 5 visibility types built-in | DIY implementation in most frameworks |
| **10+ agents** | O(n) complexity, stays clean | Graph-based approaches have O(n²) edge complexity |

### When Alternatives Win

**⚠️ Consider LangGraph when:**
- You need **extensive ecosystem integration** (LangChain tools, LangSmith debugging)
- Your workflow is **inherently sequential** (no parallelism needed)
- You want **battle-tested maturity** (LangGraph is 1.0+, Flock is 0.5.0)
- You need **extensive documentation** and large community

**⚠️ Consider AutoGen when:**
- You need **Microsoft ecosystem** integration (Azure, Office)
- You prefer **chat-based development patterns** for agent interaction
- Your team has existing **AutoGen expertise**
- You need features specific to the AutoGen ecosystem

### Honest Architectural Comparison

| Dimension | Flock | LangGraph | AutoGen (v0.2) | AutoGen (v0.4) |
|-----------|-------|-----------|---------------|----------------|
| **Core Pattern** | Blackboard subscriptions | Directed graph | Round-robin chat | Agent graphs |
| **Parallelism** | Automatic | Manual (Send API) | No | Manual |
| **Type Safety** | Pydantic + validation | TypedDict | Text-based | Typed messages |
| **Coupling** | Loose (types) | Tight (edges) | Medium (conversation) | Medium (graph) |
| **Prompt Engineering** | Zero (declarative) | Required | Required | Required |
| **Add Agent** | Subscribe to type | Rewrite graph | Update flow | Update graph |
| **Maturity** | 0.5.0 (early) | 1.0+ (mature) | 1.0+ (mature) | 0.4+ (evolving) |
| **Community** | Small | Large | Large | Growing |
| **Testing** | Isolated agents | Full graph | Full group | Graph/agents |
| **Security** | Built-in (5 types) | DIY | DIY | DIY |

**Bottom line:** Different architectures for different needs. Flock trades ecosystem maturity for better scalability patterns. Choose based on your priorities.

---

## Production Readiness

### What Works Today (v0.5.0)

**✅ Production-ready core:**
- 743 tests, 77% coverage (86-100% on critical paths)
- Blackboard orchestrator with typed artifacts
- Parallel + sequential execution (automatic)
- Zero-trust security (5 visibility types)
- Circuit breakers and feedback loop prevention
- OpenTelemetry distributed tracing with DuckDB storage
- Real-time dashboard with 7-mode trace viewer
- MCP integration (Model Context Protocol)
- Best-of-N execution, batch processing, join operations

**⚠️ What's missing for large-scale production:**
- **Persistent blackboard** - Currently in-memory only (Redis/Postgres coming Q1 2025)
- **Advanced retry logic** - Basic only (exponential backoff + dead letter queue coming Q1 2025)
- **Event replay** - No Kafka integration yet (coming Q2 2025)
- **Kubernetes-native deployment** - No Helm chart yet (coming Q2 2025)
- **OAuth/RBAC** - Dashboard has no auth (coming Q2 2025)

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

See [ROADMAP.md](ROADMAP.md) for detailed timeline. Key milestones:

**Q1 2025: Production Hardening**
- Redis/Postgres persistence
- Advanced retry & error handling (exponential backoff, circuit breakers per-agent, dead letter queues)
- Aggregation patterns (map-reduce, voting, consensus)

**Q2 2025: Enterprise Infrastructure**
- Kafka event backbone (replay, time-travel debugging)
- Kubernetes-native deployment (Helm charts, auto-scaling)
- OAuth/RBAC (multi-tenant auth)

**Q3 2025: Advanced Orchestration**
- Human-in-the-loop approval patterns
- Fan-out/fan-in workflows
- Time-based scheduling (cron triggers, sliding windows)

**Target: v1.0 by Q3 2025**

---

## Example: Multi-Modal Clinical Decision Support

```python
from flock.orchestrator import Flock
from flock.visibility import PrivateVisibility, TenantVisibility
from pydantic import BaseModel
from flock.registry import flock_type

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
flock = Flock("openai/gpt-4.1")

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

## Getting Started

```bash
# Install
pip install flock-flow

# Set API key
export OPENAI_API_KEY="sk-..."

# Try the workshop
git clone https://github.com/whiteducksoftware/flock-flow.git
cd flock-flow
uv run python examples/05-claudes-workshop/lesson_01_code_detective.py
```

**Learn by doing:**
- 📚 [7-Lesson Workshop](examples/05-claudes-workshop/) ✅ - Progressive lessons from basics to advanced
- 🎯 [Declarative Basics](examples/01-the-declarative-way/) ✅ - Understanding declarative programming
- 🗂️ [Blackboard Workflows](examples/02-the-blackboard/) 🚧 - Parallel and sequential execution patterns *(coming soon)*
- 📊 [Dashboard UI](examples/03-the-dashboard/) 🚧 - Real-time visualization *(coming soon)*
- 🔌 [REST API](examples/04-the-api/) 🚧 - API integration examples *(coming soon)*
- 📖 [Documentation](AGENTS.md) - Complete development guide

---

## Contributing

We're building Flock in the open. See [AGENTS.md](AGENTS.md) for development setup.

**We welcome:**
- Bug reports and feature requests
- Documentation improvements
- Example contributions
- Architecture discussions

**Quality standards:**
- All tests must pass (743 currently)
- Coverage requirements met (77%+ overall, 86-100% critical paths)
- Code formatted with Ruff
- Type checking passes (mypy)

---

## Why "0.5"?

We're calling this 0.5 to signal:

1. **Core is production-ready** - 743 tests, real-world deployments, comprehensive features
2. **Ecosystem is evolving** - Documentation growing, community building, features maturing
3. **Architecture is proven** - Blackboard pattern is 50+ years old, declarative contracts are sound
4. **Enterprise features are coming** - Persistence, auth, Kubernetes deployment in roadmap

**1.0 will arrive** when we've delivered persistence, advanced error handling, and enterprise deployment patterns (targeting Q3 2025).

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

**"Agents are microservices. The blackboard is their API."**

[⭐ Star on GitHub](https://github.com/whiteducksoftware/flock-flow) | [📖 Read the Docs](AGENTS.md) | [🚀 Try Examples](examples/) | [💼 Enterprise Support](mailto:support@whiteduck.de)

</div>

---

**Last Updated:** October 8, 2025
**Version:** Flock 0.5.0 (Blackboard Edition)
**Status:** Production-Ready Core, Enterprise Features Roadmapped

---

**"Declarative contracts eliminate prompt hell. Blackboard architecture eliminates graph spaghetti. Proven patterns applied to modern LLMs."**
