from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from flock import GatewayConfig, OpenClawConfig
from flock.api.base_service import BaseHTTPService
from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.api.websocket import WebSocketManager
from flock.components.server.control.control_routes_component import (
    ControlRoutesComponent,
    ControlRoutesComponentConfig,
)
from flock.components.server.models.graph import GraphRequest, GraphRequestOptions
from flock.core import Agent, Flock
from flock.core.artifacts import Artifact
from flock.core.store import ConsumptionRecord
from flock.core.visibility import PublicVisibility
from flock.utils.runtime import Context


async def _setup_artifacts(orchestrator) -> None:
    producer = Agent("producer_agent", orchestrator=orchestrator)
    consumer = Agent("consumer_agent", orchestrator=orchestrator)

    orchestrator.register_agent(producer)
    orchestrator.register_agent(consumer)

    correlation_id = str(uuid4())

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
async def test_recent_presets_show_artifacts_stamped_after_the_request(orchestrator):
    """A preset like "last 10 minutes" bounds the start only: an artifact stamped
    after the request read the clock (the clock stepped back, or the publish raced
    the request) still shows."""
    ahead = Artifact(
        type="Idea",
        payload={"topic": "pizza"},
        produced_by="producer_agent",
        created_at=datetime.now(UTC) + timedelta(seconds=2),
    )
    await orchestrator.store.publish(ahead)
    collector = DashboardEventCollector(store=orchestrator.store)
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))

    assert snapshot.filters.time_range.preset == "last10min"
    assert [node.id for node in snapshot.nodes] == [str(ahead.id)]


@pytest.mark.asyncio
async def test_a_full_view_shows_the_newest_artifacts(orchestrator):
    """With more artifacts than the limit, a (live) view shows the newest ones."""
    start = datetime.now(UTC) - timedelta(seconds=30)
    ideas = [
        Artifact(
            type="Idea",
            payload={"topic": f"idea {n}"},
            produced_by="producer_agent",
            created_at=start + timedelta(seconds=n),
        )
        for n in range(3)
    ]
    for idea in ideas:
        await orchestrator.store.publish(idea)
    collector = DashboardEventCollector(store=orchestrator.store)
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    snapshot = await assembler.build_snapshot(
        GraphRequest(view_mode="blackboard", options=GraphRequestOptions(limit=2))
    )

    assert sorted(node.id for node in snapshot.nodes) == sorted(
        str(idea.id) for idea in ideas[1:]
    )
    assert (snapshot.total_artifacts, snapshot.truncated) == (3, True)


@pytest.mark.asyncio
async def test_a_full_view_includes_artifacts_published_while_it_is_read(
    orchestrator, monkeypatch
):
    start = datetime.now(UTC) - timedelta(seconds=30)
    for n in range(3):
        await orchestrator.store.publish(
            Artifact(
                type="Idea",
                payload={"topic": f"idea {n}"},
                produced_by="producer_agent",
                created_at=start + timedelta(seconds=n),
            )
        )
    late = Artifact(
        type="Idea",
        payload={"topic": "late"},
        produced_by="producer_agent",
        created_at=start + timedelta(seconds=10),
    )
    fetch = orchestrator.store.fetch_graph_artifacts

    async def publish_after_counting(*args, **kwargs):
        found = await fetch(*args, **kwargs)
        if kwargs.get("offset") == 0:  # the read that counts the matches
            await orchestrator.store.publish(late)
        return found

    monkeypatch.setattr(
        orchestrator.store, "fetch_graph_artifacts", publish_after_counting
    )
    collector = DashboardEventCollector(store=orchestrator.store)
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    snapshot = await assembler.build_snapshot(
        GraphRequest(view_mode="blackboard", options=GraphRequestOptions(limit=2))
    )

    assert str(late.id) in {node.id for node in snapshot.nodes}
    assert (len(snapshot.nodes), snapshot.total_artifacts) == (2, 4)


@pytest.mark.asyncio
async def test_graph_assembler_includes_schedule_data(orchestrator):
    """Test GraphAssembler includes scheduleSpec and timerState for scheduled agents."""
    from datetime import timedelta

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
    normal_agent = orchestrator.agent("normal_agent").publishes(TestOutput)

    # Initialize orchestrator to start timer component
    await orchestrator._run_initialize()

    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))

    # Find scheduled agent node
    scheduled_node = next(
        (n for n in snapshot.nodes if n.id == "scheduled_agent"), None
    )
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
    from datetime import UTC, datetime, time, timedelta

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
async def test_graph_assembler_marks_openclaw_agents_for_frontend_badges():
    from pydantic import BaseModel

    class InboundIdea(BaseModel):
        topic: str

    class OutboundPlan(BaseModel):
        plan: str

    orchestrator = Flock(
        openclaw=OpenClawConfig(
            gateways={
                "remote": GatewayConfig(
                    url="https://example.openclaw.invalid",
                    token="test-token",
                )
            }
        )
    )
    orchestrator.is_dashboard = True

    (
        orchestrator.openclaw_agent("remote", name="remote_planner")
        .consumes(InboundIdea)
        .publishes(OutboundPlan)
    )

    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)

    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))

    node = next((n for n in snapshot.nodes if n.id == "remote_planner"), None)
    assert node is not None
    assert node.data["isOpenClawAgent"] is True
    assert node.data["engineKind"] == "openclaw"


