"""Dashboard graph data for escalation cascades and escalated decisions."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import Choice, FakeDecider
from flock.registry import flock_type


@flock_type
class GraphEscTicket(BaseModel):
    text: str


class GraphEscRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


def by_text(state: str) -> dict[str, float]:
    return (
        {"billing": 0.95, "tech": 0.05}
        if "refund" in state
        else {"billing": 0.6, "tech": 0.4}
    )


async def test_escalation_decider_and_decision_views():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphEscTicket).decides(
        GraphEscRoute,
        model=FakeDecider({"GraphEscRoute": by_text}, label="fast"),
        threshold=0.9,
        escalate=[FakeDecider({"billing": 0.97, "tech": 0.03}, label="strong")],
    )
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    for text in ("refund please", "charged twice?"):
        await flock.publish(GraphEscTicket(text=text))
    await flock.run_until_idle()

    assembler = GraphAssembler(flock.store, collector, flock)
    agent_view = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    triage = next(n for n in agent_view.nodes if n.id == "triage")
    assert triage.data["decision"]["escalate"] == ["strong"]

    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    views = {
        v["model"]: v
        for v in (n.data["decision"] for n in blackboard.nodes if "decision" in n.data)
    }
    assert "tier" not in views["fast"]
    assert "attempts" not in views["fast"]
    assert views["strong"]["tier"] == 1
    (attempt,) = views["strong"]["attempts"]
    assert (attempt["model"], attempt["choice"]) == ("fast", "billing")
