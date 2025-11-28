"""Tests for Webhook Integration with REST Endpoints.

Spec: 002-webhook-notifications
Phase 5: REST Endpoint Integration
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from flock.api.service import BlackboardHTTPService
from flock.core.artifacts import Artifact
from flock.registry import flock_type


@flock_type(name="WebhookTestInput")
class WebhookTestInput(BaseModel):
    """Test input artifact type."""

    value: str


@flock_type(name="WebhookTestOutput")
class WebhookTestOutput(BaseModel):
    """Test output artifact type."""

    result: str


def _make_artifact(
    type_name: str,
    payload: dict,
    produced_by: str,
    correlation_id: str,
) -> Artifact:
    """Helper to create test artifacts."""
    return Artifact(
        id=uuid4(),
        type=type_name,
        payload=payload,
        produced_by=produced_by,
        correlation_id=correlation_id,
        created_at=datetime.now(UTC),
        tags=set(),
        version=1,
    )


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator for webhook integration tests."""
    orchestrator = Mock()
    orchestrator.store = Mock()
    orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
    orchestrator.publish = AsyncMock()
    orchestrator.run_until_idle = AsyncMock()
    orchestrator.metrics = {"agent_runs": 0, "artifacts_published": 0}
    orchestrator.agents = []
    return orchestrator


@pytest.fixture
def service(mock_orchestrator):
    """Create service instance with mocked orchestrator."""
    return BlackboardHTTPService(mock_orchestrator)


class TestAsyncPublishWithWebhook:
    """Tests for POST /api/v1/artifacts with webhook configuration."""

    @pytest.mark.asyncio
    async def test_publish_with_webhook_sets_context(self, service, mock_orchestrator):
        """When webhook is provided, WebhookContext should be set."""
        from flock.api.webhooks import get_webhook_context

        captured_context = None

        async def capture_context(artifact_dict):
            nonlocal captured_context
            captured_context = get_webhook_context()

        mock_orchestrator.publish = capture_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://example.com/webhook",
                        "secret": "my-secret",
                    },
                },
            )

        assert response.status_code == 200
        # Context should have been set during publish
        assert captured_context is not None
        assert captured_context.url == "https://example.com/webhook"
        assert captured_context.secret == "my-secret"

    @pytest.mark.asyncio
    async def test_publish_correlation_id_matches_webhook_context(
        self, service, mock_orchestrator
    ):
        """Async publish should pass same correlation_id to artifact and webhook context."""
        from flock.api.webhooks import get_webhook_context

        captured_artifact = None
        captured_context = None

        async def capture_both(artifact_dict):
            nonlocal captured_artifact, captured_context
            captured_artifact = artifact_dict
            captured_context = get_webhook_context()

        mock_orchestrator.publish = capture_both

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://example.com/webhook",
                    },
                },
            )

        assert response.status_code == 200
        # Both artifact and webhook context should have matching correlation_id
        assert captured_context is not None
        assert captured_artifact is not None
        assert "correlation_id" in captured_artifact
        assert captured_artifact["correlation_id"] == captured_context.correlation_id

    @pytest.mark.asyncio
    async def test_publish_without_webhook_no_context(self, service, mock_orchestrator):
        """When no webhook is provided, context should be None."""
        from flock.api.webhooks import get_webhook_context

        captured_context = "not_checked"

        async def capture_context(artifact_dict):
            nonlocal captured_context
            captured_context = get_webhook_context()

        mock_orchestrator.publish = capture_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                },
            )

        assert response.status_code == 200
        assert captured_context is None

    @pytest.mark.asyncio
    async def test_publish_context_cleared_after_request(
        self, service, mock_orchestrator
    ):
        """WebhookContext should be cleared after request completes."""
        from flock.api.webhooks import get_webhook_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://example.com/webhook",
                    },
                },
            )

        assert response.status_code == 200
        # Context should be cleared after request
        assert get_webhook_context() is None

    @pytest.mark.asyncio
    async def test_publish_webhook_correlation_id_generated(
        self, service, mock_orchestrator
    ):
        """Webhook context should have a correlation_id."""
        from flock.api.webhooks import get_webhook_context

        captured_context = None

        async def capture_context(artifact_dict):
            nonlocal captured_context
            captured_context = get_webhook_context()

        mock_orchestrator.publish = capture_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://example.com/webhook",
                    },
                },
            )

        assert response.status_code == 200
        assert captured_context is not None
        assert captured_context.correlation_id is not None
        assert len(captured_context.correlation_id) > 0


