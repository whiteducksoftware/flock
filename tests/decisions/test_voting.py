"""Ensembles: several decision models answer, a vote decides (#474)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.decisions import UNSURE, Checklist, Choice, Decision, YesNo
from flock.decisions.providers import FakeDecider
from flock.registry import flock_type, type_registry


@flock_type
class VoteTicket(BaseModel):
    text: str


class VoteRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"
    shipping = "Delivery, tracking, returns"


class VoteUrgent(YesNo):
    """Does the customer need an answer today?"""


VoteControls = Checklist.from_items(
    "VoteControls",
    {"mfa": "MFA is enforced", "backup": "Backups are tested"},
    question="Does the document show that this control is implemented?",
)


async def _decisions(flock: Flock, question) -> list:
    name = type_registry.name_for(Decision.of(question))
    return [a.payload for a in await flock.store.list() if a.type == name]


async def _decide(question, models, **kwargs) -> dict:
    flock = Flock()
    flock.agent("triage").consumes(VoteTicket).decides(
        question, models=models, **kwargs
    )
    await flock.publish(VoteTicket(text="charged twice"))
    await flock.run_until_idle()
    (decision,) = await _decisions(flock, question)
    return decision


def _route(billing: float, tech: float, label: str, **kwargs) -> FakeDecider:
    return FakeDecider(
        {"billing": billing, "tech": tech, "shipping": round(1 - billing - tech, 6)},
        label=label,
        **kwargs,
    )


async def test_a_majority_of_firm_votes_decides():
    models = [_route(0.95, 0.05, "a"), _route(0.92, 0.08, "b"), _route(0.1, 0.9, "c")]

    decision = await _decide(VoteRoute, models, vote="majority", threshold=0.9)

    assert decision["choice"] == "billing"
    assert [vote["model"] for vote in decision["votes"]] == ["a", "b", "c"]
    assert [vote["choice"] for vote in decision["votes"]] == [
        "billing",
        "billing",
        "tech",
    ]
    # The decision's probabilities are the mean over the models
    assert decision["probabilities"]["billing"] == pytest.approx(
        (0.95 + 0.92 + 0.1) / 3
    )
    assert decision["model"] == "a + b + c"


async def test_majority_is_the_default_vote():
    models = [_route(0.95, 0.05, "a"), _route(0.92, 0.08, "b"), _route(0.1, 0.9, "c")]

    decision = await _decide(VoteRoute, models, threshold=0.9)

    assert decision["choice"] == "billing"


async def test_without_a_majority_the_decision_is_unsure():
    # One firm vote each for billing and tech, one model below the threshold
    models = [_route(0.95, 0.05, "a"), _route(0.05, 0.95, "b"), _route(0.6, 0.3, "c")]

    decision = await _decide(VoteRoute, models, vote="majority", threshold=0.9)

    assert decision["choice"] == UNSURE
    assert decision["best_guess"] == "billing"  # the most probable option on average


async def test_unanimous_needs_every_model():
    models = [_route(0.95, 0.05, "a"), _route(0.93, 0.07, "b"), _route(0.7, 0.3, "c")]

    unanimous = await _decide(VoteRoute, models, vote="unanimous", threshold=0.9)
    majority = await _decide(VoteRoute, models, vote="majority", threshold=0.9)

    assert unanimous["choice"] == UNSURE
    assert majority["choice"] == "billing"


async def test_mean_applies_the_threshold_to_the_average():
    models = [_route(0.99, 0.01, "a"), _route(0.85, 0.15, "b")]

    firm = await _decide(VoteRoute, models, vote="mean", threshold=0.9)
    unsure = await _decide(VoteRoute, models, vote="mean", threshold=0.95)

    assert firm["choice"] == "billing"
    assert firm["probabilities"]["billing"] == pytest.approx(0.92)
    assert unsure["choice"] == UNSURE


async def test_a_refusal_is_no_vote():
    models = [
        _route(0.95, 0.05, "a"),
        _route(0.5, 0.5, "b", refuse={"VoteRoute"}),
        _route(0.94, 0.06, "c"),
    ]

    decision = await _decide(VoteRoute, models, threshold=0.9)

    assert decision["choice"] == "billing"
    assert decision["votes"][1]["refused"] is True
    # The mean leaves out the refusal
    assert decision["probabilities"]["billing"] == pytest.approx((0.95 + 0.94) / 2)


async def test_every_model_refusing_is_a_refusal():
    models = [
        _route(0.5, 0.5, "a", refuse={"VoteRoute"}),
        _route(0.5, 0.5, "b", refuse={"VoteRoute"}),
    ]

    decision = await _decide(VoteRoute, models, threshold=0.9)

    assert (decision["choice"], decision["refused"]) == (UNSURE, True)


async def test_yes_no_questions_vote_too():
    models = [
        FakeDecider({"yes": 0.97, "no": 0.03}, label="a"),
        FakeDecider({"yes": 0.2, "no": 0.8}, label="b"),
        FakeDecider({"yes": 0.95, "no": 0.05}, label="c"),
    ]

    decision = await _decide(VoteUrgent, models, threshold=0.9)

    assert decision["choice"] == "yes"


async def test_checklist_items_are_voted_one_by_one():
    models = [
        FakeDecider({"VoteControls": {"mfa": 0.97, "backup": 0.95}}, label="a"),
        FakeDecider({"VoteControls": {"mfa": 0.96, "backup": 0.02}}, label="b"),
        FakeDecider({"VoteControls": {"mfa": 0.1, "backup": 0.6}}, label="c"),
    ]

    decision = await _decide(VoteControls, models, threshold=0.9)

    # mfa: yes, yes, no -> yes; backup: yes, no, unsure -> no majority
    assert decision["results"] == {"mfa": "yes", "backup": UNSURE}
    assert decision["choice"] == UNSURE
    assert decision["votes"] == [
        {"model": "a", "results": {"mfa": "yes", "backup": "yes"}},
        {"model": "b", "results": {"mfa": "yes", "backup": "no"}},
        {"model": "c", "results": {"mfa": "no", "backup": UNSURE}},
    ]


async def test_every_model_answers_every_question_once():
    models = [_route(0.95, 0.05, "a"), _route(0.92, 0.08, "b")]
    flock = Flock()
    flock.agent("triage").consumes(VoteTicket).decides(VoteRoute, models=models)

    await flock.publish(VoteTicket(text="x"))
    await flock.run_until_idle()

    assert [len(model.calls) for model in models] == [1, 1]


def test_models_and_model_cannot_be_combined():
    with pytest.raises(ValueError, match="models="):
        Flock().agent("x").consumes(VoteTicket).decides(
            VoteRoute, model=_route(0.9, 0.1, "a"), models=[_route(0.9, 0.1, "b")]
        )


def test_an_ensemble_needs_two_models():
    with pytest.raises(ValueError, match="at least two"):
        Flock().agent("x").consumes(VoteTicket).decides(
            VoteRoute, models=[_route(0.9, 0.1, "a")]
        )


def test_a_bare_model_string_is_not_an_ensemble():
    with pytest.raises(ValueError, match="at least two"):
        Flock().agent("x").consumes(VoteTicket).decides(
            VoteRoute, models="azure/decision-1"
        )


def test_unknown_votes_are_rejected():
    with pytest.raises(ValueError, match="vote="):
        Flock().agent("x").consumes(VoteTicket).decides(
            VoteRoute,
            models=[_route(0.9, 0.1, "a"), _route(0.9, 0.1, "b")],
            vote="plurality",
        )


def test_vote_without_models_is_rejected():
    with pytest.raises(ValueError, match="vote="):
        Flock().agent("x").consumes(VoteTicket).decides(
            VoteRoute, model=_route(0.9, 0.1, "a"), vote="mean"
        )


def test_ensembles_and_escalation_cannot_be_combined_yet():
    with pytest.raises(ValueError, match="escalate="):
        Flock().agent("x").consumes(VoteTicket).decides(
            VoteRoute,
            models=[_route(0.9, 0.1, "a"), _route(0.9, 0.1, "b")],
            escalate=[_route(0.9, 0.1, "c")],
        )
