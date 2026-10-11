"""Dashboard graph data for aggregating agents and coverage."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import (
    GraphFilters,
    GraphRequest,
    GraphTimeRange,
)
from flock.core import Flock
from flock.decisions import UNSURE, Checklist, FakeDecider
from flock.registry import flock_type


@flock_type
class GraphCovDocument(BaseModel):
    org: str
    text: str


GraphCovControls = Checklist.from_items(
    "GraphCovControls",
    {"mfa": "MFA is enforced", "backup": "Backups are tested"},
    question="Does the document show that this control is implemented?",
)


def by_text(state: str) -> dict[str, float]:
    if "policy" in state:
        return {"mfa": 0.97, "backup": 0.02}
    return {"mfa": 0.03, "backup": 0.96}


async def test_aggregator_and_coverage_views():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("audit").consumes(GraphCovDocument).decides(
        GraphCovControls,
        model=FakeDecider({"GraphCovControls": by_text}),
        threshold=0.9,
    )
    flock.agent("coverage").consumes(GraphCovControls.ANY).aggregates(by="org")
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    for org, text in (("acme", "policy"), ("acme", "runbook"), ("globex", "policy")):
        await flock.publish(GraphCovDocument(org=org, text=text))
    await flock.run_until_idle()

    assembler = GraphAssembler(flock.store, collector, flock)
    request = GraphRequest(
        view_mode="agent", filters=GraphFilters(time_range=GraphTimeRange(preset="all"))
    )
    agent_view = await assembler.build_snapshot(request)
    coverage_node = next(n for n in agent_view.nodes if n.id == "coverage")
    assert coverage_node.data["coverage"] == {
        "question": "GraphCovControls",
        "by": "org",
        "combine": "any",
        "groups": {"passed": 1, "failed": 1, UNSURE: 0},
    }

    request.view_mode = "blackboard"
    blackboard = await assembler.build_snapshot(request)
    views = [n.data["coverage"] for n in blackboard.nodes if "coverage" in n.data]
    acme = next(v for v in views if v["group"] == "acme" and v["documents"] == 2)
    assert acme == {
        "question": "GraphCovControls",
        "kind": "checklist",
        "group": "acme",
        "combine": "any",
        "documents": 2,
        "choice": "passed",
        "results": {"mfa": "yes", "backup": "yes"},
        "items": ["mfa", "backup"],
        "probabilities": {},
        "refusedItems": [],
    }


async def test_a_group_counts_with_its_newest_revision_outside_the_view():
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("audit").consumes(GraphCovDocument).decides(
        GraphCovControls,
        model=FakeDecider({"GraphCovControls": by_text}),
        threshold=0.9,
    )
    flock.agent("coverage").consumes(GraphCovControls.ANY).aggregates(by="org")
    collector = DashboardEventCollector(store=flock.store)
    for text in ("policy", "runbook"):  # acme fails (revision 1), then passes
        await flock.publish(GraphCovDocument(org="acme", text=text))
        await flock.run_until_idle()
    revisions = {
        a.payload["revision"]: a
        for a in await flock.store.list()
        if a.produced_by == "coverage"
    }

    # The first document's workflow in view: revision 2 belongs to the second
    request = GraphRequest(
        view_mode="agent",
        filters=GraphFilters(
            correlation_id=str(revisions[1].correlation_id),
            time_range=GraphTimeRange(preset="all"),
        ),
    )
    agent_view = await GraphAssembler(flock.store, collector, flock).build_snapshot(
        request
    )

    coverage_node = next(n for n in agent_view.nodes if n.id == "coverage")
    assert revisions[1].payload["choice"] == "failed"
    assert revisions[2].payload["choice"] == "passed"
    assert revisions[2].correlation_id != revisions[1].correlation_id
    assert coverage_node.data["coverage"]["groups"] == {
        "passed": 1,
        "failed": 0,
        UNSURE: 0,
    }
