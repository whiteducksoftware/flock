"""Tests for POST /api/v1/artifacts/sync endpoint.

Spec: 001-sync-idempotent-rest
Phase 2: Sync Publish Endpoint
"""

import asyncio
from datetime import datetime, UTC
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from flock.api.service import BlackboardHTTPService
from flock.core.artifacts import Artifact
from flock.core.store import FilterConfig
from flock.registry import flock_type


@flock_type(name="SyncTestInput")
class SyncTestInput(BaseModel):
    """Test input artifact type."""

    value: str


@flock_type(name="SyncTestOutput")
class SyncTestOutput(BaseModel):
    """Test output artifact type."""

    result: str


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator for sync publish tests."""
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


class TestSyncPublishHappyPath:
    """Test successful sync publish scenarios."""

    @pytest.mark.asyncio
    async def test_sync_publish_returns_artifacts(self, service, mock_orchestrator):
        """Sync publish should return all artifacts produced during workflow."""
        # Setup: workflow produces artifacts
        correlation_id = str(uuid4())
        produced_artifacts = [
            _make_artifact("SyncTestInput", {"value": "test"}, "api", correlation_id),
            _make_artifact("SyncTestOutput", {"result": "processed"}, "processor", correlation_id),
        ]

        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=(produced_artifacts, len(produced_artifacts))
        )

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "SyncTestInput", "payload": {"value": "test"}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is True
        assert len(data["artifacts"]) == 2
        assert data["correlation_id"] is not None
        assert data["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_sync_publish_correlation_id_matches_artifacts(
        self, service, mock_orchestrator
    ):
        """Correlation ID in response should match artifacts queried."""
        captured_cid = None

        async def capture_publish(artifact_dict):
            nonlocal captured_cid
            captured_cid = artifact_dict.get("correlation_id")

        mock_orchestrator.publish = capture_publish

        # Return artifact with matching correlation_id
        def query_with_filter(filters: FilterConfig, **kwargs):
            return ([_make_artifact("SyncTestInput", {}, "api", filters.correlation_id)], 1)

        mock_orchestrator.store.query_artifacts = AsyncMock(side_effect=query_with_filter)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "SyncTestInput", "payload": {"value": "test"}},
            )

        assert response.status_code == 200
        data = response.json()
        # Correlation ID should be set
        assert data["correlation_id"] is not None
        # Artifacts should have matching correlation_id
        if data["artifacts"]:
            assert data["artifacts"][0]["correlation_id"] == data["correlation_id"]

    @pytest.mark.asyncio
    async def test_sync_publish_no_downstream_agents(self, service, mock_orchestrator):
        """When no downstream agents, should return only input artifact."""
        correlation_id = str(uuid4())
        input_artifact = _make_artifact(
            "SyncTestInput", {"value": "lonely"}, "api", correlation_id
        )

        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=([input_artifact], 1)
        )

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "SyncTestInput", "payload": {"value": "lonely"}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is True
        assert len(data["artifacts"]) == 1


class TestSyncPublishTimeout:
    """Test timeout behavior."""

    @pytest.mark.asyncio
    async def test_sync_publish_timeout_returns_completed_false(
        self, service, mock_orchestrator
    ):
        """When timeout is reached, completed should be False."""

        async def slow_workflow():
            await asyncio.sleep(10)  # Longer than test timeout

        mock_orchestrator.run_until_idle = slow_workflow
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "SyncTestInput",
                    "payload": {"value": "slow"},
                    "timeout": 1.0,  # 1 second timeout
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is False
        assert data["duration_ms"] >= 1000  # At least 1 second

    @pytest.mark.asyncio
    async def test_sync_publish_custom_timeout(self, service, mock_orchestrator):
        """Custom timeout should be respected."""
        captured_timeout = None

        async def capture_timeout():
            pass  # Instant completion

        mock_orchestrator.run_until_idle = capture_timeout
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "SyncTestInput",
                    "payload": {"value": "test"},
                    "timeout": 60.0,
                },
            )

        assert response.status_code == 200
        # Workflow completed before timeout
        assert response.json()["completed"] is True


class TestSyncPublishFilters:
    """Test response filtering."""

    @pytest.mark.asyncio
    async def test_sync_publish_type_filter(self, service, mock_orchestrator):
        """Type filter should be passed to query."""
        correlation_id = str(uuid4())
        all_artifacts = [
            _make_artifact("SyncTestInput", {"value": "test"}, "api", correlation_id),
            _make_artifact("SyncTestOutput", {"result": "processed"}, "processor", correlation_id),
            _make_artifact("SomeOtherType", {}, "other", correlation_id),
        ]

        async def filter_artifacts(filters: FilterConfig, **kwargs):
            filtered = all_artifacts
            if filters.type_names:
                filtered = [a for a in filtered if a.type in filters.type_names]
            return (filtered, len(filtered))

        mock_orchestrator.store.query_artifacts = AsyncMock(side_effect=filter_artifacts)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "SyncTestInput",
                    "payload": {"value": "test"},
                    "filters": {"type_names": ["SyncTestOutput"]},
                },
            )

        assert response.status_code == 200
        data = response.json()
        # Should only return SyncTestOutput type
        assert all(a["type"] == "SyncTestOutput" for a in data["artifacts"])

    @pytest.mark.asyncio
    async def test_sync_publish_produced_by_filter(self, service, mock_orchestrator):
        """Produced_by filter should be passed to query."""
        correlation_id = str(uuid4())
        all_artifacts = [
            _make_artifact("SyncTestInput", {"value": "test"}, "api", correlation_id),
            _make_artifact("SyncTestOutput", {"result": "a"}, "agent_a", correlation_id),
            _make_artifact("SyncTestOutput", {"result": "b"}, "agent_b", correlation_id),
        ]

        async def filter_artifacts(filters: FilterConfig, **kwargs):
            filtered = all_artifacts
            if filters.produced_by:
                filtered = [a for a in filtered if a.produced_by in filters.produced_by]
            return (filtered, len(filtered))

        mock_orchestrator.store.query_artifacts = AsyncMock(side_effect=filter_artifacts)

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "SyncTestInput",
                    "payload": {"value": "test"},
                    "filters": {"produced_by": ["agent_a"]},
                },
            )

        assert response.status_code == 200
        data = response.json()
        # Should only return artifacts from agent_a
        assert all(a["produced_by"] == "agent_a" for a in data["artifacts"])


class TestSyncPublishValidation:
    """Test request validation."""

    @pytest.mark.asyncio
    async def test_sync_publish_requires_type(self, service, mock_orchestrator):
        """Request without type should fail validation."""
        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={"payload": {"value": "test"}},
            )

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_sync_publish_timeout_bounds(self, service, mock_orchestrator):
        """Timeout outside bounds should fail validation."""
        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Below minimum
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "SyncTestInput",
                    "payload": {"value": "test"},
                    "timeout": 0.5,
                },
            )
            assert response.status_code == 422

            # Above maximum
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={
                    "type": "SyncTestInput",
                    "payload": {"value": "test"},
                    "timeout": 400,
                },
            )
            assert response.status_code == 422


class TestSyncPublishDurationTracking:
    """Test duration tracking."""

    @pytest.mark.asyncio
    async def test_sync_publish_reports_duration(self, service, mock_orchestrator):
        """Duration should be reported in milliseconds."""
        # Simulate some processing time
        async def simulate_work():
            await asyncio.sleep(0.05)  # 50ms

        mock_orchestrator.run_until_idle = simulate_work
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        transport = ASGITransport(app=service.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/artifacts/sync",
                json={"type": "SyncTestInput", "payload": {"value": "test"}},
            )

        assert response.status_code == 200
        data = response.json()
        # Duration should be at least 50ms (but allow some slack for async overhead)
        assert data["duration_ms"] >= 40


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
