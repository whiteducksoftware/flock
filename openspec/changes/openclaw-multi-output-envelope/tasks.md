# Tasks: OpenClaw Multi-Output Envelope

## 1. TDD Harness

- [ ] 1.1 (flock-repo-0eh.1) Add failing unit tests for envelope schema generation with mixed multi-output declarations.
- [ ] 1.2 (flock-repo-0eh.2) Add failing unit tests for per-slot shape rules (object vs array by declaration).
- [ ] 1.3 (flock-repo-0eh.3) Add failing unit tests for strict slot matching (unknown/missing slot failures).
- [ ] 1.4 (flock-repo-0eh.4) Add failing unit tests for slot-name collision fail-fast behavior.
- [ ] 1.5 (flock-repo-0eh.5) Add failing tests for retry/repair behavior on malformed multi-output envelope.

## 2. Engine Implementation

- [ ] 2.1 (flock-repo-0eh.6) Implement multi-output declaration resolution + deterministic slot map builder.
- [ ] 2.2 (flock-repo-0eh.7) Implement envelope schema contract builder for multi-output groups.
- [ ] 2.3 (flock-repo-0eh.8) Implement envelope parser + per-slot validation/materialization pipeline.
- [ ] 2.4 (flock-repo-0eh.9) Reuse/enforce per-slot fan-out cardinality checks in envelope path.
- [ ] 2.5 (flock-repo-0eh.10) Preserve single-output fast path without behavior regressions.

## 3. Integration Coverage

- [ ] 3.1 (flock-repo-0eh.11) Add integration test for one OpenClaw activation publishing multiple output types.
- [ ] 3.2 (flock-repo-0eh.12) Add integration test for mixed native + OpenClaw downstream consumption from multi-output publish.
- [ ] 3.3 (flock-repo-0eh.13) Add integration test for invalid envelope failure path and surfaced error contract.

## 4. Documentation

- [ ] 4.1 (flock-repo-0eh.14) Update `docs/guides/openclaw.md` with multi-output envelope contract and examples.
- [ ] 4.2 (flock-repo-0eh.15) Update examples/readme notes for current limitations and supported envelope behavior.

## 5. Validation

- [ ] 5.1 (flock-repo-0eh.16) Run targeted OpenClaw unit/integration suites and resolve regressions.
- [ ] 5.2 (flock-repo-0eh.17) Run full test suite and summarize parity evidence for multi-output groups.
