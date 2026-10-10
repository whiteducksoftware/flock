"""Dashboard graph for yes/no and scale questions, several per decider."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.agent import EngineComponent
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import FakeDecider, Scale, YesNo
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


@flock_type
class Complaint(BaseModel):
    text: str


@flock_type
class Handled(BaseModel):
    by: str


class Escalate(YesNo):
    """Should a manager see this complaint?"""

    yes = "Legal threats or repeated failures"


class Severity(Scale):
    """How severe is the complaint?"""

    low = "Minor annoyance"
    medium = "Real problem"
    high = "Business impact"


class Done(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        return EvalResult.from_object(Handled(by=agent.name), agent=agent)


def answers(state: str) -> dict:
    if "lawyer" in state:
        return {"yes": 0.97, "no": 0.03}
    return {"yes": 0.1, "no": 0.9}


def severity(state: str) -> dict:
    if "lawyer" in state:
        return {"low": 0.0, "medium": 0.1, "high": 0.9}
    return {"low": 0.7, "medium": 0.3, "high": 0.0}


@pytest.fixture
async def triaged() -> Flock:
    flock = Flock()
    flock.is_dashboard = True
    decider = FakeDecider(
        {"Escalate": answers, "Severity": severity},
        refuse=set(),
    )
    flock.agent("triage").consumes(Complaint).decides(
        Escalate, Severity, model=decider, threshold=0.8
    )
    flock.agent("manager").consumes(Escalate.yes).with_engines(Done()).publishes(
        Handled
    )
    flock.agent("support").consumes(Severity.medium.or_higher).with_engines(
        Done()
    ).publishes(Handled)
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    flock._test_collector = collector
    for text in ("my lawyer will call", "button is a bit small"):
        await flock.publish(Complaint(text=text))
    await flock.run_until_idle()
    # A refused question lands in UNSURE and is counted as refused
    decider.refuse.add("Escalate")
    await flock.publish(Complaint(text="something odd"))
    await flock.run_until_idle()
    return flock


async def snapshot(flock: Flock, view_mode: str):
    assembler = GraphAssembler(flock.store, flock._test_collector, flock)
    return await assembler.build_snapshot(GraphRequest(view_mode=view_mode))


async def test_decider_node_lists_every_question(triaged):
    graph = await snapshot(triaged, "agent")

    triage = next(node for node in graph.nodes if node.id == "triage")
    info = triage.data["decision"]
    assert info["model"] == "fake"
    assert info["threshold"] == 0.8
    escalate, severity = info["questions"]
    assert escalate == {
        "name": "Escalate",
        "kind": "yesno",
        "instructions": "Should a manager see this complaint?",
        "options": ["yes", "no"],
        "counts": {"yes": 1, "no": 1, "UNSURE": 1},
        "refused": 1,
    }
    assert severity["kind"] == "scale"
    assert severity["options"] == ["low", "medium", "high"]
    assert severity["counts"] == {"low": 0, "medium": 0, "high": 1, "UNSURE": 2}
    # Mean of the weighted scores 1.9, 0.3 and 0.3
    assert severity["meanScore"] == pytest.approx((1.9 + 0.3 + 0.3) / 3)


async def test_yes_no_and_scale_edges_name_their_question(triaged):
    graph = await snapshot(triaged, "agent")

    labels = {e.label for e in graph.edges if e.source == "triage"}
    assert "Escalate.yes (1)" in labels
    assert any(label.startswith("Severity.") for label in labels)


async def test_decision_views_carry_kind_score_levels_and_refusals(triaged):
    graph = await snapshot(triaged, "blackboard")
    views = [node.data["decision"] for node in graph.nodes if "decision" in node.data]

    scale = next(v for v in views if v["question"] == "Severity")
    assert scale["kind"] == "scale"
    assert scale["levels"] == ["low", "medium", "high"]
    assert scale["score"] is not None
    refused = next(v for v in views if v["question"] == "Escalate" and v["refused"])
    assert refused["kind"] == "yesno"
    assert refused["choice"] == "UNSURE"
    assert refused["bestGuess"] is None
    assert refused["probabilities"] == {}
