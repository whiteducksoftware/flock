"""Tests for Sync Publish and Error Response models.

Spec: 001-sync-idempotent-rest
Phase 1: Response Models & Error Schema
"""

import pytest
from pydantic import ValidationError


class TestSyncPublishRequest:
    """Tests for SyncPublishRequest model validation."""

    def test_minimal_valid_request(self):
        """Request with just type should be valid with defaults."""
        from flock.api.models import SyncPublishRequest

        request = SyncPublishRequest(type="TestArtifact")

        assert request.type == "TestArtifact"
        assert request.payload == {}
        assert request.timeout == 30.0
        assert request.filters is None

    def test_full_request_with_all_fields(self):
        """Request with all fields should serialize correctly."""
        from flock.api.models import SyncPublishFilters, SyncPublishRequest

        request = SyncPublishRequest(
            type="TestArtifact",
            payload={"key": "value", "count": 42},
            timeout=60.0,
            filters=SyncPublishFilters(
                type_names=["OutputA", "OutputB"],
                produced_by=["agent_1"],
            ),
        )

        assert request.type == "TestArtifact"
        assert request.payload == {"key": "value", "count": 42}
        assert request.timeout == 60.0
        assert request.filters is not None
        assert request.filters.type_names == ["OutputA", "OutputB"]
        assert request.filters.produced_by == ["agent_1"]

    def test_type_is_required(self):
        """Request without type should raise ValidationError."""
        from flock.api.models import SyncPublishRequest

        with pytest.raises(ValidationError) as exc_info:
            SyncPublishRequest()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_timeout_minimum_bound(self):
        """Timeout below 1.0 should raise ValidationError."""
        from flock.api.models import SyncPublishRequest

        with pytest.raises(ValidationError) as exc_info:
            SyncPublishRequest(type="Test", timeout=0.5)

        errors = exc_info.value.errors()
        assert any("timeout" in str(e["loc"]) for e in errors)

    def test_timeout_maximum_bound(self):
        """Timeout above 300.0 should raise ValidationError."""
        from flock.api.models import SyncPublishRequest

        with pytest.raises(ValidationError) as exc_info:
            SyncPublishRequest(type="Test", timeout=301.0)

        errors = exc_info.value.errors()
        assert any("timeout" in str(e["loc"]) for e in errors)

    def test_timeout_at_bounds(self):
        """Timeout exactly at bounds should be valid."""
        from flock.api.models import SyncPublishRequest

        min_request = SyncPublishRequest(type="Test", timeout=1.0)
        max_request = SyncPublishRequest(type="Test", timeout=300.0)

        assert min_request.timeout == 1.0
        assert max_request.timeout == 300.0


class TestSyncPublishFilters:
    """Tests for SyncPublishFilters model."""

    def test_empty_filters(self):
        """Filters with no values should be valid."""
        from flock.api.models import SyncPublishFilters

        filters = SyncPublishFilters()

        assert filters.type_names is None
        assert filters.produced_by is None

    def test_type_names_filter(self):
        """Filter with type_names should work."""
        from flock.api.models import SyncPublishFilters

        filters = SyncPublishFilters(type_names=["UserStory", "BugReport"])

        assert filters.type_names == ["UserStory", "BugReport"]

    def test_produced_by_filter(self):
        """Filter with produced_by should work."""
        from flock.api.models import SyncPublishFilters

        filters = SyncPublishFilters(produced_by=["writer_agent", "reviewer_agent"])

        assert filters.produced_by == ["writer_agent", "reviewer_agent"]


