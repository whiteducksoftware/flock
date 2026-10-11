"""Human review: a person confirms or overrides a decision (#474)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.core.visibility import PrivateVisibility
from flock.decisions import Checklist, Choice, Decision, FakeDecider, Scale
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalResult


@flock_type
class RevTicket(BaseModel):
    text: str


@flock_type
class RevHandled(BaseModel):
    team: str
    text: str


class RevRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


class RevAnger(Scale):
    """How angry is the customer?"""

    calm = "Calm"
    angry = "Angry"
    furious = "Furious"


RevControls = Checklist.from_items("RevControls", {"mfa": "MFA"}, question="Shown?")


class Take(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        ticket = RevTicket(**inputs.artifacts[0].payload)
        return EvalResult.from_object(
            RevHandled(team=agent.name, text=ticket.text), agent=agent
        )


def _flock() -> Flock:
    flock = Flock()
    flock.agent("triage").consumes(RevTicket).decides(
        RevRoute, model=FakeDecider({"billing": 0.55, "tech": 0.45}), threshold=0.8
    )
    flock.agent("billing").consumes(RevRoute.billing).with_engines(Take()).publishes(
        RevHandled
    )
    flock.agent("tech").consumes(RevRoute.tech).with_engines(Take()).publishes(
        RevHandled
    )
    return flock


async def _artifacts(flock: Flock, model) -> list:
    name = type_registry.name_for(model)
    return [a for a in await flock.store.list() if a.type == name]


async def test_an_override_routes_like_any_decision():
    flock = _flock()
    await flock.publish(RevTicket(text="app crashed during checkout"))
    await flock.run_until_idle()
    (unsure,) = await _artifacts(flock, Decision.of(RevRoute))
    assert unsure.payload["choice"] == "UNSURE"

    await flock.review(unsure.id, choice="tech", reviewer="alice")
    await flock.run_until_idle()

    (handled,) = await _artifacts(flock, RevHandled)
    assert handled.payload == {"team": "tech", "text": "app crashed during checkout"}


async def test_a_review_is_a_decision_by_the_reviewer():
    flock = _flock()
    await flock.publish(RevTicket(text="charged twice"))
    await flock.run_until_idle()
    (unsure,) = await _artifacts(flock, Decision.of(RevRoute))

    reviewed = await flock.review(unsure.id, choice="billing", reviewer="alice")

    assert reviewed.produced_by == "alice"
    assert reviewed.correlation_id == unsure.correlation_id
    payload = reviewed.payload
    assert payload["choice"] == payload["best_guess"] == "billing"
    assert payload["probabilities"] == {"billing": 1.0}
    assert payload["model"] == "alice"
    assert payload["review_of"] == str(unsure.id)
    assert payload["subject_ids"] == unsure.payload["subject_ids"]


async def test_confirming_the_best_guess_is_a_review_too():
    flock = _flock()
    await flock.publish(RevTicket(text="charged twice"))
    await flock.run_until_idle()
    (unsure,) = await _artifacts(flock, Decision.of(RevRoute))

    reviewed = await flock.review(unsure.id)  # no choice: the best guess

    assert reviewed.payload["choice"] == "billing"
    assert reviewed.produced_by == "human"


async def test_a_review_keeps_the_decisions_visibility():
    flock = _flock()
    private = PrivateVisibility(agents={"triage", "billing", "tech"})
    await flock.publish(RevTicket(text="charged twice"), visibility=private)
    await flock.run_until_idle()
    (unsure,) = await _artifacts(flock, Decision.of(RevRoute))

    reviewed = await flock.review(unsure.id, choice="billing")

    assert reviewed.visibility.agents == {"triage", "billing", "tech"}


async def test_a_scale_review_sets_the_score_of_its_level():
    flock = Flock()
    flock.agent("mood").consumes(RevTicket).decides(
        RevAnger, model=FakeDecider({"calm": 0.4, "angry": 0.35, "furious": 0.25})
    )
    await flock.publish(RevTicket(text="fine I guess"))
    await flock.run_until_idle()
    (decision,) = await _artifacts(flock, Decision.of(RevAnger))

    reviewed = await flock.review(decision.id, choice="furious")

    assert reviewed.payload["score"] == 2.0


async def test_unknown_choices_and_non_decisions_are_rejected():
    flock = _flock()
    await flock.publish(RevTicket(text="charged twice"))
    await flock.run_until_idle()
    (unsure,) = await _artifacts(flock, Decision.of(RevRoute))
    (ticket,) = await _artifacts(flock, RevTicket)

    with pytest.raises(ValueError, match="shipping"):
        await flock.review(unsure.id, choice="shipping")
    with pytest.raises(ValueError, match="not a decision"):
        await flock.review(ticket.id, choice="billing")
    with pytest.raises(LookupError, match="no artifact"):
        await flock.review("00000000-0000-0000-0000-000000000000", choice="billing")


async def test_a_late_review_keeps_the_embargo_of_the_reviewed_decision():
    import asyncio
    from datetime import timedelta

    from flock.core.visibility import AfterVisibility, PublicVisibility

    flock = Flock()
    flock.agent("triage").consumes(RevTicket).decides(
        RevRoute,
        model=FakeDecider({"billing": 0.55, "tech": 0.45}),
        threshold=0.8,
        visibility=AfterVisibility(
            ttl=timedelta(milliseconds=20), then=PublicVisibility()
        ),
    )
    flock.agent("tech").consumes(RevRoute.tech).with_engines(Take()).publishes(
        RevHandled
    )
    await flock.publish(RevTicket(text="app crashed"))
    await flock.run_until_idle()
    (unsure,) = await _artifacts(flock, Decision.of(RevRoute))
    await asyncio.sleep(0.05)  # the decision's embargo is over

    reviewed = await flock.review(unsure.id, choice="tech")
    await flock.run_until_idle()

    assert reviewed.visibility.ttl == timedelta(0)  # not a fresh 20 ms
    (handled,) = await _artifacts(flock, RevHandled)
    assert handled.payload["team"] == "tech"


async def test_a_reviewer_cannot_share_an_agents_name():
    flock = _flock()
    await flock.publish(RevTicket(text="app crashed"))
    await flock.run_until_idle()
    (unsure,) = await _artifacts(flock, Decision.of(RevRoute))

    # A review by "tech" would never reach the tech agent (no self-triggering)
    with pytest.raises(ValueError, match="agent"):
        await flock.review(unsure.id, choice="tech", reviewer="tech")
    # An unknown id is still unknown, whatever the reviewer's name
    with pytest.raises(LookupError):
        await flock.review(
            "00000000-0000-0000-0000-000000000000", choice="tech", reviewer="tech"
        )


async def test_checklists_cannot_be_reviewed_yet():
    flock = Flock()
    flock.agent("audit").consumes(RevTicket).decides(
        RevControls, model=FakeDecider({"RevControls": {"mfa": 0.6}})
    )
    await flock.publish(RevTicket(text="policy"))
    await flock.run_until_idle()
    (decision,) = await _artifacts(flock, Decision.of(RevControls))

    with pytest.raises(ValueError, match="Checklist"):
        await flock.review(decision.id, choice="passed")
