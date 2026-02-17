## 1. Discovery + Workflow Bootstrap

- [x] 1.1 (flock-repo-cv4.1) Perform deep test landscape discovery (collect suites, identify relevant patterns, run representative baseline tests).
- [x] 1.2 (flock-repo-cv4.1) Initialize OpenSpec in `flock-repo`.
- [x] 1.3 (flock-repo-cv4.1) Initialize Beads in `flock-repo`.
- [x] 1.4 (flock-repo-cv4.1) Commit planning/bootstrap artifacts on `feat/openclaw`.

## 2. Test Harness for OpenClaw Config + Builder (TDD first)

- [x] 2.1 (flock-repo-cv4.2) Add failing tests for `OpenClawConfig` defaults/validation in `tests/test_openclaw_config.py`.
- [x] 2.2 (flock-repo-cv4.2) Add failing tests for `OpenClawConfig.from_env()` discovery and missing field failures in `tests/test_openclaw_config.py`.
- [x] 2.3 (flock-repo-cv4.4) Add failing tests for `flock.openclaw_agent(alias)` happy path and unknown alias failure in `tests/test_openclaw_builder.py`.
- [x] 2.4 (flock-repo-cv4.3, flock-repo-cv4.5) Implement config + builder code to make 2.1–2.3 pass in `src/flock/integrations/openclaw/*.py` + `src/flock/core/orchestrator.py`.
- [x] 2.5 (flock-repo-cv4.5) Run focused suite (`tests/test_openclaw_config.py`, `tests/test_openclaw_builder.py`) and update assertions/messages for deterministic errors.

## 3. Test Harness for OpenClaw Engine Transport (TDD first)

- [x] 3.1 (flock-repo-cv4.6) Add failing unit tests for spawn request payload formation in `tests/test_openclaw_engine.py`.
- [x] 3.2 (flock-repo-cv4.6) Add failing unit tests for response parsing (valid JSON path) in `tests/test_openclaw_engine.py`.
- [x] 3.3 (flock-repo-cv4.6) Add failing unit tests for malformed JSON + single repair attempt in `tests/test_openclaw_engine.py`.
- [x] 3.4 (flock-repo-cv4.6) Add failing unit tests for timeout/auth/transport failure mapping in `tests/test_openclaw_engine.py`.
- [x] 3.5 (flock-repo-cv4.7) Implement `OpenClawEngine` transport + parser + error mapping to satisfy 3.1–3.4 in `src/flock/integrations/openclaw/engine.py`.
- [x] 3.6 (flock-repo-cv4.7) Add/validate retry policy tests (retriable vs fail-fast conditions) in `tests/test_openclaw_engine.py`.

## 4. End-to-End Integration in Flock Pipeline (TDD first)

- [x] 4.1 (flock-repo-cv4.8) Add failing integration test in `tests/integration/openclaw/test_openclaw_pipeline.py`: `openclaw_agent(...).consumes(...).publishes(...)` produces validated artifact.
- [x] 4.2 (flock-repo-cv4.8) Add failing integration test in `tests/integration/openclaw/test_openclaw_pipeline.py` for mixed pipeline (OpenClaw + standard agent).
- [x] 4.3 (flock-repo-cv4.9) Implement orchestrator/export wiring to satisfy integration behavior across `src/flock/core/orchestrator.py`, `src/flock/__init__.py`, and `src/flock/core/__init__.py`.
- [x] 4.4 (flock-repo-cv4.9) Add remaining trace metadata propagation assertions for label fields in `tests/integration/openclaw/test_openclaw_pipeline.py` (correlation assertion already present).

## 5. Hardening + Validation

- [x] 5.1 (flock-repo-cv4.10) Run target suites:
  - `tests/test_agent_builder.py`
  - `tests/test_engines.py`
  - new OpenClaw test files
  - selected integration tests
- [x] 5.2 (flock-repo-cv4.10) Run lint/format on touched files.
- [x] 5.3 (flock-repo-cv4.10) Update docs/spec references for implemented Phase 1 details.
- [x] 5.4 (flock-repo-cv4.10) Final review pass with Claude before implementation merge progression.
