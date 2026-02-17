## Context

OpenClaw parity work is complete, but two regressions were found during real example runs:
- prompt payload composition can crash on non-JSON-native values (`datetime`) in context/input artifacts,
- fan-out streaming path can collapse output artifacts due to repeated artifact identity.

## Goals

1. Make OpenClaw prompt serialization robust for JSON-incompatible Python values.
2. Preserve one-artifact-per-fan-out-item behavior in streaming mode.
3. Keep single-output behavior unchanged.
4. Cover regressions with focused tests.

## Non-goals

- Changing orchestrator-level fan-out semantics.
- Changing OpenClaw tool architecture.
- Adding new output contract features.

## Design Decisions

### Decision 1 — Shared JSON-safe normalization helper
- Add/extend a helper in `OpenClawEngine` to normalize prompt payload data to JSON-safe forms.
- Handle common non-JSON-native values (at minimum datetime/date/time/UUID and nested containers).
- Apply it consistently to:
  - input payload fragments,
  - context payload fragments,
  - any prompt-embedded JSON contract blocks derived from runtime values.

### Decision 2 — Streaming fan-out artifact ids must be unique
- Keep pre-generated streaming artifact id behavior for single-output streaming.
- For fan-out outputs, do **not** reuse one artifact id for all items during materialization.
- Let each artifact be created with unique identity (default build path) unless an explicit per-item id strategy is introduced.

### Decision 3 — Regression-first tests
- Add tests proving datetime-bearing payload/context no longer raises serialization errors.
- Add tests proving fan-out publishes all items with distinct ids in streaming-relevant path.

## Implementation Plan

1. Add JSON-safe normalization helper and wire into payload/context prompt serialization paths.
2. Adjust materialization metadata usage so fan-out items do not share one artifact id.
3. Add unit regression tests for serialization + fan-out id uniqueness.
4. Add integration check(s) in OpenClaw pipeline tests where appropriate.
5. Update docs with the clarified behavior.

## Test Strategy

### Unit
- payload builder with `datetime` in input artifact payload does not throw.
- payload builder with `datetime` in context payload does not throw.
- fan-out artifact materialization in streaming path yields multiple artifacts with unique ids.

### Integration
- representative OpenClaw pipeline run with fan-out returns expected artifact count (no collapse to one).

## Risks / Trade-offs

- Stringifying values can reduce type fidelity in prompt context.
- Changing artifact-id behavior may alter dashboard stream/id continuity expectations for fan-out nodes.

## Mitigations

- Keep strict schema validation after generation unchanged (type safety at artifact application remains).
- Scope id-change to fan-out only; keep single-output streaming unchanged.
