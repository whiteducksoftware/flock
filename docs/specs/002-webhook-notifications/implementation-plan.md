# Implementation Plan

## Specification Identity

- **Spec ID:** 002
- **Feature:** Webhook Notifications
- **GitHub Issue:** #289

---

## Context Priming

*GATE: Read all files before starting implementation.*

**Specification Documents:**
- `docs/specs/002-webhook-notifications/product-requirements.md`
- `docs/specs/002-webhook-notifications/solution-design.md`

**Key Implementation Files:**
- `src/flock/api/service.py` - REST endpoints (add webhook params)
- `src/flock/api/models.py` - Request/response models
- `src/flock/components/server/models/events.py` - Existing event models
- `src/flock/api/websocket.py` - WebSocket pattern to reference
- `src/flock/components/orchestrator/base.py` - Component hooks

**Key Design Decisions:**
1. Per-request webhook URL (not global subscription)
2. Fire-and-forget delivery (doesn't block workflow)
3. HMAC-SHA256 signing with optional secret
4. Exponential backoff retry (3 attempts)
5. Use ContextVar for request-scoped webhook context

**Project Commands:**
- Tests: `uv run pytest tests/ -v`
- Type check: `uv run mypy src/flock`
- Lint: `uv run ruff check src/flock`
- Format: `uv run ruff format src/flock`

**Dependencies:**
- `httpx` (async HTTP client) - likely already in dependencies

---

## Implementation Phases

### Phase 1: Models & Configuration

**Goal:** Define webhook-related Pydantic models and configuration.

- [x] **T1.1 Prime Context**
    - [x] T1.1.1 Read existing request models `[ref: src/flock/api/models.py]`
    - [x] T1.1.2 Read existing event models `[ref: src/flock/components/server/models/events.py]`
    - [x] T1.1.3 Read SDD model definitions `[ref: solution-design.md; Section 1-2]`

- [x] **T1.2 Write Tests** `[activity: test-engineering]`
    - [x] T1.2.1 Test `WebhookConfig` URL validation (valid URL required)
    - [x] T1.2.2 Test `WebhookConfig` secret is optional
    - [x] T1.2.3 Test `WebhookPayload` serialization
    - [x] T1.2.4 Test `WebhookArtifact` serialization
    - **File:** `tests/api/test_webhook_models.py`

- [x] **T1.3 Implement** `[activity: api-development]`
    - [x] T1.3.1 Add `WebhookConfig` model (url: HttpUrl, secret: str | None)
    - [x] T1.3.2 Add `WebhookArtifact` model (id, type, produced_by, payload, created_at, tags)
    - [x] T1.3.3 Add `WebhookPayload` model (event_type, correlation_id, sequence, artifact, timestamp)
    - [x] T1.3.4 Extend `ArtifactPublishRequest` with optional `webhook: WebhookConfig`
    - [x] T1.3.5 Export all new models in `__all__`
    - **File:** `src/flock/api/models.py`

- [x] **T1.4 Validate**
    - [x] T1.4.1 Run `uv run pytest tests/api/test_webhook_models.py -v`
    - [x] T1.4.2 Type check models

---

### Phase 2: Webhook Delivery Service

**Goal:** Implement core webhook delivery logic with signing and retry.

- [x] **T2.1 Prime Context**
    - [x] T2.1.1 Read SDD delivery service design `[ref: solution-design.md; Section 3]`
    - [x] T2.1.2 Check if httpx is already a dependency `[ref: pyproject.toml]`

- [x] **T2.2 Write Tests** `[activity: test-engineering]`
    - [x] T2.2.1 Test `sign_payload()` produces correct HMAC-SHA256
    - [x] T2.2.2 Test `sign_payload()` with empty secret raises or handles gracefully
    - [x] T2.2.3 Test `deliver()` success returns True
    - [x] T2.2.4 Test `deliver()` retries on 500 error (mock httpx)
    - [x] T2.2.5 Test `deliver()` retries on network error
    - [x] T2.2.6 Test `deliver()` returns False after max retries exhausted
    - [x] T2.2.7 Test `deliver()` includes X-Flock-Signature header when secret provided
    - [x] T2.2.8 Test `deliver()` omits signature when no secret
    - [x] T2.2.9 Test retry backoff timing (1s, 2s, 4s)
    - **File:** `tests/api/test_webhook_delivery.py`

- [x] **T2.3 Implement** `[activity: api-development]`
    - [x] T2.3.1 Create `src/flock/api/webhooks.py`
    - [x] T2.3.2 Implement `sign_payload(payload: bytes, secret: str) -> str`
    - [x] T2.3.3 Implement `WebhookDeliveryService.__init__(max_retries, base_delay)`
    - [x] T2.3.4 Create httpx.AsyncClient with timeout
    - [x] T2.3.5 Implement `deliver(url, payload, secret)` with retry loop
    - [x] T2.3.6 Add exponential backoff (base_delay * 2^attempt)
    - [x] T2.3.7 Add logging for delivery attempts and failures
    - **File:** `src/flock/api/webhooks.py`

- [x] **T2.4 Validate**
    - [x] T2.4.1 Run `uv run pytest tests/api/test_webhook_delivery.py -v`
    - [x] T2.4.2 Type check `uv run mypy src/flock/api/webhooks.py`

---

### Phase 3: Webhook Context Management

**Goal:** Implement request-scoped context for webhook configuration.

- [x] **T3.1 Prime Context**
    - [x] T3.1.1 Read SDD context design `[ref: solution-design.md; Section 4]`
    - [x] T3.1.2 Review Python ContextVar usage patterns

- [x] **T3.2 Write Tests** `[activity: test-engineering]`
    - [x] T3.2.1 Test `WebhookContext` creation with url and correlation_id
    - [x] T3.2.2 Test `next_sequence()` increments correctly
    - [x] T3.2.3 Test ContextVar isolation between async tasks
    - [x] T3.2.4 Test `get_webhook_context()` returns None when not set
    - **File:** `tests/api/test_webhook_context.py`

- [x] **T3.3 Implement** `[activity: api-development]`
    - [x] T3.3.1 Define `WebhookContext` dataclass (url, secret, correlation_id, sequence)
    - [x] T3.3.2 Implement `next_sequence()` method
    - [x] T3.3.3 Create module-level ContextVar `_webhook_context`
    - [x] T3.3.4 Add `set_webhook_context(ctx)` helper
    - [x] T3.3.5 Add `get_webhook_context()` helper
    - [x] T3.3.6 Add `clear_webhook_context()` helper
    - **File:** `src/flock/api/webhooks.py` (add to same file)

- [x] **T3.4 Validate**
    - [x] T3.4.1 Run `uv run pytest tests/api/test_webhook_context.py -v`

---

### Phase 4: Orchestrator Integration

**Goal:** Hook webhook delivery into artifact publication events.

- [x] **T4.1 Prime Context**
    - [x] T4.1.1 Read orchestrator component base `[ref: src/flock/components/orchestrator/base.py]`
    - [x] T4.1.2 Read existing component patterns `[ref: src/flock/components/orchestrator/deduplication.py]`
    - [x] T4.1.3 Identify hook point for "after artifact published"

- [x] **T4.2 Investigate Hook Point** `[activity: architecture]`
    - [x] T4.2.1 Determine if `on_after_publish` hook exists or needs creation
    - [x] T4.2.2 If hook doesn't exist, check `on_after_agent` or similar
    - [x] T4.2.3 Document chosen integration approach
    - **Note:** Found `on_artifact_published` hook - perfect fit!

- [x] **T4.3 Write Tests** `[activity: test-engineering]`
    - [x] T4.3.1 Test component fires webhook when context is set
    - [x] T4.3.2 Test component does nothing when context is None
    - [x] T4.3.3 Test payload includes correct correlation_id and sequence
    - [x] T4.3.4 Test delivery is fire-and-forget (doesn't block)
    - **File:** `tests/components/test_webhook_component.py`

- [x] **T4.4 Implement Component** `[activity: api-development]`
    - [x] T4.4.1 Create `src/flock/components/orchestrator/webhook.py`
    - [x] T4.4.2 Define `WebhookDeliveryComponent(OrchestratorComponent)`
    - [x] T4.4.3 Set appropriate priority (run late, e.g., 200)
    - [x] T4.4.4 Implement hook method that:
        - Gets WebhookContext from ContextVar
        - Returns early if None
        - Builds WebhookPayload
        - Fires asyncio.create_task for delivery
    - [x] T4.4.5 Inject WebhookDeliveryService dependency
    - **File:** `src/flock/components/orchestrator/webhook.py`

- [x] **T4.5 Register Component**
    - [x] T4.5.1 Add to component exports in `__init__.py`
    - [x] T4.5.2 Determine if auto-registered or opt-in (opt-in for now)
    - **File:** `src/flock/components/orchestrator/__init__.py`

- [x] **T4.6 Validate**
    - [x] T4.6.1 Run `uv run pytest tests/components/test_webhook_component.py -v`

---

### Phase 5: REST Endpoint Integration

**Goal:** Wire webhook configuration into publish endpoints.

- [x] **T5.1 Prime Context**
    - [x] T5.1.1 Read existing publish endpoint `[ref: src/flock/api/service.py; lines: 126-138]`
    - [x] T5.1.2 Read sync publish endpoint (from spec 001 when implemented)

- [x] **T5.2 Write Tests** `[activity: test-engineering]`
    - [x] T5.2.1 Test `/artifacts` with webhook_url triggers delivery
    - [x] T5.2.2 Test `/artifacts` without webhook_url works as before
    - [x] T5.2.3 Test `/artifacts/sync` with webhook_url triggers delivery for all artifacts
    - [x] T5.2.4 Test webhook receives correct correlation_id
    - [x] T5.2.5 Test webhook receives artifacts in sequence order
    - **File:** `tests/api/test_webhook_integration.py`

- [x] **T5.3 Implement** `[activity: api-development]`
    - [x] T5.3.1 Update `publish_artifact` to accept `WebhookConfig`
    - [x] T5.3.2 Extract webhook config from request body
    - [x] T5.3.3 Set WebhookContext before publish
    - [x] T5.3.4 Clear WebhookContext after response
    - [x] T5.3.5 Update `publish_sync` similarly (if implemented)
    - [x] T5.3.6 Ensure WebhookDeliveryComponent is registered
    - **File:** `src/flock/api/service.py`

- [x] **T5.4 Validate**
    - [x] T5.4.1 Run `uv run pytest tests/api/test_webhook_integration.py -v`
    - [x] T5.4.2 Run full test suite

---

### Phase 6: Integration & End-to-End Validation

**Goal:** Ensure complete webhook flow works end-to-end.

- [x] **T6.1 E2E Tests** `[activity: test-engineering]`
    - [x] T6.1.1 Test full flow: publish artifact → agent processes → webhooks delivered
    - [x] T6.1.2 Test webhook signature verification (create test receiver)
    - [x] T6.1.3 Test retry behavior with failing endpoint
    - [x] T6.1.4 Test webhook doesn't block even if endpoint is slow
    - **File:** `tests/api/test_webhook_e2e.py`

- [x] **T6.2 Acceptance Criteria Verification** `[ref: product-requirements.md]`
    - [x] T6.2.1 Webhook URL specified per request works
    - [x] T6.2.2 POST notifications sent for each artifact produced
    - [x] T6.2.3 Works with both async and sync endpoints
    - [x] T6.2.4 Payload includes required fields (id, type, correlation_id, etc.)
    - [x] T6.2.5 Sequence number tracks order within workflow
    - [x] T6.2.6 X-Flock-Signature header present with secret
    - [x] T6.2.7 Retries up to 3 times with backoff
    - [x] T6.2.8 Delivery failures don't fail workflow

- [x] **T6.3 Quality Gates**
    - [x] T6.3.1 All tests passing: `uv run pytest tests/ -v`
    - [x] T6.3.2 Type check passing: `uv run mypy src/flock`
    - [x] T6.3.3 Lint passing: `uv run ruff check src/flock`
    - [x] T6.3.4 Format check: `uv run ruff format --check src/flock`

- [x] **T6.4 Documentation**
    - [x] T6.4.1 Add docstrings to webhook components
    - [x] T6.4.2 Update CHANGELOG.md

- [x] **T6.5 Final Verification**
    - [x] T6.5.1 Manual test with httpbin.org or similar
    - [x] T6.5.2 Verify backward compatibility
    - [x] T6.5.3 Review PR-ready state

---

## Parallel Execution Notes

- **Phase 1 (Models)** must complete first
- **Phase 2 (Delivery Service)** and **Phase 3 (Context)** can run in parallel
- **Phase 4 (Component)** depends on Phase 2 and 3
- **Phase 5 (Endpoints)** depends on Phase 1, 3, 4
- **Phase 6 (E2E)** requires all previous phases

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| No `on_after_publish` hook | Create new hook or use event emission pattern |
| httpx not in dependencies | Add to pyproject.toml |
| Memory leak from pending tasks | Track tasks, clean up on shutdown |
| SSRF via webhook URL | Document risk, optional IP validation |

---

## Open Questions

1. **Hook availability:** Does `on_after_publish` exist? If not, what's the best integration point?
2. **Component registration:** Auto-register or require explicit opt-in?
3. **SSRF protection:** Should we validate webhook URLs against private IPs?

---

## Success Criteria

1. Webhooks delivered for all artifacts in a workflow
2. HMAC signatures validate correctly
3. Retry logic handles transient failures
4. Delivery doesn't block workflow execution
5. All existing tests still pass
