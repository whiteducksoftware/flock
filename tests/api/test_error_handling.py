"""Tests for standardized error handling.

Spec: 001-sync-idempotent-rest
Phase 4: Error Handling Integration
"""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from unittest.mock import AsyncMock, Mock

from flock.registry import flock_type


@flock_type(name="ErrorTestInput")
class ErrorTestInput(BaseModel):
    """Test artifact type."""

    value: str


class TestValidationErrors:
    """Test validation error responses."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = Mock()
        orchestrator.store = Mock()
        orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
        orchestrator.publish = AsyncMock()
        orchestrator.run_until_idle = AsyncMock()
        orchestrator.metrics = {"agent_runs": 0}
        orchestrator.agents = []
        return orchestrator

    @pytest.mark.asyncio
    async def test_validation_error_returns_error_response(self, mock_orchestrator):
        """Validation errors should return ErrorResponse format."""
        from flock.api.service import BlackboardHTTPService

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required field (type)
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={"payload": {"value": "test"}},
            )

        assert response.status_code == 422
        data = response.json()
        # FastAPI returns validation error in detail field
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_timeout_bounds_validation(self, mock_orchestrator):
        """Timeout out of bounds should return validation error."""
        from flock.api.service import BlackboardHTTPService

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "ErrorTestInput",
                    "payload": {"value": "test"},
                    "timeout": 0.1,  # Below minimum
                },
            )

        assert response.status_code == 422


class TestPublishErrors:
    """Test publish operation errors."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = Mock()
        orchestrator.store = Mock()
        orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
        orchestrator.metrics = {"agent_runs": 0}
        orchestrator.agents = []
        return orchestrator

    @pytest.mark.asyncio
    async def test_publish_error_returns_400(self, mock_orchestrator):
        """Publish errors should return 400 status."""
        from flock.api.service import BlackboardHTTPService

        mock_orchestrator.publish = AsyncMock(
            side_effect=Exception("Type not registered")
        )

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts",
                json={"type": "UnknownType", "payload": {}},
            )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


class TestIdempotencyErrors:
    """Test idempotency-related error scenarios."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = Mock()
        orchestrator.store = Mock()
        orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
        orchestrator.publish = AsyncMock()
        orchestrator.run_until_idle = AsyncMock()
        orchestrator.metrics = {"agent_runs": 0}
        orchestrator.agents = []
        return orchestrator

    @pytest.mark.asyncio
    async def test_idempotency_cache_hit_returns_cached_data(self, mock_orchestrator):
        """Idempotency cache hit should return original response."""
        from flock.api.service import BlackboardHTTPService

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First request
            response1 = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "ErrorTestInput", "payload": {"value": "test"}},
                headers={"X-Idempotency-Key": "error-test-key"},
            )
            assert response1.status_code == 200

            # Second request with same key
            response2 = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "ErrorTestInput", "payload": {"value": "test"}},
                headers={"X-Idempotency-Key": "error-test-key"},
            )
            assert response2.status_code == 200

            # Should return same correlation_id (cached)
            assert (
                response1.json()["correlation_id"] == response2.json()["correlation_id"]
            )


class TestTimeoutErrors:
    """Test timeout error scenarios."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = Mock()
        orchestrator.store = Mock()
        orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
        orchestrator.publish = AsyncMock()
        orchestrator.metrics = {"agent_runs": 0}
        orchestrator.agents = []
        return orchestrator

    @pytest.mark.asyncio
    async def test_timeout_returns_completed_false(self, mock_orchestrator):
        """Timeout should return 200 with completed=False, not error."""
        import asyncio
        from flock.api.service import BlackboardHTTPService

        async def slow_workflow():
            await asyncio.sleep(10)

        mock_orchestrator.run_until_idle = slow_workflow

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "ErrorTestInput",
                    "payload": {"value": "test"},
                    "timeout": 1.0,
                },
            )

        # Should return 200 with completed=False, not an error
        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is False
