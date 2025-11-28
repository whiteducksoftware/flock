"""Tests for WebhookDeliveryComponent.

Spec: 002-webhook-notifications
Phase 4: Orchestrator Integration
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from flock.core.artifacts import Artifact


def _make_artifact(
    type_name: str = "TestArtifact",
    payload: dict | None = None,
    produced_by: str = "test-agent",
    correlation_id: str | None = None,
) -> Artifact:
    """Create a test artifact."""
    return Artifact(
        id=uuid4(),
        type=type_name,
        payload=payload or {"key": "value"},
        produced_by=produced_by,
        correlation_id=correlation_id or str(uuid4()),
        created_at=datetime.now(UTC),
        tags=set(),
        version=1,
    )


class TestWebhookDeliveryComponent:
    """Tests for WebhookDeliveryComponent."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        return MagicMock()

    @pytest.fixture
    def mock_delivery_service(self):
        """Create mock delivery service."""
        service = MagicMock()
        service.deliver = AsyncMock(return_value=True)
        return service

    @pytest.mark.asyncio
    async def test_fires_webhook_when_context_is_set(
        self, mock_orchestrator, mock_delivery_service
    ):
        """Component should fire webhook when WebhookContext is set."""
        from flock.api.webhooks import WebhookContext, set_webhook_context, clear_webhook_context
        from flock.components.orchestrator.webhook import WebhookDeliveryComponent

        component = WebhookDeliveryComponent(delivery_service=mock_delivery_service)
        artifact = _make_artifact(correlation_id="test-correlation")

        # Set webhook context
        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret="my-secret",
            correlation_id="test-correlation",
        )
        set_webhook_context(ctx)

        try:
            # Call the hook
            result = await component.on_artifact_published(mock_orchestrator, artifact)

            # Should return artifact unchanged
            assert result == artifact

            # Wait a bit for fire-and-forget task to start
            await asyncio.sleep(0.01)

            # Delivery service should have been called
            mock_delivery_service.deliver.assert_called_once()

            # Check the call arguments
            call_args = mock_delivery_service.deliver.call_args
            assert call_args.kwargs["url"] == "https://example.com/webhook"
            assert call_args.kwargs["secret"] == "my-secret"

            payload = call_args.kwargs["payload"]
            assert payload.correlation_id == "test-correlation"
            assert payload.artifact.id == str(artifact.id)

        finally:
            clear_webhook_context()

    @pytest.mark.asyncio
    async def test_does_nothing_when_context_is_none(
        self, mock_orchestrator, mock_delivery_service
    ):
        """Component should do nothing when no WebhookContext is set."""
        from flock.api.webhooks import clear_webhook_context
        from flock.components.orchestrator.webhook import WebhookDeliveryComponent

        component = WebhookDeliveryComponent(delivery_service=mock_delivery_service)
        artifact = _make_artifact()

        # Ensure no context
        clear_webhook_context()

        # Call the hook
        result = await component.on_artifact_published(mock_orchestrator, artifact)

        # Should return artifact unchanged
        assert result == artifact

        # Wait a bit
        await asyncio.sleep(0.01)

        # Delivery service should NOT have been called
        mock_delivery_service.deliver.assert_not_called()

    @pytest.mark.asyncio
    async def test_payload_includes_correct_correlation_and_sequence(
        self, mock_orchestrator, mock_delivery_service
    ):
        """Payload should include correct correlation_id and sequence number."""
        from flock.api.webhooks import WebhookContext, set_webhook_context, clear_webhook_context
        from flock.components.orchestrator.webhook import WebhookDeliveryComponent

        component = WebhookDeliveryComponent(delivery_service=mock_delivery_service)

        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="workflow-123",
        )
        set_webhook_context(ctx)

        try:
            # Publish first artifact
            artifact1 = _make_artifact(correlation_id="workflow-123")
            await component.on_artifact_published(mock_orchestrator, artifact1)
            await asyncio.sleep(0.01)

            # Check first payload
            call1 = mock_delivery_service.deliver.call_args_list[0]
            payload1 = call1.kwargs["payload"]
            assert payload1.correlation_id == "workflow-123"
            assert payload1.sequence == 1

            # Publish second artifact
            artifact2 = _make_artifact(correlation_id="workflow-123")
            await component.on_artifact_published(mock_orchestrator, artifact2)
            await asyncio.sleep(0.01)

            # Check second payload
            call2 = mock_delivery_service.deliver.call_args_list[1]
            payload2 = call2.kwargs["payload"]
            assert payload2.correlation_id == "workflow-123"
            assert payload2.sequence == 2

        finally:
            clear_webhook_context()

    @pytest.mark.asyncio
    async def test_delivery_is_fire_and_forget(
        self, mock_orchestrator
    ):
        """Webhook delivery should not block the hook execution."""
        from flock.api.webhooks import WebhookContext, set_webhook_context, clear_webhook_context
        from flock.components.orchestrator.webhook import WebhookDeliveryComponent

        # Create a slow delivery service
        slow_service = MagicMock()

        async def slow_deliver(*args, **kwargs):
            await asyncio.sleep(1.0)  # Simulate slow delivery
            return True

        slow_service.deliver = slow_deliver

        component = WebhookDeliveryComponent(delivery_service=slow_service)
        artifact = _make_artifact()

        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="test-corr",
        )
        set_webhook_context(ctx)

        try:
            import time
            start = time.monotonic()

            # Call the hook
            result = await component.on_artifact_published(mock_orchestrator, artifact)

            elapsed = time.monotonic() - start

            # Should return immediately (fire-and-forget)
            assert result == artifact
            assert elapsed < 0.1  # Should be much faster than 1 second

        finally:
            clear_webhook_context()

    @pytest.mark.asyncio
    async def test_payload_has_correct_artifact_data(
        self, mock_orchestrator, mock_delivery_service
    ):
        """WebhookPayload should contain correct artifact data."""
        from flock.api.webhooks import WebhookContext, set_webhook_context, clear_webhook_context
        from flock.components.orchestrator.webhook import WebhookDeliveryComponent

        component = WebhookDeliveryComponent(delivery_service=mock_delivery_service)

        artifact = _make_artifact(
            type_name="MovieReview",
            payload={"title": "Inception", "rating": 5},
            produced_by="review-agent",
        )
        artifact.tags = {"genre:scifi", "verified"}

        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="review-workflow",
        )
        set_webhook_context(ctx)

        try:
            await component.on_artifact_published(mock_orchestrator, artifact)
            await asyncio.sleep(0.01)

            call = mock_delivery_service.deliver.call_args
            payload = call.kwargs["payload"]

            assert payload.event_type == "artifact.created"
            assert payload.artifact.id == str(artifact.id)
            assert payload.artifact.type == "MovieReview"
            assert payload.artifact.produced_by == "review-agent"
            assert payload.artifact.payload == {"title": "Inception", "rating": 5}
            assert set(payload.artifact.tags) == {"genre:scifi", "verified"}

        finally:
            clear_webhook_context()

    def test_component_has_correct_priority(self):
        """Component should have high priority (run late)."""
        from flock.components.orchestrator.webhook import WebhookDeliveryComponent

        component = WebhookDeliveryComponent()
        assert component.priority == 200

    def test_component_has_correct_name(self):
        """Component should have correct name."""
        from flock.components.orchestrator.webhook import WebhookDeliveryComponent

        component = WebhookDeliveryComponent()
        assert component.name == "webhook_delivery"
