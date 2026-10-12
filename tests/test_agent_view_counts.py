"""The Agent View counts the whole filter range, not the newest artifacts (#640)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest
from pydantic import BaseModel

from flock import Endpoint
from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import (
    GraphFilters,
    GraphRequest,
    GraphRequestOptions,
    GraphSnapshot,
    GraphTimeRange,
)
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.store import ConsumptionRecord, SQLiteBlackboardStore
from flock.decisions import Checklist, Choice, Decision, FakeDecider, Scale, YesNo
from flock.decisions.coverage import Coverage
from flock.registry import flock_type, type_registry
from flock.sinks.models import DeliveryFailed
from flock.utils.runtime import Context


@flock_type
class CountTicket(BaseModel):
    org: str
    text: str


class CountRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


class CountUrgent(YesNo):
    """Does the customer need an answer today?"""


class CountMood(Scale):
    """How upset is the customer?"""

    calm = "No complaint"
    upset = "Complains"
    angry = "Threatens to leave"


CountControls = Checklist.from_items(
    "CountControls",
    {"refund": "Asks for a refund", "crash": "Reports a crash"},
    question="Does the ticket show this?",
)

# refund -> billing, crash -> tech, the rest is unsure (threshold 0.8)
TICKETS = [
    ("acme", "refund please"),
    ("globex", "refund twice!"),
    ("acme", "crash at login"),
    ("initech", "refund now"),
    ("globex", "crash again!"),
    ("acme", "what is this"),
    ("initech", "hmm"),
    ("globex", "refund!"),
    ("acme", "maybe"),
]


def route(state: str) -> dict[str, float]:
    if "refund" in state:
        return {"billing": 0.95, "tech": 0.05}
    if "crash" in state:
        return {"billing": 0.05, "tech": 0.95}
    return {"billing": 0.55, "tech": 0.45}


def mood(state: str) -> dict[str, float]:
    if "!" in state:
        return {"calm": 0.1, "upset": 0.2, "angry": 0.7}
    return {"calm": 0.8, "upset": 0.1, "angry": 0.1}


def controls(state: str) -> dict[str, float]:
    # A crash the ticket does not mention is unsure (threshold 0.9)
    return {
        "refund": 0.97 if "refund" in state else 0.03,
        "crash": 0.97 if "crash" in state else 0.5,
    }


async def _played(kind: str, tmp_path) -> Flock:
    store = (
        SQLiteBlackboardStore(str(tmp_path / "board.db")) if kind == "sqlite" else None
    )
    flock = Flock(
        **({"store": store} if store else {}),
        # Nothing listens there: every delivery fails, at once
        endpoints={"hook": Endpoint("http://127.0.0.1:9", retries=0, timeout=1.0)},
    )
    flock.agent("triage").consumes(CountTicket).decides(
        CountRoute,
        model=FakeDecider({"CountRoute": route}),
        shadow=FakeDecider({"billing": 0.9, "tech": 0.1}, label="candidate"),
        threshold=0.8,
    )
    flock.agent("billing").consumes(CountRoute.billing).decides(
        CountUrgent, model=FakeDecider({"yes": 0.9, "no": 0.1})
    )
    flock.agent("mood").consumes(CountTicket).decides(
        CountMood, model=FakeDecider({"CountMood": mood})
    )
    flock.agent("audit").consumes(CountTicket).decides(
        CountControls, model=FakeDecider({"CountControls": controls}), threshold=0.9
    )
    flock.agent("coverage").consumes(CountControls.ANY).aggregates(by="org")
    flock.sink("hook").consumes(Decision.of(CountUrgent)).post("hook:/urgent")
    for org, text in TICKETS:
        await flock.publish(CountTicket(org=org, text=text))
    await flock.run_until_idle()
    # A person answers one of the unsure tickets
    unsure = [
        a
        for a in await flock.store.list()
        if a.produced_by == "triage" and a.payload.get("choice") == "UNSURE"
    ]
    await flock.review(unsure[0].id, choice="tech", reviewer="lead")
    await flock.run_until_idle()
    return flock


async def _agent_view(
    flock: Flock,
    limit: int,
    collector: DashboardEventCollector | None = None,
    **filters,
) -> GraphSnapshot:
    collector = collector or DashboardEventCollector(store=flock.store)
    return await GraphAssembler(flock.store, collector, flock).build_snapshot(
        GraphRequest(
            view_mode="agent",
            filters=GraphFilters(time_range=GraphTimeRange(preset="all"), **filters),
            options=GraphRequestOptions(limit=limit),
        )
    )


def _counts(snapshot: GraphSnapshot) -> dict[str, Any]:
    """Every count on the Agent View: cards, decisions, sinks, coverage, edges."""
    cards = {}
    for node in snapshot.nodes:
        if node.type != "agent":
            continue
        data = node.data
        decision = data.get("decision") or {}
        cards[node.id] = {
            "sent": (data["sentCount"], data["sentByType"]),
            "received": (data["recvCount"], data["receivedByType"]),
            "questions": [
                {
                    key: question.get(key)
                    for key in ("counts", "refused", "meanScore", "itemStats")
                }
                for question in decision.get("questions", [])
            ],
            "shadow": decision.get("shadow"),
            "needsReview": decision.get("needsReviewCount"),
            "coverage": data.get("coverage"),
            "sink": {key: data["sink"][key] for key in ("delivered", "failed")}
            if data.get("sink")
            else None,
        }
    edges = {
        edge.id: (edge.label, edge.data["messageCount"])
        for edge in snapshot.edges
        if edge.type == "message_flow"
    }
    return {"cards": cards, "edges": edges}


@pytest.fixture(params=["memory", "sqlite"])
async def played(request, tmp_path):
    flock = await _played(request.param, tmp_path)
    yield flock
    if isinstance(flock.store, SQLiteBlackboardStore):
        await flock.store.close()


def _card(sent=(0, {}), received=(0, {}), questions=(), **more) -> dict[str, Any]:
    return {
        "sent": sent,
        "received": received,
        "questions": [
            {"counts": None, "refused": None, "meanScore": None, "itemStats": None}
            | question
            for question in questions
        ],
        "shadow": None,
        "needsReview": None,
        "coverage": None,
        "sink": None,
    } | more


async def test_the_agent_view_counts_more_than_the_newest_artifacts(played):
    ticket = type_registry.name_for(CountTicket)
    route_, urgent = (
        type_registry.name_for(Decision.of(q)) for q in (CountRoute, CountUrgent)
    )
    mood_, controls_ = (
        type_registry.name_for(Decision.of(q)) for q in (CountMood, CountControls)
    )
    coverage = type_registry.name_for(Coverage.of(CountControls))
    failed = type_registry.name_for(DeliveryFailed)

    # Three artifacts in view, 54 on the board: the counts of all 54
    counts = _counts(await _agent_view(played, limit=3))

    assert counts["cards"] == {
        "external": _card(sent=(9, {ticket: 9})),
        "triage": _card(
            sent=(9, {route_: 9}),
            received=(9, {ticket: 9}),
            questions=[{"counts": {"billing": 4, "tech": 2, "UNSURE": 3}}],
            shadow={"model": "candidate", "compared": 9, "agree": 4},
            needsReview=2,  # three unsure, one reviewed
        ),
        "lead": _card(sent=(1, {route_: 1})),  # the review
        "billing": _card(
            sent=(4, {urgent: 4}),
            received=(4, {route_: 4}),
            questions=[{"counts": {"yes": 4, "no": 0}}],
            needsReview=0,
        ),
        "mood": _card(
            sent=(9, {mood_: 9}),
            received=(9, {ticket: 9}),
            questions=[
                {
                    "counts": {"calm": 6, "upset": 0, "angry": 3},
                    "meanScore": pytest.approx(0.7333333),
                }
            ],
            needsReview=0,
        ),
        "audit": _card(
            sent=(9, {controls_: 9}),
            received=(9, {ticket: 9}),
            questions=[
                {
                    "counts": {"passed": 0, "failed": 5, "UNSURE": 4},
                    # [yes, no, unsure] of refund, then of crash
                    "itemStats": [[4, 5, 0], [2, 0, 7]],
                }
            ],
            needsReview=0,
        ),
        "coverage": _card(
            sent=(9, {coverage: 9}),
            received=(9, {controls_: 9}),
            coverage={
                "question": "CountControls",
                "by": "org",
                "combine": "any",
                "groups": {"passed": 2, "failed": 0, "UNSURE": 1},
            },
        ),
        "hook": _card(
            sent=(4, {failed: 4}),
            received=(4, {urgent: 4}),
            sink={"delivered": 0, "failed": 4},
        ),
    }
    assert counts["edges"] == {
        f"external__triage__{ticket}": (f"{ticket} (9)", 9),
        f"external__mood__{ticket}": (f"{ticket} (9)", 9),
        f"external__audit__{ticket}": (f"{ticket} (9)", 9),
        f"triage__billing__{route_}__billing": ("billing (4)", 4),
        f"billing__hook__{urgent}__CountUrgent.yes": ("CountUrgent.yes (4)", 4),
        f"audit__coverage__{controls_}__CountControls.failed": (
            "CountControls.failed (5)",
            5,
        ),
        f"audit__coverage__{controls_}__CountControls.UNSURE": (
            "CountControls.UNSURE (4)",
            4,
        ),
    }


async def _ticket(flock: Flock, text: str) -> Artifact:
    ticket_type = type_registry.name_for(CountTicket)
    return next(
        a
        for a in await flock.store.list()
        if a.type == ticket_type and a.payload["text"] == text
    )


async def test_a_filter_narrows_the_counts(played):
    ticket_type = type_registry.name_for(CountTicket)
    first = await _ticket(played, "refund please")

    # One ticket's workflow: one ticket, one decision of each decider
    cards = _counts(
        await _agent_view(played, limit=2, correlation_id=str(first.correlation_id))
    )["cards"]

    assert cards["external"]["sent"] == (1, {ticket_type: 1})
    assert cards["triage"]["received"] == (1, {ticket_type: 1})
    assert cards["triage"]["questions"][0]["counts"] == {
        "billing": 1,
        "tech": 0,
        "UNSURE": 0,
    }


async def test_a_review_outside_the_filter_still_answers_a_decision(played):
    # The person's review is not triage's: still, one of three is answered
    cards = _counts(await _agent_view(played, limit=2, producers=["triage"]))["cards"]

    assert cards["triage"]["questions"][0]["counts"]["UNSURE"] == 3
    assert cards["triage"]["needsReview"] == 2


async def test_a_group_counts_with_its_newest_revision_outside_the_filter(played):
    coverage_type = type_registry.name_for(Coverage.of(CountControls))
    artifacts = await played.store.list()
    first = await _ticket(played, "refund please")  # acme's first
    newest = max(
        (
            a
            for a in artifacts
            if a.type == coverage_type and a.payload["group"] == "acme"
        ),
        key=lambda a: a.payload["revision"],
    )
    assert newest.correlation_id != first.correlation_id

    cards = _counts(
        await _agent_view(played, limit=2, correlation_id=str(first.correlation_id))
    )["cards"]

    groups = cards["coverage"]["coverage"]["groups"]
    assert groups == {"passed": 0, "failed": 0, "UNSURE": 0} | {
        newest.payload["choice"]: 1
    }


async def _reading(kind: str, tmp_path) -> tuple[Flock, Any, DashboardEventCollector]:
    """A flock whose reader runs only on paper: the collector hears of its
    runs, nothing schedules them."""
    store = (
        SQLiteBlackboardStore(str(tmp_path / "runs.db")) if kind == "sqlite" else None
    )
    flock = Flock(**({"store": store} if store else {}))
    reader = flock.agent("reader").consumes(CountTicket)._agent
    return flock, reader, DashboardEventCollector(store=flock.store)


async def _ticket_on_board(flock: Flock, text: str) -> Artifact:
    ticket = Artifact(
        type=type_registry.name_for(CountTicket),
        payload={"org": "acme", "text": text},
        produced_by="external",
    )
    await flock.store.publish(ticket)  # published, not scheduled
    return ticket


async def _starts(collector, flock, reader, run_id: str, artifact: Artifact) -> None:
    ctx = Context(
        board=flock.store,
        orchestrator=flock,
        task_id=run_id,
        state={"artifacts_produced": [], "metrics": {}},
        correlation_id=str(artifact.correlation_id),
    )
    await collector.on_pre_consume(reader, ctx, [artifact])


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
async def test_what_running_agents_consume_counts_once(kind, tmp_path):
    flock, reader, collector = await _reading(kind, tmp_path)
    done = await _ticket_on_board(flock, "done")
    running = await _ticket_on_board(flock, "running")
    # A run that ended: the store and the collector know; one that runs: only
    # the collector, until it ends
    await flock.store.record_consumptions([
        ConsumptionRecord(artifact_id=done.id, consumer="reader", run_id="r1")
    ])
    await _starts(collector, flock, reader, "r1", done)
    await _starts(collector, flock, reader, "r2", running)

    counts = _counts(await _agent_view(flock, limit=5, collector=collector))

    ticket_type = type_registry.name_for(CountTicket)
    assert counts["cards"]["reader"]["received"] == (2, {ticket_type: 2})
    assert counts["edges"] == {
        f"external__reader__{ticket_type}": (f"{ticket_type} (2)", 2)
    }
    if kind == "sqlite":
        await flock.store.close()


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
async def test_a_run_that_ends_while_the_board_is_read_still_counts(
    kind, tmp_path, monkeypatch
):
    flock, reader, collector = await _reading(kind, tmp_path)
    ticket = await _ticket_on_board(flock, "running")
    await _starts(collector, flock, reader, "r1", ticket)
    counted = flock.store.flow_counts

    async def ends_meanwhile(*args, **kwargs):
        flow = await counted(*args, **kwargs)
        # The run ends and the store records it, before the newest are read
        await flock.store.record_consumptions([
            ConsumptionRecord(artifact_id=ticket.id, consumer="reader", run_id="r1")
        ])
        return flow

    monkeypatch.setattr(flock.store, "flow_counts", ends_meanwhile)
    counts = _counts(await _agent_view(flock, limit=5, collector=collector))

    ticket_type = type_registry.name_for(CountTicket)
    assert counts["cards"]["reader"]["received"] == (1, {ticket_type: 1})
    if kind == "sqlite":
        await flock.store.close()


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
async def test_a_run_that_ended_before_it_is_recorded_still_counts(kind, tmp_path):
    flock, reader, collector = await _reading(kind, tmp_path)
    ticket = await _ticket_on_board(flock, "ended")
    await _starts(collector, flock, reader, "r1", ticket)
    # The collector hears the run end; the orchestrator records what it
    # consumed only after publishing its outputs
    await collector.on_terminate(
        reader,
        Context(
            board=flock.store,
            orchestrator=flock,
            task_id="r1",
            state={"artifacts_produced": [], "metrics": {}},
            correlation_id=str(ticket.correlation_id),
        ),
    )

    counts = _counts(await _agent_view(flock, limit=5, collector=collector))

    ticket_type = type_registry.name_for(CountTicket)
    assert counts["cards"]["reader"]["received"] == (1, {ticket_type: 1})
    if kind == "sqlite":
        await flock.store.close()


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
async def test_a_failed_run_counts_what_it_consumed_for_good(
    kind, tmp_path, monkeypatch
):
    from flock.api import graph_builder

    flock, reader, collector = await _reading(kind, tmp_path)
    ticket = await _ticket_on_board(flock, "fails")
    await _starts(collector, flock, reader, "r1", ticket)
    # A failed run records nothing: the orchestrator stops before it would
    ctx = Context(
        board=flock.store,
        orchestrator=flock,
        task_id="r1",
        state={"artifacts_produced": [], "metrics": {}},
        correlation_id=str(ticket.correlation_id),
    )
    await collector.on_error(reader, ctx, RuntimeError("boom"))
    # Long after the margin in which an ended run may still be recorded
    monkeypatch.setattr(graph_builder, "_CLOCK_MARGIN", timedelta(0))

    counts = _counts(await _agent_view(flock, limit=5, collector=collector))

    ticket_type = type_registry.name_for(CountTicket)
    assert counts["cards"]["reader"]["received"] == (1, {ticket_type: 1})
    if kind == "sqlite":
        await flock.store.close()


async def test_sqlite_counts_one_state_of_the_board(tmp_path, monkeypatch):
    from flock.storage.sqlite.flow_queries import SQLiteFlowQueries

    flock, reader, collector = await _reading("sqlite", tmp_path)
    first = await _ticket_on_board(flock, "first")
    await flock.store.record_consumptions([
        ConsumptionRecord(artifact_id=first.id, consumer="reader", run_id="r1")
    ])
    rows = SQLiteFlowQueries._rows
    meanwhile: list[asyncio.Task] = []
    queries = 0

    async def publish_meanwhile():
        # Another ticket and its consumption, while the board is counted
        second = await _ticket_on_board(flock, "second")
        await flock.store.record_consumptions([
            ConsumptionRecord(artifact_id=second.id, consumer="reader", run_id="r2")
        ])

    async def interleaved(conn, query, params):
        nonlocal queries
        queries += 1
        if queries == 2:  # after the artifacts, before the consumptions
            meanwhile.append(asyncio.create_task(publish_meanwhile()))
            await asyncio.sleep(0.05)
        return await rows(conn, query, params)

    monkeypatch.setattr(SQLiteFlowQueries, "_rows", staticmethod(interleaved))
    counts = _counts(await _agent_view(flock, limit=5, collector=collector))
    await meanwhile[0]

    # What external published and what reader consumed: the same board
    sent = counts["cards"]["external"]["sent"][0]
    assert counts["cards"]["reader"]["received"][0] == sent
    await flock.store.close()


def test_a_store_that_records_no_consumptions_counts_every_run():
    from datetime import UTC, datetime

    from flock.components.server.models.graph import GraphRun, GraphState
    from flock.core.store import BlackboardStore

    class Unrecording(BlackboardStore):
        """Keeps artifacts only: what was consumed lives in the collector."""

    ended = GraphRun(
        run_id="r1",
        agent_name="reader",
        status="completed",
        consumed_artifacts=["a1"],
        completed_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    state = GraphState(runs=[ended])
    flock = Flock()
    collector = DashboardEventCollector(store=flock.store)

    recording = GraphAssembler(flock.store, collector, flock)
    unrecording = GraphAssembler(Unrecording(), collector, flock)

    # The in-memory store recorded what the long-ended run consumed
    assert recording._unrecorded_consumptions(state) == {}
    assert unrecording._unrecorded_consumptions(state) == {"a1": {"reader"}}
