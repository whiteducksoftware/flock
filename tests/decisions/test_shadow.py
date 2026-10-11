"""Shadow mode: a second model decides on every input, recorded but not routed (#474)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from PIL import Image as PILImage
from pydantic import BaseModel

from flock.components.agent import AgentComponent, EngineComponent
from flock.core import Flock
from flock.core.image import Image
from flock.decisions import UNSURE, Checklist, Choice, Decision
from flock.decisions.providers import FakeDecider
from flock.decisions.tournament import Tournament
from flock.models.system_artifacts import WorkflowError
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class ShadowTicket(BaseModel):
    text: str


@flock_type
class ShadowPhoto(BaseModel):
    picture: Image


@flock_type
class ShadowHandled(BaseModel):
    team: str


class ShadowRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


ShadowControls = Checklist.from_items(
    "ShadowControls",
    {"mfa": "MFA is enforced", "backup": "Backups are tested"},
    question="Does the document show that this control is implemented?",
)


class _Handled(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        return EvalResult.from_object(ShadowHandled(team=agent.name), agent=agent)


async def _decisions(flock: Flock, question) -> list:
    name = type_registry.name_for(Decision.of(question))
    return [a.payload for a in await flock.store.list() if a.type == name]


def _route(p_billing: float, label: str, **kwargs) -> FakeDecider:
    return FakeDecider(
        {"billing": p_billing, "tech": 1 - p_billing}, label=label, **kwargs
    )


async def _decide(question, artifact=None, **kwargs) -> tuple[Flock, dict]:
    flock = Flock()
    flock.agent("triage").consumes(type(artifact or ShadowTicket(text=""))).decides(
        question, **kwargs
    )
    await flock.publish(artifact or ShadowTicket(text="charged twice"))
    await flock.run_until_idle()
    (decision,) = await _decisions(flock, question)
    return flock, decision


async def test_the_shadow_answer_is_recorded_next_to_the_decision():
    _, decision = await _decide(
        ShadowRoute,
        model=_route(0.95, "live"),
        shadow=_route(0.3, "candidate"),
        threshold=0.6,
    )

    assert (decision["choice"], decision["model"]) == ("billing", "live")
    shadow = decision["shadow"]
    assert shadow["model"] == "candidate"
    assert shadow["choice"] == "tech"  # firm at 0.7 under the same threshold
    assert shadow["probabilities"] == {"billing": 0.3, "tech": pytest.approx(0.7)}
    assert shadow["refused"] is False


async def test_the_shadow_applies_the_same_threshold():
    _, decision = await _decide(
        ShadowRoute,
        model=_route(0.95, "live"),
        shadow=_route(0.6, "candidate"),
        threshold=0.9,
    )

    assert decision["shadow"]["choice"] == UNSURE
    assert decision["shadow"]["best_guess"] == "billing"


async def test_shadow_decisions_do_not_route():
    flock = Flock()
    flock.agent("triage").consumes(ShadowTicket).decides(
        ShadowRoute, model=_route(0.95, "live"), shadow=_route(0.05, "candidate")
    )
    flock.agent("tech").consumes(ShadowRoute.tech).with_engines(_Handled()).publishes(
        ShadowHandled
    )

    await flock.publish(ShadowTicket(text="charged twice"))
    await flock.run_until_idle()

    handled = type_registry.name_for(ShadowHandled)
    assert [a for a in await flock.store.list() if a.type == handled] == []


async def test_a_failing_shadow_does_not_fail_the_decision():
    broken = FakeDecider({"SomethingElse": {"a": 1.0}}, label="candidate")

    _, decision = await _decide(ShadowRoute, model=_route(0.95, "live"), shadow=broken)

    assert decision["choice"] == "billing"
    assert decision["shadow"]["model"] == "candidate"
    assert "no answer" in decision["shadow"]["error"]


async def test_a_failing_decision_still_fails_with_a_shadow():
    broken = FakeDecider({"SomethingElse": {"a": 1.0}}, label="live")
    flock = Flock()
    flock.agent("triage").consumes(ShadowTicket).decides(
        ShadowRoute, model=broken, shadow=_route(0.95, "candidate")
    )

    await flock.publish(ShadowTicket(text="charged twice"))
    await flock.run_until_idle()

    assert await _decisions(flock, ShadowRoute) == []
    errors = [
        a
        for a in await flock.store.list()
        if a.type == type_registry.name_for(WorkflowError)
    ]
    assert "no answer" in errors[0].payload["error_message"]


class _SlowShadow(FakeDecider):
    """Never answers; unwinding its request takes a few loop steps."""

    def __init__(self, events: list[str]):
        super().__init__({"billing": 0.5, "tech": 0.5}, label="candidate")
        self.events = events

    async def decide_many(self, state, questions, images=()):
        try:
            await asyncio.Event().wait()
        finally:
            for _ in range(3):
                await asyncio.sleep(0)
            self.events.append("shadow stopped")


class _LateFailure(FakeDecider):
    """Fails after the shadow has started."""

    async def decide_many(self, state, questions, images=()):
        await asyncio.sleep(0)
        return await super().decide_many(state, questions, images)


class _ErrorRecorder(AgentComponent):
    events: Any  # the test's list itself, not a validated copy

    async def on_error(self, agent, ctx, error):
        self.events.append("decision failed")


async def test_a_failing_decision_stops_its_shadow_before_it_fails():
    events: list[str] = []
    broken = _LateFailure({"SomethingElse": {"a": 1.0}}, label="live")
    flock = Flock()
    flock.agent("triage").consumes(ShadowTicket).decides(
        ShadowRoute, model=broken, shadow=_SlowShadow(events)
    ).with_utilities(_ErrorRecorder(events=events))

    await flock.publish(ShadowTicket(text="charged twice"))
    await flock.run_until_idle()

    assert events == ["shadow stopped", "decision failed"]


async def test_a_text_only_shadow_records_an_error_for_images():
    picture = Image.from_pil(PILImage.new("RGB", (8, 8), "red"))
    text_only = _route(0.9, "candidate", supports_images=False)

    _, decision = await _decide(
        ShadowRoute,
        ShadowPhoto(picture=picture),
        model=_route(0.95, "live"),
        shadow=text_only,
    )

    assert decision["choice"] == "billing"
    assert "does not accept images" in decision["shadow"]["error"]


async def test_a_checklist_shadow_records_its_outcome_and_results():
    _, decision = await _decide(
        ShadowControls,
        model=FakeDecider(
            {"ShadowControls": {"mfa": 0.97, "backup": 0.95}}, label="live"
        ),
        shadow=FakeDecider(
            {"ShadowControls": {"mfa": 0.96, "backup": 0.02}}, label="candidate"
        ),
        threshold=0.9,
    )

    assert decision["choice"] == "passed"
    assert decision["shadow"]["model"] == "candidate"
    assert decision["shadow"]["choice"] == "failed"
    assert decision["shadow"]["results"] == {"mfa": "yes", "backup": "no"}


async def test_the_shadow_asks_every_question_once_per_input():
    shadow = _route(0.3, "candidate")

    await _decide(ShadowRoute, model=_route(0.95, "live"), shadow=shadow)

    assert len(shadow.requests) == 1


async def test_a_decision_without_shadow_has_none():
    _, decision = await _decide(ShadowRoute, model=_route(0.95, "live"))

    assert decision["shadow"] is None


def test_shadow_and_tournaments_cannot_be_combined():
    with pytest.raises(ValueError, match="shadow="):
        Flock().agent("x").consumes(ShadowTicket).decides(
            ShadowRoute,
            model=_route(0.9, "a"),
            shadow=_route(0.9, "b"),
            tournament=Tournament(group_size=2, keep=1),
        )
