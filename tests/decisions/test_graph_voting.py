"""Dashboard graph data for ensembles and voted decisions."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import Choice, FakeDecider
from flock.registry import flock_type


@flock_type
class GraphVoteTicket(BaseModel):
    text: str


class GraphVoteRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


async def test_ensemble_decider_and_decision_views():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphVoteTicket).decides(
        GraphVoteRoute,
        models=[
            FakeDecider({"billing": 0.95, "tech": 0.05}, label="a"),
            FakeDecider({"billing": 0.2, "tech": 0.8}, label="b"),
            FakeDecider({"billing": 0.97, "tech": 0.03}, label="c"),
        ],
        threshold=0.9,
    )
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    await flock.publish(GraphVoteTicket(text="refund please"))
    await flock.run_until_idle()

    assembler = GraphAssembler(flock.store, collector, flock)
    agent_view = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    triage = next(n for n in agent_view.nodes if n.id == "triage")
    info = triage.data["decision"]
    assert (info["ensemble"], info["vote"]) == (["a", "b", "c"], "majority")

    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    (view,) = [n.data["decision"] for n in blackboard.nodes if "decision" in n.data]
    assert view["choice"] == "billing"
    assert [(v["model"], v["choice"]) for v in view["votes"]] == [
        ("a", "billing"),
        ("b", "tech"),
        ("c", "billing"),
    ]
