"""Several questions per decider: one request, one decision per question."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, PrivateAttr

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.decisions import UNSURE, Choice, Decision, Scale, YesNo
from flock.decisions.providers import FakeDecider
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class SupportTicket(BaseModel):
    body: str


@flock_type
class Answer(BaseModel):
    by: str


class Team(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


class Urgent(YesNo):
    """Does the customer need an answer today?"""


class Anger(Scale):
    """How angry is the customer?"""

    calm = "Calm"
    annoyed = "Annoyed"
    angry = "Angry"
    furious = "Furious"


class Recorder(EngineComponent):
    _seen: list = PrivateAttr(default_factory=list)

    @property
    def seen(self) -> list:
        return self._seen

    async def evaluate(self, agent, ctx, inputs, output_group):
        self._seen.append((list(inputs.artifacts), ctx.decision))
        return EvalResult.from_object(Answer(by=agent.name), agent=agent)


@pytest.fixture
def flock() -> Flock:
    return Flock()


def listener(flock: Flock, name: str, handle) -> Recorder:
    engine = Recorder()
    flock.agent(name).consumes(handle).with_engines(engine).publishes(Answer)
    return engine


async def decisions_of(flock: Flock, question) -> list:
    name = type_registry.name_for(Decision.of(question))
    return [a for a in await flock.store.list() if a.type == name]


ANSWERS = {
    "Team": {"billing": 0.95, "tech": 0.05},
    "Urgent": {"yes": 0.9, "no": 0.1},
    "Anger": {"calm": 0.0, "annoyed": 0.1, "angry": 0.6, "furious": 0.3},
}
TICKET = SupportTicket(body="Charged twice AGAIN. Fix it today.")


async def test_one_request_publishes_one_decision_per_question(flock):
    decider = FakeDecider(ANSWERS)
    flock.agent("triage").consumes(SupportTicket).decides(
        Team, Urgent, Anger, model=decider
    )

    ticket = await flock.publish(TICKET)
    await flock.run_until_idle()

    assert len(decider.requests) == 1
    assert [q.name for q in decider.requests[0][1]] == ["Team", "Urgent", "Anger"]
    assert [q.kind for q in decider.requests[0][1]] == ["choice", "yesno", "scale"]
    (team,) = await decisions_of(flock, Team)
    (urgent,) = await decisions_of(flock, Urgent)
    (anger,) = await decisions_of(flock, Anger)
    assert team.payload["choice"] == "billing"
    assert urgent.payload["choice"] == "yes"
    assert urgent.payload["kind"] == "yesno"
    assert anger.payload["choice"] == "angry"
    assert anger.payload["score"] == pytest.approx(2.2)
    for decision in (team, urgent, anger):
        assert decision.payload["subject_ids"] == [str(ticket.id)]
        assert decision.produced_by == "triage"


async def test_each_question_routes_to_its_own_subscribers(flock):
    flock.agent("triage").consumes(SupportTicket).decides(
        Team, Urgent, Anger, model=FakeDecider(ANSWERS)
    )
    billing = listener(flock, "billing", Team.billing)
    pager = listener(flock, "pager", Urgent.yes)
    calm_down = listener(flock, "calm_down", Anger.angry.or_higher)
    furious_only = listener(flock, "furious_only", Anger.furious)

    ticket = await flock.publish(TICKET)
    await flock.run_until_idle()

    for engine in (billing, pager, calm_down):
        ((inputs, decision),) = engine.seen
        assert [a.id for a in inputs] == [ticket.id]
        assert decision is not None
    assert pager.seen[0][1].question == "Urgent"
    assert furious_only.seen == []


async def test_the_threshold_applies_to_every_question(flock):
    answers = {**ANSWERS, "Urgent": {"yes": 0.6, "no": 0.4}}
    flock.agent("triage").consumes(SupportTicket).decides(
        Team, Urgent, Anger, model=FakeDecider(answers), threshold=0.8
    )
    unsure_urgent = listener(flock, "unsure_urgent", Urgent.UNSURE)
    calm_down = listener(flock, "calm_down", Anger.angry.or_higher)

    await flock.publish(TICKET)
    await flock.run_until_idle()

    (team,) = await decisions_of(flock, Team)
    (urgent,) = await decisions_of(flock, Urgent)
    (anger,) = await decisions_of(flock, Anger)
    assert team.payload["choice"] == "billing"
    assert urgent.payload["choice"] == UNSURE
    assert urgent.payload["best_guess"] == "yes"
    # The most probable level is below the threshold, the weighted score is not
    assert anger.payload["choice"] == UNSURE
    assert len(unsure_urgent.seen) == 1
    assert len(calm_down.seen) == 1


async def test_a_refused_question_goes_to_unsure(flock):
    flock.agent("triage").consumes(SupportTicket).decides(
        Team, Urgent, model=FakeDecider(ANSWERS, refuse={"Urgent"})
    )
    unsure = listener(flock, "unsure", Urgent.UNSURE)
    pager = listener(flock, "pager", Urgent.yes)

    await flock.publish(TICKET)
    await flock.run_until_idle()

    (urgent,) = await decisions_of(flock, Urgent)
    assert urgent.payload["choice"] == UNSURE
    assert urgent.payload["refused"] is True
    assert urgent.payload["best_guess"] is None
    assert urgent.payload["probabilities"] == {}
    assert len(unsure.seen) == 1
    assert pager.seen == []


def test_decides_needs_at_least_one_question(flock):
    with pytest.raises(TypeError, match="at least one"):
        flock.agent("triage").consumes(SupportTicket).decides(model=FakeDecider({}))


def test_instructions_apply_to_a_single_question_only(flock):
    with pytest.raises(ValueError, match="docstring"):
        flock.agent("triage").consumes(SupportTicket).decides(
            Team, Urgent, model=FakeDecider(ANSWERS), instructions="Route it"
        )


def test_question_names_must_be_unique(flock):
    class Other:
        class Urgent(YesNo):
            """Is it urgent for the team?"""

    with pytest.raises(ValueError, match="Urgent"):
        flock.agent("triage").consumes(SupportTicket).decides(
            Urgent, Other.Urgent, model=FakeDecider(ANSWERS)
        )


@pytest.mark.parametrize("base", [Choice, YesNo, Scale])
def test_decides_rejects_the_base_classes(flock, base):
    with pytest.raises(TypeError, match="subclass"):
        flock.agent("triage").consumes(SupportTicket).decides(
            base, model=FakeDecider(ANSWERS)
        )
