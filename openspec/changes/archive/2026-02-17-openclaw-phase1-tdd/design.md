## Context

Flock currently has a large and mature pytest surface (~2160 collected tests) with strong coverage in engine behavior, orchestration semantics, security hardening, and configuration models.

Key observed suites relevant to OpenClaw Phase 1:
- `tests/test_agent_builder.py` — builder semantics, output groups, engine invocation patterns.
- `tests/test_engines.py` — engine integration behavior and error handling.
- `tests/test_engine_context.py` + `tests/test_context_security.py` — security invariants for engine context (pre-filtered artifacts, immutable context, no store/provider access).
- `tests/api/test_webhook_e2e.py` — practical retry patterns using `respx` for HTTP mocking.
- `tests/test_dspy_engine.py` — config/env resolution patterns and parser behavior conventions.
- `tests/contract/*` — contract-style tests for deterministic behavior.

Sanity executions run during discovery:
- `uv run pytest tests/test_engine_context.py tests/test_context_security.py -k "engine" -q` → 8 passed.
- `uv run pytest tests/test_agent_builder.py -k "multiple_publishes_calls_engine_multiple_times or single_publishes_calls_engine_once or fan_out_calls_engine_once_generates_multiple or engine_calls_are_sequential_not_parallel or error_in_group_stops_subsequent_groups" -q` → 5 passed.
- `uv run pytest tests/api/test_webhook_e2e.py -k "retries_on_server_error or gives_up_after_max_retries" -q` → 2 passed.

Constraints:
- Preserve Flock semantics and DX (OpenClaw is engine-path, not orchestration fork).
- Maintain deterministic error behavior.
- Keep Phase 1 scoped to spawn mode + single output type.

## Goals / Non-Goals

**Goals:**
- Add OpenClaw engine path with minimal core disruption.
- Deliver Phase 1 using explicit TDD gates before implementation.
- Keep builder API ergonomic (`openclaw_agent`) and consistent.
- Add strong tests for transport, schema validation/repair, retries, and config loading.

**Non-Goals:**
- Session mode implementation (Phase 2+).
- Multi-output-type return envelope from one OpenClaw call.
- Streaming dashboard output from OpenClaw responses.
- Bidirectional publish-back from OpenClaw to Flock.

## Decisions

### Decision 1 — Engine-first implementation with builder sugar
- **Decision:** Implement `OpenClawEngine` in a new integration module; `flock.openclaw_agent(alias, ...)` is sugar that configures an agent with that engine.
- **Rationale:** Aligns with existing `with_engines(...)` architecture and avoids orchestrator special-casing.
- **Alternatives considered:**
  - New agent type in orchestrator: rejected (duplicates execution path + higher maintenance).
  - External plugin only: rejected for initial DX (too much setup friction for core scenario).

### Decision 2 — Phase 1 mode locked to spawn
- **Decision:** Implement spawn-mode transport first, with clean per-invocation context.
- **Rationale:** Deterministic behavior and easier testability; matches current fan-out and output-group semantics.
- **Alternatives considered:**
  - Session-first: rejected (ordering/lock complexity too high for Phase 1).

### Decision 3 — Strict output parse + single repair attempt
- **Decision:** Parse OpenClaw output strictly, run one repair attempt on malformed output, then fail.
- **Rationale:** Balances robustness with deterministic failure behavior.
- **Alternatives considered:**
  - Unlimited repair loop: rejected (unbounded retries + non-determinism).

### Decision 4 — Reuse established test idioms
- **Decision:** New OpenClaw tests follow existing patterns:
  - `respx` for HTTP retry/failure behavior,
  - focused unit tests for config + parsing,
  - integration-style tests for builder + agent execution.
- **Rationale:** Reduces novelty and makes tests legible to existing maintainers.

### Decision 5 — Test-first task order is mandatory
- **Decision:** For each implementation slice, write/land failing tests first, then implement.
- **Rationale:** User explicitly requested test-driven rollout; current repo culture already supports TDD-style files.

### Decision 6 — Exception mapping uses existing Flock error idioms in Phase 1
- **Decision:** Reuse existing exception idioms rather than introducing a new OpenClaw exception hierarchy in Phase 1.
  - Configuration/alias/env validation errors → `ValueError`
  - Remote execution/transport/timeout/parse failures → `RuntimeError`
  - Type registry and artifact type issues continue to use existing `RegistryError`
- **Rationale:** Keeps behavior consistent with current engine/config tests and avoids premature error-class proliferation.
- **Alternatives considered:**
  - New `OpenClaw*Error` classes in Phase 1: rejected (extra API surface before behavior stabilizes).

## Risks / Trade-offs

- **[Risk] Error taxonomy mismatch with existing exceptions** → **Mitigation:** Define explicit mapping table in tests first and assert exact error class/messages.
- **[Risk] HTTP transport tests become flaky** → **Mitigation:** Use `respx` mock transport only; avoid external network in tests.
- **[Risk] Builder sugar bypasses existing validation expectations** → **Mitigation:** Add contract tests in builder suite for alias missing/invalid config paths.
- **[Risk] Over-scoping Phase 1** → **Mitigation:** Lock Phase 1 to spawn + single output type; defer session/streaming/bidirectional.
- **[Risk] Init artifacts (`openspec`, `.beads`) create repo noise** → **Mitigation:** Keep initialization minimal, commit only necessary project-level files, and track execution in Beads intentionally.

## Migration Plan

1. Initialize OpenSpec and Beads in repo (done in this planning step).
2. Finalize OpenSpec artifacts (proposal/specs/design/tasks).
3. Import tasks into Beads DAG with explicit dependencies.
4. Execute implementation in TDD order (tests first for each slice).
5. Run focused test suites first, then broaden to full impacted suites.
6. Prepare PR on `feat/openclaw` with planning + implementation increments.

Rollback strategy (if Phase 1 fails quality gates):
- Revert new integration module and builder entrypoint only.
- Existing agent/engine paths remain unaffected by design.

## Open Questions

1. Do we store OpenClaw trace metadata only in logs/span attrs, or also in artifact metadata in Phase 1?
2. Should Phase 1 include optional idempotency headers immediately, or defer to Phase 2 once retry behavior stabilizes?
