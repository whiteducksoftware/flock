## Context

Current OpenClaw engine flow is single-output shaped:
- schema and output declaration are read from `output_group.outputs[0]`,
- payload contract requests one JSON object,
- parse path expects one object,
- one artifact is applied/materialized.

This conflicts with Flock fan-out declarations where one output declaration can represent N artifacts via fixed/range fan-out.

## Goals

- Add robust fan-out support for OpenClaw engine with parity to Flock output semantics.
- Keep strict typed artifact validation per item.
- Preserve backward compatibility for non-fan-out outputs.
- Fail explicitly on unsupported/ambiguous contracts.

## Non-Goals

- Multi-output-type envelope design in a single OpenClaw response.
- Changes to orchestrator scheduling semantics.
- New provider transport APIs.

## Design Decisions

### Decision 1 — Branch payload contract by output cardinality
- **Decision:** If output declaration is fan-out (`fan_out` present or count > 1), generate an array schema contract; otherwise keep object schema contract.
- **Rationale:** Makes contract explicit and machine-checkable using structured response schema.

### Decision 2 — Preserve single-type output-group limit in OpenClaw mode
- **Decision:** If `len(output_group.outputs) > 1`, fail fast with explicit unsupported message.
- **Rationale:** Existing OpenClaw contract has no stable multi-type envelope format; silent partial handling is unsafe.

### Decision 3 — Engine-side fan-out contract enforcement
- **Decision:** Enforce counts before artifact materialization finalization:
  - fixed: exact count required,
  - range: minimum required; maximum enforced.
- **Rationale:** Avoid silent under-delivery for dynamic fan-out and provide actionable failures.

### Decision 4 — Maintain one-repair-then-fail parsing strategy
- **Decision:** Reuse existing parser/repair policy for malformed responses, extended to list mode.
- **Rationale:** Consistency with current OpenClaw robustness behavior.

### Decision 5 — v1 count violations use full-request retry (no partial-accept)
- **Decision:** For fixed/range count violations, retry the full request payload in v1 rather than attempting partial-accept or "fill missing N" stitching.
- **Rationale:** Keeps retry loop deterministic and avoids complex partial-array reconciliation logic in first implementation.
- **Future consideration:** Add optional partial-accept/fill strategy in a later phase if needed.

## Implementation Plan

1. Add output cardinality resolver helper in engine:
   - identify fixed / range / single behavior,
   - produce item schema + array schema when needed.
2. Update payload builder to emit array-schema text.format contract for fan-out.
3. Extend parse/materialization flow:
   - parse list response for fan-out mode,
   - validate item objects against output spec,
   - apply output declaration per item with shared metadata.
4. Add fan-out count checks and integrate with retry policy.
5. Add fail-fast guard for multi-output groups in OpenClaw mode.

## Test Strategy

### Unit Tests (`tests/test_openclaw_engine.py`)
- fan-out payload contract (array schema, min/max or exact constraints in prompt/schema).
- parser accepts valid list and materializes N artifacts.
- fixed mismatch triggers retry/failure path.
- dynamic under-min triggers retry/failure path.
- dynamic over-max truncates + warning path.
- non-array response for fan-out triggers parse/contract error.
- multi-output-group fail-fast error.

### Integration Tests (`tests/integration/openclaw/test_openclaw_pipeline.py`)
- OpenClaw agent with fixed fan-out publishes N artifacts into store.
- OpenClaw agent with dynamic fan-out range publishes in-range N artifacts.
- downstream native agent consumes all fan-out artifacts (pipeline compatibility).

## Risks / Trade-offs

- Prompt/schema complexity for array responses may increase malformed outputs for weak prompts.
- Enforcing dynamic minimum as hard failure may surface existing workflows that relied on warning-only behavior.

## Mitigations

- Keep concise but explicit instructions in payload for list count requirements.
- Add clear runtime error messages with expected vs actual counts.
- Maintain retries for transient/model-format failures.

## Open Questions

1. Should dynamic over-max truncate (current design) or hard-fail for stricter contracts?
2. Should we optionally support a configurable `strict_dynamic_min` flag, or keep under-min strict by default?
