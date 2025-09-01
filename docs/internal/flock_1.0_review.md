# Flock 1.0 Review — Agent‑Centric Reactivity Without Cognitive Taxes

Author: AI assistant review

## Executive Summary

You’re right to keep the FlockAgent API as the main mental model. The winning move is to make “reactive” a property of agents, not a new programming style. Let me restate the 1.0 goal in that language:

- Keep the current agent API (create agents, add to a Flock, run them).
- Make it reactive by giving agents a simple, discoverable method: `agent_b.subscribe_to(agent_a, ...)`.
- Hide event envelopes, brokers, idempotency, and delivery semantics behind a friendly surface — just like Flock hides Temporal complexity.

With this approach, Flock can deliver contract‑first, reactive composition and reliability tiers — while staying approachable for “AI agent” developers. If the MVP focuses on this agent‑centric experience and the internals stay clean, this can absolutely become one of the go‑to frameworks for serious teams.

---

## What’s Gold (Keep and Lean In)

- Contracts first: Pydantic models at the boundary, JSON Schema internally, strict decoding to types.
- Reactive composition: done via agent methods, not decorators or graph editors.
- Reliability tiers: local → reliable → durable (Temporal) as a simple switch; per‑subscription overrides when needed.
- Standards as implementation details: use CloudEvents, AsyncAPI/OpenAPI, OTel, OPA, MCP internally — don’t force them on users.
- Observability: a derived graph in the UI (for debugging), not an authored DAG.

---

## What Changes (DX‑First Reactivity)

Introduce a single, memorable API and keep everything else optional:

```python
# Make b react to a’s emissions
b.subscribe_to(
    a,
    when=None,                  # optional predicate on a’s result/context
    map=None,                   # None → auto (reuse Flock’s handoff strategy); or explicit mapping/callable
    strategy="append",         # {append|override|map} (reuses existing Flock semantics)
    reliable=False,             # local by default; reliable or durable as needed
    retry=None,                 # e.g. {"max_attempts": 5, "backoff": "exp"}
    timeout=None,               # per‑subscription timeout
    idempotency_key=None,       # derive from run_id + agent + seq by default
)
```

- This mirrors today’s mental model: “Agent A hands off to B.” Subscribers generalize that to “A can hand off to many Bs.”
- The runtime drives the chain until there are no subscribers left.
- The user never has to see envelopes, brokers, or temporal jargon — unless they go looking.

---

## Minimal Mental Model

- Agents emit a typed result (enforced by contracts). Flock turns those into internal events.
- Subscriptions are stored on the agents (and in Flock). When A finishes, the runtime finds all `B.subscribe_to(A, ...)` entries, builds each B’s input using the existing handoff strategies, and continues.
- `.run(agent=a, input=...)` starts the chain. `.run_async` works the same. Everything else is additive.

---

## Contract Discipline and Decoding (No Fuss)

- Pydantic input/output remain the source of truth. Flock generates JSON Schema internally.
- Structured decoding “just works” by stacking strategies: JSON mode → constrained/grammar → schema‑guided repair with budgets.
- One config flag on the evaluator controls this behavior; no custom code required for 99% cases.

---

## Reliability Tiers (Ergonomic)

Expose reliability through `subscribe_to` in the same spirit as `enable_temporal` on Flock:

- Local (default): at‑most‑once delivery (great for dev and demos).
- Reliable: at‑least‑once delivery with internal idempotency cache and DLQ; configured per subscription.
- Durable: “just works with Temporal” — Flock maps deliveries to activities under the hood.

Users flip the switch with `reliable=True` or via a Flock‑level default — no need to learn a new system.

---

## Observability

- Derived graph view: shows the chain that actually ran.
- Event/step table: shows each agent run with inputs/outputs and the subscription that triggered it.
- OTel spans carry agent/subscription IDs, attempts, cost/time budgets.

---

## API Sketch (Agent‑First)

```python
from pydantic import BaseModel
from flock.core import Flock, FlockFactory

class Ticket(BaseModel):
    id: str
    text: str

class Suggestion(BaseModel):
    id: str
    steps: list[str]

triage = FlockFactory.create_default_agent(
    name="triage", input=Ticket, output=Suggestion, description="Triage ticket"
)

followup = FlockFactory.create_default_agent(
    name="followup", input=Suggestion, output="status: str"
)

# Make followup react to triage
followup.subscribe_to(triage, reliable=False)  # when=..., map=..., strategy=... available

flock = Flock(model="openai/gpt-5")
flock.add_agent(triage)
flock.add_agent(followup)

result = flock.run(agent=triage, input=Ticket(id="1", text="My printer is on fire"))
```

Advanced (reliable handoff + retries + idempotency):

```python
followup.subscribe_to(
    triage,
    reliable=True,
    retry={"max_attempts": 5, "backoff": "exp"},
    idempotency_key=lambda env: env.data.id,
)
```

A Flock‑level helper can exist for bulk wiring if desired:

```python
flock.subscribe(source=triage, target=followup, reliable=True)
```

### SubscriptionComponent (Modular Reactivity)

Prefer everything modular? Model subscriptions as a component:

```python
class SubscriptionComponentConfig(BaseModel):
    source: str
    when: str | Callable | None = None
    map: dict[str, str] | Callable | None = None
    strategy: str = "append"
    reliable: bool = False
    retry: dict | None = None
    timeout: float | None = None
    idempotency_key: Callable | None = None

class SubscriptionComponent(AgentComponent):
    config: SubscriptionComponentConfig
```

