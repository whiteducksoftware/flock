"""Dashboard graph data for tournament deciders and their decisions."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import Choice, FakeDecider, Tournament
from flock.registry import flock_type


@flock_type
class Evidence(BaseModel):
    text: str


Control = Choice.from_options(
    "Control",
    {f"c_{i:02d}": f"Control {i}" for i in range(60)},
    question="Which control?",
)


def peaked(state: str) -> dict[str, float]:
    winner = "c_42" if "keys" in state else "c_07"
    return {o: 0.7 if o == winner else 0.3 / 59 for o in Control.__options__}


async def test_tournament_decider_and_decision_views():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("mapper").consumes(Evidence).decides(
        Control,
        model=FakeDecider({"Control": peaked}),
        tournament=Tournament(group_size=20, keep=2),
    )
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    for text in ("we rotate keys", "badges at the door"):
        await flock.publish(Evidence(text=text))
    await flock.run_until_idle()

    assembler = GraphAssembler(flock.store, collector, flock)
    agent_view = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    mapper = next(n for n in agent_view.nodes if n.id == "mapper")
    info = mapper.data["decision"]
    assert info["tournament"] == {"groupSize": 20, "keep": 2}
    assert info["questions"][0]["counts"]["c_42"] == 1

    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    views = [n.data["decision"] for n in blackboard.nodes if "decision" in n.data]
    assert {v["choice"] for v in views} == {"c_42", "c_07"}
    for view in views:
        (round_one,) = view["rounds"]
        assert round_one["candidates"] == 60
        assert round_one["groups"] == 3
        assert len(round_one["survivors"]) == 6
