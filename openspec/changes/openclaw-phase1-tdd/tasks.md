## 1. Discovery + Workflow Bootstrap

- [x] 1.1 (flock-repo-cv4.1) Perform deep test landscape discovery (collect suites, identify relevant patterns, run representative baseline tests).
- [x] 1.2 (flock-repo-cv4.1) Initialize OpenSpec in `flock-repo`.
- [x] 1.3 (flock-repo-cv4.1) Initialize Beads in `flock-repo`.
- [x] 1.4 (flock-repo-cv4.1) Commit planning/bootstrap artifacts on `feat/openclaw`.

## 2. Test Harness for OpenClaw Config + Builder (TDD first)

- [ ] 2.1 (flock-repo-cv4.2) Add failing tests for `OpenClawConfig` object defaults and validation.
- [ ] 2.2 (flock-repo-cv4.2) Add failing tests for `OpenClawConfig.from_env()` discovery and missing field failures.
- [ ] 2.3 (flock-repo-cv4.4) Add failing tests for `flock.openclaw_agent(alias)` happy path and unknown alias failure.
- [ ] 2.4 (flock-repo-cv4.3, flock-repo-cv4.5) Implement config + builder code to make 2.1–2.3 pass.
- [ ] 2.5 (flock-repo-cv4.5) Run focused suite and update assertions/messages for deterministic errors.

## 3. Test Harness for OpenClaw Engine Transport (TDD first)

- [ ] 3.1 (flock-repo-cv4.6) Add failing unit tests for spawn request payload formation.
- [ ] 3.2 (flock-repo-cv4.6) Add failing unit tests for response parsing (valid JSON path).
- [ ] 3.3 (flock-repo-cv4.6) Add failing unit tests for malformed JSON + single repair attempt.
- [ ] 3.4 (flock-repo-cv4.6) Add failing unit tests for timeout/auth/transport failure mapping.
- [ ] 3.5 (flock-repo-cv4.7) Implement `OpenClawEngine` transport + parser + error mapping to satisfy 3.1–3.4.
- [ ] 3.6 (flock-repo-cv4.7) Add/validate retry policy tests (retriable vs fail-fast conditions).

## 4. End-to-End Integration in Flock Pipeline (TDD first)

- [ ] 4.1 (flock-repo-cv4.8) Add failing integration test: `openclaw_agent(...).consumes(...).publishes(...)` produces validated artifact.
- [ ] 4.2 (flock-repo-cv4.8) Add failing integration test for mixed pipeline (OpenClaw + standard agent).
- [ ] 4.3 (flock-repo-cv4.9) Implement orchestrator/export wiring to satisfy integration behavior.
- [ ] 4.4 (flock-repo-cv4.9) Add trace metadata propagation assertions (correlation/label fields).

## 5. Hardening + Validation

- [ ] 5.1 (flock-repo-cv4.10) Run target suites:
  - `tests/test_agent_builder.py`
  - `tests/test_engines.py`
  - new OpenClaw test files
  - selected integration tests
- [ ] 5.2 (flock-repo-cv4.10) Run lint/format on touched files.
- [ ] 5.3 (flock-repo-cv4.10) Update docs/spec references for implemented Phase 1 details.
- [ ] 5.4 (flock-repo-cv4.10) Final review pass with Claude before implementation merge progression.
