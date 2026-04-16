---
title: "refactor: Meta-Orchestrator — ExternalEngineComponent + Findings Cleanup"
type: refactor
status: completed
date: 2026-04-16
origin: docs/reviews/2026-04-16-meta-orchestrator-findings.md
---

# refactor: Meta-Orchestrator — ExternalEngineComponent + Findings Cleanup

## Overview

Replace the `ExternalAgentScheduler` parallel-system architecture with an `ExternalEngineComponent` that participates in the existing engine pipeline, and clear the residual P2/P3 + new P0/P1 findings surfaced by the April 16 review.

The April 12 review hardened the scheduler-based implementation through 19 P0/P1/P2 fixes and 233 passing tests. The April 16 review (and the SFD vs spec-driven retro the same day) showed that the core abstraction itself was wrong — R15's "external agents do NOT use `EngineComponent.evaluate()`" forced a parallel execution path that duplicates what `AgentScheduler` + `EngineComponent` already do. This plan reverses R15: external agents become a different *engine*, not a different *scheduling concern*.

The changelog stream, SSE/cursor API, retention policy, and adapter subprocess code (~1,000 LOC) are preserved as standalone-useful infrastructure. The `ExternalAgentScheduler`, scheduler-side `StreamDispatcher` coupling, REST return path, and the auth tokens that exist *only* to authenticate that return path (~700 LOC) are removed. Token auth becomes opt-in for external HTTP clients.

## Problem Frame

The findings report (`docs/reviews/2026-04-16-meta-orchestrator-findings.md`) flagged three classes of issues:

1. **Architectural** — R15 sealed in a parallel scheduling system. The retro at `docs/retro-sfd-vs-spec-driven.md` traced the cost: ~700 LOC of scheduler/dispatcher-coupling/return-path-auth that wouldn't exist if external agents were modeled as engines.
2. **Bugs** — `.produces()` typo in example 02 (will `AttributeError` at runtime), `ExternalSessionStore` defaults to in-memory (resume mode silently breaks across restarts), example 02 still wires infrastructure manually after the auto-wiring commit.
3. **Residual P2/P3 from April 12** — adapter code dedup, retention chunked DELETE, prompt enrichment with traceability metadata, audit log for token lifecycle, guard hook implementation decision, InMemoryTokenStore GC.

The branch is on `feat/meta-orchestrator`, not yet merged. Refactoring before merge is strictly cheaper than after.

## Requirements Trace

Carried forward from origin findings report (priority groups in §6):

**High priority — refactor + critical bugs:**
- R1. Fix `examples/12-external-agents/02_multi_agent_code_review.py:170` — `.produces()` → `.publishes()` (origin §3 bug 1)
- R2. Land the engine-component refactor: external agents implement `EngineComponent.evaluate()`; remove `ExternalAgentScheduler`, scheduler-side `StreamDispatcher` coupling, REST return path, and auto-wiring code that exists only for those (origin §4)
- R3. Migrate both examples to the new engine surface (origin §3 bug 2, §6 rec 3)
- R4. Carve `ChangelogStreamComponent` as an explicitly optional, independently useful add-on (origin §6 rec 5)

**Medium priority — correctness and quality:**
- R5. Make `SQLiteExternalSessionStore` the default; document persistence semantics (origin §3 residual, §6 rec 4)
- R6. Enrich engine context with `correlation_id`, `artifact_id`, and source artifact metadata so external agents have a traceback handle (origin §6 rec 6)
- R7. Land a real benchmark for changelog event emission latency under load (replace the WSL2 15ms one-off) (origin §3 bug 4, §6 rec 7)

**Low priority — cleanup:**
- R8. Extract adapter base class for shared subprocess lifecycle (origin §3 residual, §6 rec 8)
- R9. Chunked retention DELETE (the original April 8 plan promised this; never landed) (origin §3 residual, §6 rec 9)
- R10. InMemoryTokenStore GC for revoked/expired entries (origin §6 rec 10)
- R11. Audit log for token lifecycle events (origin §6 rec 11)
- R12. Decide guard hook: implement on the engine, or remove the references (origin §6 rec 12)

**Auth scope clarification (refactor consequence):**
- R13. Token auth becomes opt-in: needed only for external HTTP clients publishing into Flock from outside the process. External agents called via `ExternalEngineComponent.evaluate()` no longer need auth at all (results return through the engine, not REST). Existing token API surface stays for HTTP-client use cases; tests pass unchanged.

## Success Criteria

- SC1. An external Claude Code agent declared with `.kind("external").adapter("claude_code").consumes(A).publishes(B)` produces a typed `B` artifact when an `A` is published — exercised through the standard `AgentScheduler` → `_run_engines` path, no `ExternalAgentScheduler` involved.
- SC2. Both `examples/12-external-agents/01_*.py` and `02_*.py` execute end-to-end against real Claude Code / Codex CLIs (manual run; documented in example READMEs).
- SC3. `docs/guides/meta-orchestrator.md` and the new examples make no reference to `ExternalAgentScheduler`, `StreamDispatcher`-for-triggering, or REST-return-path tokens. Token docs remain only for HTTP-client integration.
- SC4. `ChangelogStreamComponent` documented as independently useful (dashboards, audit, replay) and works without any external agent registered.
- SC5. The full meta-orchestrator test suite passes (existing + new). Deleted scheduler tests are explicitly inventoried; new engine tests cover the equivalent surface.
- SC6. A measurable changelog-emission benchmark replaces the WSL2 15ms one-off — either passes the original < 5ms p99 / 50 events/sec target, or the README documents the actual sustainable rate as a known limit.

## Scope Boundaries