@pytest.mark.asyncio
async def test_graph_assembler_marks_inactive_openclaw_agents_for_frontend_badges():
    from pydantic import BaseModel

    class InboundIdea(BaseModel):
        topic: str

    class OutboundPlan(BaseModel):
        plan: str

    orchestrator = Flock(
        openclaw=OpenClawConfig(
            gateways={
                "remote": GatewayConfig(
                    url="https://example.openclaw.invalid",
                    token="test-token",
                )
            }
        )
    )

    builder = (
        orchestrator.openclaw_agent("remote", name="remote_historical")
        .consumes(InboundIdea)
        .publishes(OutboundPlan)
    )

    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()

    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id="openclaw-inactive-run",
        state={"artifacts_produced": [], "metrics": {}},
        correlation_id=str(uuid4()),
    )

    input_artifact = Artifact(
        type="InboundIdea",
        payload={"topic": "pizza"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=ctx.correlation_id,
    )

    await collector.on_pre_consume(builder.agent, ctx, [input_artifact])
    await collector.on_terminate(builder.agent, ctx)

    orchestrator._agents.pop("remote_historical", None)

    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)
    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))

    node = next((n for n in snapshot.nodes if n.id == "remote_historical"), None)
    assert node is not None
    assert node.data["status"] == "inactive"
    assert node.data["isOpenClawAgent"] is True
    assert node.data["engineKind"] == "openclaw"


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
        correlation_id=str(uuid4()),
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


@pytest.mark.asyncio
async def test_agent_cards_get_the_tag_of_their_engine():
    from pydantic import BaseModel

    from flock.components.agent import EngineComponent
    from flock.decisions import Choice, FakeDecider
    from flock.registry import flock_type

    @flock_type(name="EngineTagTicket")
    class EngineTagTicket(BaseModel):
        text: str

    @flock_type(name="EngineTagReply")
    class EngineTagReply(BaseModel):
        text: str

    class EngineTagRoute(Choice):
        """Which team?"""

        billing = "Charges"
        tech = "Bugs"

    class ScriptedEngine(EngineComponent):
        kind = "Script"

    class PlainEngine(EngineComponent):
        pass

    orchestrator = Flock()
    orchestrator.agent("writer").consumes(EngineTagTicket).publishes(EngineTagReply)
    orchestrator.agent("scripted").consumes(EngineTagTicket).publishes(
        EngineTagReply
    ).with_engines(ScriptedEngine())
    orchestrator.agent("plain").consumes(EngineTagTicket).publishes(
        EngineTagReply
    ).with_engines(PlainEngine())
    orchestrator.agent("triage").consumes(EngineTagTicket).decides(
        EngineTagRoute, model=FakeDecider({"billing": 0.9, "tech": 0.1})
    )
    await orchestrator.store.publish(
        Artifact(
            type="EngineTagTicket",
            payload={"text": "hi"},
            produced_by="external",
            visibility=PublicVisibility(),
        )
    )

    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)
    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    tags = {node.id: node.data.get("engineTag") for node in snapshot.nodes}

    # No engine of its own: the default DSPy engine, an LLM
    assert tags["writer"] == "LLM"
    assert tags["scripted"] == "Script"
    assert tags["plain"] is None
    # A decider shows its question instead
    assert tags["triage"] is None
    # A producer that is no agent
    assert tags["external"] == "source"


