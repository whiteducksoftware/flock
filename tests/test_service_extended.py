"""Extended tests for BlackboardHTTPService."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from flock.api.service import BlackboardHTTPService
from flock.core.artifacts import Artifact
from flock.core.store import ArtifactEnvelope, ConsumptionRecord, FilterConfig
from flock.registry import flock_type


@flock_type(name="ServiceTestInput")
class ServiceTestInput(BaseModel):
    value: str


@flock_type(name="ServiceTestOutput")
class ServiceTestOutput(BaseModel):
    result: str


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    orchestrator = Mock()
    orchestrator.store = Mock()
    orchestrator.store.list = AsyncMock(return_value=[])
    orchestrator.store.publish = AsyncMock()
    orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
    orchestrator.store.summarize_artifacts = AsyncMock(
        return_value={
            "total": 0,
            "by_type": {},
            "by_producer": {},
            "by_visibility": {},
            "tag_counts": {},
            "earliest_created_at": None,
            "latest_created_at": None,
        }
    )
    orchestrator.store.agent_history_summary = AsyncMock(
        return_value={
            "produced": {"total": 0, "by_type": {}},
            "consumed": {"total": 0, "by_type": {}},
        }
    )
    orchestrator.agents = []
    orchestrator.metrics = {"agent_runs": 5, "artifacts_published": 10}
    orchestrator.direct_invoke = AsyncMock(return_value=[])
    orchestrator.publish_artifact = AsyncMock()

    # Add get_agent method that raises KeyError if agent not found
    def get_agent(name: str):
        for agent in orchestrator.agents:
            if agent.name == name:
                return agent
        raise KeyError(f"Agent {name} not found")

    orchestrator.get_agent = get_agent
    return orchestrator


@pytest.fixture
def service(mock_orchestrator):
    """Create service instance."""
    return BlackboardHTTPService(mock_orchestrator)


@pytest.mark.asyncio
async def test_run_agent_endpoint(service, mock_orchestrator):
    """Test the run agent endpoint."""
    # Create a mock agent
    mock_agent = Mock()
    mock_agent.name = "test_agent"
    mock_agent.spec = Mock()
    mock_agent.spec.inputs = [ServiceTestInput]
    mock_agent.spec.type_name = "ServiceTestInput"

    mock_orchestrator.agents = [mock_agent]

    # Mock direct_invoke to return artifacts
    output_artifact = Artifact(
        type="ServiceTestOutput",
        payload={"result": "processed"},
        produced_by="test_agent",
    )
    mock_orchestrator.direct_invoke = AsyncMock(return_value=[output_artifact])

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agents/test_agent/run",
            json={
                "inputs": [{"type": "ServiceTestInput", "payload": {"value": "test"}}]
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "artifacts" in data
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["type"] == "ServiceTestOutput"


@pytest.mark.asyncio
async def test_run_agent_not_found(service, mock_orchestrator):
    """Test run agent with non-existent agent."""
    # Set up direct_invoke in case it's called (though it shouldn't be)
    mock_orchestrator.direct_invoke = AsyncMock()

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agents/nonexistent/run", json={"inputs": []}
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_run_agent_with_error(service, mock_orchestrator):
    """Test run agent when agent raises error."""
    mock_agent = Mock()
    mock_agent.name = "error_agent"
    mock_orchestrator.direct_invoke = AsyncMock(side_effect=ValueError("Agent error"))
    mock_agent.spec = Mock()
    mock_agent.spec.inputs = []

    mock_orchestrator.agents = [mock_agent]

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agents/error_agent/run", json={"inputs": []}
        )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_metrics_endpoint(service, mock_orchestrator):
    """Test metrics endpoint."""
    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "blackboard_agent_runs 5" in response.text
    assert "blackboard_artifacts_published 10" in response.text


@pytest.mark.asyncio
async def test_health_endpoint(service):
    """Test health endpoint."""
    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_agents_with_subscriptions(service, mock_orchestrator):
    """Test list agents with subscription details."""
    mock_agent = Mock()
    mock_agent.name = "subscriber_agent"
    mock_agent.description = "Subscribes to events"
    mock_agent.spec = Mock()
    mock_agent.spec.inputs = [ServiceTestInput]
    mock_agent.spec.type_name = "ServiceTestInput"

    # Create proper subscription mock objects with type_names attribute
    mock_subscription = Mock()
    mock_subscription.type_names = ["ServiceTestInput", "ServiceTestOutput"]
    mock_subscription.mode = "all"
    mock_agent.subscriptions = [mock_subscription]

    mock_agent.outputs = [Mock()]
    mock_agent.outputs[0].spec = Mock()
    mock_agent.outputs[0].spec.type_name = "ServiceTestOutput"

    mock_orchestrator.agents = [mock_agent]

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/agents")

    assert response.status_code == 200
    data = response.json()
    assert len(data["agents"]) == 1
    agent = data["agents"][0]
    assert agent["name"] == "subscriber_agent"
    assert agent["description"] == "Subscribes to events"
    assert len(agent["subscriptions"]) == 1
    assert "ServiceTestInput" in agent["subscriptions"][0]["types"]
    assert "ServiceTestOutput" in agent["outputs"]


@pytest.mark.asyncio
async def test_artifacts_endpoint_with_filters(service, mock_orchestrator):
    """Test getting specific artifact by ID."""
    test_id = uuid4()
    artifact = Artifact(
        type="TypeA", payload={"a": 1}, produced_by="agent1", id=test_id
    )
    mock_orchestrator.store.get = AsyncMock(return_value=artifact)

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/artifacts/{test_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_id)
    assert data["type"] == "TypeA"
    assert data["payload"] == {"a": 1}


@pytest.mark.asyncio
async def test_create_artifact_invalid_type(service, mock_orchestrator):
    """Test creating artifact with invalid type."""
    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/artifacts", json={"type": "InvalidType", "payload": {}}
        )

    # Should handle gracefully
    assert response.status_code in [400, 422, 500]


@pytest.mark.asyncio
async def test_list_artifacts_endpoint(service, mock_orchestrator):
    """Verify paginated list delegates to store query."""
    artifact = Artifact(type="TypeA", payload={"value": 1}, produced_by="agent1")
    mock_orchestrator.store.query_artifacts.return_value = ([artifact], 5)

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/artifacts",
            params={
                "type": "TypeA",
                "produced_by": "agent1",
                "correlation_id": "abc",
                "tag": ["alpha", "beta"],
                "from": "2025-01-01T00:00:00+00:00",
                "to": "2025-12-31T23:59:59+00:00",
                "limit": 10,
                "offset": 2,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 5
    assert len(payload["items"]) == 1
    mock_orchestrator.store.query_artifacts.assert_awaited_once()
    call = mock_orchestrator.store.query_artifacts.await_args
    filters = call.args[0]
    assert isinstance(filters, FilterConfig)
    assert filters.type_names == {"TypeA"}
    assert filters.produced_by == {"agent1"}
    assert filters.correlation_id == "abc"
    assert filters.tags == {"alpha", "beta"}
    assert filters.start == datetime.fromisoformat("2025-01-01T00:00:00+00:00")
    assert filters.end == datetime.fromisoformat("2025-12-31T23:59:59+00:00")
    assert call.kwargs["limit"] == 10
    assert call.kwargs["offset"] == 2
    assert call.kwargs["embed_meta"] is False


@pytest.mark.asyncio
async def test_list_artifacts_with_embed_meta(service, mock_orchestrator):
    artifact = Artifact(type="TypeA", payload={"value": 1}, produced_by="agent1")
    consumption = ConsumptionRecord(
        artifact_id=artifact.id,
        consumer="agent2",
        run_id="run-1",
        correlation_id="corr-99",
    )
    mock_orchestrator.store.query_artifacts.return_value = (
        [ArtifactEnvelope(artifact=artifact, consumptions=[consumption])],
        1,
    )

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/artifacts", params={"embed_meta": "true"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    item = payload["items"][0]
    assert item["produced_by"] == "agent1"
    assert len(item["consumptions"]) == 1
    assert item["consumptions"][0]["consumer"] == "agent2"
    call = mock_orchestrator.store.query_artifacts.await_args
    assert call.kwargs["embed_meta"] is True


@pytest.mark.asyncio
async def test_artifact_summary_endpoint(service, mock_orchestrator):
    """Verify summary endpoint returns aggregates."""
    mock_orchestrator.store.summarize_artifacts.return_value = {
        "total": 3,
        "by_type": {"TypeA": 2, "TypeB": 1},
        "by_producer": {"agent1": 3},
        "by_visibility": {"Public": 3},
        "tag_counts": {"alpha": 2},
        "earliest_created_at": "2025-01-01T00:00:00+00:00",
        "latest_created_at": "2025-01-02T00:00:00+00:00",
    }

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/artifacts/summary", params={"type": "TypeA"}
        )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["total"] == 3
    assert "TypeA" in summary["by_type"]
    mock_orchestrator.store.summarize_artifacts.assert_awaited_once()
    call = mock_orchestrator.store.summarize_artifacts.await_args
    filters = call.args[0]
    assert isinstance(filters, FilterConfig)
    assert filters.type_names == {"TypeA"}


@pytest.mark.asyncio
async def test_agent_history_summary_endpoint(service, mock_orchestrator):
    """Ensure agent history summary delegates to store."""

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/agents/pizza/history-summary",
            params={
                "type": ["Recipe"],
                "produced_by": ["pizza_master"],
                "correlation_id": "corr-1",
                "tag": ["dough"],
                "from": "2025-01-01T00:00:00+00:00",
                "to": "2025-01-02T00:00:00+00:00",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == "pizza"
    mock_orchestrator.store.agent_history_summary.assert_awaited_once()
    call = mock_orchestrator.store.agent_history_summary.await_args
    assert call.args[0] == "pizza"
    filters = call.args[1]
    assert isinstance(filters, FilterConfig)
    assert filters.type_names == {"Recipe"}
    assert filters.produced_by == {"pizza_master"}
    assert filters.correlation_id == "corr-1"
    assert filters.tags == {"dough"}
    assert filters.start == datetime.fromisoformat("2025-01-01T00:00:00+00:00")
    assert filters.end == datetime.fromisoformat("2025-01-02T00:00:00+00:00")


@pytest.mark.asyncio
async def test_service_run_method():
    """Test the synchronous run method."""
    mock_orchestrator = Mock()
    mock_orchestrator.store = Mock()
    mock_orchestrator.agents = []
    mock_orchestrator.metrics = {}

    service = BlackboardHTTPService(mock_orchestrator)

    with patch("uvicorn.run") as mock_uvicorn:
        service.run(host="0.0.0.0", port=9000)

        mock_uvicorn.assert_called_once_with(service.app, host="0.0.0.0", port=9000)


@pytest.mark.asyncio
async def test_service_run_async_method():
    """Test the async run method."""
    mock_orchestrator = Mock()
    mock_orchestrator.store = Mock()
    mock_orchestrator.agents = []
    mock_orchestrator.metrics = {}

    service = BlackboardHTTPService(mock_orchestrator)

    with (
        patch("uvicorn.Config") as mock_config_cls,
        patch("uvicorn.Server") as mock_server_cls,
    ):
        mock_config = Mock()
        mock_config_cls.return_value = mock_config
        mock_server = Mock()
        mock_server.serve = AsyncMock()
        mock_server_cls.return_value = mock_server

        await service.run_async(host="0.0.0.0", port=9000)

        mock_config_cls.assert_called_once_with(service.app, host="0.0.0.0", port=9000)
        mock_server.serve.assert_called_once()


@pytest.mark.asyncio
async def test_multiple_input_artifacts(service, mock_orchestrator):
    """Test running agent with multiple input artifacts."""
    mock_agent = Mock()
    mock_agent.name = "multi_input_agent"
    mock_orchestrator.direct_invoke = AsyncMock(return_value=[])
    mock_agent.spec = Mock()
    mock_agent.spec.inputs = [ServiceTestInput]
    mock_agent.spec.type_name = "ServiceTestInput"

    mock_orchestrator.agents = [mock_agent]

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agents/multi_input_agent/run",
            json={
                "inputs": [
                    {"type": "ServiceTestInput", "payload": {"value": "first"}},
                    {"type": "ServiceTestInput", "payload": {"value": "second"}},
                    {"type": "ServiceTestInput", "payload": {"value": "third"}},
                ]
            },
        )

    assert response.status_code == 200
    # Verify direct_invoke was called with multiple inputs
    mock_orchestrator.direct_invoke.assert_called_once()
    call_args = mock_orchestrator.direct_invoke.call_args[0][1]
    assert len(call_args) == 3
