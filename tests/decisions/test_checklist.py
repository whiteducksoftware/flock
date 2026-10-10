"""Checklists: many yes/no items about one artifact, published as one decision."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, PrivateAttr, ValidationError

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.decisions import UNSURE, Checklist, Choice, ChoiceRef, Decision, YesNo
from flock.decisions.providers import FakeDecider
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


class Controls(Checklist):
    """Does the document show that this control is implemented?"""

    mfa = "Multi-factor authentication is required for remote access"
    backup = "Backups are performed daily"
    restore_test = "Restores from backup are tested"


@flock_type
class Policy(BaseModel):
    text: str


@flock_type
class Note(BaseModel):
    by: str


class Recorder(EngineComponent):
    _seen: list = PrivateAttr(default_factory=list)

    @property
    def seen(self) -> list:
        return self._seen

    async def evaluate(self, agent, ctx, inputs, output_group):
        self._seen.append((list(inputs.artifacts), ctx.decision))
        return EvalResult.from_object(Note(by=agent.name), agent=agent)


# --- definition -----------------------------------------------------------


def test_checklist_items_and_question():
    assert Controls.__kind__ == "checklist"
    assert list(Controls.__options__) == ["mfa", "backup", "restore_test"]
    assert Controls.__question__ == (
        "Does the document show that this control is implemented?"
    )


def test_checklist_needs_at_least_one_item():
    with pytest.raises(TypeError, match="at least one item"):

        class Empty(Checklist):
            """Anything?"""


@pytest.mark.parametrize("name", ["passed", "failed"])
def test_outcome_names_are_reserved(name):
    with pytest.raises(TypeError, match="reserved"):
        type("Bad", (Checklist,), {name: "An item"})


def test_from_items_builds_a_checklist_in_the_callers_module():
    catalog = {"gov_01": "A policy exists", "gov_02": "The policy is reviewed"}
    Gov = Checklist.from_items("Gov", catalog, question="Is this control met?")

    assert issubclass(Gov, Checklist)
    assert Gov.__options__ == catalog
    assert Gov.__question__ == "Is this control met?"
    assert Gov.__module__ == __name__
    assert repr(Gov.gov_01) == "Gov.gov_01"


def test_from_items_accepts_ids_that_are_not_identifiers():
    Bsi = Checklist.from_items("Bsi", {"ORP.1.A1": "Responsibilities are defined"})

    assert getattr(Bsi, "ORP.1.A1").option == "ORP.1.A1"


@pytest.mark.parametrize("name", ["__kind__", "__options__", "_private", "from_items"])
def test_item_names_cannot_shadow_question_internals(name):
    with pytest.raises(TypeError, match="cannot declare"):
        Checklist.from_items("Shadow", {name: "An item"})


def test_option_names_cannot_shadow_choice_methods():
    with pytest.raises(TypeError, match="cannot declare"):
        Choice.from_options("Shadow", {"from_options": "A", "other": "B"})


def test_choice_from_options():
    Team = Choice.from_options(
        "Team", {"billing": "Charges", "tech": "Bugs"}, question="Which team?"
    )

    assert Team.__options__ == {"billing": "Charges", "tech": "Bugs"}
    assert Team.__question__ == "Which team?"
    assert repr(Team.billing) == "Team.billing"


# --- handles --------------------------------------------------------------


def test_outcome_and_item_handles():
    assert isinstance(Controls.passed, ChoiceRef)
    assert repr(Controls.passed) == "Controls.passed"
    assert repr(Controls.failed) == "Controls.failed"
    assert repr(Controls.mfa) == "Controls.mfa"
    assert repr(Controls.mfa.yes) == "Controls.mfa"
    assert repr(Controls.mfa.no) == "Controls.mfa.no"
    assert repr(Controls.mfa.UNSURE) == "Controls.mfa.UNSURE"


def test_item_answers_exist_only_on_checklist_items():
    class Urgent(YesNo):
        """Urgent?"""

    with pytest.raises(AttributeError):
        _ = Urgent.yes.no
    with pytest.raises(AttributeError):
        _ = Controls.passed.no
    with pytest.raises(AttributeError):
        _ = Controls.mfa.or_higher


def checklist_decision(choice: str, results: dict[str, str]):
    return Decision.of(Controls)(
        choice=choice,
        best_guess="failed" if "no" in results.values() else "passed",
        probabilities={"mfa": 0.9, "backup": 0.1, "restore_test": 0.5},
        results=results,
        model="fake",
    )


def test_handles_match_the_outcome_and_single_items():
    decision = checklist_decision(
        "failed", {"mfa": "yes", "backup": "no", "restore_test": UNSURE}
    )

    assert Controls.failed.matches(decision)
    assert not Controls.passed.matches(decision)
    assert Controls.mfa.matches(decision)
    assert not Controls.mfa.no.matches(decision)
    assert Controls.backup.no.matches(decision)
    assert Controls.restore_test.UNSURE.matches(decision)
    assert Controls.ANY.matches(decision)


def test_checklist_decision_model():
    model = Decision.of(Controls)
    decision = checklist_decision("passed", dict.fromkeys(Controls.__options__, "yes"))

    assert decision.kind == "checklist"
    with pytest.raises(ValidationError):
        model(choice="mfa", results={}, model="fake")
    with pytest.raises(ValidationError):
        model(choice="passed", results={"mfa": "maybe"}, model="fake")


# --- deciding -------------------------------------------------------------


@pytest.fixture
def flock() -> Flock:
    return Flock()


def listener(flock: Flock, name: str, handle) -> Recorder:
    engine = Recorder()
    flock.agent(name).consumes(handle).with_engines(engine).publishes(Note)
    return engine


async def decisions_of(flock: Flock, question):
    name = type_registry.name_for(Decision.of(question))
    return [a.payload for a in await flock.store.list() if a.type == name]


ANSWERS = {"Controls": {"mfa": 0.97, "backup": 0.95, "restore_test": 0.1}}


async def test_one_decision_per_artifact_with_every_item(flock):
    decider = FakeDecider(ANSWERS)
    flock.agent("audit").consumes(Policy).decides(Controls, model=decider)

    policy = await flock.publish(Policy(text="MFA everywhere, daily backups."))
    await flock.run_until_idle()

    (decision,) = await decisions_of(flock, Controls)
    assert decision["kind"] == "checklist"
    assert decision["choice"] == "failed"
    assert decision["best_guess"] == "failed"
    assert decision["results"] == {"mfa": "yes", "backup": "yes", "restore_test": "no"}
    assert decision["probabilities"] == {
        "mfa": 0.97,
        "backup": 0.95,
        "restore_test": 0.1,
    }
    assert decision["subject_ids"] == [str(policy.id)]
    # Every item is a yes/no question carrying the item text
    ((_state, questions),) = decider.requests
    assert [q.kind for q in questions] == ["yesno"] * 3
    assert questions[0].instructions == (
        "Does the document show that this control is implemented?\n"
        "Multi-factor authentication is required for remote access"
    )


async def test_large_checklists_are_split_into_requests(flock):
    decider = FakeDecider(ANSWERS)
    flock.agent("audit").consumes(Policy).decides(
        Controls, model=decider, questions_per_request=2
    )

    await flock.publish(Policy(text="..."))
    await flock.run_until_idle()

    assert [len(questions) for _state, questions in decider.requests] == [2, 1]
    (decision,) = await decisions_of(flock, Controls)
    assert set(decision["results"]) == set(Controls.__options__)


async def test_threshold_leaves_uncertain_items_unsure(flock):
    answers = {"Controls": {"mfa": 0.97, "backup": 0.6, "restore_test": 0.92}}
    flock.agent("audit").consumes(Policy).decides(
        Controls, model=FakeDecider(answers), threshold=0.9
    )

    await flock.publish(Policy(text="..."))
    await flock.run_until_idle()

    (decision,) = await decisions_of(flock, Controls)
    assert decision["results"] == {
        "mfa": "yes",
        "backup": UNSURE,
        "restore_test": "yes",
    }
    assert decision["choice"] == UNSURE
    assert decision["best_guess"] == "passed"


async def test_low_thresholds_keep_the_more_probable_answer(flock):
    """Below 0.5 the yes and no regions overlap; the more probable answer wins."""
    answers = {"Controls": {"mfa": 0.45, "backup": 0.55, "restore_test": 0.65}}
    flock.agent("audit").consumes(Policy).decides(
        Controls, model=FakeDecider(answers), threshold=0.4
    )

    await flock.publish(Policy(text="..."))
    await flock.run_until_idle()

    (decision,) = await decisions_of(flock, Controls)
    assert decision["results"] == {"mfa": "no", "backup": "yes", "restore_test": "yes"}


def test_item_questions_cannot_collide_with_other_questions(flock):
    """Checklist items go out as <Checklist>_<index>; a question of that name
    would overwrite one of their answers."""
    clash = type("Controls_0", (YesNo,), {"__doc__": "Is it urgent?"})
    with pytest.raises(ValueError, match="Controls_0"):
        flock.agent("audit").consumes(Policy).decides(
            Controls, clash, model=FakeDecider({})
        )


async def test_refused_items_are_unsure(flock):
    answers = {"Controls": {"mfa": 0.97, "backup": 0.95, "restore_test": 0.9}}
    decider = FakeDecider(answers, refuse={"Controls.restore_test"})
    flock.agent("audit").consumes(Policy).decides(Controls, model=decider)

    await flock.publish(Policy(text="..."))
    await flock.run_until_idle()

    (decision,) = await decisions_of(flock, Controls)
    assert decision["results"]["restore_test"] == UNSURE
    assert decision["refused_items"] == ["restore_test"]
    assert "restore_test" not in decision["probabilities"]
    assert decision["choice"] == UNSURE


async def test_outcome_and_item_subscribers_receive_the_artifact(flock):
    flock.agent("audit").consumes(Policy).decides(Controls, model=FakeDecider(ANSWERS))
    remediation = listener(flock, "remediation", Controls.failed)
    backup_owner = listener(flock, "backup_owner", Controls.restore_test.no)
    certified = listener(flock, "certified", Controls.passed)

    policy = await flock.publish(Policy(text="..."))
    await flock.run_until_idle()

    for engine in (remediation, backup_owner):
        ((inputs, decision),) = engine.seen
        assert [a.id for a in inputs] == [policy.id]
        assert decision.results["restore_test"] == "no"
    assert certified.seen == []


async def test_checklists_mix_with_other_questions(flock):
    class Kind(Choice):
        """What kind of document is this?"""

        policy = "A policy"
        report = "An audit report"

    answers = {**ANSWERS, "Kind": {"policy": 0.9, "report": 0.1}}
    decider = FakeDecider(answers)
    flock.agent("audit").consumes(Policy).decides(Kind, Controls, model=decider)

    await flock.publish(Policy(text="..."))
    await flock.run_until_idle()

    assert len(decider.requests) == 1
    assert len(await decisions_of(flock, Kind)) == 1
    assert len(await decisions_of(flock, Controls)) == 1


def test_questions_per_request_must_be_positive(flock):
    with pytest.raises(ValueError, match="questions_per_request"):
        flock.agent("audit").consumes(Policy).decides(
            Controls, model=FakeDecider(ANSWERS), questions_per_request=0
        )
