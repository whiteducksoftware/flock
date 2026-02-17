## Why

OpenClaw parity is now complete for transport, fan-out, context/batch, and streaming, but one major compatibility gap remains: **multi-output groups** (`publishes(TypeA, TypeB, ...)`) currently fail fast.

For practical parity with native/DSPy-style agent patterns, one OpenClaw activation should be able to return multiple typed outputs in a single response without splitting into multiple OpenClaw calls.

From discussion, we want a merged approach between:
- Claude Option A (single-call envelope), and
- Codie’s slot-oriented deterministic mapping and per-slot cardinality handling.

## What Changes

This change proposes **Envelope v1** for multi-output groups:

1. Use a **single OpenResponses call** for multi-output groups.
2. Require a deterministic envelope keyed by output slot/type:
   - top-level object with named output entries.
3. Per-slot value shape is declaration-driven:
   - non-fan-out slot → one object,
   - fan-out slot → array with declared cardinality bounds.
4. Validate each slot against its declared Pydantic schema and materialize artifacts per slot.
5. Apply strict matching rules in v1:
   - unknown slots fail,
   - missing required slots fail,
   - count violations follow existing retry/repair behavior.

## Scope

### In scope
- OpenClaw engine contract + parsing path for multi-output groups.
- Prompt/schema contract for multi-output envelope in `json_schema` and `prompt_only` modes.
- Unit + integration coverage for mixed output-group scenarios.
- OpenSpec + docs updates.

### Out of scope
- Tool forwarding/ReAct behavior.
- Multiple OpenClaw calls per output group (sequential split strategy).
- Optional output slots (v2+ discussion).
- New builder API changes (e.g., explicit alias parameter) unless required to resolve collisions.

## Risks

- Envelope complexity may reduce model adherence versus single-output flows.
- Slot-name collisions can be ambiguous without an explicit aliasing strategy.

## Mitigation

- Strict schema + explicit prompt contract.
- Deterministic slot-name resolution and fail-fast on ambiguous collisions.
- Keep single-output fast path untouched for backward compatibility.
