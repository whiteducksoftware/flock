"""Dashboard graph data for shadow deciders and shadowed decisions."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import Choice, FakeDecider
from flock.registry import flock_type


@flock_type
class GraphShadowTicket(BaseModel):
    text: str


class GraphShadowRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


def candidate(state: str) -> dict[str, float]:
    return (
        {"billing": 0.1, "tech": 0.9}
        if "crash" in state
        else {"billing": 0.9, "tech": 0.1}
    )


async def test_shadow_decider_and_decision_views():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(GraphShadowTicket).decides(
        GraphShadowRoute,
        model=FakeDecider({"billing": 0.95, "tech": 0.05}, label="live"),
        shadow=FakeDecider({"GraphShadowRoute": candidate}, label="candidate"),
        threshold=0.8,
    )
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    for text in ("refund please", "charged twice", "app crash after payment"):
        await flock.publish(GraphShadowTicket(text=text))
    await flock.run_until_idle()

    assembler = GraphAssembler(flock.store, collector, flock)
    agent_view = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    triage = next(n for n in agent_view.nodes if n.id == "triage")
    assert triage.data["decision"]["shadow"] == {
        "model": "candidate",
        "compared": 3,
        "agree": 2,
    }

    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    views = [n.data["decision"] for n in blackboard.nodes if "decision" in n.data]
    assert sorted(v["shadow"]["choice"] for v in views) == [
        "billing",
        "billing",
        "tech",
    ]
