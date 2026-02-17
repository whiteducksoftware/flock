# Tasks: OpenClaw Serialization + Fan-Out Identity Hotfix

## 1. TDD Repro Harness

- [x] 1.1 (flock-repo-8e4.1) Add failing unit test reproducing `datetime` serialization failure from context payload shaping.
- [x] 1.2 (flock-repo-8e4.2) Add failing unit test reproducing `datetime` serialization failure from input payload shaping.
- [x] 1.3 (flock-repo-8e4.3) Add failing regression test reproducing fan-out artifact collapse/identity reuse in streaming path.

## 2. Engine Fixes

- [x] 2.1 (flock-repo-8e4.4) Implement shared JSON-safe normalization helper in OpenClaw engine.
- [x] 2.2 (flock-repo-8e4.5) Apply normalization helper to context payload prompt serialization path.
- [x] 2.3 (flock-repo-8e4.6) Apply normalization helper to input payload prompt serialization path.
- [x] 2.4 (flock-repo-8e4.7) Fix fan-out materialization metadata/id handling to avoid shared artifact identity in streaming mode.

## 3. Validation + Regression Coverage

- [x] 3.1 (flock-repo-8e4.8) Run targeted OpenClaw unit/integration suites and resolve regressions.
- [x] 3.2 (flock-repo-8e4.10) Run full test suite and summarize hotfix evidence.

## 4. Documentation

- [x] 4.1 (flock-repo-8e4.9) Update `docs/guides/openclaw.md` with serialization safety + fan-out identity behavior notes.