class TestSyncPublishResponse:
    """Tests for SyncPublishResponse model."""

    def test_response_serialization(self):
        """Response should serialize with all required fields."""
        from flock.api.models import SyncPublishResponse

        response = SyncPublishResponse(
            correlation_id="corr-123",
            artifacts=[],
            completed=True,
            duration_ms=1500,
        )

        data = response.model_dump()

        assert data["correlation_id"] == "corr-123"
        assert data["artifacts"] == []
        assert data["completed"] is True
        assert data["duration_ms"] == 1500

    def test_response_with_artifacts(self):
        """Response with artifact data should serialize correctly."""
        from flock.api.models import ArtifactBase, SyncPublishResponse

        response = SyncPublishResponse(
            correlation_id="corr-456",
            artifacts=[
                ArtifactBase(
                    id="art-1",
                    type="UserStory",
                    produced_by="story_writer",
                    payload={"title": "Test Story"},
                    created_at="2024-01-01T00:00:00Z",
                    tags=["epic-1"],
                    correlation_id="corr-456",
                    visibility={"kind": "Public"},
                    visibility_kind="Public",
                    version=1,
                )
            ],
            completed=True,
            duration_ms=2500,
        )

        assert len(response.artifacts) == 1
        assert response.artifacts[0].type == "UserStory"

    def test_response_incomplete(self):
        """Response should handle timeout case (completed=False)."""
        from flock.api.models import SyncPublishResponse

        response = SyncPublishResponse(
            correlation_id="corr-timeout",
            artifacts=[],
            completed=False,
            duration_ms=30000,
        )

        assert response.completed is False


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_minimal_error(self):
        """Error with required fields only should be valid."""
        from flock.api.models import ErrorResponse

        error = ErrorResponse(
            code="VALIDATION_ERROR",
            message="Invalid input provided",
        )

        assert error.code == "VALIDATION_ERROR"
        assert error.message == "Invalid input provided"
        assert error.correlation_id is None
        assert error.retryable is False
        assert error.details is None

    def test_full_error_with_details(self):
        """Error with all fields should serialize correctly."""
        from flock.api.models import ErrorDetail, ErrorResponse

        error = ErrorResponse(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            correlation_id="corr-err-123",
            retryable=False,
            details=[
                ErrorDetail(field="timeout", message="Must be between 1 and 300"),
                ErrorDetail(field="type", message="Type not registered", code="TYPE_NOT_FOUND"),
            ],
        )

        data = error.model_dump()

        assert data["code"] == "VALIDATION_ERROR"
        assert data["correlation_id"] == "corr-err-123"
        assert data["retryable"] is False
        assert len(data["details"]) == 2
        assert data["details"][0]["field"] == "timeout"
        assert data["details"][1]["code"] == "TYPE_NOT_FOUND"

    def test_retryable_error(self):
        """Error with retryable=True for transient failures."""
        from flock.api.models import ErrorResponse

        error = ErrorResponse(
            code="TIMEOUT_ERROR",
            message="Workflow did not complete in time",
            correlation_id="corr-timeout",
            retryable=True,
        )

        assert error.retryable is True

    def test_error_codes(self):
        """Common error codes should be representable."""
        from flock.api.models import ErrorResponse

        codes = [
            "VALIDATION_ERROR",
            "TYPE_NOT_REGISTERED",
            "TIMEOUT_ERROR",
            "INTERNAL_ERROR",
            "IDEMPOTENCY_CONFLICT",
        ]

        for code in codes:
            error = ErrorResponse(code=code, message=f"Test {code}")
            assert error.code == code


class TestErrorDetail:
    """Tests for ErrorDetail model."""

    def test_detail_with_field(self):
        """Detail with field reference should work."""
        from flock.api.models import ErrorDetail

        detail = ErrorDetail(
            field="payload.items[0].name",
            message="Name is required",
        )

        assert detail.field == "payload.items[0].name"
        assert detail.message == "Name is required"
        assert detail.code is None

    def test_detail_without_field(self):
        """Detail without field (general error) should work."""
        from flock.api.models import ErrorDetail

        detail = ErrorDetail(
            message="Unknown error occurred",
            code="UNKNOWN",
        )

        assert detail.field is None
        assert detail.message == "Unknown error occurred"
        assert detail.code == "UNKNOWN"

    def test_message_is_required(self):
        """Detail without message should raise ValidationError."""
        from flock.api.models import ErrorDetail

        with pytest.raises(ValidationError) as exc_info:
            ErrorDetail()

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("message",) for e in errors)
