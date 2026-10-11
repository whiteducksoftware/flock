"""Dashboard graph data for reviewed decisions."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphRequest, GraphRequestOptions
from flock.core import Flock
from flock.decisions import Choice, Decision, FakeDecider
from flock.registry import flock_type, type_registry


@flock_type
class GraphRevTicket(BaseModel):
    text: str


class GraphRevRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


async def test_review_and_reviewed_decision_views():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphRevTicket).decides(
        GraphRevRoute, model=FakeDecider({"billing": 0.55, "tech": 0.45}), threshold=0.8
    )
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    await flock.publish(GraphRevTicket(text="crash, then a charge"))
    await flock.run_until_idle()
    name = type_registry.name_for(Decision.of(GraphRevRoute))
    (unsure,) = [a for a in await flock.store.list() if a.type == name]
    reviewed = await flock.review(unsure.id, choice="tech", reviewer="alice")

    assembler = GraphAssembler(flock.store, collector, flock)
    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    views = {n.id: n.data["decision"] for n in blackboard.nodes if "decision" in n.data}
    assert views[str(unsure.id)]["review"] == {"choice": "tech", "by": "alice"}
    assert views[str(reviewed.id)]["reviewOf"] == str(unsure.id)


async def test_a_decision_view_lists_the_options_a_person_can_choose():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphRevTicket).decides(
        GraphRevRoute,
        model=FakeDecider({"billing": 0.5, "tech": 0.5}, refuse={"GraphRevRoute"}),
    )
    collector = DashboardEventCollector(store=flock.store)
    await flock.publish(GraphRevTicket(text="?"))
    await flock.run_until_idle()

    assembler = GraphAssembler(flock.store, collector, flock)
    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    (view,) = [n.data["decision"] for n in blackboard.nodes if "decision" in n.data]
    # A refusal has no probabilities; the options still allow a review
    assert view["probabilities"] == {}
    assert view["options"] == ["billing", "tech"]


async def test_a_decision_shows_its_review_beyond_the_view_limit():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphRevTicket).decides(
        GraphRevRoute, model=FakeDecider({"billing": 0.55, "tech": 0.45}), threshold=0.8
    )
    collector = DashboardEventCollector(store=flock.store)
    await flock.publish(GraphRevTicket(text="crash, then a charge"))
    await flock.run_until_idle()
    name = type_registry.name_for(Decision.of(GraphRevRoute))
    (unsure,) = [a for a in await flock.store.list() if a.type == name]
    await flock.review(unsure.id, choice="tech", reviewer="alice")

    # The ticket and the decision fill the view; the later review is past its limit
    assembler = GraphAssembler(flock.store, collector, flock)
    request = GraphRequest(view_mode="blackboard", options=GraphRequestOptions(limit=2))
    blackboard = await assembler.build_snapshot(request)

    views = {n.id: n.data["decision"] for n in blackboard.nodes if "decision" in n.data}
    assert list(views) == [str(unsure.id)]
    assert views[str(unsure.id)]["review"] == {"choice": "tech", "by": "alice"}
