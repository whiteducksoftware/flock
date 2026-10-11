"""A decider's queue of unsure decisions that need a review (#610)."""

from __future__ import annotations

from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.decisions import Checklist, Choice, Decision, FakeDecider
from flock.registry import flock_type, type_registry


@flock_type
class GraphQueueTicket(BaseModel):
    ticket_id: str
    subject: str


class GraphQueueRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


class GraphQueueAudit(Checklist):
    """Does the ticket show these?"""

    refund = "Asks for a refund"
    crash = "Reports a crash"


async def _flock(decides) -> tuple[Flock, GraphAssembler]:
    flock = Flock()
    flock.is_dashboard = True
    decides(flock.agent("triage").consumes(GraphQueueTicket))
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    return flock, GraphAssembler(flock.store, collector, flock)


async def _decider(assembler: GraphAssembler) -> dict:
    snapshot = await assembler.build_snapshot(GraphRequest(view_mode="agent"))
    (triage,) = [node for node in snapshot.nodes if node.id == "triage"]
    return triage.data["decision"]


async def test_a_decider_lists_its_unsure_decisions_until_someone_reviews_them():
    flock, assembler = await _flock(
        lambda agent: agent.decides(
            GraphQueueRoute,
            model=FakeDecider({"billing": 0.55, "tech": 0.45}),
            threshold=0.8,
        )
    )
    first = await flock.publish(
        GraphQueueTicket(ticket_id="T-1", subject="Charged twice")
    )
    await flock.run_until_idle()
    await flock.publish(GraphQueueTicket(ticket_id="T-2", subject="Crash at login"))
    await flock.run_until_idle()

    decider = await _decider(assembler)
    newest, oldest = decider["needsReview"]
    assert decider["needsReviewCount"] == 2
    # Newest first, named by a field that names the ticket, not its first text
    assert newest["subjectTitle"] == "Crash at login"
    assert oldest["subjectTitle"] == "Charged twice"
    assert oldest["correlationId"] == str(first.correlation_id)
    assert oldest["question"] == "GraphQueueRoute"
    assert oldest["bestGuess"] == "billing"
    assert oldest["probabilities"] == {"billing": 0.55, "tech": 0.45}
    assert oldest["options"] == ["billing", "tech"]

    await flock.review(newest["id"], choice="tech", reviewer="lead")

    decider = await _decider(assembler)
    assert [entry["id"] for entry in decider["needsReview"]] == [oldest["id"]]
    assert decider["needsReviewCount"] == 1


async def test_sure_decisions_and_checklists_need_no_review():
    flock, assembler = await _flock(
        lambda agent: agent.decides(
            GraphQueueRoute, model=FakeDecider({"billing": 0.95, "tech": 0.05})
        )
    )
    await flock.publish(GraphQueueTicket(ticket_id="T-1", subject="Charged twice"))
    await flock.run_until_idle()
    assert (await _decider(assembler))["needsReview"] == []

    # A checklist's unsure items are its results, not a route to a person
    flock, assembler = await _flock(
        lambda agent: agent.decides(
            GraphQueueAudit,
            model=FakeDecider({"GraphQueueAudit": {"refund": 0.5, "crash": 0.5}}),
            threshold=0.9,
        )
    )
    await flock.publish(GraphQueueTicket(ticket_id="T-1", subject="Charged twice"))
    await flock.run_until_idle()
    name = type_registry.name_for(Decision.of(GraphQueueAudit))
    (audit,) = [a for a in await flock.store.list() if a.type == name]
    assert audit.payload["choice"] == "UNSURE"
    decider = await _decider(assembler)
    assert decider["needsReview"] == []
    assert decider["needsReviewCount"] == 0


async def test_a_view_without_unsure_decisions_reads_no_history(monkeypatch):
    flock, assembler = await _flock(
        lambda agent: agent.decides(
            GraphQueueRoute, model=FakeDecider({"billing": 0.95, "tech": 0.05})
        )
    )
    await flock.publish(GraphQueueTicket(ticket_id="T-1", subject="Charged twice"))
    await flock.run_until_idle()
    reads: list[set[str]] = []
    published_since = assembler._published_since

    async def spy(type_names, since, filters, produced_by=None):
        reads.append(set(type_names))
        return await published_since(type_names, since, filters, produced_by)

    monkeypatch.setattr(assembler, "_published_since", spy)

    assert (await _decider(assembler))["needsReview"] == []
    assert reads == []
