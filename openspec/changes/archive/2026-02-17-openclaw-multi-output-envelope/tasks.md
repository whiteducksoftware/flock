# Tasks: OpenClaw Multi-Output Envelope

## 1. TDD Harness

- [x] 1.1 (flock-repo-0eh.1) Add failing unit tests for envelope schema generation with mixed multi-output declarations.
- [x] 1.2 (flock-repo-0eh.2) Add failing unit tests for per-slot shape rules (object vs array by declaration).
- [x] 1.3 (flock-repo-0eh.3) Add failing unit tests for strict slot matching (unknown/missing slot failures).
- [x] 1.4 (flock-repo-0eh.4) Add failing unit tests for slot-name collision fail-fast behavior.
- [x] 1.5 (flock-repo-0eh.5) Add failing tests for retry/repair behavior on malformed multi-output envelope.

## 2. Engine Implementation

- [x] 2.1 (flock-repo-0eh.6) Implement multi-output declaration resolution + deterministic slot map builder.
- [x] 2.2 (flock-repo-0eh.7) Implement envelope schema contract builder for multi-output groups.
- [x] 2.3 (flock-repo-0eh.8) Implement envelope parser + per-slot validation/materialization pipeline.
- [x] 2.4 (flock-repo-0eh.9) Reuse/enforce per-slot fan-out cardinality checks in envelope path.
- [x] 2.5 (flock-repo-0eh.10) Preserve single-output fast path without behavior regressions (include explicit isolation regression test that monkeypatches envelope path to raise and proves single-output bypasses it).

## 3. Integration Coverage

- [x] 3.1 (flock-repo-0eh.11) Add integration test for one OpenClaw activation publishing multiple output types.
- [x] 3.2 (flock-repo-0eh.12) Add integration test for mixed native + OpenClaw downstream consumption from multi-output publish.
- [x] 3.3 (flock-repo-0eh.13) Add integration test for invalid envelope failure path and surfaced error contract.

## 4. Documentation

- [x] 4.1 (flock-repo-0eh.14) Update `docs/guides/openclaw.md` with multi-output envelope contract and examples.
- [x] 4.2 (flock-repo-0eh.15) Update examples/readme notes for current limitations and supported envelope behavior.

## 5. Validation

- [x] 5.1 (flock-repo-0eh.16) Run targeted OpenClaw unit/integration suites and resolve regressions.
- [x] 5.2 (flock-repo-0eh.17) Run full test suite and summarize parity evidence for multi-output groups.
