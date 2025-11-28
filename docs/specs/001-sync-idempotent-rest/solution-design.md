# Solution Design Document (Minimal)

> **Note:** This is a minimal SDD. Implementation follows existing Flock patterns.

## References

- **Existing Async Endpoint:** `src/flock/api/service.py:126-138`
- **Artifact Serialization:** `src/flock/api/service.py:62-95`
- **Orchestrator Methods:** `src/flock/core/orchestrator.py` (`run_until_idle`, `publish`)
- **Deduplication Pattern:** `src/flock/components/orchestrator/deduplication.py`
- **Response Models:** `src/flock/api/models.py`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     REST API Layer                               │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ POST /artifacts  │  │ POST /artifacts/ │                     │
│  │     (async)      │  │      sync        │                     │
│  └────────┬─────────┘  └────────┬─────────┘                     │
│           │                     │                                │
│           ▼                     ▼                                │
│  ┌──────────────────────────────────────────┐                   │
│  │         IdempotencyMiddleware            │                   │
│  │  (X-Idempotency-Key → cache lookup)      │                   │
│  └────────────────────┬─────────────────────┘                   │
│                       │                                          │
│           ┌───────────┴───────────┐                             │
│           ▼                       ▼                             │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │  IdempotencyStore │    │ Orchestrator    │                     │
│  │  (in-memory/SQL)  │    │ .publish()      │                     │
│  └─────────────────┘    │ .run_until_idle()│                     │
│                         └─────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. Sync Publish Endpoint

**Location:** `src/flock/api/service.py` (add to `BlackboardHTTPService._register_routes`)

**Request:**
```python
class SyncPublishRequest(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    filters: SyncPublishFilters | None = None  # Optional result filtering

class SyncPublishFilters(BaseModel):
    type_names: list[str] | None = None
    produced_by: list[str] | None = None
```

**Response:**
```python
class SyncPublishResponse(BaseModel):
    correlation_id: str
    artifacts: list[ArtifactBase]
    completed: bool  # True if idle, False if timeout
    duration_ms: int
```

**Implementation Pattern:**
```python
@app.post("/api/v1/artifacts/sync", response_model=SyncPublishResponse)
async def publish_sync(body: SyncPublishRequest, ...):
    correlation_id = str(uuid4())
    start = time.monotonic()

    # Publish with correlation
    await orchestrator.publish({"type": body.type, **body.payload},
                               correlation_id=correlation_id)

    # Wait for completion
    try:
        await asyncio.wait_for(
            orchestrator.run_until_idle(),
            timeout=body.timeout
        )
        completed = True
    except asyncio.TimeoutError:
        completed = False

    # Query results
    artifacts, _ = await orchestrator.store.query_artifacts(
        FilterConfig(correlation_id=correlation_id, ...),
        limit=500
    )

    return SyncPublishResponse(
        correlation_id=correlation_id,
        artifacts=[_serialize_artifact(a) for a in artifacts],
        completed=completed,
        duration_ms=int((time.monotonic() - start) * 1000)
    )
```

---

### 2. Idempotency Layer

**New Files:**
- `src/flock/api/idempotency.py` - Core idempotency logic
- `src/flock/components/server/idempotency/` - Server component (optional)

**IdempotencyStore Protocol:**
```python
class IdempotencyStore(Protocol):
    async def get(self, key: str) -> CachedResponse | None: ...
    async def set(self, key: str, response: CachedResponse, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...

@dataclass
class CachedResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]
    created_at: datetime
```

**In-Memory Implementation:**
```python
class InMemoryIdempotencyStore:
    def __init__(self, default_ttl: int = 86400):  # 24h
        self._cache: dict[str, tuple[CachedResponse, datetime]] = {}
        self._ttl = default_ttl

    async def get(self, key: str) -> CachedResponse | None:
        if key in self._cache:
            response, expires = self._cache[key]
            if datetime.utcnow() < expires:
                return response
            del self._cache[key]
        return None
```

**Middleware/Dependency:**
```python
async def idempotency_check(
    request: Request,
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    store: IdempotencyStore = Depends(get_idempotency_store),
) -> str | None:
    if idempotency_key:
        cached = await store.get(idempotency_key)
        if cached:
            raise CachedResponseException(cached)  # Return cached response
    return idempotency_key
```

---

### 3. Error Model

**New Models in `src/flock/api/models.py`:**
```python
class ErrorResponse(BaseModel):
    code: str  # e.g., "VALIDATION_ERROR", "TIMEOUT", "INTERNAL_ERROR"
    message: str
    correlation_id: str | None = None
    retryable: bool = False
    details: list[ErrorDetail] | None = None

class ErrorDetail(BaseModel):
    field: str | None = None
    message: str
    code: str | None = None
```

**Error Codes:**
| Code | HTTP Status | Retryable | Description |
|------|-------------|-----------|-------------|
| `VALIDATION_ERROR` | 400/422 | No | Invalid request payload |
| `NOT_FOUND` | 404 | No | Resource not found |
| `IDEMPOTENCY_CONFLICT` | 409 | No | Key exists with different payload |
| `TIMEOUT` | 504 | Yes | Workflow didn't complete in time |
| `INTERNAL_ERROR` | 500 | Yes | Unexpected server error |

---

## Data Flow

### Sync Publish Flow
```
1. Client → POST /api/v1/artifacts/sync + X-Idempotency-Key
2. IdempotencyMiddleware checks cache
   - HIT: Return cached response (skip execution)
   - MISS: Continue
3. Validate request payload
4. Generate correlation_id
5. orchestrator.publish(artifact, correlation_id)
6. asyncio.wait_for(orchestrator.run_until_idle(), timeout)
7. Query artifacts by correlation_id
8. Cache response (if idempotency key provided)
9. Return SyncPublishResponse
```

---

## Testing Strategy

| Component | Test Type | Key Scenarios |
|-----------|-----------|---------------|
| Sync Endpoint | Integration | Happy path, timeout, empty results |
| Idempotency | Unit | Cache hit/miss, TTL expiry, different payloads |
| Error Model | Unit | All error codes, field validation |
| E2E | Integration | Full flow with actual orchestrator |

---

## Migration Notes

- No breaking changes to existing endpoints
- Idempotency is opt-in (header not required)
- Error model applies to new endpoints first, can retrofit async later
