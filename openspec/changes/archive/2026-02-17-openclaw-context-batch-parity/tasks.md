# Tasks: OpenClaw Context + Batch Parity (Tools Non-Goal)

## 1. TDD Harness

- [x] 1.1 (flock-repo-6jb.1) Add failing unit tests for context-history payload injection (present/absent).
- [x] 1.2 (flock-repo-6jb.2) Add failing unit tests for batch-mode payload shaping (`ctx.is_batch`).
- [x] 1.3 (flock-repo-6jb.3) Add failing unit tests for `group_description` prompt injection.
- [x] 1.4 (flock-repo-6jb.4) Add failing unit tests for instructions override precedence.
- [x] 1.5 (flock-repo-6jb.5) Add failing tests for response_mode path (implement or remove dead knob).

## 2. Engine Implementation

- [x] 2.1 (flock-repo-6jb.6) Implement context-history serialization + injection in `OpenClawEngine`.
- [x] 2.2 (flock-repo-6jb.7) Implement explicit batch-mode request shaping.
- [x] 2.3 (flock-repo-6jb.8) Implement `group_description` prompt wiring.
- [x] 2.4 (flock-repo-6jb.9) Implement instructions override on `OpenClawEngine`.
- [x] 2.5 (flock-repo-6jb.10) Implement response_mode decision (live behavior or API cleanup).

## 3. Integration Coverage

- [x] 3.1 (flock-repo-6jb.11) Integration test: context-aware OpenClaw pipeline behavior.
- [x] 3.2 (flock-repo-6jb.12) Integration test: BatchSpec/OpenClaw behavior parity.

## 4. Documentation

- [x] 4.1 (flock-repo-6jb.13) Update OpenClaw guide for context + batch + instructions/response_mode semantics.

## 5. Validation

- [x] 5.1 (flock-repo-6jb.14) Run targeted suites and resolve regressions.
- [x] 5.2 (flock-repo-6jb.15) Run full test suite and summarize parity evidence.
