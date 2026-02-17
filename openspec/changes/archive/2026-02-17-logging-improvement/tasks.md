# Tasks: logging-improvemen

## 1. Quick hardening fix

- [x] 1.1 (flock-repo-6au) Implement safe `exc_info` handling in `FlockLogger` (map to Loguru `opt(exception=...)`).
- [x] 1.2 (flock-repo-bv5) Update orchestrator agent-failure logging to structured placeholder call with explicit exception binding.
- [x] 1.3 (flock-repo-bv5) Add regression tests for JSON/braces logging with `exc_info`.

## 2. Improvement concept capture

- [x] 2.1 (flock-repo-q5f) Document logging improvement concepts (error envelope, classification, payload policy, run summary).

## 3. Validation

- [x] 3.1 (flock-repo-bv5) Run targeted logging + orchestrator tests.
- [ ] 3.2 (flock-repo-549) Claude review + commit/push.

## 4. Fast OpenClaw orchestration example

- [x] 4.1 (flock-repo-3ga.1) Add `examples/11-openclaw/06_fast_orchestration_smoke.py` (headless, stream on/off toggle) covering fan-out uniqueness + datetime-safe context/input shaping with faster runtime than `05_competitive_intelligence.py`.
