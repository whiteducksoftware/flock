"""Live decision models (opt-in): FLOCK_LIVE_DECISIONS=1.

The default live target is Microsoft-Decision-1 on Azure AI Foundry, which the
team can reach with the shared Azure settings. The others run only when their
configuration is present.

- azure: AZURE_API_BASE and AZURE_API_KEY (deployment decision-1)
- openai: OPENAI_API_KEY
- jev: JEV_API_KEY
- local: DECISION_API_BASE pointing at a systemone server, e.g.
  ``llama serve -m Clef-Flash-Q8_0.gguf -b 4096 -ub 4096``
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.core.image import Image
from flock.decisions import Checklist, Choice, Decision, Scale, YesNo
from flock.registry import flock_type, type_registry


pytestmark = pytest.mark.skipif(
    os.getenv("FLOCK_LIVE_DECISIONS") != "1",
    reason="live decision models are opt-in (FLOCK_LIVE_DECISIONS=1)",
)


@flock_type
class LiveTicket(BaseModel):
    subject: str
    body: str


class LiveRoute(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges, invoices, refunds, payment problems"
    shipping = "Delivery, tracking, returns"
    tech = "Bugs, crashes, login problems"


TICKETS = {
    "billing": LiveTicket(
        subject="Charged twice", body="My credit card was charged twice for one order."
    ),
    "shipping": LiveTicket(
        subject="Where is my parcel?", body="Tracking has not moved for ten days."
    ),
    "tech": LiveTicket(
        subject="App crashes", body="The app crashes every time I open settings."
    ),
}


TEXT_MODELS = [
    pytest.param(
        "azure/decision-1",
        marks=pytest.mark.skipif(
            not (os.getenv("AZURE_API_BASE") and os.getenv("AZURE_API_KEY")),
            reason="AZURE_API_BASE / AZURE_API_KEY not set",
        ),
    ),
    pytest.param(
        "openai/gpt-6-luna",
        marks=pytest.mark.skipif(
            not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
        ),
    ),
    pytest.param(
        "jev/jev-latest",
        marks=pytest.mark.skipif(
            not os.getenv("JEV_API_KEY"), reason="JEV_API_KEY not set"
        ),
    ),
    pytest.param(
        "local/clef-flash",
        marks=pytest.mark.skipif(
            not os.getenv("DECISION_API_BASE"),
            reason="DECISION_API_BASE not set (no local decision server)",
        ),
    ),
]


@pytest.mark.parametrize("model", TEXT_MODELS)
async def test_live_model_routes_clear_tickets(model):
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(LiveTicket).decides(LiveRoute, model=model)

    for ticket in TICKETS.values():
        await flock.publish(ticket)
    await flock.run_until_idle()

    name = type_registry.name_for(Decision.of(LiveRoute))
    decisions = [
        Decision.of(LiveRoute)(**a.payload)
        for a in await flock.store.list()
        if a.type == name
    ]
    by_subject = {
        a.payload["subject"]: a.id
        for a in await flock.store.list()
        if a.type == type_registry.name_for(LiveTicket)
    }
    chosen = {
        subject: next(d.choice for d in decisions if d.subject_ids == [str(sid)])
        for subject, sid in by_subject.items()
    }
    expected = {ticket.subject: team for team, ticket in TICKETS.items()}
    assert chosen == expected
    for decision in decisions:
        assert abs(sum(decision.probabilities.values()) - 1.0) < 0.05
        assert decision.latency_ms is not None


class LiveUrgent(YesNo):
    """Does the customer need an answer today?"""

    yes = "A deadline today or money at stake right now"


class LiveAnger(Scale):
    """How angry is the customer?"""

    calm = "Calm and polite"
    annoyed = "Annoyed but civil"
    angry = "Angry, complaining strongly"
    furious = "Furious, threatening to leave"


FURIOUS = LiveTicket(
    subject="Charged twice AGAIN",
    body="Third time this month my card was charged twice. Refund it today or I "
    "cancel and tell everyone.",
)
FRIENDLY = LiveTicket(
    subject="Dark mode",
    body="Hi! It would be lovely to have a dark mode some day. Thanks for the app!",
)


@pytest.mark.parametrize("model", TEXT_MODELS)
async def test_live_model_answers_choice_yes_no_and_scale_in_one_call(model):
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("triage").consumes(LiveTicket).decides(
        LiveRoute, LiveUrgent, LiveAnger, model=model
    )

    await flock.publish(FURIOUS)
    await flock.publish(FRIENDLY)
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    subjects = {
        str(a.id): a.payload["subject"]
        for a in artifacts
        if a.type == type_registry.name_for(LiveTicket)
    }
    answers: dict[str, dict] = {}
    for question in (LiveRoute, LiveUrgent, LiveAnger):
        name = type_registry.name_for(Decision.of(question))
        for artifact in artifacts:
            if artifact.type == name:
                decision = Decision.of(question)(**artifact.payload)
                subject = subjects[decision.subject_ids[0]]
                answers.setdefault(subject, {})[question.__name__] = decision

    furious, friendly = answers[FURIOUS.subject], answers[FRIENDLY.subject]
    assert furious["LiveRoute"].choice == "billing"
    assert furious["LiveUrgent"].choice == "yes"
    assert friendly["LiveUrgent"].choice == "no"
    assert furious["LiveAnger"].score >= 2.0
    assert friendly["LiveAnger"].score <= 1.0
    for decisions in answers.values():
        # One request per ticket: all three decisions carry its latency
        assert len({d.latency_ms for d in decisions.values()}) == 1
        for decision in decisions.values():
            assert abs(sum(decision.probabilities.values()) - 1.0) < 0.05


LiveControls = Checklist.from_items(
    "LiveControls",
    {
        "mfa": "Multi-factor authentication is required for remote access",
        "backup": "Backups are performed daily",
        "restore_test": "Restores from backup are tested",
        "pentest": "Penetration tests are performed annually",
        "training": "Employees receive annual security awareness training",
        "dc_access": "Access to the data centre is logged",
    },
    question="Does the policy show that this control is implemented?",
)


@flock_type
class LivePolicy(BaseModel):
    text: str


@pytest.mark.parametrize("model", TEXT_MODELS)
async def test_live_model_answers_a_checklist(model):
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("audit").consumes(LivePolicy).decides(LiveControls, model=model)

    await flock.publish(
        LivePolicy(
            text="Remote access requires multi-factor authentication. All business "
            "data is backed up every night. Restoring from backup has never been "
            "tested. All staff complete security awareness training every year."
        )
    )
    await flock.run_until_idle()

    (artifact,) = [
        a
        for a in await flock.store.list()
        if a.type == type_registry.name_for(Decision.of(LiveControls))
    ]
    decision = Decision.of(LiveControls)(**artifact.payload)
    assert decision.results == {
        "mfa": "yes",
        "backup": "yes",
        "restore_test": "no",
        "pentest": "no",
        "training": "yes",
        "dc_access": "no",
    }
    assert decision.choice == "failed"


@flock_type
class LiveSwatch(BaseModel):
    photo: Image


class LiveColor(Choice):
    """What is the color of the square in the image?"""

    red = "Red"
    green = "Green"
    blue = "Blue"


def _square(rgb: tuple[int, int, int]) -> Image:
    from PIL import Image as PILImage

    return Image.from_pil(PILImage.new("RGB", (128, 128), rgb))


@pytest.mark.parametrize(
    "model",
    [
        pytest.param(
            "openai/gpt-6-luna",
            marks=pytest.mark.skipif(
                not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
            ),
        ),
        pytest.param(
            "local/clef",
            marks=pytest.mark.skipif(
                not os.getenv("DECISION_API_BASE"),
                reason="DECISION_API_BASE not set (no local decision server)",
            ),
        ),
    ],
)
async def test_live_model_sorts_images(model):
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("painter").consumes(LiveSwatch).decides(LiveColor, model=model)
    squares = {"red": (220, 30, 30), "green": (30, 180, 60), "blue": (30, 60, 220)}

    for rgb in squares.values():
        await flock.publish(LiveSwatch(photo=_square(rgb)))
    await flock.run_until_idle()

    by_id = {
        str(a.id): a.payload["photo"]["url"]
        for a in await flock.store.list()
        if a.type == type_registry.name_for(LiveSwatch)
    }
    expected = {_square(rgb).url: color for color, rgb in squares.items()}
    decisions = [
        a.payload
        for a in await flock.store.list()
        if a.type == type_registry.name_for(Decision.of(LiveColor))
    ]
    assert len(decisions) == 3
    for decision in decisions:
        assert decision["choice"] == expected[by_id[decision["subject_ids"][0]]]
