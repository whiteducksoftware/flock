## Why

Phase 1 of OpenClaw integration should ship as a **test-first implementation** because it introduces a new execution backend (remote runtime over HTTP) into Flock’s core agent loop. The current codebase has strong engine, orchestration, and safety contracts; we should preserve those contracts by anchoring the rollout in existing test patterns before writing production code.

## What Changes

- Add Phase 1 OpenClaw integration as an engine-backed execution path that preserves existing Flock semantics.
- Add configuration objects for OpenClaw gateways + aliases, including env-based loading.
- Add `flock.openclaw_agent("alias")` builder sugar that maps to engine wiring (DX parity with existing fluent API).
- Implement spawn-mode invocation with strict structured-output validation for single output type.
- Add deterministic failure mapping for transport/auth/timeout/schema failures.
- Add TDD-first test suites (unit + integration style) modeled after current engine, webhook, and builder tests.
- Initialize OpenSpec + Beads in repo and create an execution DAG derived from the OpenSpec tasks.

## Capabilities

### New Capabilities
- `openclaw-engine-integration`: Add OpenClaw as a first-class engine-backed execution path for Flock agents.
- `openclaw-config-loading`: Add typed config + env discovery for OpenClaw gateways/aliases.
- `openclaw-tdd-harness`: Add dedicated test suites validating transport contract, schema handling, retries, and builder behavior.

### Modified Capabilities
- _None in OpenSpec baseline yet (repo did not previously use OpenSpec specs)._ 

## Impact

- **Affected code (planned):**
  - `src/flock/core/orchestrator.py` (optional config acceptance + `openclaw_agent` entrypoint)
  - `src/flock/integrations/openclaw/*` (new module)
  - `src/flock/__init__.py` and possibly `src/flock/core/__init__.py` exports
- **Affected tests (planned additions):**
  - new tests under `tests/integration/openclaw/` and `tests/test_openclaw_*.py`
  - targeted additions to `tests/test_agent_builder.py` (builder sugar behavior)
- **Operational:** no breaking behavior to existing agents; OpenClaw path is opt-in.
- **Dependencies:** reuse existing `httpx` and `respx` (already present in dev deps).
