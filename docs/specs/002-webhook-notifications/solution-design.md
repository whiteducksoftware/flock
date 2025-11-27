# Solution Design Document (Minimal)

> **Note:** This is a minimal SDD. Implementation follows existing Flock patterns.

## References

- **WebSocket Manager:** `src/flock/api/websocket.py`
- **Event Models:** `src/flock/components/server/models/events.py`
- **Async Publish Endpoint:** `src/flock/api/service.py:126-138`
- **Orchestrator Hooks:** `src/flock/components/orchestrator/base.py`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        REST API Layer                                │
│  ┌────────────────────┐    ┌────────────────────┐                   │
│  │ POST /artifacts    │    │ POST /artifacts/   │                   │
│  │   + webhook_url    │    │   sync + webhook   │                   │
│  └─────────┬──────────┘    └─────────┬──────────┘                   │
│            │                         │                               │
│            ▼                         ▼                               │
│  ┌──────────────────────────────────────────────┐                   │
│  │            WebhookContext                     │                   │
│  │  (stores webhook_url + secret per request)   │                   │
│  └──────────────────────┬───────────────────────┘                   │
│                         │                                            │
└─────────────────────────┼────────────────────────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────────────────────────┐
│                    Orchestrator                                       │
│                         │                                             │
│  ┌──────────────────────▼───────────────────────┐                    │
│  │         WebhookDeliveryComponent             │                    │
│  │  (OrchestratorComponent - on_after_publish)  │                    │
│  └──────────────────────┬───────────────────────┘                    │
│                         │                                             │
└─────────────────────────┼────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   WebhookDeliveryService                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │  HMAC Signing   │  │  HTTP Client    │  │  Retry Queue    │      │
│  │  (SHA-256)      │  │  (httpx async)  │  │  (in-memory)    │      │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. Request Models

**Add to `src/flock/api/models.py`:**
```python
class WebhookConfig(BaseModel):
    """Webhook configuration for a publish request."""
    url: HttpUrl
    secret: str | None = None  # For HMAC signing

class ArtifactPublishRequest(BaseModel):  # Extend existing
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    webhook: WebhookConfig | None = None  # NEW

class SyncPublishRequest(BaseModel):  # Extend existing
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    webhook: WebhookConfig | None = None  # NEW
```

### 2. Webhook Payload Model

```python
class WebhookPayload(BaseModel):
    """Payload sent to webhook endpoints."""
    event_type: Literal["artifact.created"] = "artifact.created"
    correlation_id: str
    sequence: int  # Order within this workflow
    artifact: WebhookArtifact
    timestamp: str  # ISO 8601

class WebhookArtifact(BaseModel):
    """Artifact data in webhook payload."""
    id: str
    type: str
    produced_by: str
    payload: dict[str, Any]
    created_at: str
    tags: list[str] = []
```

### 3. WebhookDeliveryService

**New file: `src/flock/api/webhooks.py`**

```python
class WebhookDeliveryService:
    """Handles webhook delivery with signing and retry."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self._client = httpx.AsyncClient(timeout=10.0)
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._pending: dict[str, asyncio.Task] = {}  # correlation_id -> task

    def sign_payload(self, payload: bytes, secret: str) -> str:
        """Generate HMAC-SHA256 signature."""
        return hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

    async def deliver(
        self,
        url: str,
        payload: WebhookPayload,
        secret: str | None = None,
    ) -> bool:
        """Deliver webhook with retry logic."""
        body = payload.model_dump_json().encode()
        headers = {"Content-Type": "application/json"}

        if secret:
            headers["X-Flock-Signature"] = f"sha256={self.sign_payload(body, secret)}"

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(url, content=body, headers=headers)
                if response.is_success:
                    return True
                # Non-2xx, retry
            except httpx.RequestError:
                pass  # Network error, retry

            if attempt < self._max_retries:
                delay = self._base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        return False  # All retries exhausted
```

### 4. WebhookContext (Request-Scoped)

```python
@dataclass
class WebhookContext:
    """Request-scoped webhook configuration."""
    url: str
    secret: str | None
    correlation_id: str
    sequence: int = 0

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

# Store in ContextVar for request-scoped access
_webhook_context: ContextVar[WebhookContext | None] = ContextVar("webhook_context", default=None)
```

### 5. Integration Point: OrchestratorComponent

**Option A: Hook into orchestrator event emission**
```python
class WebhookDeliveryComponent(OrchestratorComponent):
    """Delivers webhooks when artifacts are published."""

    name: str = "webhook_delivery"
    priority: int = 200  # Run late, after other components

    async def on_after_publish(
        self,
        orchestrator: Flock,
        artifact: Artifact,
    ) -> None:
        ctx = _webhook_context.get()
        if ctx is None:
            return  # No webhook configured for this request

        payload = WebhookPayload(
            correlation_id=ctx.correlation_id,
            sequence=ctx.next_sequence(),
            artifact=WebhookArtifact(
                id=str(artifact.id),
                type=artifact.type,
                produced_by=artifact.produced_by,
                payload=artifact.payload,
                created_at=artifact.created_at.isoformat(),
                tags=list(artifact.tags),
            ),
            timestamp=datetime.utcnow().isoformat(),
        )

        # Fire-and-forget delivery (don't block workflow)
        asyncio.create_task(
            self._delivery_service.deliver(ctx.url, payload, ctx.secret)
        )
```

**Option B: Hook into existing WebSocketManager pattern**

The existing `WebSocketManager.broadcast()` in `control_routes_component.py:238` already emits events. We can add a webhook variant alongside websocket.

---

## Data Flow

### Webhook Delivery Flow
```
1. Client → POST /api/v1/artifacts + webhook_url
2. Create WebhookContext (store in ContextVar)
3. Publish artifact to orchestrator
4. [For each artifact produced]:
   a. WebhookDeliveryComponent.on_after_publish() triggered
   b. Build WebhookPayload with sequence number
   c. Sign payload if secret provided
   d. Fire-and-forget async delivery (don't block)
   e. Retry on failure (1s, 2s, 4s backoff)
5. Return response to client (webhook delivery continues in background)
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| URL injection | Validate URL format (HttpUrl type) |
| SSRF attacks | Optional: restrict to non-private IPs |
| Replay attacks | Include timestamp in payload |
| Spoofing | HMAC signature with shared secret |

---

## Testing Strategy

| Component | Test Type | Key Scenarios |
|-----------|-----------|---------------|
| HMAC Signing | Unit | Correct signature, empty secret |
| Delivery | Unit | Success, retry on 500, retry exhausted |
| Integration | E2E | Publish → webhook received |
| Timeout | Unit | Slow endpoint doesn't block workflow |
