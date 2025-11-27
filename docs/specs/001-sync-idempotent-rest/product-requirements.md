# Product Requirements Document (Minimal)

> **Note:** This is a minimal PRD. Full requirements are documented in GitHub issues.

## References

- **GitHub Issue #287:** [Sync REST Publish Endpoint](https://github.com/whiteducksoftware/flock/issues/287)
- **GitHub Issue #291:** [REST Idempotency & Error Model](https://github.com/whiteducksoftware/flock/issues/291)
- **Existing Implementation:** `src/flock/api/service.py` (async publish endpoint)

---

## Problem Statement

REST clients integrating with Flock face two challenges:

1. **No synchronous workflow execution:** The current `POST /api/v1/artifacts` is fire-and-forget. Clients must poll or implement custom idle detection to know when processing completes.

2. **No idempotency guarantees:** Transient network failures can cause duplicate artifacts or partial workflows because there's no way to safely retry publish calls.

## Value Proposition

- **Simplified integration:** One REST call to publish and receive all resulting artifacts
- **Reliable retries:** Idempotency keys prevent duplicate processing on retry
- **Production-ready:** Standard error semantics enable proper client error handling

---

## Feature Requirements

### Must Have (P0)

#### Feature 1: Sync Publish Endpoint
- **Endpoint:** `POST /api/v1/artifacts/sync`
- **Behavior:** Publish artifact → `run_until_idle()` → return all produced artifacts
- **Acceptance Criteria:**
  - [ ] Returns all artifacts produced during the workflow cascade
  - [ ] Supports configurable timeout (default 30s, max 300s)
  - [ ] Includes correlation_id in response for tracing
  - [ ] Respects existing visibility rules

#### Feature 2: Idempotency Keys
- **Header:** `X-Idempotency-Key` (optional)
- **Behavior:** Duplicate requests within retention window return cached response
- **Acceptance Criteria:**
  - [ ] Keys stored with configurable TTL (default 24h)
  - [ ] Duplicate requests return original response (not re-execute)
  - [ ] Works on both `/artifacts` and `/artifacts/sync` endpoints

#### Feature 3: Standardized Error Model
- **Format:** Consistent JSON error responses
- **Acceptance Criteria:**
  - [ ] All errors include `code`, `message`, `correlation_id`
  - [ ] Errors indicate `retryable` boolean for client retry logic
  - [ ] Validation errors include field-level details

### Should Have (P1)

- [ ] Batch submission support (array of artifacts, per-item status)
- [ ] Optional result filtering by type/produced_by

### Won't Have (This Phase)

- Webhook notifications (separate issue #289)
- Advanced condition-based completion (issue #364)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Sync endpoint latency p95 | < 5s for simple workflows |
| Idempotency key collision rate | < 0.001% |
| Error response consistency | 100% adherence to schema |

---

## Constraints

- Must maintain backward compatibility with existing async endpoint
- Idempotency store should work with both in-memory and SQL backends
- No breaking changes to existing REST API contracts
