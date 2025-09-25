# Temporal vs. Restate (in context of Flock)

This document compares Temporal and Restate as the durable runtime and messaging backbone for Flock’s “prod mode.” It focuses on developer ergonomics, failure semantics, messaging, Python support, and how each fits Flock’s future (DX‑first, reactive, minimal dependencies).

## Quick Summary

- Temporal: battle‑tested durable workflow engine; strong semantics (signals, timers, activities, versioning). Downsides: deterministic workflow constraints, replay/versioning footguns, heavier cluster/operational model, and code patterns that leak engine concerns into app logic.
- Restate: promotes Durable Execution + Reliable Communication + Consistent State (stateful entities) with language SDKs. Semantics emphasize request/response, one‑way messages, scheduled tasks, durable promises/timers, typed state, and “suspending user code” to resume on completion. Lighter mental model and a built‑in messaging story. Python SDK exists and is evolving.
- Recommendation: Pilot Restate as Flock’s default “prod mode” and event backbone to implement subscribe_to chains (reactive). Keep Temporal as an optional backend for organizations standardized on it. Hide both behind a small runtime interface.

## What We Have Today (Temporal in Flock)

Pros
- Durable execution with strong guarantees; signals, timers, activities, retries, heartbeats.
- Scales in production; mature ecosystem and tooling.
- Temporal.io concepts map to multi‑step LLM workflows (activities for tools/IO, workflow state for orchestration).

Cons (pain encountered in Flock)
- Determinism constraints force awkward code in workflow functions (no non‑deterministic APIs; careful use of time/random; replay‑safe patterns only).
- Versioning and history replay create maintenance surface: code changes can break replay; require explicit version gates.
- Operationally heavier: dedicated cluster/services and SDK workers; adds complexity compared to a simpler embedded/event system.
- Cognitive load for contributors unfamiliar with workflow programming; leaks into otherwise simple agents.

## Restate At A Glance (from repo/docs)

Core ideas (restate/restate README)
- Durable Execution: guarantees code runs to completion; uses durable execution to recover partial progress and prevent re‑execution of completed steps.
- Reliable Communication: request/response, one‑way messages, scheduled tasks; durable delivery and idempotency baked in.
- Durable Promises and Timers: futures/promises and timers are first‑class and survive failures.
- Consistent State: stateful entities (K/V per entity) updated atomically with execution progress.
- Suspending User Code: long-running code suspends on awaits and resumes when the awaited promise completes (removes the need for user‑land state machines in many cases).
- Observability & Introspection: UI/CLI to inspect state and interactions.

Python SDK (restate/sdk-python)
- Active SDK with version matrix vs server (pre‑1.0; note compatibility ranges).
- Packaged via maturin (Rust extension) + Python; typical Python dev setup guidance.
- Intends parity with TypeScript/Java features over time (check version tables for supported features).

## Head‑to‑Head for Flock

Category | Temporal | Restate
---|---|---
Programming model | Workflows must be deterministic; activities for side‑effects; replay/versioning | Durable execution with suspending code; fewer explicit determinism hoops in user code
Durable messaging | Signals/queries/activities; external queues common | Built‑in: request/response, one‑way, scheduled tasks; reliable delivery semantics
Timers/promises | Timers, signals, activities; manual glue | First‑class durable timers/promises
State | Workflow local state; external stores for large data | Stateful entities (K/V) per service/object with atomic updates
Operational footprint | Temporal cluster + workers | Restate server + lightweight handlers; K8s operator available
Python SDK | Mature client/worker; many patterns established | SDK present, evolving; still reaching feature parity
DX for Flock agents | Leaks workflow constraints (determinism/versioning) into our evaluator routing | Closer to “just write async code that survives failures”; integrates messaging naturally
Event backbone | External bus (NATS/Kafka) typically used alongside | Restate doubles as messaging/event substrate; could power subscribe_to natively

Notes
- Temporal’s strengths are unquestioned in production. But for Flock’s DX goals, the workflow determinism and versioning demands introduce avoidable complexity into simple agent chains.
- Restate’s premise (durable execution + reliable messaging) matches Flock’s reactive subscribe_to and engine‑agnostic orchestration better. It can be both the durable runtime and the event substrate, reducing moving parts.

## What Would Switching (or Adding) Restate Enable?

- Simpler prod mode: 
  - Use Restate’s durable promises/timers for long LLM calls, tool invocations, retries.
  - Co‑locate durable state (per agent instance) without building custom stores.
- First‑class reactive wiring:
  - Implement `agent_b.reacts_to(agent_a)` via Restate messages between stateful entities or handlers.
  - Fan‑out/fan‑in realized as messages and durable promises, not external glue.
- Clean DX boundary:
  - Keep restate/temporal hidden behind a small `DurableRuntime` interface; users only see `app.run(..., mode="prod")`.
  - Local mode remains in‑proc without Restate (mock runtime).

## Risks and Caveats

- SDK maturity in Python: validate that required features (durable calls, timers, state, messaging) are available and stable in restatedev/sdk-python for our needs.
- Operational readiness: ensure Restate server fits our deployment story (container, operator, resource needs). Temporal remains more battle‑tested at large scale.
- Lock‑in/portability: keep an abstraction so we can swap runtimes. Some features (stateful entities) may need a compatibility layer.

## Integration Plan (Incremental)

1) Runtime SPI
- Define `DurableRuntime` interface with the minimal set: run task with durable retries; send/receive message; set/get state; set timer; correlation IDs; idempotency.
- Implement `TemporalRuntimeAdapter` (current) and `RestateRuntimeAdapter` (new).

2) Reactive wiring
- Compile `.reacts_to(...)` into runtime messages (Restate) or synthetic routing (Temporal + external bus). Prefer Restate when available.

3) Engines/tools
- No change; engines remain pluggable. Tool calls execute under durable runtime with idempotency keys.

4) Rollout
- Default to Restate in “prod” for greenfield users; keep Temporal as opt‑in backend for existing deployments.
- Provide migration guidance and toggles per environment.

## Recommendation

- Proceed with a spike to integrate Restate as Flock’s default durable runtime + messaging substrate, guarded behind a runtime interface. Goals of the spike:
  - Implement `RestateRuntimeAdapter` with durable calls, timers, state, and simple request/response messaging.
  - Port a small multi‑agent chain using `.reacts_to(...)` to Restate and measure DX improvements (lines of code, error‑handling clarity, removal of determinism workarounds).
  - Add a feature flag to select Temporal vs Restate per environment.
- Keep Temporal support: organizations invested in Temporal should not lose a path; our runtime abstraction preserves compatibility.

Bottom line: For Flock’s future DX and reactive design, Restate appears lighter to reason about and closer to our “subscribe_to” mental model, with fewer determinism pitfalls surfacing in user code. Temporal remains a solid optional backend for teams that prefer it.
