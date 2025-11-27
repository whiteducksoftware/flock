"""
Example 09: Webhook Notifications with httpbin

This example demonstrates Flock's webhook notification system.
When artifacts are published, Flock can send real-time HTTP POST
notifications to external endpoints.

We use httpbin.org (or a local httpbin instance) to test webhooks.

Setup:
    # Option 1: Use httpbin.org (public, inspect at https://httpbin.org/#/Anything)
    WEBHOOK_URL = "https://httpbin.org/anything"

    # Option 2: Run local httpbin for faster testing
    docker run -p 80:80 kennethreitz/httpbin
    WEBHOOK_URL = "http://localhost/anything"

What this example shows:
    1. Basic webhook configuration
    2. Webhook payload structure
    3. How artifacts trigger webhooks
    4. HMAC signature verification (optional)

Run:
    uv run python examples/01-getting-started/09_webhook_notifications.py
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.components.orchestrator import WebhookDeliveryComponent
from flock.core import flock_type

# ============================================================================
# CONFIGURATION - Update this URL to point to your httpbin instance
# ============================================================================

# Use httpbin.org for testing (responses visible at URL)
# Or run local: docker run -p 80:80 kennethreitz/httpbin
WEBHOOK_URL = "https://httpbin.org/anything"

# Optional: Set a secret for HMAC signature verification
# When set, each webhook will include X-Flock-Signature header
WEBHOOK_SECRET = None  # Set to "your-secret" to enable HMAC

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
    """Run the webhook notification example."""
    print("=" * 60)
    print("Flock Webhook Notifications Example")
    print("=" * 60)
    print(f"\nWebhook URL: {WEBHOOK_URL}")
    print(f"HMAC Signing: {'Enabled' if WEBHOOK_SECRET else 'Disabled'}")
    print()

    # Create Flock instance
    flock = Flock("openai/gpt-4.1")

    # Add webhook component
    # This will POST to WEBHOOK_URL whenever an artifact is published
    webhook_component = WebhookDeliveryComponent(
        webhook_url=WEBHOOK_URL,
        webhook_secret=WEBHOOK_SECRET,  # Optional HMAC signing
        max_retries=2,  # Retry failed deliveries
        timeout=10.0,  # 10 second timeout
    )
    flock.add_component(webhook_component)

    # Define a simple bug analyzer agent
    flock.agent("bug_analyzer").description(
        "Analyzes bug reports and categorizes them"
    ).consumes(BugReport).publishes(BugAnalysis)

    print("Starting workflow...")
    print("-" * 60)

    # Publish a bug report - this will:
    # 1. Trigger webhook for BugReport (input artifact)
    # 2. Run bug_analyzer agent
    # 3. Trigger webhook for BugAnalysis (output artifact)
    await flock.publish(
        BugReport(
            title="Login button not working",
            description="Users report the login button is unresponsive on mobile",
            severity="high",
        )
    )

    # Run until all agents complete
    await flock.run_until_idle()

    print("-" * 60)
    print("\nWorkflow complete!")
    print("\nWebhooks were sent to:", WEBHOOK_URL)
    print("\nPayload structure sent to your endpoint:")
    print(
        """
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
    "correlation_id": "workflow-123",
    "created_at": "2025-01-15T10:30:00.000000Z"
  }
}
"""
    )

    if WEBHOOK_SECRET:
        print("HMAC Signature Header: X-Flock-Signature")
        print("Format: sha256=<hex-digest>")
        print("\nVerify signature with:")
        print(
            """
import hmac
import hashlib

def verify(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
"""
        )

    print("\nFor more details, see: docs/guides/webhooks.md")


if __name__ == "__main__":
    asyncio.run(main())
