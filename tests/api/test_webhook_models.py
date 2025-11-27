"""Tests for Webhook Models.

Spec: 002-webhook-notifications
Phase 1: Models & Configuration
"""

import pytest
from pydantic import ValidationError


class TestWebhookConfig:
    """Tests for WebhookConfig model."""

    def test_valid_url_required(self):
        """WebhookConfig requires a valid HTTP(S) URL."""
        from flock.api.models import WebhookConfig

        # Valid HTTPS URL
        config = WebhookConfig(url="https://example.com/webhook")
        assert str(config.url) == "https://example.com/webhook"

        # Valid HTTP URL
        config = WebhookConfig(url="http://localhost:8080/hook")
        assert str(config.url) == "http://localhost:8080/hook"

    def test_invalid_url_rejected(self):
        """WebhookConfig rejects invalid URLs."""
        from flock.api.models import WebhookConfig

        with pytest.raises(ValidationError):
            WebhookConfig(url="not-a-url")

        with pytest.raises(ValidationError):
            WebhookConfig(url="ftp://invalid-scheme.com")

    def test_secret_is_optional(self):
        """WebhookConfig secret field is optional."""
        from flock.api.models import WebhookConfig

        # Without secret
        config = WebhookConfig(url="https://example.com/webhook")
        assert config.secret is None

        # With secret
        config = WebhookConfig(url="https://example.com/webhook", secret="my-secret")
        assert config.secret == "my-secret"

    def test_secret_can_be_empty_string(self):
        """WebhookConfig secret can be empty string (treated as no secret)."""
        from flock.api.models import WebhookConfig

        config = WebhookConfig(url="https://example.com/webhook", secret="")
        assert config.secret == ""


class TestWebhookArtifact:
    """Tests for WebhookArtifact model."""

    def test_serialization(self):
        """WebhookArtifact serializes correctly."""
        from flock.api.models import WebhookArtifact

        artifact = WebhookArtifact(
            id="artifact-123",
            type="TestArtifact",
            produced_by="test-agent",
            payload={"key": "value", "nested": {"a": 1}},
            created_at="2025-01-15T10:30:00Z",
            tags=["tag1", "tag2"],
        )

        data = artifact.model_dump()
        assert data["id"] == "artifact-123"
        assert data["type"] == "TestArtifact"
        assert data["produced_by"] == "test-agent"
        assert data["payload"] == {"key": "value", "nested": {"a": 1}}
        assert data["created_at"] == "2025-01-15T10:30:00Z"
        assert data["tags"] == ["tag1", "tag2"]

    def test_tags_default_to_empty_list(self):
        """WebhookArtifact tags default to empty list."""
        from flock.api.models import WebhookArtifact

        artifact = WebhookArtifact(
            id="artifact-123",
            type="TestArtifact",
            produced_by="test-agent",
            payload={},
            created_at="2025-01-15T10:30:00Z",
        )

        assert artifact.tags == []

    def test_json_serialization(self):
        """WebhookArtifact produces valid JSON."""
        from flock.api.models import WebhookArtifact
        import json

        artifact = WebhookArtifact(
            id="artifact-123",
            type="TestArtifact",
            produced_by="test-agent",
            payload={"key": "value"},
            created_at="2025-01-15T10:30:00Z",
        )

        json_str = artifact.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["id"] == "artifact-123"


