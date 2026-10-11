"""An artifact by ID with its consumption history (#605)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from flock.components.server.artifacts.artifacts_component import (
    ArtifactComponentConfig,
    ArtifactsComponent,
)
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.store import (
    ConsumptionRecord,
    InMemoryBlackboardStore,
    SQLiteBlackboardStore,
)
from flock.core.visibility import PrivateVisibility
from flock.registry import flock_type


@flock_type(name="ConsumedTicket")
class ConsumedTicket(BaseModel):
    subject: str


AT = datetime(2026, 10, 11, 12, 0, 0, 123456, tzinfo=UTC)


@pytest.fixture(params=["memory", "sqlite"])
async def store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryBlackboardStore()
        return
    sqlite = SQLiteBlackboardStore(str(tmp_path / "consumptions.db"))
    await sqlite.ensure_schema()
    yield sqlite
    await sqlite.close()


def _client(orchestrator: Flock, *, enforce_visibility: bool = False) -> TestClient:
    app = FastAPI()
    ArtifactsComponent(
        name="artifacts",
        config=ArtifactComponentConfig(
            prefix="/api/v1/", enforce_visibility=enforce_visibility
        ),
    ).register_routes(app, orchestrator)
    return TestClient(app)


def _ticket(subject: str, **fields) -> Artifact:
    return Artifact(**{
        "type": "ConsumedTicket",
        "payload": {"subject": subject},
        "produced_by": "external",
        "correlation_id": "run-1",
        "created_at": AT,
        **fields,
    })


def _consumed(artifact: Artifact, consumer: str, seconds: int) -> ConsumptionRecord:
    return ConsumptionRecord(
        artifact_id=artifact.id,
        consumer=consumer,
        run_id=f"{consumer}-run",
        correlation_id="run-1",
        consumed_at=AT + timedelta(seconds=seconds),
    )


async def test_an_artifact_by_id_brings_its_consumption_history(store):
    ticket = _ticket("Refund not received")
    # Its twin in all but the ID: same type, producer, run and time
    twin = _ticket("Charged twice")
    for artifact in (ticket, twin):
        await store.publish(artifact)
    await store.record_consumptions([
        _consumed(ticket, "triage", 1),
        _consumed(ticket, "billing_team", 2),
        _consumed(twin, "supervisor", 3),
    ])

    data = (
        _client(Flock(store=store))
        .get(f"/api/v1/artifacts/{ticket.id}", params={"embed_meta": "true"})
        .json()
    )

    assert data["payload"] == {"subject": "Refund not received"}
    assert data["consumed_by"] == ["billing_team", "triage"]
    assert [
        (entry["consumer"], entry["run_id"], entry["correlation_id"])
        for entry in sorted(
            data["consumptions"], key=lambda entry: entry["consumed_at"]
        )
    ] == [
        ("triage", "triage-run", "run-1"),
        ("billing_team", "billing_team-run", "run-1"),
    ]
    assert datetime.fromisoformat(data["consumptions"][0]["consumed_at"]) > AT


async def test_without_embed_meta_the_artifact_comes_alone(store):
    ticket = _ticket("Refund not received")
    await store.publish(ticket)
    await store.record_consumptions([_consumed(ticket, "triage", 1)])

    data = _client(Flock(store=store)).get(f"/api/v1/artifacts/{ticket.id}").json()

    assert "consumptions" not in data
    assert "consumed_by" not in data


async def test_an_artifact_no_one_consumed_has_an_empty_history(store):
    ticket = _ticket("Refund not received", correlation_id=None)
    await store.publish(ticket)

    data = (
        _client(Flock(store=store))
        .get(f"/api/v1/artifacts/{ticket.id}", params={"embed_meta": "true"})
        .json()
    )

    assert data["consumptions"] == []
    assert data["consumed_by"] == []


async def test_a_private_artifact_stays_hidden_with_its_history():
    orchestrator = Flock()
    ticket = _ticket(
        "Refund not received", visibility=PrivateVisibility(agents={"triage"})
    )
    await orchestrator.store.publish(ticket)

    response = _client(orchestrator, enforce_visibility=True).get(
        f"/api/v1/artifacts/{ticket.id}", params={"embed_meta": "true"}
    )

    assert response.status_code == 404