class TestSyncPublishWithWebhook:
    """Tests for POST /api/v1/artifacts/sync with webhook configuration."""

    @pytest.mark.asyncio
    async def test_sync_publish_with_webhook_sets_context(
        self, service, mock_orchestrator
    ):
        """When webhook is provided to sync endpoint, context should be set."""
        from flock.api.webhooks import get_webhook_context

        captured_context = None

        async def capture_context(artifact_dict):
            nonlocal captured_context
            captured_context = get_webhook_context()

        mock_orchestrator.publish = capture_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://example.com/webhook",
                        "secret": "sync-secret",
                    },
                },
            )

        assert response.status_code == 200
        assert captured_context is not None
        assert captured_context.url == "https://example.com/webhook"
        assert captured_context.secret == "sync-secret"

    @pytest.mark.asyncio
    async def test_sync_publish_webhook_uses_response_correlation_id(
        self, service, mock_orchestrator
    ):
        """Webhook context correlation_id should match response correlation_id."""
        from flock.api.webhooks import get_webhook_context

        captured_context = None

        async def capture_context(artifact_dict):
            nonlocal captured_context
            captured_context = get_webhook_context()

        mock_orchestrator.publish = capture_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://example.com/webhook",
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()

        # Webhook context correlation_id should match response
        assert captured_context is not None
        assert captured_context.correlation_id == data["correlation_id"]

    @pytest.mark.asyncio
    async def test_sync_publish_without_webhook_no_context(
        self, service, mock_orchestrator
    ):
        """When no webhook provided to sync endpoint, context should be None."""
        from flock.api.webhooks import get_webhook_context

        captured_context = "not_checked"

        async def capture_context(artifact_dict):
            nonlocal captured_context
            captured_context = get_webhook_context()

        mock_orchestrator.publish = capture_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                },
            )

        assert response.status_code == 200
        assert captured_context is None

    @pytest.mark.asyncio
    async def test_sync_publish_context_cleared_after_request(
        self, service, mock_orchestrator
    ):
        """Context should be cleared after sync request completes."""
        from flock.api.webhooks import get_webhook_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://example.com/webhook",
                    },
                },
            )

        assert response.status_code == 200
        # Context should be cleared after request
        assert get_webhook_context() is None


class TestWebhookContextIsolation:
    """Test that webhook context is isolated per request."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_isolated_contexts(
        self, service, mock_orchestrator
    ):
        """Concurrent requests should have isolated webhook contexts."""
        from flock.api.webhooks import get_webhook_context

        contexts_captured = []

        async def capture_context(artifact_dict):
            ctx = get_webhook_context()
            if ctx:
                contexts_captured.append(ctx.url)
            else:
                contexts_captured.append(None)
            # Add small delay to allow interleaving
            await asyncio.sleep(0.01)

        mock_orchestrator.publish = capture_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send two concurrent requests with different webhook URLs
            task1 = client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test1"},
                    "webhook": {"url": "https://webhook1.example.com"},
                },
            )
            task2 = client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test2"},
                    "webhook": {"url": "https://webhook2.example.com"},
                },
            )

            responses = await asyncio.gather(task1, task2)

        assert all(r.status_code == 200 for r in responses)
        # Both contexts should have been captured
        assert len(contexts_captured) == 2
        # Each request should see its own URL (not the other's)
        # Note: Pydantic HttpUrl normalizes URLs (may add trailing slash)
        # Convert to strings for comparison
        url_strings = sorted([str(url) for url in contexts_captured])
        # Verify we captured both distinct webhook URLs (test isolation check)
        # Check exact expected URLs (Pydantic may normalize with trailing slash)
        expected_url1 = "https://webhook1.example.com/"
        expected_url2 = "https://webhook2.example.com/"
        assert url_strings[0] == expected_url1, (
            f"Expected {expected_url1}, got {url_strings[0]}"
        )
        assert url_strings[1] == expected_url2, (
            f"Expected {expected_url2}, got {url_strings[1]}"
        )


class TestWebhookValidation:
    """Test webhook configuration validation."""

    @pytest.mark.asyncio
    async def test_invalid_webhook_url_rejected(self, service, mock_orchestrator):
        """Invalid webhook URL should be rejected."""
        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {"url": "not-a-valid-url"},
                },
            )

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_webhook_secret_optional(self, service, mock_orchestrator):
        """Webhook should work without secret."""
        from flock.api.webhooks import get_webhook_context

        captured_context = None

        async def capture_context(artifact_dict):
            nonlocal captured_context
            captured_context = get_webhook_context()

        mock_orchestrator.publish = capture_context

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "WebhookTestInput",
                    "payload": {"value": "test"},
                    "webhook": {"url": "https://example.com/webhook"},
                },
            )

        assert response.status_code == 200
        assert captured_context is not None
        assert captured_context.secret is None
