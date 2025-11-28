"""Webhook delivery and context management.

Provides webhook delivery service with HMAC signing and retry logic,
plus request-scoped context management using ContextVar.

Spec: 002-webhook-notifications
"""

import asyncio
import hashlib
import hmac
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field

import httpx

from flock.api.models import WebhookPayload


logger = logging.getLogger(__name__)


# ============================================================================
# HMAC Signing
# ============================================================================


def sign_payload(payload: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload.

    Args:
        payload: The raw bytes to sign
        secret: The secret key for HMAC

    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    return hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()


# ============================================================================
# Webhook Delivery Service
# ============================================================================


class WebhookDeliveryService:
    """Handles webhook delivery with signing and retry logic.

    Features:
    - HMAC-SHA256 signing with optional secret
    - Exponential backoff retry (base_delay * 2^attempt)
    - Configurable max retries and timeout
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        timeout: float = 10.0,
    ) -> None:
        """Initialize delivery service.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds for exponential backoff (default: 1.0)
            timeout: HTTP request timeout in seconds (default: 10.0)
        """
        self._client = httpx.AsyncClient(timeout=timeout)
        self._max_retries = max_retries
        self._base_delay = base_delay

    async def deliver(
        self,
        url: str,
        payload: WebhookPayload,
        secret: str | None = None,
    ) -> bool:
        """Deliver webhook payload to URL with retry logic.

        Args:
            url: Webhook endpoint URL
            payload: The webhook payload to deliver
            secret: Optional secret for HMAC signing

        Returns:
            True if delivery succeeded, False if all retries exhausted
        """
        body = payload.model_dump_json().encode()
        headers = {"Content-Type": "application/json"}

        if secret:
            signature = sign_payload(body, secret)
            headers["X-Flock-Signature"] = f"sha256={signature}"

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(url, content=body, headers=headers)
                if response.is_success:
                    logger.debug(
                        "Webhook delivered successfully",
                        extra={"url": url, "attempt": attempt + 1},
                    )
                    return True

                logger.warning(
                    "Webhook delivery failed with status %d",
                    response.status_code,
                    extra={"url": url, "attempt": attempt + 1},
                )

            except httpx.RequestError as e:
                logger.warning(
                    "Webhook delivery network error: %s",
                    str(e),
                    extra={"url": url, "attempt": attempt + 1},
                )

            # Apply exponential backoff before retry
            if attempt < self._max_retries:
                delay = self._base_delay * (2**attempt)
                await asyncio.sleep(delay)

        logger.error(
            "Webhook delivery failed after %d attempts",
            self._max_retries + 1,
            extra={"url": url},
        )
        return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


# ============================================================================
# Webhook Context (Request-Scoped)
# ============================================================================


@dataclass
class WebhookContext:
    """Request-scoped webhook configuration.

    Stores webhook URL, optional secret, and tracks sequence numbers
    for artifacts produced within a single workflow.
    """

    url: str
    secret: str | None
    correlation_id: str
    sequence: int = field(default=0)

    def next_sequence(self) -> int:
        """Increment and return the next sequence number.

        Returns:
            The new sequence number (starts at 1)
        """
        self.sequence += 1
        return self.sequence


# Module-level ContextVar for request-scoped webhook context
_webhook_context: ContextVar[WebhookContext | None] = ContextVar(
    "webhook_context", default=None
)


def set_webhook_context(ctx: WebhookContext) -> None:
    """Set the webhook context for the current async task.

    Args:
        ctx: The WebhookContext to store
    """
    _webhook_context.set(ctx)


def get_webhook_context() -> WebhookContext | None:
    """Get the webhook context for the current async task.

    Returns:
        The current WebhookContext, or None if not set
    """
    return _webhook_context.get()


def clear_webhook_context() -> None:
    """Clear the webhook context for the current async task."""
    _webhook_context.set(None)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "WebhookContext",
    "WebhookDeliveryService",
    "clear_webhook_context",
    "get_webhook_context",
    "set_webhook_context",
    "sign_payload",
]