- **In scope:** Engine refactor for external agents; deletion of scheduler/dispatcher-coupling/return-path-auth-injection code; bug fixes from the findings report; doc/example rewrite; opt-in carving of changelog + token surfaces; benchmark.
- **Out of scope:** New external agent adapters (Gemini CLI, Aider, Copilot); MCP server (piece #5 of the original 7-piece vision); Capability Manifests; Artifact Lineage; Subscription-as-Discovery; Human-as-Agent; cross-machine coordination.

### Deferred to Separate Tasks

- **Dashboard frontend updates** for the new `agent_kind="external"` event shape — backend events already exist; frontend rendering is its own ticket.
- **Production sandboxing guidance** for external agent processes (containers, dedicated users) — operational doc, not code change.
- **OpenClaw migration** to use external agents through the new surface — separate validation exercise after this lands.

## Context & Research

### Relevant Code and Patterns

- **Engine base class:** `src/flock/components/agent/base.py:102` — `EngineComponent` with `evaluate(agent, ctx, inputs, output_group) -> EvalResult`. The exact signature `ExternalEngineComponent` must implement.
- **Reference engine implementation:** `src/flock/engines/dspy_engine.py:122` — shows how to build a signature from `output_group`, run something async, return `EvalResult.from_objects()`. The structural template the external engine mirrors.
- **Engine resolution:** `src/flock/core/agent.py:447` — `_resolve_engines()` returns user-provided engines or defaults to `DSPyEngine`. External agents will provide an `ExternalEngineComponent` here instead.
- **Builder seam:** `src/flock/core/agent.py:913` — `with_engines(*engines)` is the existing engine attachment surface. The `.kind("external").adapter(...)` builder methods should ultimately call this with an `ExternalEngineComponent`, not flag a separate `agent_kind`.
- **Engine execution:** `src/flock/core/agent.py:316` — `_run_engines()` calls `engine.evaluate()` per `OutputGroup`. External engines slot in here unchanged.
- **Adapters (preserved):** `src/flock/integrations/external/adapters/{claude_code.py, codex.py, base.py}` — the `ExternalAgentRuntime` protocol and concrete adapters survive intact. Only the *caller* changes (engine instead of scheduler).
- **Adapter protocol:** `src/flock/integrations/external/runtime.py` — `ExternalAgentRuntime` protocol (`spawn`, `monitor`, `terminate`).
- **Session store:** `src/flock/integrations/external/models.py:105` (in-memory) and `SQLiteExternalSessionStore` (SQLite). `scheduler.py:111` shows the in-memory default that must flip.
- **To delete:** `src/flock/integrations/external/scheduler.py` (686 LOC), `src/flock/core/orchestrator.py:1212-1263` (auto-wiring block for ExternalAgentScheduler).
- **To preserve:** `src/flock/models/changelog.py`, `src/flock/storage/sqlite/schema_manager.py` (v4 migration), `src/flock/components/server/changelog/`, `src/flock/components/orchestrator/retention.py`, `src/flock/components/server/auth/`, `src/flock/auth/`.
- **Auto-wiring counterpart:** `src/flock/core/orchestrator.py:1183-1210` — the existing `TimerComponent` auto-wiring is the pattern external agent setup should mirror in spirit (detect agent traits → install needed component) but at engine-attach time, not scheduler-install time.

### Institutional Learnings

- **R15 lesson (`docs/retro-sfd-vs-spec-driven.md`):** When ce:ideate frames the problem and ce:plan faithfully implements that framing, no step in the pipeline questions the framing itself. The "user types this" surface checkpoint is the missing gate. Apply here by writing the user-facing surface for the new engine path *before* designing the internal model.
- **WebSocket deadlock (`docs/bugfixes/websocket-streaming-deadlock-fix.md`):** Fire-and-forget with `asyncio.create_task()` is mandatory for any broadcast in an event-producing loop. Still applies to changelog event emission in `ArtifactManager.persist_and_schedule()` — that part doesn't change.
- **April 12 review patterns:** atomic single-transaction persist (artifact + changelog event in one commit), per-token salt SHA-256, stdin-only payload passing, env var allowlisting, cascade depth tracked server-side per `correlation_id`. All of these survive the refactor and apply equally to the engine path.
- **Output normalization at write boundary:** External agents return text; engines must convert to typed Pydantic `output_group` objects with the same validation discipline as `DSPyEngine`. Lesson previously surfaced in ClawBoard and CORAL prior art.

### External References

- DSPy structured output patterns — referenced via `src/flock/engines/dspy_engine.py` for how to coerce LLM output to typed Pydantic models. The external engine reproduces this without DSPy by hand-crafting JSON-schema prompts and validating responses against `output_group.outputs[*].artifact_type`.

## Key Technical Decisions

- **`ExternalEngineComponent` is the unit of integration, not `ExternalAgentScheduler`.** External agents declare `.kind("external").adapter("claude_code")` on the builder; the builder attaches an `ExternalEngineComponent(adapter=...)` instance via the existing `engines` list. From `Agent._run_engines()`'s perspective, an external engine is indistinguishable from `DSPyEngine`. (Reverses origin requirement R15.)
- **Adapter output → typed Pydantic via JSON schema in prompt.** The engine composes a prompt that includes (a) the input artifact(s), (b) the JSON schema(s) of the expected output type(s) from `output_group`, (c) instructions to emit valid JSON. The adapter returns text; the engine parses, validates against each output type, and returns `EvalResult.from_objects(...)`. Validation failure → engine error → standard error path. Mirrors how `DSPyEngine` coerces output, just without DSPy's framework.
- **Changelog stream stays — repurposed as observability, not triggering.** `ChangelogEvent`, store schema v4, SSE, WebSocket, cursor API, retention all remain. `ArtifactManager.persist_and_schedule()` continues to emit events. The *only* consumer that goes away is `ExternalAgentScheduler` subscribing for triggering. Dashboards, replay, audit, external observers all keep working.
- **REST return path and its auth requirement go away.** External engines return results in-process via `evaluate()`. No REST POST back from the spawned subprocess. The `FLOCK_API_TOKEN` / `FLOCK_API_URL` injection in scheduler.py:320 is deleted along with the scheduler.
- **Token auth and `TokenManagementComponent` survive but become opt-in for HTTP clients only.** They are no longer required when external agents are active. Documentation reframes their use case: "for external HTTP clients publishing into Flock," not "for external agent return path." Tests pass unchanged.
- **`SQLiteExternalSessionStore` becomes the default.** The session store moves from a `PrivateAttr(default_factory=ExternalSessionStore)` on the scheduler to a constructor argument on `ExternalEngineComponent` with `SQLiteExternalSessionStore` as the auto-wired default when an orchestrator-level SQLite store is in use. In-memory remains available for tests and the no-persistence opt-out.
- **Builder API surface preserved verbatim.** `flock.agent("x").kind("external").adapter("claude_code").working_dir(...).spawn_timeout(...).consumes(A).publishes(B).session_mode("resume")` continues to work. The user surface is the contract; the internal wiring shift is invisible.
- **Auto-wiring shifts from "install scheduler" to "attach engine."** The auto-detection block at `orchestrator.py:1212` is rewritten: instead of installing an `ExternalAgentScheduler` and a `StreamDispatcher`, it walks external agents at initialization and ensures each has an `ExternalEngineComponent` attached with the right adapter instance. Because `engines` is a list, this is idempotent and respects user-supplied engines.
- **Cascade depth + visibility filtering preserved.** Both safeguards added in the April 12 review work at the `AgentScheduler.schedule_artifact()` layer, not in the now-deleted `ExternalAgentScheduler`. They apply to all agents (internal and external) automatically once external agents are routed through the standard scheduler.
- **Guard hook lives on the engine.** `EngineComponent` already has `on_pre_evaluate` / `on_post_evaluate` lifecycle hooks (`agent.py:338, 354`). `ExternalEngineComponent` calls `guard.scan_input(prompt, [artifact])` in `on_pre_evaluate` and `guard.scan_output(text)` in `on_post_evaluate`. The current commented-out scheduler stub is replaced with a real engine-level implementation. Honors plan R12.
- **Benchmark scope.** A targeted micro-benchmark in `tests/perf/test_changelog_publish_latency.py` measures `persist_and_schedule()` p99 over 1000 publishes. Result is asserted against either the original < 5ms target or a documented relaxed bar; the README captures whichever applies.

## Open Questions

### Resolved During Planning

- **Should we keep `agent_kind` field?** Keep it — useful for dashboards and introspection (the dashboard `agent_kind="external"` event shape exists and works). It's just no longer the discriminator that decides which scheduler runs the agent.
- **Does `with_engines()` need a new shape for external?** No. `ExternalEngineComponent(adapter=ClaudeCodeRuntime(), ...)` is just an `EngineComponent` instance. The auto-wiring path uses it; users can also pass it explicitly.
- **What happens to the 821-line `tests/integration/test_meta_orchestrator_e2e.py`?** Rewritten, not deleted. SC1-SC6 still apply; the test exercises the engine path instead of the scheduler path. Roughly 50% of the test cases (cascade depth, visibility, dashboard events, atomic persist) survive verbatim because they test orchestrator-level behavior; ~50% (REST return path, token-for-spawn, scheduler-queue serialization) get replaced with engine-equivalent tests.
- **Does removing the REST return path break any existing user?** No — the branch is unmerged, so there is no public API consumer. The token API surface is preserved; only its *mandated* use (external agents) goes away.

### Deferred to Implementation

- **Exact prompt template for output schema injection.** Will be tuned during Unit 1 implementation against the real Claude Code / Codex output. Plan-time we know it's "input artifact JSON + output schema JSON + 'reply with valid JSON of this shape'"; the exact wording is execution discovery.
- **Whether `ExternalEngineComponent` is a single class with a registry of adapters, or one subclass per adapter.** Both are tenable; preference is a single class taking an adapter instance, but the implementation may discover that adapter-specific prompt assembly justifies subclasses.
- **Concrete benchmark thresholds on hardware other than WSL2.** Plan commits to running the benchmark; the threshold value and pass/fail decision is execution-time.
- **Whether the changelog event emission can be flagged off entirely.** Possibly worth a `ChangelogConfig.enabled` field for users who want zero overhead; deferred until benchmark numbers come back.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### Before vs After (the architectural shift)

```
BEFORE (current scheduler-based)
─────────────────────────────────
publish(A)
  → ArtifactManager.persist_and_schedule(A)
    → Store: INSERT artifact + INSERT changelog_event (atomic)
    → AgentScheduler.schedule_artifact(A)         ── for internal agents
    → StreamDispatcher.publish(event)             ── for external agents
       └→ ExternalAgentScheduler queue → adapter.spawn → subprocess
            └→ subprocess HTTP POST /api/v1/artifacts (Bearer <token>)
                 └→ AuthMiddleware → publish(B) → repeats

AFTER (engine-based)
─────────────────────
publish(A)
  → ArtifactManager.persist_and_schedule(A)
    → Store: INSERT artifact + INSERT changelog_event (atomic)
    → AgentScheduler.schedule_artifact(A)         ── ALL agents
       └→ Agent._run_engines(...)
            ├→ DSPyEngine.evaluate(...)           [internal]
            └→ ExternalEngineComponent.evaluate(...) [external]
                 └→ adapter.spawn → subprocess → text
                 └→ parse JSON → validate against output_group types
                 └→ return EvalResult → publish(B) → repeats

  StreamDispatcher (preserved, observation only)
    → SSE / WebSocket / cursor API → dashboards, audit, replay
```

### `ExternalEngineComponent.evaluate` flow

```
async def evaluate(agent, ctx, inputs, output_group) -> EvalResult:
    # 1. Compose prompt
    prompt = compose_prompt(
        instructions=agent.description,
        inputs=[a.payload for a in inputs.artifacts],
        output_schemas=[o.artifact_type.model_json_schema() for o in output_group.outputs],
    )
    # 2. Resolve session
    session_id = session_store.get(agent.name) if session_mode == "resume" else None
    # 3. Spawn via adapter
    config = SpawnConfig(prompt=prompt, working_dir=..., session_id=session_id, ...)
    result = await adapter.spawn(config)
    outcome = await adapter.monitor(result)
    # 4. Parse + validate
    parsed = json.loads(outcome.stdout_payload)
    objects = [Type.model_validate(parsed[i]) for i, Type in enumerate(output_types)]
    # 5. Persist session
    if session_mode in ("new", "resume"):
        session_store.set(agent.name, outcome.session_id)
    # 6. Return typed EvalResult
    return EvalResult.from_objects(*objects, agent=agent)
```

`on_pre_evaluate` and `on_post_evaluate` hook in here for guards (R12).

### Component lifecycle change

| Component | Before | After |
|-----------|--------|-------|
| `ChangelogStreamComponent` | Required when external agents present | Optional, opt-in for observability |
| `ExternalAgentScheduler` | Auto-wired when external agents present | **Deleted** |
| `StreamDispatcher` (for triggering) | Auto-wired alongside scheduler | **Deleted** (the dispatcher class survives for SSE/WS observers) |
| `AuthenticationComponent` + `bearer_token` handler | Required when external agents present | Optional, only for HTTP clients |
| `TokenManagementComponent` | Required when external agents present | Optional, only for HTTP clients |
| `ExternalEngineComponent` | Did not exist | Auto-attached to agents with `kind="external"` |

## Implementation Units

### Phase 1 — Engine surface (foundation)

- [x] **Unit 1: ExternalEngineComponent + adapter glue**

**Goal:** Implement `ExternalEngineComponent` that wraps an `ExternalAgentRuntime` adapter and produces typed `EvalResult`s through the existing engine pipeline.

**Requirements:** R2, R6

**Dependencies:** None (adapters already exist, engine base class already exists)

**Files:**
- Create: `src/flock/integrations/external/engine.py`
- Modify: `src/flock/integrations/external/__init__.py` (export new symbol)
- Test: `tests/test_external_engine.py`

**Approach:**
- Subclass `EngineComponent`. Constructor takes `adapter: ExternalAgentRuntime`, `working_dir: str`, `spawn_timeout: float`, `session_mode: Literal["new","resume"] | None`, `session_store: ExternalSessionStore | SQLiteExternalSessionStore | None`, optional `additional_env: dict[str, str]`.
- `evaluate(agent, ctx, inputs, output_group)`:
  1. Compose prompt: agent description + serialized input artifacts + JSON schema(s) of output type(s) + "respond with valid JSON matching this schema" instruction.
  2. Resolve session via `session_store.get(agent.name)` if `session_mode == "resume"`; fall back to `new` with a logged warning if missing.
  3. Build `SpawnConfig` (no token env vars — that's deleted with the REST path).
  4. `adapter.spawn(config)` → `adapter.monitor(result)` with `wait_for(timeout)`.
  5. Parse output text as JSON. Validate against each `output_group.outputs[*].artifact_type` via Pydantic `model_validate`.
  6. On parse/validate failure: raise so the agent's existing error path takes over.
  7. `session_store.set(agent.name, outcome.session_id)` for both new and resume modes.
  8. Return `EvalResult.from_objects(*objects, agent=agent)`.
- Cascade depth and visibility are **not** the engine's concern — they're handled by `AgentScheduler.schedule_artifact()` upstream, which already covers all agents.

**Patterns to follow:**
- `src/flock/engines/dspy_engine.py` for `evaluate()` shape and `EvalResult.from_objects()` use
- `src/flock/components/agent/base.py:102` (`EngineComponent` base) for hook surface
- Existing adapter spawn/monitor pattern in `src/flock/integrations/external/scheduler.py:_handle_event` (the parts that wrap adapter calls — copy the spawn semantics, drop the queue/REST/auth scaffolding)

**Test scenarios:**
- Happy path: Mock adapter returns valid JSON for a single output type → `evaluate` returns `EvalResult` with one validated artifact
- Happy path: Multi-output `output_group` → adapter JSON list parsed into multiple typed artifacts
- Happy path: `session_mode="resume"` with stored session → adapter `SpawnConfig.session_id` is populated
- Happy path: `session_mode="resume"` with no stored session → falls back to `new`, warning logged, runs successfully
- Happy path: `session_mode="new"` → adapter called without `session_id`
- Happy path: Outcome `session_id` is stored after both new and resume runs
- Edge case: Adapter returns valid JSON but schema mismatch → `ValidationError` propagated (caught by agent error path)
- Edge case: Adapter returns non-JSON text → `JSONDecodeError` propagated
- Edge case: Adapter timeout → `asyncio.TimeoutError` propagated, no zombie process (adapter cleanup)
- Edge case: Empty `output_group.outputs` → engine returns empty `EvalResult` (matches `DSPyEngine` behavior for side-effect agents)
- Error path: Adapter raises during `spawn` → engine raises, no session state mutated
- Integration: With `SQLiteExternalSessionStore`, sessions persist across engine instance recreation
- Integration: `on_pre_evaluate` and `on_post_evaluate` hooks fire (defer guard-specific tests to Unit 6)

**Verification:**
- `ExternalEngineComponent` instances pass `isinstance(_, EngineComponent)`
- A mock-adapter test agent declared with `.with_engines(ExternalEngineComponent(adapter=Mock()))` runs through `Agent._run_engines` end-to-end with no scheduler involved
- Output artifacts have correct types and pass downstream subscription matching

---

- [x] **Unit 2: Builder + auto-wiring rewrite**

**Goal:** Update `.kind("external").adapter(...)` to attach an `ExternalEngineComponent` via the existing engine list, and rewrite the orchestrator's auto-detect block to install engines instead of an external scheduler.

**Requirements:** R2, R5

**Dependencies:** Unit 1

**Files:**
- Modify: `src/flock/core/agent.py` (lines ~1078-1129 for builder methods; engine attachment logic)
- Modify: `src/flock/core/orchestrator.py` (replace auto-wiring block ~1212-1263)
- Test: `tests/test_external_agent_builder.py`

**Approach:**
- The fluent builder methods stay (`.kind`, `.adapter`, `.working_dir`, `.spawn_timeout`, `.session_mode`, `.spawn_env`) — they store config on the `Agent`. Behavior change: at engine resolution, if `agent_kind == "external"` and no engines have been explicitly added, auto-construct an `ExternalEngineComponent` from the agent's stored config + the adapter registry.
- Two viable wiring points: (a) in `Agent._resolve_engines()` — check `agent_kind`, build engine on first call; (b) in orchestrator `_run_initialize` — walk external agents and attach engines proactively. Pick (b) for consistency with existing `TimerComponent` auto-wiring; document the decision in Unit 2's Approach. Either way, the code that previously installed `ExternalAgentScheduler` + `StreamDispatcher`-for-triggering is replaced by code that installs `ExternalEngineComponent` instances on the agents themselves.
- Adapter registry: a small dict at orchestrator init time (`{"claude_code": ClaudeCodeRuntime(), "codex": CodexRuntime()}`) populated based on which `adapter_name`s are present on external agents. Allows users to register additional adapters via `flock.register_external_adapter(name, runtime)` (new method, optional).
- Session store default: `SQLiteExternalSessionStore` when the orchestrator's blackboard store is SQLite-backed, else `ExternalSessionStore`. Engine instances share one store keyed by orchestrator.

**Patterns to follow:**
- `src/flock/core/orchestrator.py:1183-1210` (TimerComponent auto-wiring) for the auto-detection idiom
- `src/flock/core/agent.py:447` (`_resolve_engines`) for default-engine fallback pattern

**Test scenarios:**
- Happy path: Agent with `.kind("external").adapter("claude_code")` gets an `ExternalEngineComponent` with `ClaudeCodeRuntime` adapter at orchestrator initialize
- Happy path: Agent with explicit `.with_engines(ExternalEngineComponent(adapter=Custom()))` keeps the user-supplied engine (auto-wire is idempotent / no-op when engines exist)
- Happy path: Two external agents with different adapters get different engine instances with the right adapters
- Happy path: External agent registered after orchestrator init via `flock.add_agent()` still gets engine attached (or has documented limitation)
- Happy path: `SQLiteExternalSessionStore` is the default when the blackboard is SQLite-backed; `ExternalSessionStore` when in-memory
- Happy path: User-supplied session store via `with_engines(ExternalEngineComponent(session_store=...))` overrides the default
- Edge case: Agent declares `.kind("external")` but no `.adapter(...)` → orchestrator init raises clear error naming the missing adapter
- Edge case: Agent declares unknown adapter name → orchestrator init raises with available adapter list
- Edge case: Mixed internal + external agents → both wire correctly; internal agents unchanged
- Integration: `flock.publish(A)` with an external agent declared end-to-end → typed B artifact produced via the standard `AgentScheduler` → `_run_engines` path

**Verification:**
- No `ExternalAgentScheduler` or scheduler-coupled `StreamDispatcher` is installed for any external-agent scenario
- The previous example 01 (`examples/12-external-agents/01_claude_code_query.py`) runs unchanged against the new wiring
- `flock.list_components()` (or equivalent introspection) shows no external-specific orchestrator components beyond what observers like `ChangelogStreamComponent` opt-in to

---

### Phase 2 — Demolition

- [x] **Unit 3: Delete scheduler, return-path-token-injection, and scheduler-coupled dispatcher wiring**

**Goal:** Remove `ExternalAgentScheduler`, the `set_token_store` / token-injection code that exists only to authenticate the REST return path, and the dispatcher-for-triggering coupling on `ArtifactManager`. Preserve `StreamDispatcher` itself for SSE/cursor observers.

**Requirements:** R2, R13

**Dependencies:** Units 1, 2

**Files:**
- Delete: `src/flock/integrations/external/scheduler.py`
- Modify: `src/flock/integrations/external/__init__.py` (remove `ExternalAgentScheduler` export)
- Modify: `src/flock/orchestrator/artifact_manager.py` (`_notify_dispatcher` / `_stream_dispatcher` reference may stay — used by `ChangelogStreamComponent` observers — but external-scheduler subscription path is gone)
- Modify: `src/flock/core/orchestrator.py` (already covered in Unit 2; double-check no orphaned imports)
- Modify: `src/flock/api/service.py` (remove the type-scope-enforcement-on-publish code added solely for external-agent return path — keep auth middleware as an option for HTTP clients)
- Modify: `src/flock/components/server/auth/auth_component.py` (no functional change but verify nothing references the deleted scheduler)
- Delete: `tests/test_external_runtime.py` (scheduler-specific tests; engine equivalents land in Unit 1's `tests/test_external_engine.py`)
- Modify: `tests/test_external_dashboard.py` (events still work; just verify they fire from the engine path not scheduler path)

**Approach:**
- Audit and delete in this order to keep imports clean: (1) remove scheduler from `external/__init__.py`, (2) remove orchestrator auto-wiring references, (3) delete `scheduler.py`, (4) delete `tests/test_external_runtime.py`, (5) audit `api/service.py` for code that exists only to support spawned-agent REST POSTs and remove it.
- Do **not** delete `StreamDispatcher` class itself — it still serves SSE clients via `ChangelogStreamComponent`. Only the path where the scheduler subscribes to it goes away.
- Do **not** delete token store, token API, or auth handler — they remain for HTTP-client use cases. Just stop *requiring* them when external agents are active.
- Inventory the deletion: produce a short markdown note in `docs/reviews/2026-04-16-meta-orchestrator-findings.md` (append section) listing every file/symbol removed, so the next reviewer can audit completeness.

**Test scenarios:**
- Import test: `from flock.integrations.external.scheduler import ExternalAgentScheduler` raises `ModuleNotFoundError`
- Import test: `from flock.integrations.external import ExternalAgentScheduler` raises `ImportError`
- Existing test pass: `tests/test_token_auth.py`, `tests/api/test_token_api.py` continue to pass (auth surface intact)
- Existing test pass: `tests/api/test_changelog_api.py` continues to pass (SSE/cursor still work)
- Existing test pass: `tests/test_changelog_event.py`, `tests/test_changelog_store.py`, `tests/test_changelog_retention.py` unchanged
- Adversarial: grep the repo for `ExternalAgentScheduler` after deletion — only references should be in the historical plan + retro + this plan

**Verification:**
- Repo-wide grep for `ExternalAgentScheduler` returns only historical/doc files
- `pytest` passes with no scheduler tests; engine tests cover the equivalent surface
- `examples/12-external-agents/01_claude_code_query.py` still runs end-to-end (already auto-wired to the new path via Unit 2)

---

### Phase 3 — Bug fixes from findings report

- [x] **Unit 4: Quick correctness fixes**

**Goal:** Land the small, isolated bug fixes flagged in the findings report.

**Requirements:** R1, R5

**Dependencies:** None (parallel-safe with Phase 1/2)

**Files:**
- Modify: `examples/12-external-agents/02_multi_agent_code_review.py` (line 170: `.produces(ReviewSummary)` → `.publishes(ReviewSummary)`)
- Modify: `src/flock/integrations/external/models.py` (default factory swap; covered in Unit 2 for the engine path, but verify no in-memory default leaks back through other code paths)
- Test: existing example execution + `tests/test_external_engine.py` covers session store

**Approach:**
- The `.produces()` typo is a 1-line fix; landing it as part of this plan rather than a separate hotfix keeps the branch coherent.
- The session store default flips in Unit 2's auto-wiring; this unit confirms the model-level default factory is also `SQLiteExternalSessionStore` (or that the only caller is the engine which sets it explicitly).

**Test scenarios:**
- Happy path: `python examples/12-external-agents/02_multi_agent_code_review.py --dry-run` (or equivalent import smoke test) does not `AttributeError` at line 170
- Edge case: `ExternalEngineComponent()` with no explicit `session_store` and a SQLite blackboard uses `SQLiteExternalSessionStore`
- Edge case: `ExternalEngineComponent()` with no explicit `session_store` and an in-memory blackboard uses `ExternalSessionStore`
- Integration: Resume mode survives an orchestrator restart when SQLite backend is used (sessions read back from DB)

**Verification:**
- Both examples can be imported without error (regression smoke)
- A resume-mode test that restarts the orchestrator successfully reuses the prior session_id

---

### Phase 4 — Examples and documentation

- [x] **Unit 5: Rewrite both examples + meta-orchestrator guide**

**Goal:** Migrate `examples/12-external-agents/01_*.py` and `02_*.py` to the new engine surface (no infrastructure imports). Rewrite `docs/guides/meta-orchestrator.md` to match.

**Requirements:** R1, R3, R4, SC2, SC3, SC4

**Dependencies:** Units 1, 2, 3

**Files:**
- Modify: `examples/12-external-agents/01_claude_code_query.py` (verify no changes needed; it already uses auto-wiring)
- Modify: `examples/12-external-agents/02_multi_agent_code_review.py` (drop manual `InMemoryTokenStore`, `ChangelogStreamComponent`, `AuthenticationComponent`, `ExternalAgentScheduler` wiring; rely on auto-attached engines)
- Modify: `examples/12-external-agents/README.md` (update prose to the engine pattern)
- Modify: `docs/guides/meta-orchestrator.md` (the architecture section, the "How It Works" section, the auth section)
- Create: `docs/guides/changelog-stream.md` (carve out the changelog stream as an independently useful feature — observability, audit, replay — independent of external agents) (R4, SC4)

**Approach:**
- Example 02 should drop from 243 LOC toward ~120-150 LOC after auto-wiring (mirrors example 01's earlier 171 → 101 reduction).
- Guide rewrites should retain the diagrams and quick-start surface; only the internal-architecture descriptions change.
- New `changelog-stream.md` guide documents: when to register `ChangelogStreamComponent`, what events look like, how to subscribe via SSE/WebSocket/cursor, retention configuration. Explicitly notes "useful even without external agents."
- Auth doc reframes: "needed only for external HTTP clients publishing into Flock," not "needed for external agents."

**Patterns to follow:**
- `examples/12-external-agents/01_claude_code_query.py` (the already-clean example; example 02 should look structurally similar)
- `docs/guides/` existing guide format (frontmatter, heading hierarchy, mermaid diagrams)

**Test scenarios:**
- Test expectation: none -- documentation and examples; verified manually per `examples/12-external-agents/README.md` instructions
- Regression: import-only smoke tests (`python -c "import examples.12-external-agents.01_claude_code_query"` equivalent) work for both examples
- Doc lint: no references to `ExternalAgentScheduler`, `set_token_store` (for spawn), or `FLOCK_API_TOKEN` injection in `docs/guides/meta-orchestrator.md`

**Verification:**
- Both examples execute end-to-end against real CLIs (manual; capture output in PR description)
- The new `changelog-stream.md` guide stands alone — a reader without external agents in their workflow finds value in registering the component
- `grep -rE 'ExternalAgentScheduler|FLOCK_API_TOKEN' docs/guides/` returns nothing

---

### Phase 5 — Residual cleanup

- [x] **Unit 6: Guard hook on the engine**

**Goal:** Implement `GuardComponent.scan_input` / `scan_output` integration on `ExternalEngineComponent` (replacing the commented-out scheduler stub).

**Requirements:** R12

**Dependencies:** Unit 1

**Files:**
- Modify: `src/flock/integrations/external/engine.py` (add guard hooks to `on_pre_evaluate` / `on_post_evaluate`)
- Test: `tests/test_external_engine.py` (extend with guard scenarios)

**Approach:**
- `EngineComponent.on_pre_evaluate(agent, ctx, inputs)` — call attached `GuardComponent.scan_input(prompt_text, [artifact_payload_docs])` for each guard; if `safe=False` and `on_input_flagged="block"`, raise `GuardBlockedError`.
- `EngineComponent.on_post_evaluate(...)` — call `scan_output(result_text)` similarly.
- Guards attach to external agents the same way they attach to internal agents — no new API.

**Test scenarios:**
- Happy path: Agent with no guard attached → engine evaluates normally, no guard call
- Happy path: Agent with passing guard → guard called, `evaluate` proceeds
- Error path: Agent with blocking guard, input flagged → `GuardBlockedError` raised pre-spawn, no subprocess spawned
- Happy path: Guard in `warn` mode → spawn proceeds, warning logged
- Integration: `GuardVerdict` details included in any error event

**Verification:**
- The commented-out guard stub in (formerly) scheduler.py has no remaining references in the codebase
- Existing internal-agent guard tests still pass unchanged

---

- [x] **Unit 7: Adapter base class + retention chunked DELETE + token store GC + audit log**

**Goal:** Land the residual P2/P3 cleanup items in one focused unit.

**Requirements:** R8, R9, R10, R11

**Dependencies:** None (parallel-safe with most of the plan)

**Files:**
- Modify: `src/flock/integrations/external/adapters/base.py` (extract shared subprocess lifecycle: env composition, stdin write with BrokenPipe handling, monitor wrapping, terminate sequence)
- Modify: `src/flock/integrations/external/adapters/claude_code.py`, `codex.py` (use new base class methods)
- Modify: `src/flock/core/store.py` (`prune_changelog`: chunk DELETE in batches of 500 with `await asyncio.sleep(0)` between batches)
- Modify: `src/flock/auth/token_store.py` (`InMemoryTokenStore`: add periodic GC of revoked/expired entries, or GC-on-access policy)
- Modify: `src/flock/components/server/auth/auth_component.py` (structured audit log on token verify success/failure/exception via existing logger)
- Modify: `src/flock/components/server/auth/token_management_component.py` (audit log on create/list/revoke)
- Test: `tests/test_changelog_retention.py` (extend with chunked-delete behavior under interleaved publishes)
- Test: `tests/test_token_auth.py` (extend with audit log assertion + GC behavior)
- Test: `tests/test_claude_adapter.py`, `tests/test_codex_adapter.py` (update to assert base-class behavior is reused; no behavioral change)

**Approach:**
- Adapter base class extracts ~50 LOC of duplication. Mirror the existing `ServerComponent` base class style.
- Chunked DELETE: the original April 8 plan promised this; implementation regressed to a single DELETE. Restore the chunked behavior, with a test that verifies publish operations interleave with retention pruning under load.
- Token GC: simple policy is fine — sweep on every Nth verify call, or scheduled via `RetentionPolicyComponent`-style background task. Choose simpler.
- Audit log: structured fields (event, identity_name, prefix, timestamp, outcome). Use existing `logging` infrastructure; do not introduce a new sink.

**Test scenarios:**
- Adapter base: claude_code and codex both use the shared `_build_env` / `_handle_broken_pipe` / `_terminate` methods (verified by patching the base method and observing both adapters use it)
- Chunked DELETE: pruning 5000 events runs in measurable batches with publish calls succeeding interleaved (no head-of-line blocking)
- Token GC: revoked tokens older than retention threshold are removed from the in-memory dict
- Audit log: token create emits a structured log line with identity_name, prefix; token verify failure emits with reason
- Edge case: GC during high concurrent verify load doesn't drop valid tokens

**Verification:**
- Adapter line count drops by ~50 LOC across the two files
- Retention pruning under load passes a stress test (publish + prune concurrent, no deadlocks, no events missed)
- A token lifecycle test asserts the audit log contains expected entries

---

- [x] **Unit 8: Prompt enrichment with traceability metadata**

**Goal:** Replace the lossy `_build_prompt` (which strips `correlation_id` and `artifact_id`) with a structured composition that gives external agents a traceback handle.

**Requirements:** R6

**Dependencies:** Unit 1

**Files:**
- Modify: `src/flock/integrations/external/engine.py` (prompt composition includes correlation_id, artifact_id, source_artifact_type)
- Test: `tests/test_external_engine.py` (assert traceback fields are in the rendered prompt)

**Approach:**
- The prompt template gains a `<context>` section: `correlation_id`, `triggering_artifact_id`, `triggering_artifact_type`, plus the existing input artifact JSON. Output instructions remain the same.
- Optional: include a `respond_with` schema reference that names the expected output type — helps the agent stay focused.

**Test scenarios:**
- Happy path: Prompt for a single-input single-output agent contains `correlation_id`, `artifact_id`, source type name
- Happy path: Multi-input prompt lists all input artifact IDs
- Edge case: Artifact with no `correlation_id` → field omitted, no error
- Integration: Adapter receives the enriched prompt verbatim via stdin

**Verification:**
- Manual sample: a Claude Code agent run produces output that references the source `artifact_id` when asked, confirming the metadata round-trips

---

### Phase 6 — Integration verification + benchmark

- [x] **Unit 9: Rewrite end-to-end integration test**

**Goal:** Rewrite `tests/integration/test_meta_orchestrator_e2e.py` against the engine path. SC1-SC6 are restated where they still apply; SC1 in particular is rewritten to exercise the engine path, not the scheduler path.

**Requirements:** SC1, SC5

**Dependencies:** Units 1-8

**Files:**
- Modify: `tests/integration/test_meta_orchestrator_e2e.py` (substantial rewrite — keep the SC structure, replace scheduler-path tests with engine-path tests)

**Approach:**
- Keep tests that exercise orchestrator-level behavior: cascade depth, visibility filtering, atomic persist, dashboard events. These still apply.
- Replace tests that exercise scheduler-specific behavior (per-agent serial queue, REST return path, token-for-spawn) with engine-equivalent tests where applicable, or delete where the behavior is no longer reachable.
- New SC1 test: publish artifact A → mock-adapter external agent processes via engine path → typed artifact B appears in store → downstream internal agent consumes B → cascade completes.
- Use mock adapters (no real subprocess) for deterministic CI runs; gate real-CLI runs behind an env var (`FLOCK_RUN_REAL_EXTERNAL=1`).

**Test scenarios:**
- SC1 happy path: external engine agent triggers downstream cascade
- SC2 (deferred manual): OpenClaw flow, validated separately
- SC3 happy path: with mock adapters of both types, both engine pipelines exercise correctly
- SC4: covered by Unit 10's benchmark
- SC5: token enforcement still works for HTTP clients (auth tests pass)
- SC6: changelog SSE still streams events (existing test passes)
- Regression: cascade depth fail-safe still triggers at the configured depth
- Regression: visibility filtering still applies to external agents (now via standard scheduler)

**Verification:**
- `pytest tests/integration/test_meta_orchestrator_e2e.py` passes with mock adapters
- Real-CLI gated runs pass when both CLIs are installed (manual)

---

- [x] **Unit 10: Changelog publish latency benchmark**

**Goal:** Replace the WSL2 15ms one-off with a reproducible benchmark of `persist_and_schedule()` under load. Document the actual sustainable throughput as a known limit.

**Requirements:** R7, SC6

**Dependencies:** Phases 1-3 complete (so the measured path is the post-refactor path)

**Files:**
- Create: `tests/perf/test_changelog_publish_latency.py`
- Create: `tests/perf/__init__.py` (if needed)
- Modify: `docs/guides/changelog-stream.md` (record the measured numbers and known limits)

**Approach:**
- Benchmark publishes 1000-5000 artifacts back-to-back, measures p50/p95/p99 of `persist_and_schedule()` latency on both in-memory and SQLite stores.
- Pytest marker (`@pytest.mark.perf`) so the benchmark doesn't run in default CI; documented invocation `uv run pytest -m perf`.
- Benchmark asserts results are recorded to a JSON artifact (or stdout) — the *number* is the deliverable; the test itself only fails on regression beyond a wide tolerance.

**Test scenarios:**
- Happy path: 1000 publishes complete; p99 recorded
- Edge case: SQLite backend with `_write_lock` contention measured separately from in-memory
- Edge case: Concurrent publishes via `asyncio.gather(*[publish() for _ in range(N)])` — assert sequence numbers monotonically increase
- Integration: Benchmark runs alongside an active SSE subscriber to measure observer overhead

**Verification:**
- The numbers are written to `docs/guides/changelog-stream.md` under "Performance characteristics"
- If the original < 5ms target is met, README says so; if not, README documents the actual sustained rate as the known limit

---

## System-Wide Impact

- **Interaction graph:** The big shift is in *which* component drives an external agent. Previously: `ArtifactManager` → `StreamDispatcher` → `ExternalAgentScheduler` → adapter. After: `ArtifactManager` → `AgentScheduler.schedule_artifact()` → `Agent._run_engines()` → `ExternalEngineComponent.evaluate()` → adapter. All other infrastructure (changelog event emission, retention, dashboard events, cascade depth, visibility) is unchanged.
- **Error propagation:** External agent failures now propagate through the standard `EngineComponent` error path (raises in `evaluate()` → caught by `Agent._run_engines()` → `on_error` lifecycle). Dashboard events still fire from the agent's existing lifecycle hooks. The bespoke "monitor task → emit error event → publish error artifact" code in the scheduler is replaced with the engine's standard error handling.
- **State lifecycle risks:** Session state moves from a scheduler `PrivateAttr` to an engine constructor argument. The `SQLiteExternalSessionStore`-by-default decision in Unit 2 mitigates the prior in-memory-only data loss risk on restart.
- **API surface parity:** Builder API (`.kind`, `.adapter`, `.working_dir`, `.spawn_timeout`, `.session_mode`, `.spawn_env`) is preserved verbatim. REST API surface gains nothing; loses nothing public (the deleted code was internal). Token API is unchanged but reframed in docs.
- **Integration coverage:** Cross-layer scenarios that the engine path must prove (covered in Unit 9): publish → subscription match → engine spawn → typed output → downstream cascade. Cross-component scenarios that survive verbatim: cascade depth fail-safe, visibility filtering, atomic artifact+event persist, retention pruning, SSE delivery to observers.
- **Unchanged invariants:** Internal agent scheduling via `AgentScheduler.schedule_artifact()` and `_run_engines()` is unchanged. Dashboard WebSocket at `/plugin/ws` is unchanged. Visibility, fan-out, BatchSpec, JoinSpec, Until DSL, semantic subscriptions are unchanged. The `EngineComponent` base class and `DSPyEngine` are unchanged. The `ChangelogEvent` model, store schema v4, retention policy, SSE/cursor API are unchanged. Token API and auth handler are unchanged (just no longer required for external agents).

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| **Engine pattern can't model long-running agents (minutes per spawn) cleanly within `AgentScheduler`'s expectations** | Verify in Unit 1 that the existing scheduler tolerates long-running engine evaluations. `AgentScheduler.schedule_artifact()` already creates an `asyncio.Task` per engine call — there's no inherent latency assumption. If there are timeout/heartbeat assumptions baked into orchestration components, surface them in Unit 2. |
| **Output schema injection into prompts fails for unstructured agent responses** | The validation step in `evaluate()` raises on parse/validate failure, surfacing the issue immediately. Unit 1 includes a JSON-decode-failure test path. If real CLIs prove unreliable at structured output, fall back to a strict prompt template + retry-with-correction loop (deferred to execution discovery). |
| **Deleting scheduler tests removes coverage for behaviors the engine path doesn't replicate** | Unit 3 produces a deletion inventory; Unit 9 explicitly maps each old SC to either an engine-equivalent test or a documented "no longer applicable" entry. No silent coverage loss. |
| **Auto-wiring shift breaks late-added external agents (`flock.add_agent()` after init)** | Document the limitation (mirrors the existing TimerComponent constraint). If users hit it, add a hot-attach API in a follow-up; not in scope here. |
| **`SQLiteExternalSessionStore` default conflicts with in-memory test fixtures** | Constructor takes an explicit override; auto-wire respects user-supplied stores. Tests that need in-memory pass it explicitly. |
| **Removing the REST return path closes off use cases we don't yet know about (e.g., a remote external agent on another host)** | Cross-machine external agents are explicitly out of scope (matches origin scope). The token API + REST publish endpoint remain available for any HTTP-client publishing into Flock — that path isn't deleted, just no longer required for external agents. |
| **Refactor invalidates the April 12 review's hardening work** | Most April 12 fixes target shared infrastructure (changelog event model, atomic persist, SSE, token API, adapter security) and survive intact. Inventory in Unit 3 confirms which fixes are scheduler-specific vs. shared. The "wasted" hardening (~5 fixes around scheduler internals) is a one-time cost, paid against permanent architectural debt. |
| **Plan re-treads ground covered in original April 8 plan + April 12 review** | Acknowledged. The point of this plan is the architectural reversal of R15 + cleanup of items April 12 left as residual. Implementation reuses 90% of existing code; the delta is structural. |

## Documentation / Operational Notes

- **Update `docs/plans/2026-04-08-001-feat-meta-orchestrator-plan.md`:** add a header note pointing at this plan as a follow-up that supersedes R15.
- **Update `docs/reviews/2026-04-16-meta-orchestrator-findings.md`:** mark recommendations resolved as units land.
- **Append the deletion inventory** (Unit 3) to the findings report so the next reviewer can see what was removed.
- **`docs/guides/meta-orchestrator.md` rewrite is the primary user-facing doc change.**
- **`docs/guides/changelog-stream.md` is a new doc** — surface it from the docs index.
- **Migration note for any consumers:** the branch is unmerged, so there is no migration required for downstream users. The internal architecture change is invisible at the surface.
- **No version bump required** in this branch (internal change). When the branch eventually merges, a feature release note can summarize "external agents land via engine pattern; changelog stream + token auth land as independent opt-in features."

## Sources & References

- **Origin findings report:** [docs/reviews/2026-04-16-meta-orchestrator-findings.md](docs/reviews/2026-04-16-meta-orchestrator-findings.md)
- **Original meta-orchestrator plan (superseded for R15):** [docs/plans/2026-04-08-001-feat-meta-orchestrator-plan.md](docs/plans/2026-04-08-001-feat-meta-orchestrator-plan.md)
- **April 12 prior code review:** [docs/reviews/2026-04-12-meta-orchestrator-review.md](docs/reviews/2026-04-12-meta-orchestrator-review.md)
- **SFD vs spec-driven retro (architectural rationale):** [docs/retro-sfd-vs-spec-driven.md](docs/retro-sfd-vs-spec-driven.md)
- **Engine base class:** `src/flock/components/agent/base.py`
- **Reference engine implementation:** `src/flock/engines/dspy_engine.py`
- **Existing adapters (preserved):** `src/flock/integrations/external/adapters/`
- **Auto-wiring template:** `src/flock/core/orchestrator.py` (TimerComponent block)
- **WebSocket deadlock learning:** `docs/bugfixes/websocket-streaming-deadlock-fix.md`
