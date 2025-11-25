# Flock Basics 
---

## 1. What Problem Does Flock Solve?

**Typical multi-agent pain today:**

- Long, fragile prompts that break when models change.
- “Smart orchestrators” that secretly hard-code all domain knowledge.
- Graphs that are painful to extend (“add one agent → rewire the whole DAG”).
- Hard-to-test workflows because everything is just text and prompts.
- No clear security model: agents see everything unless *you* remember to filter.

**Flock’s answer:**

- **Declarative type contracts** instead of giant prompts.
- **Blackboard architecture** instead of hard-wired graphs.
- **Typed artifacts** flowing through a shared workspace.
- **Agents subscribe to data**, not to each other.
- **Visibility + context providers** as first-class security and cost controls.

> “Stop engineering prompts. Start declaring contracts.  
> Stop wiring graphs. Start publishing artifacts.”

---

## 2. The Mental Model in One Slide

Think in terms of **four building blocks**:

1. **Artifacts** – Typed data objects (Pydantic models) on the blackboard.  
   Examples: `BugReport`, `BugDiagnosis`, `BlogIdea`, `DailyReport`.

2. **Agents** – Functions that **consume** some artifact types and **publish** others.  
   They never call each other directly.

3. **Blackboard** – Shared, typed workspace that stores artifacts and metadata.

4. **Orchestrator (`Flock`)** – Runs agents whenever new matching artifacts appear.

```text
┌─────────────────────────────────────────────┐
│               BLACKBOARD                   │
│  BugReport → BugDiagnosis → FinalReview    │
│   ↑            ↑            ↑              │
│   │            │            │              │
│  Agent A     Agent B      Agent C          │
└─────────────────────────────────────────────┘
```

---

## 3. From Prompts to Type Contracts

**Traditional approach:**

- You write a 300–500 line prompt that describes JSON format, validation rules, examples, etc.
- You hope the model follows it; you pray it won’t break when models update.

**Flock approach:**

- You describe the desired output as a **Pydantic model**; that *is* the contract.
- Flock uses that schema with the model (and validates at runtime).

Example:

```python
from pydantic import BaseModel, Field
from flock import flock_type

@flock_type
class BugDiagnosis(BaseModel):
    severity: str = Field(pattern="^(Critical|High|Medium|Low)$")
    category: str = Field(description="Short category like 'UI' or 'Backend'")
    root_cause_hypothesis: str = Field(min_length=50)
    confidence_score: float = Field(ge=0.0, le=1.0)
```

Key ideas:

- The schema defines what is valid – not the prompt.
- If the model outputs something invalid, Flock can:
  - Retry with improved instructions.
  - Surface validation errors instead of corrupting downstream logic.
- This makes outputs:
  - **Upgradable** (new models still understand JSON schemas).
  - **Testable** (you can construct and assert against `BugDiagnosis` in unit tests).

---

## 4. From Graphs/Chats to Blackboard

Compared to LangGraph / AutoGen, the key **topology difference** is:

**Graph-based frameworks:**

- You explicitly wire edges: “after A, run B, then C.”
- Adding a new agent often means rewiring the graph.
- The “orchestrator” or “graph” object ends up knowing *everything*.

**Flock’s blackboard:**

- Agents declare: “I consume X, I publish Y.”
- The orchestrator looks at the blackboard and decides which agents can run.
- Workflows **emerge from data**, not from a static graph.

Simple example:

```python
from flock import Flock, flock_type
from pydantic import BaseModel

@flock_type
class CodeSubmission(BaseModel):
    code: str
    language: str

@flock_type
class BugAnalysis(BaseModel):
    issues: list[str]

@flock_type
class SecurityAnalysis(BaseModel):
    vulnerabilities: list[str]

@flock_type
class FinalReview(BaseModel):
    summary: str

flock = Flock("openai/gpt-4.1")

bug_detector = (
    flock.agent("bug_detector")
    .consumes(CodeSubmission)
    .publishes(BugAnalysis)
)

security_auditor = (
    flock.agent("security_auditor")
    .consumes(CodeSubmission)
    .publishes(SecurityAnalysis)
)

final_reviewer = (
    flock.agent("final_reviewer")
    .consumes(BugAnalysis, SecurityAnalysis)
    .publishes(FinalReview)
)
```

Execution:

```python
submission = CodeSubmission(code="...", language="python")
await flock.publish(submission)
await flock.run_until_idle()
```

What happens:

- `CodeSubmission` goes onto the blackboard.
- `bug_detector` and `security_auditor` both trigger in parallel.
- Once both `BugAnalysis` and `SecurityAnalysis` exist for that submission,  
  `final_reviewer` triggers automatically.
- No edges or “next step” wiring were needed.

---

## 5. Execution Model: `publish()` + `run_until_idle()`

Flock deliberately separates **publishing** from **execution**:

```python
await flock.publish(submission_1)
await flock.publish(submission_2)
await flock.publish(submission_3)

await flock.run_until_idle()
```

Key ideas:

- You can **batch** many artifacts, then process them in one go.
- Agents run **in parallel** whenever they’re independent.
- This maximizes throughput and makes it easy to simulate workloads.

In contrast:

- “Every publish automatically runs everything to completion” – less control.
- “Every node/agent step is explicitly invoked” – less scalable.

Additionally:

