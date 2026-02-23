## Why

Two runtime regressions are currently blocking reliable use of `examples/11-openclaw/05_competitive_intelligence.py` and similar pipelines:

1. **Context/input serialization crash**
   - OpenClaw payload shaping uses raw `json.dumps(...)` on artifact payload/context fragments.
   - Non-JSON-native values (for example `datetime`) can appear in those structures.
   - Result: `Object of type datetime is not JSON serializable` at runtime.

2. **Fan-out publish collapse in streaming path**
   - Fan-out producer may generate multiple valid items, but only one artifact is effectively published/observed.
   - Root cause is artifact identity reuse in OpenClaw streaming materialization path (single pre-generated artifact id reused across fan-out artifacts).

These are behavior bugs, not feature gaps, and need a production-grade fix.

## What Changes

This change introduces a focused hotfix with tests:

1. Add JSON-safe serialization for OpenClaw prompt payload composition (both input payloads and context payloads).
2. Ensure fan-out materialization in streaming mode does not reuse one artifact id across multiple artifacts.
3. Add unit/integration regression coverage for both bugs.
4. Update OpenClaw docs with explicit note on serialization safety and fan-out artifact identity behavior.

## Scope

### In scope
- `OpenClawEngine` payload serialization and materialization behavior.
- Regression tests for datetime-bearing payload/context serialization.
- Regression tests for fan-out artifact count + unique identity in streaming path.
- Docs updates.

### Out of scope
- New OpenClaw features.
- Tool forwarding behavior.
- Dashboard visualization redesign.

## Impact

### Affected files (planned)
- `src/flock/integrations/openclaw/engine.py`
- `tests/test_openclaw_engine.py`
- `tests/integration/openclaw/test_openclaw_pipeline.py`
- `docs/guides/openclaw.md`
- `examples/11-openclaw/README.md` (if clarification needed)

### Risks
- Over-aggressive stringification could hide schema errors.
- Artifact-id handling changes could affect streaming UI correlation expectations.

### Mitigation
- Keep serialization helper structural (convert known types, preserve dict/list/object shapes).
- Add explicit tests for fan-out artifact count + uniqueness to catch regressions.
- Preserve current single-output behavior unchanged.