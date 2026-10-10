"""YesNo and Scale questions: options, handles and decision models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flock.decisions import UNSURE, ChoiceRef, Decision, Scale, YesNo


class Urgent(YesNo):
    """Does the customer need an answer today?"""


class Refund(YesNo):
    """Does the customer ask for a refund?"""

    yes = "They want money back"
    no = "No refund request"


class Anger(Scale):
    """How angry is the customer?"""

    calm = "Calm"
    annoyed = "Annoyed"
    angry = "Angry"
    furious = "Furious"


def test_yes_no_has_fixed_options_with_optional_descriptions():
    assert Urgent.__kind__ == "yesno"
    assert Urgent.__options__ == {"yes": "", "no": ""}
    assert Refund.__options__ == {
        "yes": "They want money back",
        "no": "No refund request",
    }
    assert Urgent.__question__ == "Does the customer need an answer today?"


def test_yes_no_handles():
    assert isinstance(Urgent.yes, ChoiceRef)
    assert repr(Urgent.yes) == "Urgent.yes"
    assert repr(Urgent.no) == "Urgent.no"
    assert Urgent.UNSURE.option == UNSURE


def test_yes_no_rejects_other_attributes():
    with pytest.raises(TypeError, match="yes"):

        class Bad(YesNo):
            maybe = "Not a yes/no option"


def test_scale_keeps_level_order():
    assert Anger.__kind__ == "scale"
    assert list(Anger.__options__) == ["calm", "annoyed", "angry", "furious"]


@pytest.mark.parametrize("count", [1, 11])
def test_scale_needs_two_to_ten_levels(count):
    namespace = {f"l{i}": f"Level {i}" for i in range(count)}
    with pytest.raises(TypeError, match="2 and 10 levels"):
        type("Bad", (Scale,), namespace)


def scale_decision(choice: str, score: float):
    return Decision.of(Anger)(
        choice=choice,
        best_guess="angry" if choice == UNSURE else choice,
        probabilities={"calm": 0.0, "annoyed": 0.1, "angry": 0.6, "furious": 0.3},
        score=score,
        model="fake",
    )


def test_scale_level_handles_match_the_most_probable_level():
    decision = scale_decision("angry", 2.2)

    assert Anger.angry.matches(decision)
    assert not Anger.furious.matches(decision)


def test_or_higher_and_or_lower_compare_the_weighted_score():
    decision = scale_decision(UNSURE, 2.2)

    assert Anger.angry.or_higher.matches(decision)
    assert Anger.annoyed.or_higher.matches(decision)
    assert not Anger.furious.or_higher.matches(decision)
    assert Anger.furious.or_lower.matches(decision)
    assert not Anger.angry.or_lower.matches(decision)
    assert repr(Anger.angry.or_higher) == "Anger.angry.or_higher"
    assert repr(Anger.annoyed.or_lower) == "Anger.annoyed.or_lower"


def test_or_higher_exists_only_on_scale_levels():
    with pytest.raises(AttributeError):
        _ = Urgent.yes.or_higher


def test_decision_models_per_kind():
    yes_no = Decision.of(Urgent)(
        choice="yes", best_guess="yes", probabilities={"yes": 0.9, "no": 0.1}, model="m"
    )
    assert yes_no.kind == "yesno"
    assert (
        Decision.of(Anger)(
            choice="angry", best_guess="angry", probabilities={}, score=2.0, model="m"
        ).kind
        == "scale"
    )
    with pytest.raises(ValidationError):
        Decision.of(Urgent)(choice="maybe", best_guess="yes", model="m")


def test_refused_decisions_have_no_best_guess():
    refused = Decision.of(Urgent)(
        choice=UNSURE, best_guess=None, refused=True, model="openai/gpt-6-luna"
    )

    assert refused.refused
    assert refused.probabilities == {}


def test_question_types_are_exported_from_flock():
    import flock

    assert flock.YesNo is YesNo
    assert flock.Scale is Scale