class TestWebhookPayload:
    """Tests for WebhookPayload model."""

    def test_serialization(self):
        """WebhookPayload serializes correctly."""
        from flock.api.models import WebhookArtifact, WebhookPayload

        artifact = WebhookArtifact(
            id="artifact-123",
            type="TestArtifact",
            produced_by="test-agent",
            payload={"key": "value"},
            created_at="2025-01-15T10:30:00Z",
        )

        payload = WebhookPayload(
            correlation_id="corr-456",
            sequence=1,
            artifact=artifact,
            timestamp="2025-01-15T10:30:01Z",
        )

        data = payload.model_dump()
        assert data["event_type"] == "artifact.created"
        assert data["correlation_id"] == "corr-456"
        assert data["sequence"] == 1
        assert data["artifact"]["id"] == "artifact-123"
        assert data["timestamp"] == "2025-01-15T10:30:01Z"

    def test_event_type_defaults_to_artifact_created(self):
        """WebhookPayload event_type defaults to 'artifact.created'."""
        from flock.api.models import WebhookArtifact, WebhookPayload

        artifact = WebhookArtifact(
            id="artifact-123",
            type="TestArtifact",
            produced_by="test-agent",
            payload={},
            created_at="2025-01-15T10:30:00Z",
        )

        payload = WebhookPayload(
            correlation_id="corr-456",
            sequence=1,
            artifact=artifact,
            timestamp="2025-01-15T10:30:01Z",
        )

        assert payload.event_type == "artifact.created"

    def test_sequence_must_be_positive_or_zero(self):
        """WebhookPayload sequence can be zero or positive."""
        from flock.api.models import WebhookArtifact, WebhookPayload

        artifact = WebhookArtifact(
            id="artifact-123",
            type="TestArtifact",
            produced_by="test-agent",
            payload={},
            created_at="2025-01-15T10:30:00Z",
        )

        # Zero is valid
        payload = WebhookPayload(
            correlation_id="corr-456",
            sequence=0,
            artifact=artifact,
            timestamp="2025-01-15T10:30:01Z",
        )
        assert payload.sequence == 0

        # Positive is valid
        payload = WebhookPayload(
            correlation_id="corr-456",
            sequence=100,
            artifact=artifact,
            timestamp="2025-01-15T10:30:01Z",
        )
        assert payload.sequence == 100

    def test_json_serialization(self):
        """WebhookPayload produces valid JSON."""
        from flock.api.models import WebhookArtifact, WebhookPayload
        import json

        artifact = WebhookArtifact(
            id="artifact-123",
            type="TestArtifact",
            produced_by="test-agent",
            payload={"key": "value"},
            created_at="2025-01-15T10:30:00Z",
        )

        payload = WebhookPayload(
            correlation_id="corr-456",
            sequence=1,
            artifact=artifact,
            timestamp="2025-01-15T10:30:01Z",
        )

        json_str = payload.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "artifact.created"
        assert parsed["artifact"]["type"] == "TestArtifact"


class TestArtifactPublishRequestWithWebhook:
    """Tests for ArtifactPublishRequest webhook extension."""

    def test_webhook_is_optional(self):
        """ArtifactPublishRequest webhook field is optional."""
        from flock.api.models import ArtifactPublishRequest

        # Without webhook (backward compatible)
        request = ArtifactPublishRequest(type="TestType", payload={"key": "value"})
        assert request.webhook is None

    def test_webhook_can_be_provided(self):
        """ArtifactPublishRequest can include webhook config."""
        from flock.api.models import ArtifactPublishRequest, WebhookConfig

        request = ArtifactPublishRequest(
            type="TestType",
            payload={"key": "value"},
            webhook=WebhookConfig(url="https://example.com/hook", secret="secret123"),
        )

        assert request.webhook is not None
        assert str(request.webhook.url) == "https://example.com/hook"
        assert request.webhook.secret == "secret123"


class TestSyncPublishRequestWithWebhook:
    """Tests for SyncPublishRequest webhook extension."""

    def test_webhook_is_optional(self):
        """SyncPublishRequest webhook field is optional."""
        from flock.api.models import SyncPublishRequest

        # Without webhook (backward compatible)
        request = SyncPublishRequest(type="TestType", payload={"key": "value"})
        assert request.webhook is None

    def test_webhook_can_be_provided(self):
        """SyncPublishRequest can include webhook config."""
        from flock.api.models import SyncPublishRequest, WebhookConfig

        request = SyncPublishRequest(
            type="TestType",
            payload={"key": "value"},
            timeout=60.0,
            webhook=WebhookConfig(url="https://example.com/hook"),
        )

        assert request.webhook is not None
        assert str(request.webhook.url) == "https://example.com/hook"
