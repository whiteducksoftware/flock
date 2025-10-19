from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from flock.core import Agent
from flock.core.artifacts import Artifact
from flock.core.store import ConsumptionRecord
from flock.core.visibility import PublicVisibility
from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.graph_builder import GraphAssembler
from flock.dashboard.models.graph import GraphRequest
from flock.dashboard.service import DashboardHTTPService
from flock.utils.runtime import Context


async def _setup_artifacts(orchestrator) -> None:
    producer = Agent("producer_agent", orchestrator=orchestrator)
    consumer = Agent("consumer_agent", orchestrator=orchestrator)

    orchestrator.register_agent(producer)
    orchestrator.register_agent(consumer)

    correlation_id = uuid4()

    idea = Artifact(
        type="Idea",
        payload={"topic": "pizza"},
        produced_by="producer_agent",
        correlation_id=correlation_id,
    )
    review = Artifact(
        type="Review",
        payload={"score": 9},
        produced_by="consumer_agent",
        correlation_id=correlation_id,
    )

    await orchestrator.store.publish(idea)
    await orchestrator.store.publish(review)

    await orchestrator.store.record_consumptions([
        ConsumptionRecord(
            artifact_id=idea.id,
            consumer="consumer_agent",
            run_id="run-1",
            correlation_id=str(correlation_id),
        )
    ])


@pytest.mark.asyncio
async def test_graph_assembler_agent_and_blackboard(orchestrator):
    await _setup_artifacts(orchestrator)

    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    agent_snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    assert agent_snapshot.view_mode == "agent"
    assert agent_snapshot.total_artifacts == 2
    assert any(node.id == "producer_agent" for node in agent_snapshot.nodes)
    assert any(node.id == "consumer_agent" for node in agent_snapshot.nodes)
    assert len(agent_snapshot.edges) == 1
    assert agent_snapshot.edges[0].source == "producer_agent"
    assert agent_snapshot.edges[0].target == "consumer_agent"

    blackboard_snapshot = await assembler.build_snapshot(
        GraphRequest(view_mode="blackboard")
    )
    assert blackboard_snapshot.view_mode == "blackboard"
    assert blackboard_snapshot.total_artifacts == 2
    assert len(blackboard_snapshot.nodes) == 2
    assert any(edge.type == "transformation" for edge in blackboard_snapshot.edges)
    transformation_edge = blackboard_snapshot.edges[0]
    assert transformation_edge.source != transformation_edge.target
    assert transformation_edge.label == "consumer_agent"


@pytest.mark.asyncio
async def test_dashboard_graph_endpoint(monkeypatch, orchestrator):
    monkeypatch.setenv("DASHBOARD_GRAPH_V2", "true")

    await _setup_artifacts(orchestrator)

    service = DashboardHTTPService(orchestrator)
    transport = ASGITransport(app=service.get_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/dashboard/graph", json={"viewMode": "agent"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["viewMode"] == "agent"
    assert payload["totalArtifacts"] == 2
    assert len(payload["nodes"]) >= 2
    assert any(edge["type"] == "message_flow" for edge in payload["edges"])


@pytest.mark.asyncio
async def test_graph_assembler_inactive_agent_node(orchestrator):
    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    builder = orchestrator.agent("historical_agent")
    agent = builder._agent
    agent.description = "Legacy agent"
    agent.labels.add("legacy")

    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id="inactive-run",
        state={"artifacts_produced": [], "metrics": {}},
        correlation_id=uuid4(),
    )

    input_artifact = Artifact(
        type="LegacyInput",
        payload={"value": "sample"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=ctx.correlation_id,
    )

    await collector.on_pre_consume(agent, ctx, [input_artifact])
    await collector.on_terminate(agent, ctx)

    orchestrator._agents.pop("historical_agent", None)

    produced = Artifact(
        type="LegacyOutput",
        payload={"status": "done"},
        produced_by="historical_agent",
        visibility=PublicVisibility(),
        correlation_id=ctx.correlation_id,
    )

    await orchestrator.store.publish(produced)
    await orchestrator.store.record_consumptions([
        ConsumptionRecord(
            artifact_id=produced.id,
            consumer="consumer_b",
            run_id="inactive-run",
            correlation_id=str(ctx.correlation_id),
        )
    ])

    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    node = next(n for n in snapshot.nodes if n.id == "historical_agent")
    assert node.data["status"] == "inactive"
    assert node.data["firstSeen"] is not None
    assert node.data["lastSeen"] is not None
    assert node.data["signature"]
