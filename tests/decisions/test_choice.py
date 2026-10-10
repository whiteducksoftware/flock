"""Choice types: options, question text and subscription handles."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flock.decisions import ANY_OPTION, UNSURE, Choice, ChoiceRef, Decision
from flock.registry import type_registry


class Route(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds"
    shipping = "Delivery, tracking, returns"
    tech = "Bugs, crashes, login problems"


def test_options_keep_declaration_order_and_descriptions():
    assert Route.__options__ == {
        "billing": "Charges, invoices, refunds",
        "shipping": "Delivery, tracking, returns",
        "tech": "Bugs, crashes, login problems",
    }


def test_docstring_is_the_question():
    assert Route.__question__ == "Which team should handle this support ticket?"


def test_option_attribute_is_a_subscription_handle():
    ref = Route.billing
    assert isinstance(ref, ChoiceRef)
    assert ref.choice is Route
    assert ref.option == "billing"
    assert repr(ref) == "Route.billing"


def test_reserved_handles_for_unsure_and_any():
    assert Route.UNSURE.option == UNSURE
    assert Route.ANY.option == ANY_OPTION
    assert repr(Route.UNSURE) == "Route.UNSURE"
    assert repr(Route.ANY) == "Route.ANY"


def test_handles_are_hashable_and_compare_by_value():
    assert Route.billing == ChoiceRef(Route, "billing")
    assert len({Route.billing, Route.billing, Route.tech}) == 2


def test_handle_matches_decisions_by_option():
    model = Decision.of(Route)
    billing = model(
        choice="billing",
        best_guess="billing",
        probabilities={"billing": 0.9, "shipping": 0.05, "tech": 0.05},
        model="fake",
    )
    unsure = model(
        choice=UNSURE,
        best_guess="tech",
        probabilities={"billing": 0.3, "shipping": 0.3, "tech": 0.4},
        model="fake",
    )

    assert Route.billing.matches(billing)
    assert not Route.tech.matches(billing)
    assert Route.UNSURE.matches(unsure)
    assert not Route.UNSURE.matches(billing)
    assert Route.ANY.matches(billing)
    assert Route.ANY.matches(unsure)


@pytest.mark.parametrize("reserved", ["UNSURE", "ANY"])
def test_reserved_option_names_are_rejected(reserved):
    with pytest.raises(TypeError, match=reserved):
        type("Bad", (Choice,), {reserved: "x", "other": "y"})


def test_choice_needs_at_least_two_options():
    with pytest.raises(TypeError, match="at least two options"):

        class Lonely(Choice):
            only = "the only option"


def test_choice_without_docstring_gets_a_generic_question():
    class Mood(Choice):
        happy = "Positive"
        sad = "Negative"

    assert Mood.__question__ == "Which Mood option applies?"


def test_decision_model_is_cached_and_registered_per_choice():
    model = Decision.of(Route)

    assert model is Decision.of(Route)
    assert issubclass(model, Decision)
    assert type_registry.resolve(type_registry.name_for(model)) is model
    assert type_registry.name_for(model) == f"Decision[{__name__}.Route]"


def test_decision_model_validates_options():
    model = Decision.of(Route)
    with pytest.raises(ValidationError):
        model(
            choice="marketing",
            best_guess="billing",
            probabilities={},
            model="fake",
        )
