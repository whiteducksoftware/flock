"""Reviewing decisions over the control API (#474)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from flock import Flock
from flock.decisions import Choice, Decision, FakeDecider
from flock.registry import flock_type, type_registry


@flock_type
class ApiRevTicket(BaseModel):
    text: str


class ApiRevRoute(Choice):
    """Which team should handle this ticket?"""

    billing = "Charges, invoices, refunds"
    tech = "Bugs, crashes, login problems"


@pytest.fixture
def dashboard():
    from flock.api.websocket import WebSocketManager
    from flock.components.server.control.control_routes_component import (
        ControlRoutesComponent,
        ControlRoutesComponentConfig,
    )

    flock = Flock()
    flock.agent("triage").consumes(ApiRevTicket).decides(
        ApiRevRoute, model=FakeDecider({"billing": 0.55, "tech": 0.45}), threshold=0.8
    )
    app = FastAPI()
    ControlRoutesComponent(
        name="control",
        config=ControlRoutesComponentConfig(prefix="/api/"),
        websocket_manager=WebSocketManager(),
    ).register_routes(app, flock)
    return flock, TestClient(app)


async def _decisions(flock: Flock) -> list:
    name = type_registry.name_for(Decision.of(ApiRevRoute))
    return [a for a in await flock.store.list() if a.type == name]


async def test_the_dashboard_reviews_a_decision(dashboard):
    flock, client = dashboard
    await flock.publish(ApiRevTicket(text="crash, then a charge"))
    await flock.run_until_idle()
    (unsure,) = await _decisions(flock)

    response = client.post(
        f"/api/control/decisions/{unsure.id}/review",
        json={"choice": "tech", "reviewer": "alice"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["choice"] == "tech"
    reviewed = next(
        d for d in await _decisions(flock) if str(d.id) == body["artifact_id"]
    )
    assert reviewed.payload["review_of"] == str(unsure.id)
    assert reviewed.produced_by == "alice"


async def test_a_review_without_choice_confirms_the_best_guess(dashboard):
    flock, client = dashboard
    await flock.publish(ApiRevTicket(text="charged twice"))
    await flock.run_until_idle()
    (unsure,) = await _decisions(flock)

    response = client.post(f"/api/control/decisions/{unsure.id}/review", json={})

    assert response.status_code == 200, response.text
    assert response.json()["choice"] == "billing"


async def test_review_errors_are_client_errors(dashboard):
    flock, client = dashboard
    await flock.publish(ApiRevTicket(text="charged twice"))
    await flock.run_until_idle()
    (unsure,) = await _decisions(flock)

    unknown = client.post(
        "/api/control/decisions/00000000-0000-0000-0000-000000000000/review", json={}
    )
    bad_choice = client.post(
        f"/api/control/decisions/{unsure.id}/review", json={"choice": "shipping"}
    )

    assert unknown.status_code == 404
    assert bad_choice.status_code == 422
    assert "shipping" in bad_choice.json()["detail"]
