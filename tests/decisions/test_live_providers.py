"""Live decision models (opt-in): FLOCK_LIVE_DECISIONS=1.

- local: a systemone server at DECISION_API_BASE (default http://127.0.0.1:8080),
  e.g. ``llama serve -m Clef-Flash-Q8_0.gguf -b 4096 -ub 4096``
- jev: needs JEV_API_KEY
"""

from __future__ import annotations

import os

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.decisions import Choice, Decision
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


@pytest.mark.parametrize(
    "model",
    [
        "local/clef-flash",
        pytest.param(
            "jev/jev-latest",
            marks=pytest.mark.skipif(
                not os.getenv("JEV_API_KEY"), reason="JEV_API_KEY not set"
            ),
        ),
    ],
)
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
