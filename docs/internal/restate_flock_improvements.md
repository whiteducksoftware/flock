# Restate × Flock — Opportunities, Fit, and Migration Plan

This document evaluates Restate as an alternative/compliment to Temporal for Flock’s “production‑ready” execution layer. It builds on prior notes in docs/internal/temporal_vs_restate.md, incorporates the Restate examples in vendor/restate (including Python SDK and AI examples), and proposes a concrete integration path that reduces Temporal‑specific friction (determinism constraints, unsafe import shims) while enabling event‑driven/reactive features Flock wants for 1.0.

## Executive Summary

- Today: Flock supports an optional Temporal execution mode. It works, but it forces Temporal determinism concerns into core modules, leading to code patterns like `workflow.unsafe.imports_passed_through()` across evaluation and logging. This adds maintenance overhead and makes multi‑provider execution behavior leak into core code.
- Restate is a “durable async/await” runtime with first‑class service/workflow/virtual‑object abstractions, built‑in eventing, and Python SDK. It promises less intrusive determinism work (no workflow‑VM patching), rich messaging/awaitables, and simpler concurrent orchestration patterns that map naturally to AI agents.
- Recommendation: Add Restate as a first‑class optional execution engine (beside Temporal) and bias our reactive roadmap (pub/sub, subscriptions) to Restate’s messaging and durable “awaitables”. This lets Flock shed Temporal‑specific hacks, improve developer ergonomics, and unlock event‑driven features for 1.0.

## Current Pain Points with Temporal in Flock

- Determinism bleed‑through:
  - We guard imports and side‑effects via `workflow.unsafe.imports_passed_through()` in core files (e.g., components/evaluation/declarative_evaluation_component.py, core/logging/telemetry.py, workflow/flock_workflow.py). This scatters Temporal constraints across non‑workflow code.
  - Heavy libs and lazy imports require careful placement to avoid replay divergence.

- Strict workflow boundary and activity mapping:
  - We model each agent run and “determine_next_agent” as Temporal activities with explicit retry policies and timeouts. This is powerful but verbose and forces a mapping layer from Flock’s orchestration model into Temporal’s workflow/activity split.

- Testing/observability friction:
  - The determinism VM makes it harder to “just run” arbitrary code during replay. We add wrappers and explicit conversions to keep logic outside replay, which complicates debugging and diffing.

## Restate Capabilities Relevant to Flock

From vendor/restate (sdk-python, docs‑restate):

- Durable async/await: Services, Workflows, and Virtual Objects persist progress and resume across failures without manual retry plumbing. Replay semantics are handled by the runtime; Python SDK provides `Context`, durable timers, durable promises, and helpers like `gather`, `as_completed`, `select`.
- Eventing and messaging:
  - “Awakeables” and durable futures to coordinate events; message ingestion via HTTP/ingress; “attach” semantics to active workflows; clean patterns for long‑running conversations and waiting for human/tool signals.
- Concurrency patterns:
  - Durable parallel tasks with `RestatePromise`/gather/select; timeouts; cancellation. Matches multi‑tool chaining and agent orchestration idioms.
- Python SDK:
  - `restate.Service`, `restate.Workflow`, `restate.VirtualObject`; `restate.endpoint.app(...)` to expose services; logging that hides replay noise; test harness support (optional extra).
- Minimal determinism leakage:
  - User code looks like normal async functions. The SDK persists and replays I/O boundaries (ctx.run/awaitables) without forcing pervasive import guards.

## Fit to Flock Architecture

- Orchestration model
  - Flock’s orchestrator runs an agent → evaluates → routes next_agent → repeats. In Restate, this maps to a `Workflow` or `Service` that awaits sub‑calls and external events. The “determine_next” logic remains a step in the same durable function, without splitting into separate activities unless desired for isolation.

- State and context
  - FlockContext (history, variables, run_id) can be serialized into Restate state or passed through workflow invocations. Durable state allows appending history and awaiting events (e.g., tool callbacks or user inputs) without extra staging tables.

- Reactivity and pub/sub (1.0 pitch)
  - Restate’s event primitives and messaging fit the “SubscriptionComponent” and reactive agent ideas. A workflow can `await` on timers, awakeables, or inbound messages while maintaining context; a `VirtualObject` can encapsulate long‑lived agent state or subscriptions keyed by identity.

- Tools and MCP
  - MCP servers integrate well: tool calls can be awaited directly inside a durable step (`ctx.run("tool", ...)`), or modeled as messages that the workflow waits for. This reduces the need to split tool calls into Temporal activities for determinism reasons.

## Advantages Over Temporal (for our use case)

- Less intrusive determinism handling:
  - Fewer `unsafe.imports_passed_through()` shims; evaluation component and logging can remain clean async code, with Restate persisting effects at call sites.

- Simpler async code = closer to mental model:
  - “Durable async/await” reads like normal Python. Orchestrating tools, timers, and user events feels like normal asyncio (“await event; then continue”), which is a strong fit for agent workflows.

- Reactive features built‑in:
  - Pub/sub style event flows and durable waiting out‑of‑the‑box; aligns with Flock’s future 1.0 ideas (subscriptions, reactivity) without introducing another broker.

