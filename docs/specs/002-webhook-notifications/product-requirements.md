# Product Requirements Document (Minimal)

> **Note:** This is a minimal PRD. Full requirements are documented in GitHub issue #289.

## References

- **GitHub Issue #289:** [Webhook Notifications](https://github.com/whiteducksoftware/flock/issues/289)
- **Existing WebSocket Implementation:** `src/flock/api/websocket.py`
- **Event Models:** `src/flock/components/server/models/events.py`

---

## Problem Statement

Integrators want real-time callbacks when artifacts are produced so they don't have to poll status or store endpoints. Currently the REST APIs return only immediate results; there is no native webhook support to push updates as a workflow progresses.

## Value Proposition

- **Real-time integration:** External systems receive instant notifications when artifacts are produced
- **No polling overhead:** Eliminates the need for clients to repeatedly poll for status
- **Secure callbacks:** HMAC signing prevents spoofing and ensures payload authenticity

---

## Feature Requirements

### Must Have (P0)

#### Feature 1: Per-Request Webhook URL
- **Behavior:** REST publish endpoints accept optional `webhook_url` parameter
- **Acceptance Criteria:**
  - [ ] Webhook URL specified per request (not global configuration)
  - [ ] POST notifications sent for each artifact produced during workflow
  - [ ] Works with both async (`/artifacts`) and sync (`/artifacts/sync`) endpoints

#### Feature 2: Webhook Payload
- **Content:** Artifact metadata and payload
- **Acceptance Criteria:**
  - [ ] Includes: artifact_id, type, produced_by, correlation_id, payload, created_at
  - [ ] Includes ordering metadata (sequence number within workflow)
  - [ ] JSON format with consistent schema

#### Feature 3: HMAC Signature
- **Header:** `X-Flock-Signature` with HMAC-SHA256
- **Acceptance Criteria:**
  - [ ] Secret provided via request parameter or Flock configuration
  - [ ] Signature computed over raw payload body
  - [ ] Recipients can verify authenticity

#### Feature 4: Retry with Backoff
- **Behavior:** Failed deliveries retry with exponential backoff
- **Acceptance Criteria:**
  - [ ] Up to 3 retry attempts
  - [ ] Exponential backoff (1s, 2s, 4s)
  - [ ] Non-2xx responses trigger retry
  - [ ] Delivery failures logged but don't fail the workflow

### Should Have (P1)

- [ ] Delivery status tracking (per correlation_id)
- [ ] Configurable retry policy
- [ ] Webhook delivery metrics (success/failure counts)

### Won't Have (This Phase)

- Persistent webhook subscriptions (global registration)
- Webhook management API (CRUD for subscriptions)
- Dead letter queue for failed deliveries
- Custom headers per webhook

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Webhook delivery latency p95 | < 500ms from artifact creation |
| Delivery success rate | > 99% for reachable endpoints |
| Retry effectiveness | > 80% of transient failures recovered |

---

## Constraints

- Webhook delivery must not block workflow execution
- Must integrate with existing tracing/metrics infrastructure
- Should reuse existing event models where possible