Use it explicitly or via sugar:

```python
# sugar: adds a SubscriptionComponent under the hood
followup.subscribe_to(triage, SubscriptionComponentConfig(source="triage", reliable=True))

# explicit:
followup.add_component(
    SubscriptionComponent(
        name="on_triage",
        config=SubscriptionComponentConfig(source="triage", strategy="append"),
    )
)
```

Need a complex consumption filter or join? Inherit from `SubscriptionComponent` and override. This keeps reactivity fully pluggable and consistent with Flock’s unified components.

---

## Implementation Plan (Incremental)

### Phase 1 — Reactive Core (4–6 weeks)
- Subscription registry stored on `Flock` (and serialized with agents) with a minimal data model: `{source_agent, target_agent, when, map, strategy, delivery, retry, timeout, idempotency_key}`.
- In‑process reactive router: after A finishes, emit an internal envelope (`run_id, source, seq, data`) and resolve subscribers; schedule B runs with constructed inputs.
- Reuse existing handoff strategies (append/override/map) and `resolve_inputs` to build B’s input from A’s output/context.
- Observability: enrich logs and spans; show derived graph in the UI.

Deliverables: working `.subscribe_to(...)` API, examples (simple chain, fan‑out, condition), snapshots/tests.

### Phase 2 — Reliability (3–5 weeks)
- Reliable delivery: at‑least‑once with idempotency keys (auto‑derived by default); local store (SQLite) for pending deliveries; retry/backoff; DLQ.
- Configurable per subscription; sane defaults at Flock level.
- Testing helpers to simulate duplicate deliveries.

Deliverables: examples (retry & DLQ), tests for dupes/backoff; docs.

### Phase 3 — Durable (Temporal) (4–6 weeks)
- Map deliveries to Temporal activities; ensure causation and run graph survive worker restarts; clear visibility and error reporting.

Deliverables: long‑running durable example; chaos test.

### Phase 4 — Optional Compose & Packaging (time‑boxed)
- Minimal Compose YAML to declare subscriptions; CLI to apply it to a Flock.
- Packaging v1: “Flock Bundle” (dir/tar) with manifest + contracts + code + SBOM. OCI/artifact registry later.

Deliverables: examples and docs. Keep entirely optional.

---

## Internals (Hidden by Default)

- Envelopes & schemas: use CloudEvents and JSON Schema internally; generate AsyncAPI/OpenAPI for interop — don’t surface unless requested.
- Policy hooks: allow budget/time limits and approval gates through a simple policy API; OPA integration optional.
- Memory: keep a single pluggable interface with local/default stores; advanced memory types later.

---

## Risks and Mitigations

- Scope creep: commit to the above phases; ship Phase 1 as soon as it’s solid.
- Idempotency UX: auto‑derive keys, provide strong defaults; expose overrides only when needed.
- “Reactive” fear: the method name and defaults must feel like “handoff, but smarter.” Documentation and examples should read like Flock today, just with subscribers.

---

## Final Opinion

This agent‑centric reactive design is the right path. It preserves Flock’s approachable feel while unlocking robust, production‑ready systems. If we obsess over the simplicity of `subscribe_to` (and the `SubscriptionComponent`), get structured decoding right, and layer reliability ergonomically, Flock can be one of the frameworks people reach for when they need correctness, durability, and speed — without learning three new paradigms.

---

## Post‑1.0: Where Flock Can Win Big

1) Contract Synthesis and Negotiation
- Auto‑generate adapters when contracts differ (rename/coerce/reshape), surface the diff for approval, then persist as mapping in the subscription config.

2) Self‑Optimizing Subscriptions
- A/B or multi‑armed bandit across routing policies and delivery tiers to optimize cost/latency/quality under budgets; persist learnings per subscription.

3) Elastic Multi‑Model Policy
- Per‑subscription smart model selection with budget/SLO guardrails (fallback/escalation on confidence);
  clear audit trail of choices.

4) Judges and Quality Gates
- First‑class judge components to gate emissions; structured quality checks and auto‑repair before subscribers receive data.

5) Time‑Travel Debugging and Replay
- Typed event store, deterministic replay, and “replay from here / branch run” in UI; stable CI via recorded LLM outputs.

6) Memory, Typed
- Pluggable memory interface with typed queries (e.g., `Memory[CustomerProfile]`), contract‑aware reads/writes; local defaults, optional backends.

7) Interop Without Lock‑In
- Wrap LangGraph nodes, AutoGen actors, PydanticAI handlers as Flock agents via contracts; export AsyncAPI/OpenAPI.

8) Security and Supply Chain by Default
- Signed bundles/artifacts, SBOMs, policy checks; per‑subscription capability scopes for MCP/tools.

9) Analytics and SLOs at the Subscription Level
- Track latency/cost/quality per subscription and contract version; surface simple SLOs in UI/logs.

10) Local‑First Dev Server & Flock Lab
- Zero‑dep dev server with derived graph and envelope inspector; property‑based fuzzing for contracts; scenario builders (dup delivery, timeouts).

11) Visual Inspector that Respects Devs
- Read‑only graph, branch runs from any event; no drag‑and‑drop editors required.

12) Multi‑Language SDKs with Codegen
- TypeScript/Go generated from AsyncAPI/OpenAPI so cross‑language services can participate in Flock flows.
