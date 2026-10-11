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
    labels = {"t1": "billing", "t2": "billing", "t3": "tech", "t4": "tech"}

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
        "d1": {"mfa": "yes", "logs": "yes"},
        "d2": {"mfa": "no", "logs": "no"},
        "d3": {"mfa": "yes", "logs": "yes"},
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

    assert labels_from_reviews(decisions) == {"t1": "tech"}
    (suggestion,) = calibrate(decisions, labels_from_reviews(decisions), min_support=1)
    assert suggestion.labeled == 1


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
