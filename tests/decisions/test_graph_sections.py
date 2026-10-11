"""Dashboard graph data for decisions about long documents."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import Checklist, FakeDecider, Sections
from flock.registry import flock_type


@flock_type
class GraphSecManual(BaseModel):
    text: str


GraphSecControls = Checklist.from_items(
    "GraphSecControls",
    {"mfa": "MFA is enforced", "backup": "Backups are tested"},
    question="Does the document show that this control is implemented?",
)


def by_section(state: str) -> dict[str, float]:
    if "MFA" in state:
        return {"mfa": 0.97, "backup": 0.05}
    return {"mfa": 0.04, "backup": 0.96}


async def test_decision_views_carry_their_sections():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("audit").consumes(GraphSecManual).decides(
        GraphSecControls,
        model=FakeDecider({"GraphSecControls": by_section}),
        threshold=0.9,
        sections=Sections(field="text", max_chars=40),
    )
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    text = "MFA is enforced for all staff.\n\nRestores are tested monthly."
    await flock.publish(GraphSecManual(text=text))
    await flock.run_until_idle()

    assembler = GraphAssembler(flock.store, collector, flock)
    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    (view,) = [n.data["decision"] for n in blackboard.nodes if "decision" in n.data]
    assert view["sections"] == {
        "field": "text",
        "spans": [[0, 30], [32, 60]],
        "answeredBy": {"mfa": 0, "backup": 1},
    }
