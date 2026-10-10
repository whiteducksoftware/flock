"""Dashboard graph data for checklist deciders and checklist decisions."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.agent import EngineComponent
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import Checklist, FakeDecider
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


@flock_type
class Procedure(BaseModel):
    text: str


@flock_type
class Gap(BaseModel):
    by: str


class Audit(Checklist):
    """Does the procedure show that this control is implemented?"""

    mfa = "MFA for remote access"
    review = "Access rights are reviewed"
    leaver = "Leavers lose access within a day"


class Fix(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        return EvalResult.from_object(Gap(by=agent.name), agent=agent)


def answers(state: str) -> dict[str, float]:
    if "complete" in state:
        return {"mfa": 0.99, "review": 0.97, "leaver": 0.95}
    if "partial" in state:
        return {"mfa": 0.98, "review": 0.05, "leaver": 0.6}
    return {"mfa": 0.02, "review": 0.03, "leaver": 0.01}


@pytest.fixture
async def audited() -> Flock:
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("audit").consumes(Procedure).decides(
        Audit, model=FakeDecider({"Audit": answers}), threshold=0.9
    )
    flock.agent("remediation").consumes(Audit.failed).with_engines(Fix()).publishes(Gap)
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    flock._test_collector = collector
    for text in ("complete procedure", "partial procedure", "empty procedure"):
        await flock.publish(Procedure(text=text))
    await flock.run_until_idle()
    return flock


async def snapshot(flock: Flock, view_mode: str):
    assembler = GraphAssembler(flock.store, flock._test_collector, flock)
    return await assembler.build_snapshot(GraphRequest(view_mode=view_mode))


async def test_checklist_decider_counts_outcomes_and_items(audited):
    graph = await snapshot(audited, "agent")

    audit = next(node for node in graph.nodes if node.id == "audit")
    (info,) = audit.data["decision"]["questions"]
    assert info["kind"] == "checklist"
    assert info["options"] == ["mfa", "review", "leaver"]
    assert info["counts"] == {"passed": 1, "failed": 2, "UNSURE": 0}
    # [yes, no, unsure] per item over the three procedures
    assert info["itemStats"] == [[2, 1, 0], [1, 2, 0], [1, 1, 1]]
    assert info["descriptions"]["leaver"] == "Leavers lose access within a day"


async def test_checklist_edges_carry_the_outcome(audited):
    graph = await snapshot(audited, "agent")

    labels = {e.label for e in graph.edges if e.source == "audit"}
    assert labels == {"Audit.failed (2)"}


async def test_checklist_decision_view_has_results_in_item_order(audited):
    graph = await snapshot(audited, "blackboard")

    views = [n.data["decision"] for n in graph.nodes if "decision" in n.data]
    partial = next(
        v for v in views if v["results"]["mfa"] == "yes" and v["choice"] == "failed"
    )
    assert partial["kind"] == "checklist"
    assert partial["items"] == ["mfa", "review", "leaver"]
    assert partial["results"] == {"mfa": "yes", "review": "no", "leaver": "UNSURE"}
    assert partial["refusedItems"] == []
