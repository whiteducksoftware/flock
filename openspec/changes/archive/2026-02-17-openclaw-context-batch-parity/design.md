## Context

OpenClawEngine now has transport + fan-out + streaming parity foundations, but request shaping still lags native DSPy semantics in key places:
- context history (`ctx.artifacts`) is not injected,
- batch mode (`ctx.is_batch`) is not explicitly represented,
- output group description is ignored,
- `response_mode` appears as config surface but not active behavior,
- no explicit engine-level `instructions` override.

Tool forwarding/ReAct parity is intentionally excluded: OpenClaw executes tools server-side.

## Goals

1. Implement context-history parity as top priority.
2. Add explicit batch-aware request shaping.
3. Wire output group description into OpenClaw request guidance.
4. Resolve config parity (`instructions` override + `response_mode` decision).
5. Keep behavior deterministic and test-driven.

## Non-Goals

- Passing `agent.tools`/MCP definitions through Flock to OpenClaw.
- Implementing client-side ReAct loop in OpenClaw engine.
- Streaming changes.

## Design Decisions

### Decision 1 — Context-first implementation
- **Decision:** add context serialization path first, with bounded and deterministic formatting.
- **Rationale:** highest user-facing parity gap and requested priority.

### Decision 2 — Batch as explicit prompt/input mode
- **Decision:** when `ctx.is_batch` is true, include clear batch instruction and batch-shaped inputs.
- **Rationale:** avoids implicit/fragile interpretation by gateway model.

### Decision 3 — Output group description is additive guidance
- **Decision:** append `group_description` to request instructions/task text rather than replacing agent-level instructions.
- **Rationale:** preserves existing behavior while restoring missing guidance channel.

### Decision 4 — response_mode cleanup by behavior gate
- **Decision:** if only `json_schema` remains supported, remove dead public knob; otherwise implement explicit branch behavior and tests.
- **Rationale:** avoid misleading configuration fields.

### Decision 5 — Tools remain architecture non-goal
- **Decision:** no Flock-side tool forwarding in this change.
- **Rationale:** OpenClaw already owns tool orchestration.

## Implementation Plan

1. Add context formatting helper(s) in OpenClaw engine and inject into payload build flow.
2. Add batch-aware request composition branch (`ctx.is_batch`) with tests.
3. Inject `group_description` into request guidance.
4. Add `instructions` override surface and precedence logic.
5. Resolve `response_mode` path (implementation or removal) with migration-safe tests.
6. Add integration tests for context and batch behavior with stable fixtures.
7. Update docs guide sections for context + batch + config semantics.

## Test Strategy

### Unit Tests
- payload includes context section when `ctx.artifacts` present.
- payload omits context when absent.
- batch mode toggles request instruction/input shaping.
- group description appears in prompt/task text.
- instructions override precedence over agent.description.
- response_mode behavior tests (or API removal tests).

### Integration Tests
- OpenClaw pipeline uses upstream context artifacts in downstream request behavior.
- batch-triggered OpenClaw path behaves as expected with BatchSpec flow.
- mixed OpenClaw + native pipeline remains compatible.

## Risks / Trade-offs

- Context payload growth can impact token efficiency.
- Batch representation might need iteration to match expected model quality.

## Mitigations

- Keep context representation concise (schema-validated payload summaries).
- Bound context entries and include deterministic ordering.
- Add regression tests for prompt shape stability.
