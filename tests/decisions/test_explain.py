"""Explain on demand: an LLM explains decisions it is subscribed to (#474)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.core.visibility import PrivateVisibility
from flock.decisions import UNSURE, Checklist, Choice, Decision, FakeDecider
from flock.decisions.explain import DecisionToExplain, Explanation
from flock.engines.dspy_engine import DSPyEngine
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class ExplainTicket(BaseModel):
    text: str


class ExplainRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


ExplainControls = Checklist.from_items(
    "ExplainControls",
    {"mfa": "MFA is enforced", "backup": "Backups are tested"},
    question="Does the document show that this control is implemented?",
)


@pytest.fixture
def llm(monkeypatch):
    """Replaces the LLM call; records the inputs the explainer sent."""
    seen: list = []

    async def fake(self, agent, ctx, inputs, *, batched, output_group=None):
        seen.append(inputs)
        explanation = Explanation(
            explanation="Charged twice after a crash: billing or tech.",
            missing="Whether the crash caused the second charge.",
            decision_ids=["made-up"],
        )
        return EvalResult.from_object(explanation, agent=agent)

    monkeypatch.setattr(DSPyEngine, "_evaluate_internal", fake)
    return seen


def _flock(p_billing: float) -> Flock:
    flock = Flock("openai/gpt-4.1")
    flock.agent("triage").consumes(ExplainTicket).decides(
        ExplainRoute,
        model=FakeDecider({"billing": p_billing, "tech": 1 - p_billing}, label="fast"),
        threshold=0.8,
    )
    flock.agent("explainer").consumes(ExplainRoute.UNSURE).explains(
        model="openai/gpt-4.1"
    )
    return flock


async def _artifacts(flock: Flock, model: type[BaseModel]) -> list:
    name = type_registry.name_for(model)
    return [a for a in await flock.store.list() if a.type == name]


async def test_an_unsure_decision_is_explained_and_linked(llm):
    flock = _flock(0.55)

    await flock.publish(ExplainTicket(text="charged twice after the app crashed"))
    await flock.run_until_idle()

    (decision,) = await _artifacts(flock, Decision.of(ExplainRoute))
    (ticket,) = await _artifacts(flock, ExplainTicket)
    (explanation,) = await _artifacts(flock, Explanation)
    payload = explanation.payload
    assert payload["explanation"].startswith("Charged twice")
    assert payload["missing"].startswith("Whether the crash")
    # Link fields come from the decision, not from the LLM
    assert payload["decision_ids"] == [str(decision.id)]
    assert payload["subject_ids"] == [str(ticket.id)]
    assert payload["questions"] == ["ExplainRoute"]
    assert payload["model"] == "openai/gpt-4.1"


async def test_the_llm_sees_the_subject_and_the_decision(llm):
    flock = _flock(0.55)

    await flock.publish(ExplainTicket(text="charged twice after the app crashed"))
    await flock.run_until_idle()

    (inputs,) = llm
    types = [a.type for a in inputs.artifacts]
    assert types == [
        type_registry.name_for(ExplainTicket),
        type_registry.name_for(DecisionToExplain),
    ]
    case = DecisionToExplain(**inputs.artifacts[1].payload)
    assert case.question == "Which team should handle this ticket?"
    assert case.options == {
        "billing": "Charges, invoices, refunds",
        "tech": "Bugs, crashes, login problems",
    }
    assert (case.choice, case.best_guess, case.threshold) == (UNSURE, "billing", 0.8)
    assert case.probabilities["billing"] == pytest.approx(0.55)


async def test_firm_decisions_are_not_explained(llm):
    flock = _flock(0.95)

    await flock.publish(ExplainTicket(text="refund please"))
    await flock.run_until_idle()

    assert llm == []
    assert await _artifacts(flock, Explanation) == []


async def test_an_explanation_keeps_the_subjects_visibility(llm):
    flock = _flock(0.55)

    await flock.publish(
        ExplainTicket(text="charged twice"),
        visibility=PrivateVisibility(agents={"triage", "explainer"}),
    )
    await flock.run_until_idle()

    (explanation,) = await _artifacts(flock, Explanation)
    assert explanation.visibility.kind == "Private"
    assert explanation.visibility.agents == {"triage", "explainer"}


async def test_a_checklist_case_carries_the_item_results(llm):
    flock = Flock("openai/gpt-4.1")
    flock.agent("audit").consumes(ExplainTicket).decides(
        ExplainControls,
        model=FakeDecider({"ExplainControls": {"mfa": 0.97, "backup": 0.6}}),
        threshold=0.9,
    )
    flock.agent("explainer").consumes(ExplainControls.UNSURE).explains()

    await flock.publish(ExplainTicket(text="policy"))
    await flock.run_until_idle()

    (inputs,) = llm
    case = DecisionToExplain(**inputs.artifacts[1].payload)
    assert case.results == {"mfa": "yes", "backup": UNSURE}
    assert case.options["backup"] == "Backups are tested"


def test_explains_needs_a_decision_subscription():
    with pytest.raises(ValueError, match="explains"):
        Flock("openai/gpt-4.1").agent("x").consumes(ExplainTicket).explains()


def test_explains_cannot_be_combined_with_publishes():
    with pytest.raises(ValueError, match="publishes"):
        Flock("openai/gpt-4.1").agent("x").consumes(ExplainRoute.UNSURE).publishes(
            ExplainTicket
        ).explains()


def test_an_explainer_cannot_publish_anything_else_later():
    builder = (
        Flock("openai/gpt-4.1").agent("x").consumes(ExplainRoute.UNSURE).explains()
    )

    with pytest.raises(ValueError, match="explanations"):
        builder.publishes(ExplainTicket)


def test_an_explainer_cannot_take_other_engines_later():
    builder = (
        Flock("openai/gpt-4.1").agent("x").consumes(ExplainRoute.UNSURE).explains()
    )

    with pytest.raises(ValueError, match="explains"):
        builder.with_engines(DSPyEngine())
