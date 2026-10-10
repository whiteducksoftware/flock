"""Dashboard graph: decision nodes, option-labelled edges, decision artifacts."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.agent import EngineComponent
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import Choice, Decision, FakeDecider
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class GraphTicket(BaseModel):
    text: str


@flock_type
class GraphReply(BaseModel):
    team: str


class GraphRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges and refunds"
    tech = "Bugs and crashes"


class ReplyEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        return EvalResult.from_object(GraphReply(team=agent.name), agent=agent)


def probabilities(state: str) -> dict[str, float]:
    if "card" in state:
        return {"billing": 0.95, "tech": 0.05}
    return {"billing": 0.55, "tech": 0.45}


@pytest.fixture
async def routed() -> Flock:
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphTicket).decides(
        GraphRoute, model=FakeDecider(probabilities), threshold=0.8
    )
    for name, handle in (
        ("billing", GraphRoute.billing),
        ("supervisor", GraphRoute.UNSURE),
    ):
        flock.agent(name).consumes(handle).with_engines(ReplyEngine()).publishes(
            GraphReply
        )
    # As in serve(dashboard=True): the event collector runs on every agent
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    flock._test_collector = collector
    for text in ("card charged twice", "my card expired", "something odd"):
        await flock.publish(GraphTicket(text=text))
    await flock.run_until_idle()
    return flock


async def snapshot(flock: Flock, view_mode: str):
    assembler = GraphAssembler(flock.store, flock._test_collector, flock)
    return await assembler.build_snapshot(GraphRequest(view_mode=view_mode))


async def test_decider_node_describes_its_question_and_counts(routed):
    graph = await snapshot(routed, "agent")

    triage = next(node for node in graph.nodes if node.id == "triage")
    assert triage.data["decision"] == {
        "question": "GraphRoute",
        "instructions": "Which team should handle this ticket?",
        "options": ["billing", "tech"],
        "threshold": 0.8,
        "model": "fake",
        "counts": {"billing": 2, "tech": 0, "UNSURE": 1},
    }


async def test_choice_subscribers_get_readable_type_labels(routed):
    graph = await snapshot(routed, "agent")
    decision_type = type_registry.name_for(Decision.of(GraphRoute))

    billing = next(node for node in graph.nodes if node.id == "billing")
    supervisor = next(node for node in graph.nodes if node.id == "supervisor")
    assert billing.data["typeLabels"] == {decision_type: "◆ GraphRoute.billing"}
    assert supervisor.data["typeLabels"] == {decision_type: "◆ GraphRoute.UNSURE"}


async def test_decision_edges_are_labelled_by_option(routed):
    graph = await snapshot(routed, "agent")

    edges = {
        (edge.source, edge.target): edge
        for edge in graph.edges
        if edge.source == "triage"
    }
    billing = edges[("triage", "billing")]
    unsure = edges[("triage", "supervisor")]
    assert billing.label == "billing (2)"
    assert billing.data["decisionChoice"] == "billing"
    assert billing.data["decisionUnsure"] is False
    assert unsure.label == "UNSURE (1)"
    assert unsure.data["decisionUnsure"] is True


async def test_decision_artifacts_carry_their_probabilities(routed):
    graph = await snapshot(routed, "blackboard")
    decision_type = type_registry.name_for(Decision.of(GraphRoute))

    decisions = [
        node.data["decision"]
        for node in graph.nodes
        if node.data.get("artifactType") == decision_type
    ]
    assert len(decisions) == 3
    unsure = next(d for d in decisions if d["choice"] == "UNSURE")
    assert unsure["question"] == "GraphRoute"
    assert unsure["bestGuess"] == "billing"
    assert unsure["probabilities"] == {"billing": 0.55, "tech": 0.45}
    assert unsure["threshold"] == 0.8
    assert unsure["model"] == "fake"
    assert unsure["latencyMs"] is not None

    others = [
        node for node in graph.nodes if node.data.get("artifactType") != decision_type
    ]
    assert all("decision" not in node.data for node in others)


async def test_choice_subscribers_are_drawn_from_the_decider_only(routed):
    graph = await snapshot(routed, "agent")

    into_billing = {
        (e.source, e.data["messageType"]) for e in graph.edges if e.target == "billing"
    }
    assert into_billing == {("triage", type_registry.name_for(Decision.of(GraphRoute)))}


async def test_blackboard_links_decisions_to_what_the_subscriber_produced(routed):
    graph = await snapshot(routed, "blackboard")
    types = {node.id: node.data["artifactType"] for node in graph.nodes}
    decision_type = type_registry.name_for(Decision.of(GraphRoute))

    from_billing = {
        (types[e.source], types[e.target]) for e in graph.edges if e.label == "billing"
    }
    assert from_billing == {(decision_type, type_registry.name_for(GraphReply))}
