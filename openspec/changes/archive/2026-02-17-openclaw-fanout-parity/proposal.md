## Why

OpenClaw-backed agents currently declare fan-out in Flock (`publishes(..., fan_out=...)`) but the engine path still behaves like single-output execution. The OpenClaw engine builds schema/prompting from only `output_group.outputs[0]`, expects one JSON object, and materializes one artifact. This creates a parity gap versus expected fan-out semantics and caused real confusion in example pipelines (e.g., competitive intelligence scout returning only one profile despite `fan_out=(3, 8)`).

Without dedicated fan-out handling, dynamic fan-out ranges can silently under-deliver in OpenClaw mode, and users cannot trust parity between OpenClaw and non-OpenClaw engine behavior.

## What Changes

- Add OpenClaw engine fan-out-aware request/response handling for single-type output groups.
- For fan-out output declarations, request a JSON **array** of typed objects and materialize one artifact per item.
- Enforce declared fan-out contract at engine boundary:
  - fixed fan-out (`fan_out=N`): exact count required,
  - range fan-out (`fan_out=(min,max)`): minimum required, maximum enforced.
- Preserve existing non-fan-out single-object behavior.
- Add explicit guardrails + errors for unsupported multi-output-type groups in OpenClaw mode (until multi-type envelope support is designed separately).
- Add tests and docs updates so expected fan-out behavior is explicit.

## Scope

### In Scope
- `OpenClawEngine` payload/schema generation for fan-out declarations.
- Parsing/materialization of list responses into multiple artifacts.
- Fan-out count validation logic and retry/failure integration.
- Unit + integration tests for fixed/dynamic fan-out behavior.
- Docs/examples clarifying OpenClaw fan-out semantics and current limits.

### Out of Scope
- Multi-output-type envelope support from one OpenClaw response.
- Cross-agent parallel scheduling changes (orchestrator-level fan-out execution strategy remains unchanged).
- New transport protocols beyond current OpenResponses path.

## Impact

### Affected code (planned)
- `src/flock/integrations/openclaw/engine.py`
- `tests/test_openclaw_engine.py`
- `tests/integration/openclaw/test_openclaw_pipeline.py`
- `docs/guides/openclaw.md`
- `examples/11-openclaw/*` (comments/expectations only if needed)

### Risk
- Fan-out prompt/parse brittleness if model returns malformed list payloads.
- Behavior shift for dynamic range under-minimum (from silent under-delivery to explicit failure) may surface previously hidden issues.

### Mitigations
- Keep strict schema mode + one repair attempt behavior.
- Add focused failure-mode tests for under/over bounds and non-array responses.
- Keep implementation scoped to single-type output groups with clear fail-fast messaging for unsupported cases.
