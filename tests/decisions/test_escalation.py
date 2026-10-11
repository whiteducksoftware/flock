"""Escalation cascades: an unsure decision is asked again one tier up (#474)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PIL import Image as PILImage
from pydantic import BaseModel

from flock.core import Flock
from flock.core.image import Image
from flock.decisions import UNSURE, Checklist, Choice, Decision, YesNo
from flock.decisions.providers import FakeDecider
from flock.decisions.tournament import Tournament
from flock.models.system_artifacts import WorkflowError
from flock.registry import flock_type, type_registry


@flock_type
class EscTicket(BaseModel):
    text: str


@flock_type
class EscPhoto(BaseModel):
    picture: Image


class EscRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


class EscUrgent(YesNo):
    """Does the customer need an answer today?"""


EscControls = Checklist.from_items(
    "EscControls",
    {"mfa": "MFA is enforced", "backup": "Backups are tested", "logs": "Logs are kept"},
    question="Does the document show that this control is implemented?",
)


async def _decisions(flock: Flock, question) -> list:
    name = type_registry.name_for(Decision.of(question))
    return [a.payload for a in await flock.store.list() if a.type == name]


async def _run(flock: Flock, artifact: BaseModel) -> None:
    await flock.publish(artifact)
    await flock.run_until_idle()


def _route(p_billing: float, label: str) -> FakeDecider:
    return FakeDecider({"billing": p_billing, "tech": 1 - p_billing}, label=label)


async def test_a_confident_first_tier_answers_alone():
    first, second = _route(0.95, "fast"), _route(0.99, "strong")
    flock = Flock()
    flock.agent("triage").consumes(EscTicket).decides(
        EscRoute, model=first, threshold=0.9, escalate=[second]
    )

    await _run(flock, EscTicket(text="refund please"))

    (decision,) = await _decisions(flock, EscRoute)
    assert decision["choice"] == "billing"
    assert decision["model"] == "fast"
    assert decision["tier"] == 0
    assert decision["attempts"] == []
    assert second.calls == []


async def test_an_unsure_decision_is_asked_one_tier_up():
    first, second = _route(0.6, "fast"), _route(0.97, "strong")
    flock = Flock()
    flock.agent("triage").consumes(EscTicket).decides(
        EscRoute, model=first, threshold=0.9, escalate=[second]
    )

    await _run(flock, EscTicket(text="charged twice?"))

    (decision,) = await _decisions(flock, EscRoute)
    assert decision["choice"] == "billing"
    assert decision["model"] == "strong"
    assert decision["tier"] == 1
    (attempt,) = decision["attempts"]
    assert attempt["model"] == "fast"
    assert attempt["choice"] == "billing"
    assert attempt["probabilities"] == {"billing": 0.6, "tech": pytest.approx(0.4)}
    assert attempt["refused"] is False


async def test_unsure_after_the_last_tier_routes_to_unsure():
    tiers = [_route(0.55, "a"), _route(0.6, "b"), _route(0.7, "c")]
    flock = Flock()
    flock.agent("triage").consumes(EscTicket).decides(
        EscRoute, model=tiers[0], threshold=0.9, escalate=tiers[1:]
    )

    await _run(flock, EscTicket(text="something odd"))

    (decision,) = await _decisions(flock, EscRoute)
    assert decision["choice"] == UNSURE
    assert decision["best_guess"] == "billing"
    assert decision["model"] == "c"
    assert decision["tier"] == 2
    assert [attempt["model"] for attempt in decision["attempts"]] == ["a", "b"]


async def test_only_unsure_questions_go_up():
    first = FakeDecider(
        {
            "EscRoute": {"billing": 0.95, "tech": 0.05},
            "EscUrgent": {"yes": 0.6, "no": 0.4},
        },
        label="fast",
    )
    second = FakeDecider({"EscUrgent": {"yes": 0.98, "no": 0.02}}, label="strong")
    flock = Flock()
    flock.agent("triage").consumes(EscTicket).decides(
        EscRoute, EscUrgent, model=first, threshold=0.9, escalate=[second]
    )

    await _run(flock, EscTicket(text="refund today"))

    assert [question.name for _, question in second.calls] == ["EscUrgent"]
    (route,) = await _decisions(flock, EscRoute)
    (urgent,) = await _decisions(flock, EscUrgent)
    assert (route["tier"], route["model"]) == (0, "fast")
    assert (urgent["tier"], urgent["model"], urgent["choice"]) == (1, "strong", "yes")


async def test_refusals_escalate():
    first = FakeDecider(
        {"billing": 0.5, "tech": 0.5}, label="fast", refuse={"EscRoute"}
    )
    second = _route(0.96, "strong")
    flock = Flock()
    flock.agent("triage").consumes(EscTicket).decides(
        EscRoute, model=first, threshold=0.9, escalate=[second]
    )

    await _run(flock, EscTicket(text="?"))

    (decision,) = await _decisions(flock, EscRoute)
    assert (decision["choice"], decision["tier"], decision["refused"]) == (
        "billing",
        1,
        False,
    )
    assert decision["attempts"][0]["refused"] is True


async def test_checklist_items_escalate_one_by_one():
    first = FakeDecider(
        {"EscControls": {"mfa": 0.95, "backup": 0.6, "logs": 0.02}}, label="fast"
    )
    second = FakeDecider({"EscControls": {"backup": 0.97}}, label="strong")
    flock = Flock()
    flock.agent("audit").consumes(EscTicket).decides(
        EscControls, model=first, threshold=0.9, escalate=[second]
    )

    await _run(flock, EscTicket(text="policy document"))

    assert [question.item for _, question in second.calls] == ["backup"]
    (decision,) = await _decisions(flock, EscControls)
    assert decision["results"] == {"mfa": "yes", "backup": "yes", "logs": "no"}
    assert decision["tier"] == 1
    assert decision["attempts"] == [{"model": "fast", "results": {"backup": UNSURE}}]


class _ServedModel(FakeDecider):
    """Reports the model the server ran, which differs from its label."""

    def __init__(self, *args, served: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.served = served

    async def decide_many(self, state, questions, images=()):
        answers = await super().decide_many(state, questions, images)
        return {name: replace(a, model=self.served) for name, a in answers.items()}


async def test_an_escalated_checklist_names_the_model_the_server_reported():
    first = FakeDecider({"EscControls": {"mfa": 0.95, "backup": 0.6, "logs": 0.02}})
    second = _ServedModel(
        {"EscControls": {"backup": 0.97}}, label="strong", served="strong-2026-10"
    )
    flock = Flock()
    flock.agent("audit").consumes(EscTicket).decides(
        EscControls, model=first, threshold=0.9, escalate=[second]
    )

    await _run(flock, EscTicket(text="policy document"))

    (decision,) = await _decisions(flock, EscControls)
    assert decision["model"] == "strong-2026-10"


async def test_escalation_and_tournaments_cannot_be_combined():
    flock = Flock()

    with pytest.raises(ValueError, match="escalate="):
        flock.agent("big").consumes(EscTicket).decides(
            EscRoute,
            model=_route(0.5, "a"),
            escalate=[_route(0.9, "b")],
            tournament=Tournament(group_size=2, keep=1),
        )


async def test_every_tier_must_accept_images_for_image_inputs():
    picture = Image.from_pil(PILImage.new("RGB", (8, 8), "red"))
    text_only = FakeDecider(
        {"billing": 0.9, "tech": 0.1}, label="text-only", supports_images=False
    )
    flock = Flock()
    flock.agent("sorter").consumes(EscPhoto).decides(
        EscRoute, model=_route(0.5, "vision"), threshold=0.9, escalate=[text_only]
    )

    await _run(flock, EscPhoto(picture=picture))

    assert await _decisions(flock, EscRoute) == []
    errors = [
        a
        for a in await flock.store.list()
        if a.type == type_registry.name_for(WorkflowError)
    ]
    assert "text-only" in errors[0].payload["error_message"]
