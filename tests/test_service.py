import pytest
from httpx import ASGITransport, AsyncClient

from flock.api.service import BlackboardHTTPService
from flock.examples import Idea, create_demo_orchestrator
from flock.registry import type_registry


@pytest.mark.asyncio
async def test_http_control_plane_run_agent():
    orchestrator, _agents = create_demo_orchestrator()
    service = BlackboardHTTPService(orchestrator)

    transport = ASGITransport(app=service.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Publish an idea artifact via HTTP
        idea_type = type_registry.name_for(Idea)
        response = await client.post(
            "/api/v1/artifacts",
            json={"type": idea_type, "payload": {"topic": "AI", "genre": "comedy"}},
        )
        if response.status_code != 200:
            print(f"Failed with status {response.status_code}: {response.text}")
        assert response.status_code == 200

        # Directly run the movie agent
        response = await client.post(
            "/api/v1/agents/movie/run",
            json={
                "inputs": [
                    {
                        "type": idea_type,
                        "payload": {"topic": "Robots", "genre": "adventure"},
                    }
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["artifacts"]
        assert data["artifacts"][0]["type"] != idea_type

        # List agents metadata
        response = await client.get("/api/v1/agents")
        assert response.status_code == 200
        assert len(response.json()["agents"]) >= 3

        # Metrics endpoint exposes counters
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "blackboard_agent_runs" in response.text
