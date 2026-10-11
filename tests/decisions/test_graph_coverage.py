"""Dashboard graph data for aggregating agents and coverage."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import (
    GraphFilters,
    GraphRequest,
    GraphRequestOptions,
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


async def test_a_group_counts_with_its_newest_revision_beyond_the_view_limit():
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
    ordered = sorted(await flock.store.list(), key=lambda a: (a.created_at, a.id))
    newest = max(
        (a for a in ordered if a.produced_by == "coverage"),
        key=lambda a: a.payload["revision"],
    )

    # The view ends right before the newest revision
    request = GraphRequest(
        view_mode="agent",
        filters=GraphFilters(time_range=GraphTimeRange(preset="all")),
        options=GraphRequestOptions(limit=ordered.index(newest)),
    )
    agent_view = await GraphAssembler(flock.store, collector, flock).build_snapshot(
        request
    )

    coverage_node = next(n for n in agent_view.nodes if n.id == "coverage")
    in_view = ordered[: ordered.index(newest)]
    assert [a.payload["choice"] for a in in_view if a.produced_by == "coverage"] == [
        "failed"
    ]
    assert newest.payload["choice"] == "passed"
    assert coverage_node.data["coverage"]["groups"] == {
        "passed": 1,
        "failed": 0,
        UNSURE: 0,
    }
