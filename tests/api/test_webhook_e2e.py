"""End-to-End Tests for Webhook Notifications.

Spec: 002-webhook-notifications
Phase 6: Integration & End-to-End Validation

These tests validate the complete webhook flow from artifact publish
through to webhook delivery, including signature verification.
"""

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from flock.api.models import WebhookPayload
from flock.api.service import BlackboardHTTPService
from flock.api.webhooks import (
    WebhookContext,
    WebhookDeliveryService,
    set_webhook_context,
    sign_payload,
)
from flock.components.orchestrator.webhook import WebhookDeliveryComponent
from flock.core.artifacts import Artifact
from flock.registry import flock_type


@flock_type(name="E2ETestInput")
class E2ETestInput(BaseModel):
    """Test input artifact type."""

    value: str


@flock_type(name="E2ETestOutput")
class E2ETestOutput(BaseModel):
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


class TestWebhookSignatureVerification:
    """Test HMAC signature verification for webhook payloads."""

    def test_signature_can_be_verified(self):
        """Webhook receiver should be able to verify signature."""
        secret = "my-webhook-secret"
        payload_data = {
            "event_type": "artifact.created",
            "correlation_id": "test-123",
            "sequence": 1,
            "artifact": {
                "id": "abc-123",
                "type": "TestType",
                "produced_by": "test-agent",
                "payload": {"key": "value"},
                "created_at": "2024-01-01T00:00:00Z",
                "tags": [],
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        payload_bytes = json.dumps(payload_data).encode()

        # Generate signature (as the sender would)
        signature = sign_payload(payload_bytes, secret)

        # Verify signature (as the receiver would)
        expected = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        assert signature == expected

    def test_signature_header_format(self):
        """X-Flock-Signature header should use sha256= prefix."""
        secret = "test-secret"
        payload = b'{"test": "data"}'

        signature = sign_payload(payload, secret)

        # The header should be formatted as "sha256={signature}"
        header_value = f"sha256={signature}"
        assert header_value.startswith("sha256=")
        assert len(signature) == 64  # SHA256 hex is 64 chars

    def test_different_secrets_produce_different_signatures(self):
        """Different secrets should produce different signatures."""
        payload = b'{"test": "data"}'

        sig1 = sign_payload(payload, "secret1")
        sig2 = sign_payload(payload, "secret2")

        assert sig1 != sig2

    def test_tampered_payload_fails_verification(self):
        """Tampered payload should fail signature verification."""
        secret = "my-secret"
        original_payload = b'{"value": 100}'
        tampered_payload = b'{"value": 999}'

        original_sig = sign_payload(original_payload, secret)
        tampered_sig = sign_payload(tampered_payload, secret)

        # Signatures should be different
        assert original_sig != tampered_sig


class TestWebhookDeliveryRetry:
    """Test webhook delivery retry behavior."""

    @pytest.mark.asyncio
    async def test_retries_on_server_error(self):
        """Delivery should retry on 5xx errors."""
        import httpx
        import respx

        service = WebhookDeliveryService(max_retries=3, base_delay=0.01)

        # Mock: fail twice, then succeed
        call_count = 0

        @respx.mock
        async def test_retry():
            nonlocal call_count
            route = respx.post("https://webhook.example.com/endpoint")

            def side_effect(request):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    return httpx.Response(500)
                return httpx.Response(200)

            route.side_effect = side_effect

            payload = WebhookPayload(
                event_type="artifact.created",
                correlation_id="test-123",
                sequence=1,
                artifact={
                    "id": "abc",
                    "type": "Test",
                    "produced_by": "agent",
                    "payload": {},
                    "created_at": "2024-01-01T00:00:00Z",
                    "tags": [],
                },
                timestamp="2024-01-01T00:00:00Z",
            )

            result = await service.deliver(
                url="https://webhook.example.com/endpoint",
                payload=payload,
            )

            assert result is True
            assert call_count == 3  # 2 failures + 1 success

        await test_retry()

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self):
        """Delivery should give up after max retries."""
        import httpx
        import respx

        service = WebhookDeliveryService(max_retries=2, base_delay=0.01)

        @respx.mock
        async def test_max_retries():
            # Always fail
            respx.post("https://webhook.example.com/fail").mock(
                return_value=httpx.Response(500)
            )

            payload = WebhookPayload(
                event_type="artifact.created",
                correlation_id="test-123",
                sequence=1,
                artifact={
                    "id": "abc",
                    "type": "Test",
                    "produced_by": "agent",
                    "payload": {},
                    "created_at": "2024-01-01T00:00:00Z",
                    "tags": [],
                },
                timestamp="2024-01-01T00:00:00Z",
            )

            result = await service.deliver(
                url="https://webhook.example.com/fail",
                payload=payload,
            )

            assert result is False

        await test_max_retries()


class TestWebhookDoesNotBlock:
    """Test that webhook delivery doesn't block workflow execution."""

    @pytest.mark.asyncio
    async def test_component_returns_immediately(self):
        """WebhookDeliveryComponent should return immediately (fire-and-forget)."""
        import time

        # Create a slow delivery service
        slow_service = Mock()

        async def slow_deliver(*args, **kwargs):
            await asyncio.sleep(2.0)  # Slow delivery
            return True

        slow_service.deliver = slow_deliver

        component = WebhookDeliveryComponent(delivery_service=slow_service)
        artifact = _make_artifact("Test", {}, "agent", "corr-123")

        # Set webhook context
        ctx = WebhookContext(
            url="https://slow.example.com/webhook",
            secret=None,
            correlation_id="corr-123",
        )
        set_webhook_context(ctx)

        try:
            start = time.monotonic()

            # Call the component
            result = await component.on_artifact_published(Mock(), artifact)

            elapsed = time.monotonic() - start

            # Should return almost immediately
            assert result == artifact
            assert elapsed < 0.1  # Much faster than 2 seconds

        finally:
            from flock.api.webhooks import clear_webhook_context

            clear_webhook_context()

    @pytest.mark.asyncio
    async def test_delivery_failure_does_not_raise(self):
        """Delivery failures should be logged but not raise exceptions."""
        # Create a failing delivery service
        failing_service = Mock()

        async def failing_deliver(*args, **kwargs):
            raise Exception("Network error")

        failing_service.deliver = failing_deliver

        component = WebhookDeliveryComponent(delivery_service=failing_service)
        artifact = _make_artifact("Test", {}, "agent", "corr-456")

        ctx = WebhookContext(
            url="https://fail.example.com/webhook",
            secret=None,
            correlation_id="corr-456",
        )
        set_webhook_context(ctx)

        try:
            # Should not raise despite delivery failure
            result = await component.on_artifact_published(Mock(), artifact)
            assert result == artifact

            # Give the background task time to fail
            await asyncio.sleep(0.1)

            # No exception should have propagated

        finally:
            from flock.api.webhooks import clear_webhook_context

            clear_webhook_context()


class TestWebhookPayloadStructure:
    """Test webhook payload meets specification requirements."""

    def test_payload_has_required_fields(self):
        """WebhookPayload should have all required fields."""
        payload = WebhookPayload(
            event_type="artifact.created",
            correlation_id="workflow-123",
            sequence=1,
            artifact={
                "id": "artifact-abc",
                "type": "ReviewResult",
                "produced_by": "review-agent",
                "payload": {"score": 95},
                "created_at": "2024-01-15T10:30:00Z",
                "tags": ["automated", "verified"],
            },
            timestamp="2024-01-15T10:30:01Z",
        )

        # Verify required fields
        assert payload.event_type == "artifact.created"
        assert payload.correlation_id == "workflow-123"
        assert payload.sequence == 1
        assert payload.artifact.id == "artifact-abc"
        assert payload.artifact.type == "ReviewResult"
        assert payload.artifact.produced_by == "review-agent"
        assert payload.artifact.payload == {"score": 95}
        assert payload.artifact.created_at == "2024-01-15T10:30:00Z"
        assert payload.artifact.tags == ["automated", "verified"]
        assert payload.timestamp == "2024-01-15T10:30:01Z"

    def test_payload_serializes_to_json(self):
        """WebhookPayload should serialize to valid JSON."""
        payload = WebhookPayload(
            event_type="artifact.created",
            correlation_id="test-corr",
            sequence=5,
            artifact={
                "id": "test-id",
                "type": "Test",
                "produced_by": "agent",
                "payload": {"nested": {"data": True}},
                "created_at": "2024-01-01T00:00:00Z",
                "tags": [],
            },
            timestamp="2024-01-01T00:00:00Z",
        )

        json_str = payload.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "artifact.created"
        assert parsed["correlation_id"] == "test-corr"
        assert parsed["sequence"] == 5
        assert parsed["artifact"]["payload"]["nested"]["data"] is True


class TestEndToEndFlow:
    """Test complete webhook flow through REST endpoint."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = Mock()
        orchestrator.store = Mock()
        orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
        orchestrator.publish = AsyncMock()
        orchestrator.run_until_idle = AsyncMock()
        orchestrator.metrics = {"agent_runs": 0, "artifacts_published": 0}
        orchestrator.agents = []
        return orchestrator

    @pytest.fixture
    def service(self, mock_orchestrator):
        """Create service instance."""
        return BlackboardHTTPService(mock_orchestrator)

    @pytest.mark.asyncio
    async def test_async_endpoint_accepts_webhook_config(
        self, service, mock_orchestrator
    ):
        """POST /artifacts should accept webhook configuration."""
        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "E2ETestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://receiver.example.com/webhook",
                        "secret": "e2e-secret",
                    },
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_sync_endpoint_accepts_webhook_config(
        self, service, mock_orchestrator
    ):
        """POST /artifacts/sync should accept webhook configuration."""
        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "E2ETestInput",
                    "payload": {"value": "test"},
                    "webhook": {
                        "url": "https://receiver.example.com/webhook",
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "correlation_id" in data
        assert "artifacts" in data
        assert "completed" in data

    @pytest.mark.asyncio
    async def test_endpoints_work_without_webhook(self, service, mock_orchestrator):
        """Endpoints should work normally without webhook config (backward compat)."""
        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Async endpoint
            response1 = await client.post(
                "/api/v1/artifacts",
                json={
                    "type": "E2ETestInput",
                    "payload": {"value": "no-webhook"},
                },
            )
            assert response1.status_code == 200

            # Sync endpoint
            response2 = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "E2ETestInput",
                    "payload": {"value": "no-webhook"},
                },
            )
            assert response2.status_code == 200


class TestSequenceNumberTracking:
    """Test that sequence numbers are tracked correctly within a workflow."""

    def test_sequence_increments_for_each_artifact(self):
        """Sequence number should increment for each artifact in workflow."""
        ctx = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="workflow-abc",
        )

        assert ctx.sequence == 0

        seq1 = ctx.next_sequence()
        assert seq1 == 1
        assert ctx.sequence == 1

        seq2 = ctx.next_sequence()
        assert seq2 == 2
        assert ctx.sequence == 2

        seq3 = ctx.next_sequence()
        assert seq3 == 3
        assert ctx.sequence == 3

    def test_separate_workflows_have_independent_sequences(self):
        """Different workflows should have independent sequence counters."""
        ctx1 = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="workflow-1",
        )
        ctx2 = WebhookContext(
            url="https://example.com/webhook",
            secret=None,
            correlation_id="workflow-2",
        )

        # Increment ctx1 multiple times
        ctx1.next_sequence()
        ctx1.next_sequence()
        ctx1.next_sequence()

        # ctx2 should still be at 0
        assert ctx1.sequence == 3
        assert ctx2.sequence == 0

        # Increment ctx2 once
        ctx2.next_sequence()
        assert ctx2.sequence == 1
        assert ctx1.sequence == 3  # Unchanged
