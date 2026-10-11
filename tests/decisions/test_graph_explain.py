"""Dashboard graph data for explanations and explained decisions."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphFilters, GraphRequest
from flock.core import Flock
from flock.decisions import Choice, Decision, FakeDecider
from flock.decisions.explain import Explanation
from flock.engines.dspy_engine import DSPyEngine
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class GraphExplainTicket(BaseModel):
    text: str


class GraphExplainRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


async def test_explanation_and_explained_decision_views(monkeypatch):
    async def fake(self, agent, ctx, inputs, *, batched, output_group=None):
        explanation = Explanation(
            explanation="Both a crash and a charge.", missing="Which came first."
        )
        return EvalResult.from_object(explanation, agent=agent)

    monkeypatch.setattr(DSPyEngine, "_evaluate_internal", fake)
    flock = Flock("openai/gpt-4.1")
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphExplainTicket).decides(
        GraphExplainRoute,
        model=FakeDecider({"billing": 0.55, "tech": 0.45}, label="fast"),
        threshold=0.8,
    )
    flock.agent("explainer").consumes(GraphExplainRoute.UNSURE).explains()
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    await flock.publish(GraphExplainTicket(text="crash, then a charge"))
    await flock.run_until_idle()

    assembler = GraphAssembler(flock.store, collector, flock)
    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    (explanation,) = [
        n.data["explanation"] for n in blackboard.nodes if "explanation" in n.data
    ]
    assert explanation == {
        "explanation": "Both a crash and a charge.",
        "missing": "Which came first.",
        "model": "openai/gpt-4.1",
        "questions": ["GraphExplainRoute"],
    }
    (decision,) = [n.data["decision"] for n in blackboard.nodes if "decision" in n.data]
    assert decision["explanation"] == {
        "explanation": "Both a crash and a charge.",
        "missing": "Which came first.",
        "model": "openai/gpt-4.1",
        "by": "explainer",
    }


async def test_a_decision_shows_its_explanation_when_the_view_leaves_it_out(
    monkeypatch,
):
    async def fake(self, agent, ctx, inputs, *, batched, output_group=None):
        explanation = Explanation(explanation="Both.", missing="The order.")
        return EvalResult.from_object(explanation, agent=agent)

    monkeypatch.setattr(DSPyEngine, "_evaluate_internal", fake)
    flock = Flock("openai/gpt-4.1")
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphExplainTicket).decides(
        GraphExplainRoute,
        model=FakeDecider({"billing": 0.55, "tech": 0.45}, label="fast"),
        threshold=0.8,
    )
    flock.agent("explainer").consumes(GraphExplainRoute.UNSURE).explains()
    collector = DashboardEventCollector(store=flock.store)
    await flock.publish(GraphExplainTicket(text="crash, then a charge"))
    await flock.run_until_idle()

    # Only decisions in view: the explanation itself is filtered out
    decision_type = type_registry.name_for(Decision.of(GraphExplainRoute))
    request = GraphRequest(
        view_mode="blackboard", filters=GraphFilters(artifact_types=[decision_type])
    )
    blackboard = await GraphAssembler(flock.store, collector, flock).build_snapshot(
        request
    )

    (decision,) = [n.data["decision"] for n in blackboard.nodes if "decision" in n.data]
    assert not any("explanation" in n.data for n in blackboard.nodes)
    assert decision["explanation"]["explanation"] == "Both."