async def test_agent_cards_get_their_description_and_model():
    from pydantic import BaseModel

    from flock.components.agent import EngineComponent
    from flock.decisions import Choice, FakeDecider
    from flock.engines import DSPyEngine
    from flock.registry import flock_type

    @flock_type(name="ModelCardTicket")
    class ModelCardTicket(BaseModel):
        text: str

    @flock_type(name="ModelCardReply")
    class ModelCardReply(BaseModel):
        text: str

    class ModelCardRoute(Choice):
        """Which team?"""

        billing = "Charges"
        tech = "Bugs"

    class ScriptedEngine(EngineComponent):
        pass

    orchestrator = Flock("azure/gpt-5")
    orchestrator.agent("writer").description("Writes replies").consumes(
        ModelCardTicket
    ).publishes(ModelCardReply)
    orchestrator.agent("tuned").consumes(ModelCardTicket).publishes(
        ModelCardReply
    ).with_engines(DSPyEngine(model="azure/gpt-4.1-mini"))
    orchestrator.agent("unset").consumes(ModelCardTicket).publishes(
        ModelCardReply
    ).with_engines(DSPyEngine())
    orchestrator.agent("scripted").consumes(ModelCardTicket).publishes(
        ModelCardReply
    ).with_engines(ScriptedEngine())
    orchestrator.agent("triage").consumes(ModelCardTicket).decides(
        ModelCardRoute, model=FakeDecider({"billing": 0.9, "tech": 0.1})
    )
    # Registered directly, not through the builder
    orchestrator.register_agent(Agent("direct", orchestrator=orchestrator))
    await orchestrator.store.publish(
        Artifact(
            type="ModelCardTicket",
            payload={"text": "hi"},
            produced_by="external",
            visibility=PublicVisibility(),
        )
    )

    collector = DashboardEventCollector(store=orchestrator.store)
    await collector.load_persistent_snapshots()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)
    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    data = {node.id: node.data for node in snapshot.nodes}

    assert data["writer"]["description"] == "Writes replies"
    assert data["tuned"]["description"] is None
    # No engine of its own, or an engine without a model: the flock's model
    assert data["writer"]["model"] == "azure/gpt-5"
    assert data["unset"]["model"] == "azure/gpt-5"
    assert data["direct"]["model"] == "azure/gpt-5"
    assert data["tuned"]["model"] == "azure/gpt-4.1-mini"
    # An engine that names no model, and a decider (its decision model is in its decider info)
    assert data["scripted"]["model"] is None
    assert data["triage"]["model"] is None
    assert data["triage"]["decision"]["model"]


def test_engines_label_themselves():
    from flock.engines import DSPyEngine
    from flock.integrations.openclaw.engine import OpenClawEngine

    assert DSPyEngine.kind == "LLM"
    assert OpenClawEngine.kind == "OpenClaw"


@pytest.mark.asyncio
async def test_agent_cards_get_their_subscription_groups():
    from pydantic import BaseModel

    from flock.registry import flock_type, type_registry

    @flock_type(name="GroupTicket")
    class GroupTicket(BaseModel):
        text: str

    @flock_type(name="GroupUrgent")
    class GroupUrgent(BaseModel):
        text: str

    @flock_type(name="GroupNote")
    class GroupNote(BaseModel):
        text: str

    orchestrator = Flock()
    # An AND gate, then a second subscription of its own
    orchestrator.agent("pager").consumes(GroupTicket, GroupUrgent).consumes(
        GroupNote
    ).publishes(GroupNote)
    # Three of a kind
    orchestrator.agent("triplets").consumes(GroupNote, GroupNote, GroupNote).publishes(
        GroupTicket
    )

    collector = DashboardEventCollector(store=orchestrator.store)
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)
    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    (pager,) = [node for node in snapshot.nodes if node.id == "pager"]

    name = type_registry.name_for
    assert pager.data["subscriptionGroups"] == [
        sorted([name(GroupTicket), name(GroupUrgent)]),
        [name(GroupNote)],
    ]
    (triplets,) = [node for node in snapshot.nodes if node.id == "triplets"]
    assert triplets.data["subscriptionGroups"] == [[name(GroupNote)] * 3]


@pytest.mark.asyncio
async def test_a_failed_agent_card_says_what_failed():
    from pydantic import BaseModel

    from flock.components.agent import EngineComponent
    from flock.registry import flock_type

    @flock_type(name="FailingTicket")
    class FailingTicket(BaseModel):
        text: str

    @flock_type(name="FailingReply")
    class FailingReply(BaseModel):
        text: str

    class RateLimitError(RuntimeError):
        pass

    class LimitedEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            raise RateLimitError("429 Too Many Requests")

    orchestrator = Flock(no_output=True)
    orchestrator.agent("tech_support").consumes(FailingTicket).publishes(
        FailingReply
    ).with_engines(LimitedEngine())
    collector = DashboardEventCollector(store=orchestrator.store)
    sent: list[str] = []

    class Broadcasts:
        async def broadcast(self, event):
            sent.append(type(event).__name__)

    collector.set_websocket_manager(Broadcasts())
    for agent in orchestrator.agents:
        agent._add_utilities([collector])

    await orchestrator.publish(FailingTicket(text="login broken"))
    await orchestrator.run_until_idle()
    assembler = GraphAssembler(orchestrator.store, collector, orchestrator)
    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    (node,) = [n for n in snapshot.nodes if n.id == "tech_support"]
    (run,) = await collector.agent_runs("tech_support")

    assert node.data["status"] == "error"
    error = node.data["lastError"]
    assert error["type"] == "RateLimitError"
    assert error["message"] == "429 Too Many Requests"
    assert error["runId"] == run["run_id"]
    assert error["correlationId"] == run["correlation_id"]
    assert datetime.fromisoformat(error["at"]) <= datetime.now(UTC)
    assert run["error_type"] == "RateLimitError"
    # The dashboard hears of the failure, and no "completed" undoes it
    assert "AgentErrorEvent" in sent
    assert "AgentCompletedEvent" not in sent
