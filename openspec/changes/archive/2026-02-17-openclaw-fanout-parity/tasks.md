# Tasks: OpenClaw Fan-Out Parity

## 1. Engine TDD Harness (fan-out contract first)

- [x] 1.1 (flock-repo-2vu.1) Add failing unit tests for fan-out payload contract (array schema + count instructions).
- [x] 1.2 (flock-repo-2vu.2) Add failing unit tests for fan-out response parsing/materialization (list -> artifacts).
- [x] 1.3 (flock-repo-2vu.3) Add failing unit tests for fan-out count violations (fixed mismatch, dynamic under/over bounds).
- [x] 1.4 (flock-repo-2vu.4) Add failing unit test for multi-output-group fail-fast in OpenClaw engine.

## 2. Engine Implementation

- [x] 2.1 (flock-repo-2vu.5) Implement fan-out cardinality resolver + payload builder array schema.
- [x] 2.2 (flock-repo-2vu.6) Implement fan-out list parsing and per-item artifact materialization.
- [x] 2.3 (flock-repo-2vu.7) Implement fan-out contract enforcement + retry/error mapping (v1: full-request retry on count violations, no partial-accept).
- [x] 2.4 (flock-repo-2vu.8) Implement explicit fail-fast for unsupported multi-output groups.

## 3. Integration Coverage

- [x] 3.1 (flock-repo-2vu.9) Add integration test: fixed fan-out publishes exact N artifacts.
- [x] 3.2 (flock-repo-2vu.10) Add integration test: dynamic fan-out range + downstream native consumer.

## 4. Docs

- [x] 4.1 (flock-repo-2vu.11) Update `docs/guides/openclaw.md` fan-out behavior and current limitations.

## 5. Validation

- [x] 5.1 (flock-repo-2vu.12) Run targeted test suites and fix regressions.
- [x] 5.2 (flock-repo-2vu.13) Run full test suite and summarize validation evidence.
