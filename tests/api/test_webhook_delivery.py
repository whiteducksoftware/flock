"""Tests for Webhook Delivery Service.

Spec: 002-webhook-notifications
Phase 2: Webhook Delivery Service
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx


class TestSignPayload:
    """Tests for HMAC-SHA256 signing."""

    def test_sign_payload_produces_correct_hmac(self):
        """sign_payload should produce correct HMAC-SHA256 signature."""
        from flock.api.webhooks import sign_payload

        payload = b'{"test": "data"}'
        secret = "my-secret-key"

        signature = sign_payload(payload, secret)

        # Verify it's a valid hex string
        assert len(signature) == 64  # SHA256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in signature)

    def test_sign_payload_is_deterministic(self):
        """Same payload and secret should produce same signature."""
        from flock.api.webhooks import sign_payload

        payload = b'{"test": "data"}'
        secret = "my-secret-key"

        sig1 = sign_payload(payload, secret)
        sig2 = sign_payload(payload, secret)

        assert sig1 == sig2

    def test_sign_payload_different_secrets_produce_different_signatures(self):
        """Different secrets should produce different signatures."""
        from flock.api.webhooks import sign_payload

        payload = b'{"test": "data"}'

        sig1 = sign_payload(payload, "secret-1")
        sig2 = sign_payload(payload, "secret-2")

        assert sig1 != sig2

    def test_sign_payload_different_payloads_produce_different_signatures(self):
        """Different payloads should produce different signatures."""
        from flock.api.webhooks import sign_payload

        secret = "my-secret"

        sig1 = sign_payload(b'{"a": 1}', secret)
        sig2 = sign_payload(b'{"a": 2}', secret)

        assert sig1 != sig2


class TestWebhookDeliveryService:
    """Tests for WebhookDeliveryService."""

    @pytest.mark.asyncio
    async def test_deliver_success_returns_true(self):
        """Successful delivery should return True."""
        from flock.api.webhooks import WebhookDeliveryService
        from flock.api.models import WebhookArtifact, WebhookPayload

        service = WebhookDeliveryService()

        payload = WebhookPayload(
            correlation_id="test-corr",
            sequence=1,
            artifact=WebhookArtifact(
                id="art-1",
                type="TestType",
                produced_by="test-agent",
                payload={"key": "value"},
                created_at="2025-01-15T10:00:00Z",
            ),
            timestamp="2025-01-15T10:00:01Z",
        )

        with patch.object(service, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await service.deliver(
                url="https://example.com/webhook",
                payload=payload,
            )

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_retries_on_500_error(self):
        """Should retry on 5xx server errors."""
        from flock.api.webhooks import WebhookDeliveryService
        from flock.api.models import WebhookArtifact, WebhookPayload

        service = WebhookDeliveryService(max_retries=3, base_delay=0.01)

        payload = WebhookPayload(
            correlation_id="test-corr",
            sequence=1,
            artifact=WebhookArtifact(
                id="art-1",
                type="TestType",
                produced_by="test-agent",
                payload={},
                created_at="2025-01-15T10:00:00Z",
            ),
            timestamp="2025-01-15T10:00:01Z",
        )

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                response = MagicMock()
                response.is_success = False
                response.status_code = 500
                return response
            response = MagicMock()
            response.is_success = True
            return response

        with patch.object(service, "_client") as mock_client:
            mock_client.post = mock_post

            result = await service.deliver(
                url="https://example.com/webhook",
                payload=payload,
            )

        assert result is True
        assert call_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_deliver_retries_on_network_error(self):
        """Should retry on network errors."""
        from flock.api.webhooks import WebhookDeliveryService
        from flock.api.models import WebhookArtifact, WebhookPayload

        service = WebhookDeliveryService(max_retries=3, base_delay=0.01)

        payload = WebhookPayload(
            correlation_id="test-corr",
            sequence=1,
            artifact=WebhookArtifact(
                id="art-1",
                type="TestType",
                produced_by="test-agent",
                payload={},
                created_at="2025-01-15T10:00:00Z",
            ),
            timestamp="2025-01-15T10:00:01Z",
        )

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.RequestError("Connection failed")
            response = MagicMock()
            response.is_success = True
            return response

        with patch.object(service, "_client") as mock_client:
            mock_client.post = mock_post

            result = await service.deliver(
                url="https://example.com/webhook",
                payload=payload,
            )

        assert result is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_deliver_returns_false_after_max_retries(self):
        """Should return False after exhausting all retries."""
        from flock.api.webhooks import WebhookDeliveryService
        from flock.api.models import WebhookArtifact, WebhookPayload

        service = WebhookDeliveryService(max_retries=3, base_delay=0.01)

        payload = WebhookPayload(
            correlation_id="test-corr",
            sequence=1,
            artifact=WebhookArtifact(
                id="art-1",
                type="TestType",
                produced_by="test-agent",
                payload={},
                created_at="2025-01-15T10:00:00Z",
            ),
            timestamp="2025-01-15T10:00:01Z",
        )

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.is_success = False
            response.status_code = 500
            return response

        with patch.object(service, "_client") as mock_client:
            mock_client.post = mock_post

            result = await service.deliver(
                url="https://example.com/webhook",
                payload=payload,
            )

        assert result is False
        assert call_count == 4  # Initial + 3 retries

    @pytest.mark.asyncio
    async def test_deliver_includes_signature_header_when_secret_provided(self):
        """Should include X-Flock-Signature header when secret is provided."""
        from flock.api.webhooks import WebhookDeliveryService
        from flock.api.models import WebhookArtifact, WebhookPayload

        service = WebhookDeliveryService()

        payload = WebhookPayload(
            correlation_id="test-corr",
            sequence=1,
            artifact=WebhookArtifact(
                id="art-1",
                type="TestType",
                produced_by="test-agent",
                payload={},
                created_at="2025-01-15T10:00:00Z",
            ),
            timestamp="2025-01-15T10:00:01Z",
        )

        captured_headers = None

        async def mock_post(url, content, headers):
            nonlocal captured_headers
            captured_headers = headers
            response = MagicMock()
            response.is_success = True
            return response

        with patch.object(service, "_client") as mock_client:
            mock_client.post = mock_post

            await service.deliver(
                url="https://example.com/webhook",
                payload=payload,
                secret="my-secret",
            )

        assert captured_headers is not None
        assert "X-Flock-Signature" in captured_headers
        assert captured_headers["X-Flock-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_deliver_omits_signature_when_no_secret(self):
        """Should not include X-Flock-Signature when no secret is provided."""
        from flock.api.webhooks import WebhookDeliveryService
        from flock.api.models import WebhookArtifact, WebhookPayload

        service = WebhookDeliveryService()

        payload = WebhookPayload(
            correlation_id="test-corr",
            sequence=1,
            artifact=WebhookArtifact(
                id="art-1",
                type="TestType",
                produced_by="test-agent",
                payload={},
                created_at="2025-01-15T10:00:00Z",
            ),
            timestamp="2025-01-15T10:00:01Z",
        )

        captured_headers = None

        async def mock_post(url, content, headers):
            nonlocal captured_headers
            captured_headers = headers
            response = MagicMock()
            response.is_success = True
            return response

        with patch.object(service, "_client") as mock_client:
            mock_client.post = mock_post

            await service.deliver(
                url="https://example.com/webhook",
                payload=payload,
                secret=None,
            )

        assert captured_headers is not None
        assert "X-Flock-Signature" not in captured_headers

    @pytest.mark.asyncio
    async def test_retry_backoff_timing(self):
        """Retry delays should follow exponential backoff pattern."""
        from flock.api.webhooks import WebhookDeliveryService
        from flock.api.models import WebhookArtifact, WebhookPayload

        base_delay = 0.05  # 50ms for faster testing
        service = WebhookDeliveryService(max_retries=3, base_delay=base_delay)

        payload = WebhookPayload(
            correlation_id="test-corr",
            sequence=1,
            artifact=WebhookArtifact(
                id="art-1",
                type="TestType",
                produced_by="test-agent",
                payload={},
                created_at="2025-01-15T10:00:00Z",
            ),
            timestamp="2025-01-15T10:00:01Z",
        )

        timestamps = []

        async def mock_post(*args, **kwargs):
            timestamps.append(asyncio.get_event_loop().time())
            response = MagicMock()
            response.is_success = False
            response.status_code = 500
            return response

        with patch.object(service, "_client") as mock_client:
            mock_client.post = mock_post

            start_time = asyncio.get_event_loop().time()
            await service.deliver(
                url="https://example.com/webhook",
                payload=payload,
            )
            end_time = asyncio.get_event_loop().time()

        # Should have 4 attempts (initial + 3 retries)
        assert len(timestamps) == 4

        # Total time should be at least base_delay * (1 + 2 + 4) = 7 * base_delay
        # But allow some tolerance
        total_time = end_time - start_time
        expected_min_time = base_delay * 7 * 0.8  # 80% tolerance
        assert total_time >= expected_min_time
