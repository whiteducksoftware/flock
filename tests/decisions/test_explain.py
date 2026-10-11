"""Explain on demand: an LLM explains decisions it is subscribed to (#474)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.core.visibility import PrivateVisibility
from flock.decisions import UNSURE, Checklist, Choice, Decision, FakeDecider, YesNo
from flock.decisions.explain import DecisionsToExplain, Explanation
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
        type_registry.name_for(DecisionsToExplain),
    ]
    (case,) = DecisionsToExplain(**inputs.artifacts[1].payload).decisions
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
    (case,) = DecisionsToExplain(**inputs.artifacts[1].payload).decisions
    assert case.results == {"mfa": "yes", "backup": UNSURE}
    assert case.options["backup"] == "Backups are tested"


async def test_a_restricted_decision_shows_only_its_candidates(llm):
    flock = Flock("openai/gpt-4.1")
    flock.agent("triage").consumes(ExplainTicket).decides(
        ExplainControls,
        model=FakeDecider({"ExplainControls": {"backup": 0.6}}),
        threshold=0.9,
        options=lambda ctx: ["backup"],
    )
    flock.agent("explainer").consumes(ExplainControls.UNSURE).explains()

    await flock.publish(ExplainTicket(text="policy"))
    await flock.run_until_idle()

    (inputs,) = llm
    (case,) = DecisionsToExplain(**inputs.artifacts[1].payload).decisions
    assert case.options == {"backup": "Backups are tested"}


async def test_refused_checklist_items_are_named(llm):
    flock = Flock("openai/gpt-4.1")
    flock.agent("audit").consumes(ExplainTicket).decides(
        ExplainControls,
        model=FakeDecider(
            {"ExplainControls": {"mfa": 0.97, "backup": 0.5}},
            refuse={"ExplainControls.backup"},
        ),
        threshold=0.9,
    )
    flock.agent("explainer").consumes(ExplainControls.UNSURE).explains()

    await flock.publish(ExplainTicket(text="policy"))
    await flock.run_until_idle()

    (inputs,) = llm
    (case,) = DecisionsToExplain(**inputs.artifacts[1].payload).decisions
    assert (case.refused, case.refused_items) == (False, ["backup"])


async def test_an_execution_without_a_decision_is_not_explained(llm):
    from flock.core.artifacts import Artifact
    from flock.decisions.explain import ExplainEngine
    from flock.utils.runtime import Context, EvalInputs

    agent = Flock("openai/gpt-4.1").agent("explainer").agent
    ticket = Artifact(
        type=type_registry.name_for(ExplainTicket),
        payload={"text": "charged twice"},
        produced_by="external",
    )

    # e.g. a timer run: no decision in the context
    result = await ExplainEngine().evaluate(
        agent, Context(task_id="t"), EvalInputs(artifacts=[ticket]), None
    )

    assert result.artifacts == []
    assert llm == []


def test_explains_rejects_subscriptions_without_decisions():
    with pytest.raises(ValueError, match="explains"):
        Flock("openai/gpt-4.1").agent("x").consumes(ExplainRoute.UNSURE).consumes(
            ExplainTicket
        ).explains()


@flock_type
class ExplainNote(BaseModel):
    text: str


def _mixed_flock(**explains) -> Flock:
    """A decision about a private ticket and a public note."""
    flock = Flock("openai/gpt-4.1")
    flock.agent("triage").consumes(ExplainTicket, ExplainNote).decides(
        ExplainRoute,
        model=FakeDecider({"billing": 0.55, "tech": 0.45}),
        threshold=0.8,
        visibility=PrivateVisibility(agents={"explainer"}),
    )
    flock.agent("explainer").consumes(ExplainRoute.UNSURE).explains(**explains)
    return flock


async def _publish_mixed(flock: Flock) -> None:
    await flock.publish(
        ExplainTicket(text="charged twice"),
        visibility=PrivateVisibility(agents={"triage", "explainer"}),
    )
    await flock.publish(ExplainNote(text="customer since 2019"))
    await flock.run_until_idle()


async def test_mixed_subject_visibilities_need_an_explicit_readership(llm):
    flock = _mixed_flock()

    await _publish_mixed(flock)

    assert llm == []  # refused before the LLM is called
    errors = [a for a in await flock.store.list() if "WorkflowError" in a.type]
    assert ".explains()" in errors[0].payload["error_message"]


async def test_explains_visibility_sets_the_readership(llm):
    flock = _mixed_flock(visibility=PrivateVisibility(agents={"auditor"}))

    await _publish_mixed(flock)

    (explanation,) = await _artifacts(flock, Explanation)
    assert explanation.visibility.agents == {"auditor"}


class ExplainUrgent(YesNo):
    """Does the customer need an answer today?"""


async def test_every_decision_of_an_and_handle_reaches_the_llm(llm):
    flock = Flock("openai/gpt-4.1")
    flock.agent("triage").consumes(ExplainTicket).decides(
        ExplainRoute,
        ExplainUrgent,
        model=FakeDecider({
            "ExplainRoute": {"billing": 0.55, "tech": 0.45},
            "ExplainUrgent": {"yes": 0.6, "no": 0.4},
        }),
        threshold=0.8,
    )
    flock.agent("explainer").consumes(
        ExplainRoute.UNSURE, ExplainUrgent.UNSURE
    ).explains()

    await flock.publish(ExplainTicket(text="charged twice, need it fixed today?"))
    await flock.run_until_idle()

    (inputs,) = llm
    cases = DecisionsToExplain(**inputs.artifacts[1].payload).decisions
    # The decisions arrive in any order
    assert sorted(case.question for case in cases) == [
        "Does the customer need an answer today?",
        "Which team should handle this ticket?",
    ]
    (explanation,) = await _artifacts(flock, Explanation)
    assert sorted(explanation.payload["questions"]) == ["ExplainRoute", "ExplainUrgent"]


def test_a_batched_subscription_cannot_be_added_to_an_explainer_later():
    from flock.core.subscription import BatchSpec

    builder = (
        Flock("openai/gpt-4.1").agent("x").consumes(ExplainRoute.UNSURE).explains()
    )

    with pytest.raises(ValueError, match="batch"):
        builder.consumes(ExplainRoute.billing, batch=BatchSpec(size=2))


async def test_the_question_text_actually_asked_reaches_the_explainer(llm):
    flock = Flock("openai/gpt-4.1")
    flock.agent("triage").consumes(ExplainTicket).decides(
        ExplainRoute,
        model=FakeDecider({"billing": 0.55, "tech": 0.45}),
        threshold=0.8,
        instructions="Which department owns this ticket?",
    )
    flock.agent("explainer").consumes(ExplainRoute.UNSURE).explains()

    await flock.publish(ExplainTicket(text="charged twice"))
    await flock.run_until_idle()

    (inputs,) = llm
    (case,) = DecisionsToExplain(**inputs.artifacts[1].payload).decisions
    assert case.question == "Which department owns this ticket?"


def test_a_plain_decision_subscription_cannot_be_added_to_an_explainer_later():
    builder = (
        Flock("openai/gpt-4.1").agent("x").consumes(ExplainRoute.UNSURE).explains()
    )

    with pytest.raises(ValueError, match="handle"):
        builder.consumes(Decision.of(ExplainUrgent))  # another question's decisions


def test_another_handle_can_be_added_to_an_explainer_later():
    builder = (
        Flock("openai/gpt-4.1").agent("x").consumes(ExplainRoute.UNSURE).explains()
    )

    builder.consumes(ExplainUrgent.UNSURE)

    assert len(builder.agent.subscriptions) == 2


def test_explains_rejects_batched_subscriptions():
    from flock.core.subscription import BatchSpec

    with pytest.raises(ValueError, match="batch"):
        Flock("openai/gpt-4.1").agent("x").consumes(
            ExplainRoute.UNSURE, batch=BatchSpec(size=2)
        ).explains()


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
