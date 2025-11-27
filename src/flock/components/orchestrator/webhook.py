"""Webhook delivery component for orchestrator integration.

Fires webhooks when artifacts are published to the blackboard,
using request-scoped WebhookContext to determine delivery configuration.

Spec: 002-webhook-notifications
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import PrivateAttr

from flock.api.models import WebhookArtifact, WebhookPayload
from flock.api.webhooks import (
    WebhookDeliveryService,
    get_webhook_context,
)
from flock.components.orchestrator.base import OrchestratorComponent
from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from flock.core import Flock
    from flock.core.artifacts import Artifact


logger = get_logger("flock.components.orchestrator.webhook")


class WebhookDeliveryComponent(OrchestratorComponent):
    """Delivers webhooks when artifacts are published.

    Uses the request-scoped WebhookContext (set by REST endpoints) to determine
    whether and where to deliver webhook notifications. Delivery is fire-and-forget
    to avoid blocking workflow execution.

    Priority: 200 (runs late, after other processing components)

    Examples:
        >>> # Component is typically auto-registered or added to Flock
        >>> flock = Flock("openai/gpt-4.1")
        >>> flock.add_component(WebhookDeliveryComponent())

        >>> # Webhooks are triggered automatically when:
        >>> # 1. REST endpoint sets WebhookContext
        >>> # 2. Artifact is published to blackboard
        >>> # 3. This component fires webhook in background
    """

    name: str = "webhook_delivery"
    priority: int = 200  # Run late, after other components

    # Private attributes for dependency injection
    _delivery_service: WebhookDeliveryService = PrivateAttr()
    _pending_tasks: set[asyncio.Task[None]] = PrivateAttr(default_factory=set)

    def __init__(
        self,
        delivery_service: WebhookDeliveryService | None = None,
        **kwargs,
    ):
        """Initialize webhook delivery component.

        Args:
            delivery_service: Optional delivery service (for testing).
                              If not provided, creates default instance.
            **kwargs: Additional arguments passed to OrchestratorComponent
        """
        super().__init__(**kwargs)
        self._delivery_service = delivery_service or WebhookDeliveryService()

    async def on_artifact_published(
        self,
        orchestrator: Flock,
        artifact: Artifact,
    ) -> Artifact | None:
        """Fire webhook when artifact is published (if context is set).

        Checks for WebhookContext in the current async task. If present,
        builds a WebhookPayload and fires delivery in the background.

        Args:
            orchestrator: Flock orchestrator instance
            artifact: The artifact that was just published

        Returns:
            The artifact unchanged (webhook delivery doesn't modify artifacts)
        """
        # Check for webhook context (set by REST endpoints)
        ctx = get_webhook_context()
        if ctx is None:
            # No webhook configured for this request
            return artifact

        # Build webhook payload
        payload = WebhookPayload(
            event_type="artifact.created",
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
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Fire-and-forget delivery (don't block workflow)
        # Store task reference to prevent garbage collection (RUF006)
        task = asyncio.create_task(
            self._deliver_webhook(ctx.url, payload, ctx.secret),
            name=f"webhook-delivery-{artifact.id}",
        )
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

        logger.debug(
            "Webhook delivery scheduled for artifact %s to %s",
            artifact.id,
            ctx.url,
        )

        return artifact

    async def _deliver_webhook(
        self,
        url: str,
        payload: WebhookPayload,
        secret: str | None,
    ) -> None:
        """Deliver webhook payload (background task).

        Args:
            url: Webhook endpoint URL
            payload: The webhook payload to deliver
            secret: Optional secret for HMAC signing
        """
        try:
            success = await self._delivery_service.deliver(
                url=url,
                payload=payload,
                secret=secret,
            )
            if not success:
                logger.warning(
                    "Webhook delivery failed after retries for artifact %s",
                    payload.artifact.id,
                )
        except Exception as e:
            logger.error(
                "Unexpected error during webhook delivery: %s",
                str(e),
                exc_info=True,
            )


__all__ = ["WebhookDeliveryComponent"]