- Multi‑language and SDK maturity
  - Python SDK is present in vendor, with examples; TypeScript/Java SDKs can power sidecar services if needed.

## Trade‑Offs and Risks

- Ecosystem delta:
  - Temporal has a large ecosystem and proven operations at scale; Restate is newer (though actively developed). We’d want a measured rollout: optional engine first, production later.

- Operational footprint:
  - Requires running Restate server/ingress. We’d need dev‑mode guidance similar to our Temporal helpers (docker compose, “start restate server” task) and cloud deployment patterns.

- Feature parity
  - Some Temporal features (advanced visibility, long‑lived cron workflows) have different idioms in Restate. We’ll need mapping docs and examples for contributors.

## Proposed Integration Design

1) Add RestateExecutor alongside Temporal and Local
   - File: `src/flock/core/execution/restate_executor.py` (new)
   - Responsibilities:
     - Wrap Restate Python SDK entrypoints; expose `run_workflow(flock, context, start_agent)` that mirrors `run_temporal_workflow`.
     - Provide dev bootstrap helpers (connect to server at env URL; register handlers if needed; or call via ingress HTTP).

2) Map Flock.run() to engines via a switch
   - Extend `FlockExecution` to dispatch to local/temporal/restate based on `enable_temporal` vs a new `enable_restate` flag or an `execution_engine="local|temporal|restate"` enum.

3) Workflow shape in Restate
   - Create a `restate.Workflow` named e.g. `FlockWorkflow` with a `run(ctx, args)` handler:
     - Initialize `FlockContext` from args; set `run_id`.
     - Loop: evaluate agent (call into DeclarativeEvaluationComponent as normal async); append history; decide `next_agent` (router); continue until done.
     - Await external events optionally (e.g., if a component sets `await_event(topic)`).
   - Keep evaluation and routing inside the same durable function; use `ctx.run("tool", ...)` wrapping for bounded I/O if needed.

4) Reactive pub/sub surface
   - Add a `SubscriptionComponent` prototype (opt‑in) that registers interest in an event/topic and exposes helpers to publish or attach to running workflows. Under the hood, it uses Restate “awakeables” or durable futures to pause and resume the workflow.
   - Introduce `agent.subscribe_to(topic, handler=...)` sugar that installs a listener and resumes the flow when messages arrive.

5) Tool/MCP integration
   - Short‑term: keep current MCP client/manager; invoke tools from within the Restate workflow using async calls and await the result; no special wrapping required.
   - Longer‑term: let tools push back results via a Restate endpoint to resume waiting workflows (for long‑running external tasks).

6) Observability and logging
   - Use `restate.getLogger()` for evaluation steps to hide replay noise. Keep Flock’s OpenTelemetry spans around orchestration boundaries.

7) Determinism cleanup in core
   - Replace Temporal‑only guards with engine‑specific shims at the executor boundary. Core code (components, logging) shouldn’t import Temporal or Restate directly.

## Migration Plan (Incremental, Low Risk)

Phase A — Spike (engine scaffold, no default change)
- Add Restate executor and a simple `FlockWorkflow` with the agent loop, powered by the existing evaluation/routing components.
- Add `execution_engine` option to `Flock` (default “local”).
- Provide dev instructions to run Restate locally (vendor sdk hints) and a demo example (single agent run).

Phase B — Reactive features
- Implement `SubscriptionComponent` using Restate awakeables; add an example that waits on a user/message event to continue an agent plan.
- Map FlockContext variables/history to Restate durable state; sanity‑check resumption after a simulated failure.

Phase C — Cleanups and parity
- Remove `workflow.unsafe.imports_passed_through()` usages gated by engine (keep for Temporal runs only).
- Align error handling and retries: use Restate’s durable await and timeouts rather than Temporal activity retry for common cases.
- Snapshot tests and serialization remain unchanged; orchestrator engine is transparent to core components.

Phase D — Optional cutover
- Document guidance for choosing engines: Temporal for existing deployments; Restate for reactive/evented agents and minimal determinism boilerplate.
- Keep both engines supported; allow per‑Flock choice.

## Testing Strategy

- p0: local execution unchanged; the new engine code is covered by small integration tests that don’t require a live Restate unless marked.
- integration (opt‑in): start Restate server locally (or use test harness if available) and run a minimal agent workflow; assert resumption after simulated failure; test a subscription wakeup.
- Determinism sanity: heavy imports in evaluation should run without special guards under Restate.

## Open Questions

- Do we want to default to Restate for “reactive” examples in docs while keeping Temporal for “batch orchestration” examples?
- Should we expose a minimal messaging API at the Flock layer (publish/subscribe) or keep it inside components?
- How much of the engine choice do we surface to users (env var vs explicit parameter)?

## Conclusion

Restate aligns strongly with Flock’s goals: contract‑first agents, simple async orchestration, and reactive/event‑driven patterns without determinism hacks bleeding into core code. By adding Restate as an optional engine and steering reactive features to it, we can reduce Temporal‑specific boilerplate (unsafe import guards, activity scaffolding) and deliver cleaner, more powerful agent workflows—especially for the “Subscriptions/Reactiveness” planned for 1.0—while keeping Temporal available for teams already invested in it.

