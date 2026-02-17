# Tasks: OpenClaw Context + Batch Parity (Tools Non-Goal)

## 1. TDD Harness

- [ ] 1.1 (flock-repo-6jb.1) Add failing unit tests for context-history payload injection (present/absent).
- [ ] 1.2 (flock-repo-6jb.2) Add failing unit tests for batch-mode payload shaping (`ctx.is_batch`).
- [ ] 1.3 (flock-repo-6jb.3) Add failing unit tests for `group_description` prompt injection.
- [ ] 1.4 (flock-repo-6jb.4) Add failing unit tests for instructions override precedence.
- [ ] 1.5 (flock-repo-6jb.5) Add failing tests for response_mode path (implement or remove dead knob).

## 2. Engine Implementation

- [ ] 2.1 (flock-repo-6jb.6) Implement context-history serialization + injection in `OpenClawEngine`.
- [ ] 2.2 (flock-repo-6jb.7) Implement explicit batch-mode request shaping.
- [ ] 2.3 (flock-repo-6jb.8) Implement `group_description` prompt wiring.
- [ ] 2.4 (flock-repo-6jb.9) Implement instructions override on `OpenClawEngine`.
- [ ] 2.5 (flock-repo-6jb.10) Implement response_mode decision (live behavior or API cleanup).

## 3. Integration Coverage

- [ ] 3.1 (flock-repo-6jb.11) Integration test: context-aware OpenClaw pipeline behavior.
- [ ] 3.2 (flock-repo-6jb.12) Integration test: BatchSpec/OpenClaw behavior parity.

## 4. Documentation

- [ ] 4.1 (flock-repo-6jb.13) Update OpenClaw guide for context + batch + instructions/response_mode semantics.

## 5. Validation

- [ ] 5.1 (flock-repo-6jb.14) Run targeted suites and resolve regressions.
- [ ] 5.2 (flock-repo-6jb.15) Run full test suite and summarize parity evidence.
