"""Calibration: thresholds for a target precision from labelled decisions (#474)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from flock.core import Flock
from flock.core.store import SQLiteBlackboardStore
from flock.decisions import UNSURE, Checklist, Choice, Decision, FakeDecider
from flock.decisions.calibration import (
    calibrate,
    calibrate_store,
    labels_from_reviews,
    suggest_threshold,
)
from flock.registry import flock_type, type_registry


@flock_type
class CalTicket(BaseModel):
    text: str


class CalRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


CalControls = Checklist.from_items(
    "CalControls",
    {"mfa": "MFA is enforced", "logs": "Logs are kept"},
    question="Shown?",
)


def test_the_lowest_threshold_that_reaches_the_target_wins():
    # (confidence, correct): wrong answers only below 0.7
    points = [
        (0.95, True),
        (0.9, True),
        (0.8, True),
        (0.75, True),
        (0.65, False),
        (0.6, True),
    ]

    threshold, precision, coverage = suggest_threshold(
        points, target=0.95, min_support=3
    )

    assert threshold == 0.75
    assert precision == 1.0
    assert coverage == pytest.approx(4 / 6)


def test_no_threshold_when_the_target_is_out_of_reach():
    points = [(0.95, False), (0.9, True), (0.8, False)]

    assert suggest_threshold(points, target=0.95, min_support=1)[0] is None


def test_a_threshold_needs_enough_answers_above_it():
    points = [(0.99, True), (0.6, False), (0.5, False)]

    assert suggest_threshold(points, target=0.95, min_support=2)[0] is None


def _decision(subject: str, probabilities: dict[str, float], **extra) -> dict:
    best = max(probabilities, key=probabilities.__getitem__)
    return {
        "question": "CalRoute",
        "kind": "choice",
        "choice": best,
        "best_guess": best,
        "probabilities": probabilities,
        "subject_ids": [subject],
        "model": "fast",
        **extra,
    }


def test_calibrate_suggests_a_threshold_per_question():
    decisions = [
        _decision("t1", {"billing": 0.95, "tech": 0.05}),
        _decision("t2", {"billing": 0.9, "tech": 0.1}),
        _decision("t3", {"billing": 0.1, "tech": 0.9}),
        _decision("t4", {"billing": 0.6, "tech": 0.4}),  # wrong
    ]
    labels = {
        "t1": {"CalRoute": "billing"},
        "t2": {"CalRoute": "billing"},
        "t3": {"CalRoute": "tech"},
        "t4": {"CalRoute": "tech"},
    }

    (suggestion,) = calibrate(decisions, labels, target_precision=0.95, min_support=2)

    assert suggestion.question == "CalRoute"
    assert suggestion.item is None
    assert suggestion.labeled == 4
    assert suggestion.threshold == 0.9
    assert suggestion.precision == 1.0


def test_checklists_get_a_threshold_per_item():
    def checklist(subject: str, mfa: float, logs: float) -> dict:
        return {
            "question": "CalControls",
            "kind": "checklist",
            "choice": "UNSURE",
            "probabilities": {"mfa": mfa, "logs": logs},
            "results": {},
            "subject_ids": [subject],
            "model": "fast",
        }

    decisions = [
        checklist("d1", mfa=0.95, logs=0.7),
        checklist("d2", mfa=0.1, logs=0.65),  # logs wrong at 0.65
        checklist("d3", mfa=0.85, logs=0.9),
    ]
    labels = {
        "d1": {"CalControls": {"mfa": "yes", "logs": "yes"}},
        "d2": {"CalControls": {"mfa": "no", "logs": "no"}},
        "d3": {"CalControls": {"mfa": "yes", "logs": "yes"}},
    }

    suggestions = calibrate(decisions, labels, target_precision=0.95, min_support=2)

    by_item = {s.item: s for s in suggestions}
    assert by_item["mfa"].threshold == 0.85  # every mfa answer is right
    assert by_item["logs"].threshold == 0.7  # the 0.65 answer is wrong


def test_reviews_are_labels_and_are_not_calibrated_themselves():
    decisions = [
        _decision("t1", {"billing": 0.6, "tech": 0.4}),
        _decision("t1", {"tech": 1.0}, model="lead", review_of="x"),
    ]

    assert labels_from_reviews(decisions) == {"t1": {"CalRoute": "tech"}}
    (suggestion,) = calibrate(decisions, labels_from_reviews(decisions), min_support=1)
    assert suggestion.labeled == 1


def test_a_label_counts_only_for_its_question():
    decisions = [
        _decision("t1", {"billing": 0.9, "tech": 0.1}),
        {
            **_decision("t1", {"yes": 0.9, "no": 0.1}),
            "question": "CalUrgent",
            "kind": "yesno",
        },
    ]

    suggestions = calibrate(decisions, {"t1": {"CalUrgent": "yes"}}, min_support=1)

    assert [s.question for s in suggestions] == ["CalUrgent"]


def test_deciders_are_calibrated_apart():
    from flock.core.artifacts import Artifact

    def decision(producer: str, subject: str, p: float) -> Artifact:
        return Artifact(
            type="x",
            payload=_decision(subject, {"billing": p, "tech": 1 - p}),
            produced_by=producer,
        )

    decisions = [decision("fast", "t1", 0.9), decision("strong", "t1", 0.99)]

    suggestions = calibrate(decisions, {"t1": {"CalRoute": "billing"}}, min_support=1)

    assert sorted((s.decider, s.threshold) for s in suggestions) == [
        ("fast", 0.9),
        ("strong", 0.99),
    ]


def test_calibration_constraints_are_checked():
    with pytest.raises(ValueError, match="target"):
        suggest_threshold([(0.9, True)], target=0)
    with pytest.raises(ValueError, match="target"):
        suggest_threshold([(0.9, True)], target=1.5)
    with pytest.raises(ValueError, match="min_support"):
        suggest_threshold([(0.9, True)], target=0.9, min_support=0)


async def test_item_thresholds_can_name_the_checklist():
    other = Checklist.from_items("CalOther", {"mfa": "MFA"}, question="Shown?")
    flock = Flock()
    flock.agent("audit").consumes(CalTicket).decides(
        CalControls,
        other,
        model=FakeDecider({
            "CalControls": {"mfa": 0.75, "logs": 0.75},
            "CalOther": {"mfa": 0.75},
        }),
        threshold=0.9,
        item_thresholds={"CalControls.mfa": 0.7},
    )

    await flock.publish(CalTicket(text="policy"))
    await flock.run_until_idle()

    results = {
        a.payload["question"]: a.payload["results"]
        for a in await flock.store.list()
        if a.type.startswith("Decision[")
    }
    assert results["CalControls"]["mfa"] == "yes"
    assert results["CalOther"]["mfa"] == UNSURE


async def test_calibrate_store_finds_decision_types_it_never_imported(tmp_path):
    from flock.core.artifacts import Artifact

    store = SQLiteBlackboardStore(str(tmp_path / "foreign.db"))
    await store.ensure_schema()
    # Decisions of an application this process never imported
    original = Artifact(
        type="Decision[elsewhere.app.Route]",
        payload=_decision("t1", {"billing": 0.9, "tech": 0.1}),
        produced_by="triage",
    )
    review = Artifact(
        type="Decision[elsewhere.app.Route]",
        payload=_decision(
            "t1", {"billing": 1.0}, model="lead", review_of=str(original.id)
        ),
        produced_by="lead",
    )
    await store.publish(original)
    await store.publish(review)

    suggestions = await calibrate_store(store, target_precision=0.9, min_support=1)
    await store.close()

    assert [(s.decider, s.threshold) for s in suggestions] == [("triage", 0.9)]


def test_the_cli_rejects_a_zero_target(tmp_path):
    from flock.cli import app

    result = CliRunner().invoke(
        app,
        ["decisions", "calibrate", str(tmp_path / "x.db"), "--target-precision", "0"],
    )

    assert result.exit_code == 2  # a usage error, not a crash
    assert "target" in result.output.lower()


def test_dotted_item_ids_keep_their_dots():
    dotted = Checklist.from_items(
        "CalBsi", {"ORP.1.A1": "Responsibilities"}, question="Shown?"
    )
    builder = Flock().agent("x").consumes(CalTicket)

    builder.decides(dotted, model=FakeDecider({}), item_thresholds={"ORP.1.A1": 0.7})
    Flock().agent("y").consumes(CalTicket).decides(
        dotted, model=FakeDecider({}), item_thresholds={"CalBsi.ORP.1.A1": 0.7}
    )


def test_an_item_cannot_get_two_thresholds():
    with pytest.raises(ValueError, match="twice"):
        Flock().agent("x").consumes(CalTicket).decides(
            CalControls,
            model=FakeDecider({}),
            item_thresholds={"mfa": 0.7, "CalControls.mfa": 0.9},
        )


def test_escalated_or_voted_decisions_are_not_calibrated():
    decisions = [
        _decision("t1", {"billing": 0.9, "tech": 0.1}),
        _decision(
            "t2",
            {"billing": 0.95, "tech": 0.05},
            tier=1,
            attempts=[{"model": "fast", "choice": "billing", "probabilities": {}}],
        ),
    ]
    labels = {"t1": {"CalRoute": "billing"}, "t2": {"CalRoute": "billing"}}

    (suggestion,) = calibrate(decisions, labels, min_support=1)

    assert suggestion.threshold is None
    assert "escalat" in suggestion.note


async def test_decisions_record_the_item_thresholds_that_applied():
    flock = Flock()
    flock.agent("audit").consumes(CalTicket).decides(
        CalControls,
        model=FakeDecider({"CalControls": {"mfa": 0.75, "logs": 0.75}}),
        threshold=0.9,
        item_thresholds={"mfa": 0.7},
    )

    await flock.publish(CalTicket(text="policy"))
    await flock.run_until_idle()

    name = type_registry.name_for(Decision.of(CalControls))
    (decision,) = [a.payload for a in await flock.store.list() if a.type == name]
    assert decision["item_thresholds"] == {"mfa": 0.7}


def test_a_plain_item_name_must_be_unambiguous():
    other = Checklist.from_items("CalOther2", {"mfa": "MFA"}, question="Shown?")
    with pytest.raises(ValueError, match="CalControls.mfa"):
        Flock().agent("x").consumes(CalTicket).decides(
            CalControls, other, model=FakeDecider({}), item_thresholds={"mfa": 0.7}
        )


async def test_item_thresholds_apply_per_checklist_item():
    flock = Flock()
    flock.agent("audit").consumes(CalTicket).decides(
        CalControls,
        model=FakeDecider({"CalControls": {"mfa": 0.75, "logs": 0.75}}),
        threshold=0.9,
        item_thresholds={"mfa": 0.7},
    )

    await flock.publish(CalTicket(text="policy"))
    await flock.run_until_idle()

    name = type_registry.name_for(Decision.of(CalControls))
    (decision,) = [a.payload for a in await flock.store.list() if a.type == name]
    assert decision["results"] == {"mfa": "yes", "logs": UNSURE}


def test_item_thresholds_name_items_of_the_checklist():
    with pytest.raises(ValueError, match="item_thresholds"):
        Flock().agent("x").consumes(CalTicket).decides(
            CalControls, model=FakeDecider({}), item_thresholds={"backup": 0.7}
        )
    with pytest.raises(ValueError, match="item_thresholds"):
        Flock().agent("y").consumes(CalTicket).decides(
            CalRoute, model=FakeDecider({}), item_thresholds={"mfa": 0.7}
        )


async def _reviewed_store(path) -> None:
    flock = Flock(store=SQLiteBlackboardStore(str(path)))

    def route(state: str) -> dict:
        return (
            {"billing": 0.6, "tech": 0.4}
            if "crash" in state
            else {"billing": 0.97, "tech": 0.03}
        )

    flock.agent("triage").consumes(CalTicket).decides(
        CalRoute, model=FakeDecider({"CalRoute": route}), threshold=0.8
    )
    for text in ("charged twice", "refund please", "app crash", "another crash"):
        await flock.publish(CalTicket(text=text))
    await flock.run_until_idle()
    name = type_registry.name_for(Decision.of(CalRoute))
    for artifact in [a for a in await flock.store.list() if a.type == name]:
        choice = (
            "tech"
            if artifact.payload["best_guess"] == "billing"
            and artifact.payload["choice"] == "UNSURE"
            else artifact.payload["best_guess"]
        )
        await flock.review(artifact.id, choice=choice, reviewer="lead")
    await flock.run_until_idle()
    await flock.store.close()


async def test_calibrate_store_uses_the_reviews(tmp_path):
    path = tmp_path / "blackboard.db"
    await _reviewed_store(path)

    store = SQLiteBlackboardStore(str(path))
    (suggestion,) = await calibrate_store(store, target_precision=0.95, min_support=2)
    await store.close()

    assert suggestion.labeled == 4
    assert suggestion.threshold == 0.97  # the 0.6 answers were wrong


def test_the_cli_prints_the_suggestions(tmp_path):
    import asyncio

    from flock.cli import app

    path = tmp_path / "blackboard.db"
    asyncio.run(_reviewed_store(path))  # the CLI runs its own event loop

    result = CliRunner().invoke(
        app,
        [
            "decisions",
            "calibrate",
            str(path),
            "--target-precision",
            "0.95",
            "--min-support",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "CalRoute" in result.output
    assert "0.97" in result.output


async def test_the_decider_view_lists_its_item_thresholds():
    from flock.api.collector import DashboardEventCollector
    from flock.api.graph_builder import GraphAssembler
    from flock.components.server.models.graph import GraphRequest

    flock = Flock()
    flock.is_dashboard = True
    flock.agent("audit").consumes(CalTicket).decides(
        CalControls,
        model=FakeDecider({"CalControls": {"mfa": 0.75, "logs": 0.75}}),
        threshold=0.9,
        item_thresholds={"mfa": 0.7},
    )
    collector = DashboardEventCollector(store=flock.store)
    assembler = GraphAssembler(flock.store, collector, flock)
    graph = await assembler.build_snapshot(GraphRequest(view_mode="agent"))

    audit = next(node for node in graph.nodes if node.id == "audit")
    assert audit.data["decision"]["itemThresholds"] == {"mfa": 0.7}

    await flock.publish(CalTicket(text="policy"))
    await flock.run_until_idle()
    blackboard = await assembler.build_snapshot(GraphRequest(view_mode="blackboard"))
    (view,) = [n.data["decision"] for n in blackboard.nodes if "decision" in n.data]
    assert view["itemThresholds"] == {"mfa": 0.7}
