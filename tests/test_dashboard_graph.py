from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from flock.api.base_service import BaseHTTPService
from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.api.websocket import WebSocketManager
from flock.components.server.control.control_routes_component import (
    ControlRoutesComponent,
    ControlRoutesComponentConfig,
)
from flock.components.server.models.graph import GraphRequest
from flock.core import Agent
from flock.core.artifacts import Artifact
from flock.core.store import ConsumptionRecord
from flock.core.visibility import PublicVisibility
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
async def test_graph_assembler_includes_schedule_data(orchestrator):
    """Test GraphAssembler includes scheduleSpec and timerState for scheduled agents."""
    from datetime import timedelta
    from flock.core.subscription import ScheduleSpec
    from pydantic import BaseModel

    class TestOutput(BaseModel):
        value: str

    # Create scheduled agent using builder pattern
    scheduled_agent = (
        orchestrator.agent("scheduled_agent")
        .publishes(TestOutput)
        .schedule(every=timedelta(seconds=30))
    )

    # Create normal agent
    normal_agent = (
        orchestrator.agent("normal_agent")
        .publishes(TestOutput)
    )

    # Initialize orchestrator to start timer component
    await orchestrator._run_initialize()

    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))

    # Find scheduled agent node
    scheduled_node = next((n for n in snapshot.nodes if n.id == "scheduled_agent"), None)
    assert scheduled_node is not None

    # Verify schedule data is included
    assert "scheduleSpec" in scheduled_node.data
    schedule_spec = scheduled_node.data["scheduleSpec"]
    assert schedule_spec["type"] == "interval"
    assert "interval" in schedule_spec

    # Verify timer state is included if timer component is available
    timer_component = assembler._get_timer_component()
    if timer_component:
        assert "timerState" in scheduled_node.data
        timer_state = scheduled_node.data["timerState"]
        assert "iteration" in timer_state
        assert "is_active" in timer_state
        assert timer_state["iteration"] == 0  # Initial state

    # Verify normal agent doesn't have schedule data
    normal_node = next((n for n in snapshot.nodes if n.id == "normal_agent"), None)
    assert normal_node is not None
    assert "scheduleSpec" not in normal_node.data
    assert "timerState" not in normal_node.data

    await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_graph_assembler_serializes_schedule_spec(orchestrator):
    """Test GraphAssembler correctly serializes different schedule types."""
    from datetime import timedelta, time, datetime, UTC
    from flock.core.subscription import ScheduleSpec
    from pydantic import BaseModel

    class TestOutput(BaseModel):
        value: str

    # Test interval schedule
    interval_agent = (
        orchestrator.agent("interval_agent")
        .publishes(TestOutput)
        .schedule(every=timedelta(seconds=30))
    )

    # Test time schedule
    time_agent = (
        orchestrator.agent("time_agent")
        .publishes(TestOutput)
        .schedule(at=time(hour=17, minute=0))
    )

    # Test datetime schedule
    future_dt = datetime.now(UTC) + timedelta(days=1)
    datetime_agent = (
        orchestrator.agent("datetime_agent")
        .publishes(TestOutput)
        .schedule(at=future_dt)
    )

    # Test cron schedule
    cron_agent = (
        orchestrator.agent("cron_agent")
        .publishes(TestOutput)
        .schedule(cron="0 * * * *")
    )

    await orchestrator._run_initialize()

    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))

    # Verify interval schedule
    interval_node = next((n for n in snapshot.nodes if n.id == "interval_agent"), None)
    assert interval_node is not None
    assert interval_node.data["scheduleSpec"]["type"] == "interval"
    assert "PT30S" in interval_node.data["scheduleSpec"]["interval"]

    # Verify time schedule
    time_node = next((n for n in snapshot.nodes if n.id == "time_agent"), None)
    assert time_node is not None
    assert time_node.data["scheduleSpec"]["type"] == "time"
    assert "17:00:00" in time_node.data["scheduleSpec"]["time"]

    # Verify datetime schedule
    datetime_node = next((n for n in snapshot.nodes if n.id == "datetime_agent"), None)
    assert datetime_node is not None
    assert datetime_node.data["scheduleSpec"]["type"] == "datetime"
    assert "datetime" in datetime_node.data["scheduleSpec"]

    # Verify cron schedule
    cron_node = next((n for n in snapshot.nodes if n.id == "cron_agent"), None)
    assert cron_node is not None
    assert cron_node.data["scheduleSpec"]["type"] == "cron"
    assert cron_node.data["scheduleSpec"]["cron"] == "0 * * * *"

    await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_dashboard_graph_endpoint(monkeypatch, orchestrator):
    monkeypatch.setenv("DASHBOARD_GRAPH_V2", "true")

    await _setup_artifacts(orchestrator)
    graph_assembler = GraphAssembler(
        store=orchestrator.store,
        orchestrator=orchestrator,
        collector=DashboardEventCollector(
            store=orchestrator.store,
        ),
    )
    orchestrator = orchestrator.add_component(
        ControlRoutesComponent(
            name="control_routes_test",
            priority=1,
            websocket_manager=WebSocketManager(
                enable_heartbeat=False,
            ),
            config=ControlRoutesComponentConfig(prefix="/api/", tags=["Test"]),
            graph_assembler=graph_assembler,
        )
    )

    service = BaseHTTPService(
        orchestrator=orchestrator,
    ).add_component(
        ControlRoutesComponent(
            name="control_routes_test",
            config=ControlRoutesComponentConfig(
                prefix="/api/", tags=["Internal Testing"]
            ),
            graph_assembler=GraphAssembler(
                store=orchestrator.store,
                collector=DashboardEventCollector(
                    store=orchestrator.store,
                ),
                orchestrator=orchestrator,
            ),
        )
    )
    service.configure()  # Routes need to be set up first.
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