- `invoke(agent, artifact, publish_outputs=False)` is for **unit-style testing** of a single agent.
- `invoke(..., publish_outputs=True)` + `run_until_idle()` is for **cascading workflows**.

---

## 6. Fan-Out: Many Artifacts from One Call

Flock has a first-class fan-out mechanism:

```python
@flock_type
class BlogIdea(BaseModel):
    title: str
    score: float

idea_agent = (
    flock.agent("idea_generator")
    .consumes(Topic)
    .publishes(BlogIdea, fan_out=5)  # 5 variations in one go
)
```

Key points:

- Single agent execution can emit **multiple artifacts** of the same type.
- Or even multiple types with multi-fan-out (e.g., ideas + outlines + titles).
- Often much **cheaper** than calling the model 5 times in a loop.

Dynamic fan-out:

```python
from flock.core import FanOutRange

idea_agent = (
    flock.agent("idea_generator")
    .consumes(Topic)
    .publishes(
        BlogIdea,
        fan_out=FanOutRange(5, 20),
        where=lambda idea: idea.score >= 7.0,
    )
)
```

Details:

- Engine decides how many ideas (between 5 and 20).
- Then `where` filters down to only high-quality ones.

---

## 7. Semantic Subscriptions (High-Level)

Key ideas:

- Agents can subscribe **by meaning**, not just by tags or types.
- Example scenario: routing support tickets to Security vs Billing vs Tech Support.

High-level code sketch:

```python
security_team = (
    flock.agent("security_team")
    .consumes(SupportTicket, semantic_match="security vulnerability exploit")
    .publishes(SecurityAlert)
)

billing_team = (
    flock.agent("billing_team")
    .consumes(SupportTicket, semantic_match="payment refund billing")
    .publishes(BillingResponse)
)
```

Key points:

- There is no need to invent perfect tags up front.
- Flock can use embeddings to decide which agent is relevant.

---

## 8. Visibility & Context Providers (Security & Cost)

Two very important ideas:

1. **Visibility** – Who is allowed to see which artifacts at all?
2. **Context providers** – Of the allowed artifacts, which ones should actually be sent to the model?

Simple visibility example:

```python
from flock.core.visibility import TenantVisibility

@flock_type
class CustomerTicket(BaseModel):
    tenant_id: str
    message: str

ticket_agent = (
    flock.agent("tenant_support")
    .consumes(CustomerTicket)
    .publishes(Response)
)

await flock.publish(
    CustomerTicket(tenant_id="acme", message="..."),
    visibility=TenantVisibility(tenant_id="acme"),
)
```

Key points:

- This is how you enforce **multi-tenant isolation**.
- An agent for tenant A never sees artifacts for tenant B.

Context provider example (high level):

```python
from flock.core.context_provider import FilteredContextProvider
from flock.core.store import FilterConfig

error_only = FilteredContextProvider(
    FilterConfig(tags={"ERROR", "CRITICAL"}),
    limit=50,
)

flock = Flock("openai/gpt-4.1", context_provider=error_only)
```

Details:

- The agent’s **history** is filtered – it only sees the last N relevant artifacts.
- This keeps token usage under control and enforces a **principle of least privilege**.

---

## 9. Timers & Scheduling (Just the Idea)

Flock can run agents on a **schedule**, not only when artifacts appear.

Very small example:

```python
from datetime import timedelta

health_monitor = (
    flock.agent("health_monitor")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)
```

Key points:

- Timer-triggered agents get an empty `ctx.artifacts`, but can **query** the blackboard.
- Great for:
  - Daily reports.
  - Periodic health checks.
  - Batched log analysis.

Scheduled examples exist in `03-additional-examples/08-scheduling/`.

---

## 10. How This Repo Fits In

Repo structure:

- **`01-hackathon/`** – Main guided track.  
  Each file introduces one concept (basic agent, fan-out, semantic, timers, MCP, etc.).

- **`02-patterns/`** – Focused publishing patterns:
  - Single publish, multi-publish, fan-out, multi fan-out, dynamic fan-out.

- **`03-additional-examples/`** – Deep dive examples:
  - `01-getting-started/` – “classic” intro examples.
  - `02-misc/` – persistence, scale tests, logging, LM Studio.
  - `03-engines/`, `04-agent-components/`, `05-orchestrator-components/`.
  - `06-semantic/`, `07-server-components/`, `08-scheduling/`.
  - `09-app-sketches/` – bigger app-style sketches.

Example walkthrough flow:

1. Show the **mental model** (artifacts + agents + blackboard).
2. Walk through the **basic agent** example in `01-hackathon/01_basic_agent.py`.
3. Show how adding another agent is just `.consumes(...)` / `.publishes(...)`.
4. Briefly highlight fan-out and visibility/semantic as “coming up”.

---

## 11. Cheat-Sheet Summary Slide

Summary slide:

**Flock is about:**

- **Contracts, not prompts** – Pydantic types define behavior and validation.
- **Blackboard, not graphs** – Agents subscribe to data, not to each other.
- **Parallelism by default** – Independent agents run concurrently.
- **Security & cost as first-class** – Visibility + context providers.
- **Extensibility** – Engines, components, server components, semantic routing, timers.

Key takeaway:

> “In Flock, you put **typed artifacts** on a **blackboard**, and let **agents react** to them – everything else (routing, parallelism, fan-out, visibility) follows from that.”  
