# Tasks: OpenClaw Serialization + Fan-Out Identity Hotfix

## 1. TDD Repro Harness

- [ ] 1.1 (flock-repo-8e4.1) Add failing unit test reproducing `datetime` serialization failure from context payload shaping.
- [ ] 1.2 (flock-repo-8e4.2) Add failing unit test reproducing `datetime` serialization failure from input payload shaping.
- [ ] 1.3 (flock-repo-8e4.3) Add failing regression test reproducing fan-out artifact collapse/identity reuse in streaming path.

## 2. Engine Fixes

- [ ] 2.1 (flock-repo-8e4.4) Implement shared JSON-safe normalization helper in OpenClaw engine.
- [ ] 2.2 (flock-repo-8e4.5) Apply normalization helper to context payload prompt serialization path.
- [ ] 2.3 (flock-repo-8e4.6) Apply normalization helper to input payload prompt serialization path.
- [ ] 2.4 (flock-repo-8e4.7) Fix fan-out materialization metadata/id handling to avoid shared artifact identity in streaming mode.

## 3. Validation + Regression Coverage

- [ ] 3.1 (flock-repo-8e4.8) Run targeted OpenClaw unit/integration suites and resolve regressions.
- [ ] 3.2 (flock-repo-8e4.10) Run full test suite and summarize hotfix evidence.

## 4. Documentation

- [ ] 4.1 (flock-repo-8e4.9) Update `docs/guides/openclaw.md` with serialization safety + fan-out identity behavior notes.
