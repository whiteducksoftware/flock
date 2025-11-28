# Webhook Notifications

Flock can deliver real-time notifications to external HTTP endpoints when artifacts are published. This enables integration with external systems like Slack, Discord, custom dashboards, or any service that accepts HTTP callbacks.

## Quick Start

```python
from flock import Flock
from flock.components.orchestrator import WebhookDeliveryComponent

flock = Flock("openai/gpt-4.1")

# Add webhook component with your endpoint
flock.add_component(WebhookDeliveryComponent(
    webhook_url="https://your-server.com/webhook",
))

# Now every published artifact triggers a webhook!
```

## Configuration Options

```python
WebhookDeliveryComponent(
    # Required
    webhook_url="https://your-server.com/webhook",

    # Optional authentication
    webhook_secret="your-hmac-secret",  # For HMAC-SHA256 signatures
    auth_header="Authorization",         # Custom auth header name
    auth_value="Bearer your-token",      # Auth header value

    # Retry configuration
    max_retries=3,                       # Number of retry attempts (default: 3)
    retry_delay=1.0,                     # Initial delay in seconds (default: 1.0)
    retry_backoff=2.0,                   # Exponential backoff multiplier (default: 2.0)

    # Timeout
    timeout=30.0,                        # Request timeout in seconds (default: 30.0)
)
```

## Webhook Payload

When an artifact is published, Flock sends a POST request with this JSON payload:

```json
{
  "event": "artifact.published",
  "timestamp": "2025-01-15T10:30:00.123456Z",
  "artifact": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "BugAnalysis",
    "payload": {
      "severity": "High",
      "bugs_found": ["Memory leak in cache handler"],
      "confidence": 0.92
    },
    "produced_by": "bug_detector",
    "correlation_id": "workflow-123",
    "created_at": "2025-01-15T10:30:00.000000Z",
    "tags": ["critical", "reviewed"],
    "version": 1
  }
}
```

## HMAC Signature Verification

When `webhook_secret` is configured, Flock signs each request with HMAC-SHA256. The signature is sent in the `X-Flock-Signature` header.

### Verifying Signatures (Python Example)

```python
import hmac
import hashlib

def verify_webhook(request_body: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature."""
    expected = hmac.new(
        secret.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(f"sha256={expected}", signature)

# In your webhook handler:
@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Flock-Signature", "")

    if not verify_webhook(body, signature, "your-secret"):
        raise HTTPException(401, "Invalid signature")

    data = json.loads(body)
    # Process the webhook...
```

### Verifying Signatures (Node.js Example)

```javascript
const crypto = require('crypto');

function verifyWebhook(body, signature, secret) {
  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(body)
    .digest('hex');

  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}
```

## Retry Behavior

Failed webhook deliveries are automatically retried with exponential backoff:

| Attempt | Delay | Total Wait |
|---------|-------|------------|
| 1 | Immediate | 0s |
| 2 | 1s | 1s |
| 3 | 2s | 3s |
| 4 | 4s | 7s |

After all retries are exhausted, the failure is logged but does not block artifact publishing.

## Filtering Webhooks

You can filter which artifacts trigger webhooks by subclassing:

```python
from flock.components.orchestrator import WebhookDeliveryComponent

class FilteredWebhookComponent(WebhookDeliveryComponent):
    """Only send webhooks for specific artifact types."""

    async def on_artifact_published(self, orchestrator, artifact):
        # Only notify for high-severity analyses
        if artifact.type == "BugAnalysis":
            payload = artifact.payload
            if payload.get("severity") in ["Critical", "High"]:
                return await super().on_artifact_published(orchestrator, artifact)

        return artifact  # Pass through without webhook
```

## Integration Examples

### Slack Integration

```python
# Slack expects a specific format
class SlackWebhookComponent(WebhookDeliveryComponent):
    async def _build_payload(self, artifact):
        return {
            "text": f"New {artifact.type} from {artifact.produced_by}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{artifact.type}*\n{json.dumps(artifact.payload, indent=2)}"
                    }
                }
            ]
        }
```

### Discord Integration

```python
class DiscordWebhookComponent(WebhookDeliveryComponent):
    async def _build_payload(self, artifact):
        return {
            "content": f"New artifact: {artifact.type}",
            "embeds": [{
                "title": artifact.type,
                "description": f"Produced by: {artifact.produced_by}",
                "fields": [
                    {"name": k, "value": str(v), "inline": True}
                    for k, v in artifact.payload.items()
                ]
            }]
        }
```

## Best Practices

1. **Always use HMAC signatures in production** - Prevents unauthorized webhook spoofing
2. **Set reasonable timeouts** - Don't let slow endpoints block your workflow
3. **Handle failures gracefully** - Webhook failures shouldn't crash your application
4. **Use idempotency** - Your webhook handler should handle duplicate deliveries
5. **Log webhook activity** - Helps debugging integration issues

## Troubleshooting

### Webhooks not being sent

1. Check that `WebhookDeliveryComponent` is added to your Flock instance
2. Verify the `webhook_url` is correct and reachable
3. Check logs for error messages

### Signature verification failing

1. Ensure the secret matches on both sides
2. Verify you're using the raw request body (not parsed JSON)
3. Check that the signature header name is correct (`X-Flock-Signature`)

### Retries exhausted

1. Check your endpoint's availability
2. Increase `max_retries` or `timeout` if needed
3. Consider using a message queue for guaranteed delivery

## See Also

- [REST API Guide](rest-api.md) - Programmatic access to Flock
- [Orchestrator Components](orchestrator-components.md) - Extending orchestrator behavior
- [Examples: Webhook with httpbin](../../examples/01-getting-started/09_webhook_notifications.py) - Working example
