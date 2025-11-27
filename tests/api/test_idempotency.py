"""Tests for Idempotency Layer.

Spec: 001-sync-idempotent-rest
Phase 3: Idempotency Layer
"""

import asyncio
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from flock.registry import flock_type


@flock_type(name="IdempotencyTestInput")
class IdempotencyTestInput(BaseModel):
    """Test artifact type."""

    value: str


class TestInMemoryIdempotencyStore:
    """Tests for InMemoryIdempotencyStore."""

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown_key(self):
        """Unknown key should return None."""
        from flock.api.idempotency import InMemoryIdempotencyStore

        store = InMemoryIdempotencyStore()
        result = await store.get("unknown-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_stores_response(self):
        """Set should store response in cache."""
        from flock.api.idempotency import CachedResponse, InMemoryIdempotencyStore

        store = InMemoryIdempotencyStore()
        response = CachedResponse(
            status_code=200,
            body=b'{"status": "ok"}',
            headers={"content-type": "application/json"},
            created_at=datetime.now(UTC),
        )
        await store.set("test-key", response, ttl=3600)

        result = await store.get("test-key")
        assert result is not None
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_get_returns_cached_response(self):
        """Get should return cached response."""
        from flock.api.idempotency import CachedResponse, InMemoryIdempotencyStore

        store = InMemoryIdempotencyStore()
        response = CachedResponse(
            status_code=200,
            body=b'{"correlation_id": "123"}',
            headers={"content-type": "application/json"},
            created_at=datetime.now(UTC),
        )
        await store.set("my-key", response, ttl=3600)

        result = await store.get("my-key")
        assert result is not None
        assert result.body == b'{"correlation_id": "123"}'
        assert result.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        """Expired entries should return None."""
        from flock.api.idempotency import CachedResponse, InMemoryIdempotencyStore

        store = InMemoryIdempotencyStore()
        response = CachedResponse(
            status_code=200,
            body=b"{}",
            headers={},
            created_at=datetime.now(UTC),
        )
        # Set with very short TTL
        await store.set("expiring-key", response, ttl=0)

        # Wait a tiny bit to ensure expiry
        await asyncio.sleep(0.01)

        result = await store.get("expiring-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_removes_entry(self):
        """Delete should remove entry from cache."""
        from flock.api.idempotency import CachedResponse, InMemoryIdempotencyStore

        store = InMemoryIdempotencyStore()
        response = CachedResponse(
            status_code=200,
            body=b"{}",
            headers={},
            created_at=datetime.now(UTC),
        )
        await store.set("delete-me", response, ttl=3600)

        # Verify it's there
        assert await store.get("delete-me") is not None

        # Delete it
        await store.delete("delete-me")

        # Verify it's gone
        assert await store.get("delete-me") is None


class TestIdempotencyIntegration:
    """Integration tests for idempotency with HTTP endpoints."""

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
    async def test_idempotency_returns_cached_response(self, mock_orchestrator):
        """Same idempotency key should return cached response."""
        from flock.api.service import BlackboardHTTPService

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First request
            response1 = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "IdempotencyTestInput", "payload": {"value": "first"}},
                headers={"X-Idempotency-Key": "unique-key-123"},
            )
            assert response1.status_code == 200
            correlation_id_1 = response1.json()["correlation_id"]

            # Second request with same key should return cached response
            response2 = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "IdempotencyTestInput", "payload": {"value": "first"}},
                headers={"X-Idempotency-Key": "unique-key-123"},
            )
            assert response2.status_code == 200
            correlation_id_2 = response2.json()["correlation_id"]

            # Should be the same correlation_id (cached response)
            assert correlation_id_1 == correlation_id_2

    @pytest.mark.asyncio
    async def test_different_keys_execute_separately(self, mock_orchestrator):
        """Different idempotency keys should execute independently."""
        from flock.api.service import BlackboardHTTPService

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First request
            response1 = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "IdempotencyTestInput", "payload": {"value": "a"}},
                headers={"X-Idempotency-Key": "key-a"},
            )
            assert response1.status_code == 200

            # Second request with different key
            response2 = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "IdempotencyTestInput", "payload": {"value": "b"}},
                headers={"X-Idempotency-Key": "key-b"},
            )
            assert response2.status_code == 200

            # Different keys should have different correlation IDs
            assert (
                response1.json()["correlation_id"] != response2.json()["correlation_id"]
            )

    @pytest.mark.asyncio
    async def test_no_key_allows_execution(self, mock_orchestrator):
        """Request without idempotency key should execute normally."""
        from flock.api.service import BlackboardHTTPService

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Request without idempotency key
            response1 = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "IdempotencyTestInput", "payload": {"value": "test"}},
            )
            assert response1.status_code == 200

            # Another request without key should also execute
            response2 = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "IdempotencyTestInput", "payload": {"value": "test"}},
            )
            assert response2.status_code == 200

            # Different correlation IDs (both executed)
            assert (
                response1.json()["correlation_id"] != response2.json()["correlation_id"]
            )

    @pytest.mark.asyncio
    async def test_idempotency_on_async_endpoint(self, mock_orchestrator):
        """Idempotency should work on async publish endpoint too."""
        from flock.api.service import BlackboardHTTPService

        service = BlackboardHTTPService(mock_orchestrator)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First request
            response1 = await client.post(
                "/api/v1/artifacts",
                json={"type": "IdempotencyTestInput", "payload": {"value": "async"}},
                headers={"X-Idempotency-Key": "async-key-1"},
            )
            assert response1.status_code == 200

            # Reset publish mock call count
            mock_orchestrator.publish.reset_mock()

            # Second request with same key should be cached (publish not called again)
            response2 = await client.post(
                "/api/v1/artifacts",
                json={"type": "IdempotencyTestInput", "payload": {"value": "async"}},
                headers={"X-Idempotency-Key": "async-key-1"},
            )
            assert response2.status_code == 200

            # Publish should NOT have been called (cached response)
            mock_orchestrator.publish.assert_not_called()
