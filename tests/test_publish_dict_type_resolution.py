"""Dict publishes resolve simple type names and reject unknown ones.

Regression tests for the ArtifactManager dict branch: ``{"type": "Task", ...}``
must resolve ``Task`` to the canonical registered name so subscriptions match,
and an unknown type must fail loudly instead of persisting an artifact nobody
can consume.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from flock import Flock
from flock.api.service import BlackboardHTTPService
from flock.registry import RegistryError, flock_type, type_registry


@flock_type
class DictPublishProbe(BaseModel):
    """Registered without an explicit name → canonical name is module-qualified."""

    value: str


CANONICAL = type_registry.name_for(DictPublishProbe)


@pytest.mark.asyncio
async def test_simple_name_resolves_to_canonical_name():
    assert CANONICAL != "DictPublishProbe"
    orchestrator = Flock()

    artifact = await orchestrator.publish(
        {"type": "DictPublishProbe", "value": "x"}, schedule_immediately=False
    )

    assert artifact.type == CANONICAL
    assert artifact.payload == {"value": "x"}


@pytest.mark.asyncio
async def test_canonical_name_is_kept():
    orchestrator = Flock()

    artifact = await orchestrator.publish(
        {"type": CANONICAL, "payload": {"value": "y"}}, schedule_immediately=False
    )

    assert artifact.type == CANONICAL


@pytest.mark.asyncio
async def test_unknown_type_raises_registry_error():
    orchestrator = Flock()

    with pytest.raises(RegistryError, match="Unknown artifact type"):
        await orchestrator.publish(
            {"type": "NoSuchArtifactType", "value": "x"}, schedule_immediately=False
        )


def test_rest_publish_with_unknown_type_returns_400():
    client = TestClient(BlackboardHTTPService(Flock()).app)

    response = client.post(
        "/api/v1/artifacts",
        json={"type": "NoSuchArtifactType", "payload": {"value": "x"}},
    )

    assert response.status_code == 400
    assert "Unknown artifact type" in response.json()["detail"]


def test_rest_publish_with_simple_name_is_stored_canonically():
    client = TestClient(BlackboardHTTPService(Flock()).app)

    response = client.post(
        "/api/v1/artifacts",
        json={"type": "DictPublishProbe", "payload": {"value": "z"}},
    )
    assert response.status_code == 200

    listing = client.get("/api/v1/artifacts", params={"type": CANONICAL}).json()
    assert [item["type"] for item in listing["items"]] == [CANONICAL]
