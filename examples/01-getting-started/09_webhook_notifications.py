"""
Example 09: Webhook Notifications with Flock REST API

This example demonstrates Flock's webhook notification system.
When artifacts are published via the REST API with a webhook configuration,
Flock sends real-time HTTP POST notifications to your endpoint.

We use httpbin.org to test webhooks - it echoes back what it receives.

Key Concepts:
    1. Webhooks are configured PER-REQUEST via the REST API
    2. The WebhookDeliveryComponent reads from request context (not constructor)
    3. Each artifact published triggers a webhook to your configured URL
    4. HMAC signatures provide request authenticity verification

Run:
    # Start the Flock server first
    uv run python examples/01-getting-started/09_webhook_notifications.py

    # Then in another terminal, publish with webhook:
    curl -X POST http://localhost:8000/api/v1/artifacts/sync \\
        -H "Content-Type: application/json" \\
        -d '{
            "type": "BugReport",
            "payload": {"title": "Test bug", "description": "Test", "severity": "high"},
            "webhook": {
                "url": "https://httpbin.org/anything",
                "secret": "your-hmac-secret"
            }
        }'
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.api.service import BlackboardHTTPService
from flock.components.orchestrator import WebhookDeliveryComponent
from flock.core import flock_type


# ============================================================================
# CONFIGURATION
# ============================================================================

# Server settings
HOST = "localhost"
PORT = 8000

# ============================================================================


@flock_type
class BugReport(BaseModel):
    """A bug report to analyze."""

    title: str
    description: str
    severity: str = "medium"


@flock_type
class BugAnalysis(BaseModel):
    """Analysis of a bug report."""

    category: str
    priority: int
    recommendation: str


async def main():
    """Run the webhook notification example server."""
    print("=" * 60)
    print("Flock Webhook Notifications Example")
    print("=" * 60)
    print()

    # Create Flock instance
    flock = Flock("openai/gpt-4.1")

    # Add the WebhookDeliveryComponent
    # This component reads webhook config from request context (set by REST endpoints)
    # It does NOT take webhook_url as a constructor parameter
    flock.add_component(WebhookDeliveryComponent())

    # Define a simple bug analyzer agent
    flock.agent("bug_analyzer").description(
        "Analyzes bug reports and categorizes them"
    ).consumes(BugReport).publishes(BugAnalysis)

    # Create HTTP service
    service = BlackboardHTTPService(flock)

    print("Starting Flock HTTP server...")
    print(f"Server running at: http://{HOST}:{PORT}")
    print()
    print("=" * 60)
    print("HOW TO USE WEBHOOKS")
    print("=" * 60)
    print()
    print("1. Async publish with webhook notification:")
    print()
    print(f'   curl -X POST http://{HOST}:{PORT}/api/v1/artifacts \\')
    print('       -H "Content-Type: application/json" \\')
    print("       -d '{")
    print('           "type": "BugReport",')
    print('           "payload": {')
    print('               "title": "Login broken",')
    print('               "description": "Cannot login on mobile",')
    print('               "severity": "high"')
    print("           },")
    print('           "webhook": {')
    print('               "url": "https://httpbin.org/anything",')
    print('               "secret": "optional-hmac-secret"')
    print("           }")
    print("       }'")
    print()
    print("2. Sync publish (waits for completion) with webhook:")
    print()
    print(f'   curl -X POST http://{HOST}:{PORT}/api/v1/artifacts/sync \\')
    print('       -H "Content-Type: application/json" \\')
    print("       -d '{")
    print('           "type": "BugReport",')
    print('           "payload": {"title": "Test", "description": "Test bug"},')
    print('           "webhook": {"url": "https://httpbin.org/anything"},')
    print('           "timeout": 30')
    print("       }'")
    print()
    print("=" * 60)
    print("WEBHOOK PAYLOAD STRUCTURE")
    print("=" * 60)
    print("""
{
  "event": "artifact.published",
  "timestamp": "2025-01-15T10:30:00.123456Z",
  "artifact": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "BugAnalysis",
    "payload": {
      "category": "UI/UX",
      "priority": 1,
      "recommendation": "..."
    },
    "produced_by": "bug_analyzer",
    "correlation_id": "workflow-123"
  }
}
""")
    print("HMAC Signature: X-Flock-Signature: sha256=<hex-digest>")
    print()
    print("=" * 60)
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()

    # Run the server
    import uvicorn

    await uvicorn.Server(
        uvicorn.Config(service.app, host=HOST, port=PORT, log_level="info")
    ).serve()


if __name__ == "__main__":
    asyncio.run(main())
