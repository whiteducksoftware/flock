## Context

Current OpenClaw behavior rejects output groups with more than one declaration. This was intentional in earlier parity phases to avoid ambiguous mapping.

We now want multi-output support while preserving:
- one activation → one OpenClaw call,
- typed artifact guarantees,
- deterministic mapping from response JSON to output declarations,
- existing single-output behavior.

## Goals

1. Support `publishes(TypeA, TypeB, ...)` in one OpenClaw evaluation call.
2. Keep mapping deterministic and schema-validated.
3. Reuse existing retry/repair semantics for malformed or contract-violating outputs.
4. Maintain backward compatibility for single-output groups.

## Non-goals

- Tool/ReAct forwarding changes.
- Sequential N-call strategy per output declaration.
- Optional slot production in v1.
- Broad API redesign for output aliasing unless strictly needed.

## Decision: Envelope v1 (merged approach)

We adopt a merged variant of Option A + slot semantics:

- Request asks for one JSON object envelope with named output slots.
- Each slot corresponds to one output declaration.
- Slot value shape follows declaration:
  - no `fan_out` => one object,
  - fixed/range `fan_out` => array with cardinality constraints.

Example:

```json
{
  "Draft": {"draft": "..."},
  "Review": {"verdict": "...", "source": "..."},
  "Alternatives": [
    {"title": "A", "score": 0.8},
    {"title": "B", "score": 0.7}
  ]
}
```

## Slot resolution

v1 slot naming strategy:
1. Use declaration type name as slot key.
2. If keys collide (duplicate type names in group), fail fast with explicit error.
3. Alias support is deferred to a follow-up change and is the real long-term fix for collisions (not a cosmetic enhancement). v1 fail-fast behavior is a guardrail until aliasing exists.

## Contract strictness

- Unknown slot keys: fail.
- Missing required slot keys: fail.
- Slot value type mismatch (object/array mismatch): fail.
- Per-slot schema validation and cardinality validation required before materialization.

## Request shaping

### json_schema mode
- Build strict envelope schema where each slot property is typed per declaration.
- `required` includes all declared slots in v1.
- `additionalProperties=false`.

### prompt_only mode
- Provide explicit textual contract with slot table:
  - slot name,
  - expected schema/type,
  - cardinality rule.

## Materialization

- Parse envelope once.
- For each slot declaration:
  - validate value shape + count,
  - validate payload(s) against output model,
  - materialize artifact(s) with standard metadata/correlation.
- Preserve artifact ordering by declaration order; within fan-out slots, keep source order.

## Test strategy

### Unit
- Envelope schema generation for mixed declarations.
- Parse+validate success for mixed object + fan-out array slots.
- Unknown slot, missing slot, wrong slot shape, and cardinality violations.
- Collision fail-fast behavior.
- `prompt_only` and `json_schema` request shaping.

### Integration
- Mixed OpenClaw pipeline where one activation emits multiple output types and downstream native/OpenClaw agents consume them.
- Retry/repair behavior on malformed envelope.

## Migration / compatibility

- Single-output groups remain on current path (no contract changes).
- Multi-output groups move from fail-fast to envelope contract.
- Existing fan-out behavior for single-output groups remains unchanged.
