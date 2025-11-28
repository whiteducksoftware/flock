# Implementation Plan

## Specification Identity

- **Spec ID:** 001
- **Feature:** Sync & Idempotent REST API
- **GitHub Issues:** #287 (Sync Publish), #291 (Idempotency & Error Model)

---

## Context Priming

*GATE: Read all files before starting implementation.*

**Specification Documents:**
- `docs/specs/001-sync-idempotent-rest/product-requirements.md`
- `docs/specs/001-sync-idempotent-rest/solution-design.md`

**Key Implementation Files:**
- `src/flock/api/service.py` - Main REST service (add sync endpoint here)
- `src/flock/api/models.py` - Response models (add new models here)
- `src/flock/core/orchestrator.py` - `run_until_idle()` method
- `src/flock/core/store.py` - `FilterConfig`, `query_artifacts()`

**Key Design Decisions:**
1. Sync endpoint blocks until `run_until_idle()` completes or timeout
2. Idempotency uses `X-Idempotency-Key` header (opt-in)
3. In-memory idempotency store first, SQL can come later
4. Error model is additive (doesn't break existing endpoints)

**Project Commands:**
- Tests: `uv run pytest tests/ -v`
- Type check: `uv run mypy src/flock`
- Lint: `uv run ruff check src/flock`
- Format: `uv run ruff format src/flock`

---

## Implementation Phases

### Phase 1: Response Models & Error Schema

**Goal:** Add Pydantic models for sync responses and standardized errors.

- [ ] **T1.1 Prime Context**
    - [ ] T1.1.1 Read existing models `[ref: src/flock/api/models.py]`
    - [ ] T1.1.2 Read SDD error model section `[ref: solution-design.md; Section 3]`

- [ ] **T1.2 Write Tests** `[activity: test-engineering]`
    - [ ] T1.2.1 Test `SyncPublishRequest` validation (type required, timeout bounds)
    - [ ] T1.2.2 Test `SyncPublishResponse` serialization
    - [ ] T1.2.3 Test `ErrorResponse` with and without details
    - [ ] T1.2.4 Test `ErrorDetail` field validation
    - **File:** `tests/api/test_models.py` (add to existing or create)

- [ ] **T1.3 Implement** `[activity: api-development]`
    - [ ] T1.3.1 Add `SyncPublishRequest` model with timeout validation (1-300s)
    - [ ] T1.3.2 Add `SyncPublishFilters` model (optional type/produced_by filters)
    - [ ] T1.3.3 Add `SyncPublishResponse` model (correlation_id, artifacts, completed, duration_ms)
    - [ ] T1.3.4 Add `ErrorResponse` model (code, message, correlation_id, retryable, details)
    - [ ] T1.3.5 Add `ErrorDetail` model (field, message, code)
    - [ ] T1.3.6 Export all new models in `__all__`
    - **File:** `src/flock/api/models.py`

- [ ] **T1.4 Validate**
    - [ ] T1.4.1 Run `uv run pytest tests/api/test_models.py -v`
    - [ ] T1.4.2 Run `uv run mypy src/flock/api/models.py`
    - [ ] T1.4.3 Run `uv run ruff check src/flock/api/models.py`

---

### Phase 2: Sync Publish Endpoint

**Goal:** Implement `POST /api/v1/artifacts/sync` endpoint.

- [ ] **T2.1 Prime Context**
    - [ ] T2.1.1 Read existing publish endpoint `[ref: src/flock/api/service.py; lines: 126-138]`
    - [ ] T2.1.2 Read artifact serialization helper `[ref: src/flock/api/service.py; lines: 62-95]`
    - [ ] T2.1.3 Read `run_until_idle()` implementation `[ref: src/flock/core/orchestrator.py; lines: 537-562]`
    - [ ] T2.1.4 Read SDD sync endpoint design `[ref: solution-design.md; Section 1]`

- [ ] **T2.2 Write Tests** `[activity: test-engineering]`
    - [ ] T2.2.1 Test sync publish happy path (publish → returns artifacts)
    - [ ] T2.2.2 Test sync publish with timeout (workflow exceeds timeout → completed=false)
    - [ ] T2.2.3 Test sync publish with no downstream agents (returns only input artifact)
    - [ ] T2.2.4 Test sync publish with type filter (only returns matching types)
    - [ ] T2.2.5 Test sync publish with produced_by filter
    - [ ] T2.2.6 Test sync publish invalid type (returns 400/422)
    - [ ] T2.2.7 Test sync publish correlation_id is returned and matches artifacts
    - **File:** `tests/api/test_sync_publish.py`

- [ ] **T2.3 Implement** `[activity: api-development]`
    - [ ] T2.3.1 Add `publish_sync` route in `BlackboardHTTPService._register_routes()`
    - [ ] T2.3.2 Generate unique correlation_id via `uuid4()`
    - [ ] T2.3.3 Publish artifact with correlation_id
    - [ ] T2.3.4 Wrap `run_until_idle()` in `asyncio.wait_for()` with body.timeout
    - [ ] T2.3.5 Catch `asyncio.TimeoutError` and set `completed=False`
    - [ ] T2.3.6 Query artifacts by correlation_id using existing `query_artifacts()`
    - [ ] T2.3.7 Apply optional type_names/produced_by filters
    - [ ] T2.3.8 Calculate duration_ms from start time
    - [ ] T2.3.9 Return `SyncPublishResponse`
    - **File:** `src/flock/api/service.py`

- [ ] **T2.4 Validate**
    - [ ] T2.4.1 Run `uv run pytest tests/api/test_sync_publish.py -v`
    - [ ] T2.4.2 Run full test suite `uv run pytest tests/ -v --tb=short`
    - [ ] T2.4.3 Manual test with example workflow (optional)

---

### Phase 3: Idempotency Layer

**Goal:** Implement idempotency key support for publish endpoints.

- [ ] **T3.1 Prime Context**
    - [ ] T3.1.1 Read SDD idempotency design `[ref: solution-design.md; Section 2]`
    - [ ] T3.1.2 Review existing dedup component pattern `[ref: src/flock/components/orchestrator/deduplication.py]`

- [ ] **T3.2 Write Tests** `[activity: test-engineering]`
    - [ ] T3.2.1 Test `InMemoryIdempotencyStore.get()` returns None for unknown key
    - [ ] T3.2.2 Test `InMemoryIdempotencyStore.set()` stores response
    - [ ] T3.2.3 Test `InMemoryIdempotencyStore.get()` returns cached response
    - [ ] T3.2.4 Test TTL expiry (set with short TTL, wait, get returns None)
    - [ ] T3.2.5 Test idempotency middleware returns cached response on duplicate key
    - [ ] T3.2.6 Test idempotency middleware allows different keys
    - [ ] T3.2.7 Test idempotency middleware allows no key (opt-in behavior)
    - **File:** `tests/api/test_idempotency.py`

- [ ] **T3.3 Implement Idempotency Store** `[activity: api-development]`
    - [ ] T3.3.1 Create `src/flock/api/idempotency.py`
    - [ ] T3.3.2 Define `CachedResponse` dataclass (status_code, body, headers, created_at)
    - [ ] T3.3.3 Define `IdempotencyStore` Protocol
    - [ ] T3.3.4 Implement `InMemoryIdempotencyStore` with dict + TTL expiry
    - [ ] T3.3.5 Add cleanup method for expired entries (optional background task)
    - **File:** `src/flock/api/idempotency.py`

- [ ] **T3.4 Implement Middleware/Dependency** `[activity: api-development]`
    - [ ] T3.4.1 Create `idempotency_check` FastAPI dependency
    - [ ] T3.4.2 Extract `X-Idempotency-Key` header (optional)
    - [ ] T3.4.3 On cache hit: raise custom exception that returns cached response
    - [ ] T3.4.4 Create `IdempotencyCacheHit` exception class
    - [ ] T3.4.5 Add exception handler in service to return cached response
    - **File:** `src/flock/api/idempotency.py`

- [ ] **T3.5 Integrate with Endpoints** `[activity: api-development]`
    - [ ] T3.5.1 Add idempotency dependency to `publish_artifact` endpoint
    - [ ] T3.5.2 Add idempotency dependency to `publish_sync` endpoint
    - [ ] T3.5.3 Cache successful responses with idempotency key
    - [ ] T3.5.4 Register exception handler in `BlackboardHTTPService.__init__`
    - **File:** `src/flock/api/service.py`

- [ ] **T3.6 Validate**
    - [ ] T3.6.1 Run `uv run pytest tests/api/test_idempotency.py -v`
    - [ ] T3.6.2 Run full test suite
    - [ ] T3.6.3 Type check `uv run mypy src/flock/api/idempotency.py`

---

### Phase 4: Error Handling Integration

**Goal:** Apply standardized error model to new endpoints.

- [ ] **T4.1 Prime Context**
    - [ ] T4.1.1 Read SDD error codes table `[ref: solution-design.md; Section 3]`
    - [ ] T4.1.2 Review existing error handling patterns in service.py

- [ ] **T4.2 Write Tests** `[activity: test-engineering]`
    - [ ] T4.2.1 Test validation error returns `ErrorResponse` with field details
    - [ ] T4.2.2 Test unknown type returns `ErrorResponse` with NOT_FOUND code
    - [ ] T4.2.3 Test timeout returns `ErrorResponse` with TIMEOUT code and retryable=true
    - [ ] T4.2.4 Test idempotency conflict returns 409 with IDEMPOTENCY_CONFLICT code
    - **File:** `tests/api/test_error_handling.py`

- [ ] **T4.3 Implement Error Handlers** `[activity: api-development]`
    - [ ] T4.3.1 Create `create_error_response()` helper function
    - [ ] T4.3.2 Add exception handler for `RequestValidationError` → VALIDATION_ERROR
    - [ ] T4.3.3 Add exception handler for `RegistryError` → NOT_FOUND
    - [ ] T4.3.4 Add exception handler for `asyncio.TimeoutError` → TIMEOUT
    - [ ] T4.3.5 Add exception handler for `IdempotencyConflict` → IDEMPOTENCY_CONFLICT
    - [ ] T4.3.6 Include correlation_id in error responses where available
    - **File:** `src/flock/api/service.py` or `src/flock/api/errors.py`

- [ ] **T4.4 Validate**
    - [ ] T4.4.1 Run `uv run pytest tests/api/test_error_handling.py -v`
    - [ ] T4.4.2 Verify error responses match `ErrorResponse` schema

---

### Phase 5: Integration & End-to-End Validation

**Goal:** Ensure all components work together and meet acceptance criteria.

- [ ] **T5.1 Integration Tests** `[activity: test-engineering]`
    - [ ] T5.1.1 Test full sync flow: publish → agent processes → returns all artifacts
    - [ ] T5.1.2 Test idempotency + sync: same key returns cached result without re-execution
    - [ ] T5.1.3 Test error flow: invalid input → standardized error response
    - [ ] T5.1.4 Test concurrent requests with different idempotency keys
    - **File:** `tests/api/test_integration.py`

- [ ] **T5.2 Acceptance Criteria Verification** `[ref: product-requirements.md]`
    - [ ] T5.2.1 Sync endpoint returns all artifacts produced during workflow cascade
    - [ ] T5.2.2 Sync endpoint supports configurable timeout (default 30s, max 300s)
    - [ ] T5.2.3 Sync endpoint includes correlation_id in response
    - [ ] T5.2.4 Idempotency keys stored with TTL (default 24h)
    - [ ] T5.2.5 Duplicate requests return original response
    - [ ] T5.2.6 Idempotency works on both async and sync endpoints
    - [ ] T5.2.7 All errors include code, message, correlation_id
    - [ ] T5.2.8 Errors indicate retryable boolean

- [ ] **T5.3 Quality Gates**
    - [ ] T5.3.1 All tests passing: `uv run pytest tests/ -v`
    - [ ] T5.3.2 Type check passing: `uv run mypy src/flock`
    - [ ] T5.3.3 Lint passing: `uv run ruff check src/flock`
    - [ ] T5.3.4 Format check: `uv run ruff format --check src/flock`
    - [ ] T5.3.5 Test coverage maintained (no regression)

- [ ] **T5.4 Documentation**
    - [ ] T5.4.1 Update OpenAPI docs if needed (FastAPI auto-generates from models)
    - [ ] T5.4.2 Add docstrings to new endpoints
    - [ ] T5.4.3 Update CHANGELOG.md with new features

- [ ] **T5.5 Final Verification**
    - [ ] T5.5.1 Manual smoke test of sync endpoint
    - [ ] T5.5.2 Verify backward compatibility (existing async endpoint unchanged)
    - [ ] T5.5.3 Review PR-ready state

---

## Parallel Execution Notes

The following can be executed in parallel:
- **T3.3 (Idempotency Store)** and **T3.4 (Middleware)** are independent
- **Phase 1 (Models)** must complete before **Phase 2-4**
- **Phase 2 (Sync Endpoint)** and **Phase 3 (Idempotency)** can run in parallel after Phase 1
- **Phase 4 (Error Handling)** can start after Phase 1, parallel with Phase 2-3
- **Phase 5 (Integration)** requires all previous phases complete

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| `run_until_idle()` blocks forever | Enforce max timeout, return partial results |
| Idempotency cache memory growth | TTL-based expiry, periodic cleanup |
| Breaking existing clients | Error model is additive, async endpoint unchanged |

---

## Success Criteria

1. `POST /api/v1/artifacts/sync` works end-to-end
2. Idempotency prevents duplicate workflow execution
3. Error responses follow consistent schema
4. All existing tests still pass
5. New tests provide good coverage of new functionality
