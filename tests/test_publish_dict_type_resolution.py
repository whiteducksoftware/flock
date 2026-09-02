"""Dict publishes resolve simple type names and reject unknown ones.

Regression tests for the ArtifactManager dict branch: ``{"type": "Task", ...}``
must resolve ``Task`` to the canonical registered name so subscriptions match,
and an unknown type must fail loudly instead of persisting an artifact nobody
can consume.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from flock import Flock
from flock.api.service import BlackboardHTTPService
from flock.registry import RegistryError, flock_type, type_registry


@flock_type
class DictPublishProbe(BaseModel):
    """Registered without an explicit name → canonical name is module-qualified."""

    value: str
    priority: int = 1


CANONICAL = type_registry.name_for(DictPublishProbe)


@pytest.mark.asyncio
async def test_simple_name_resolves_to_canonical_name():
    assert CANONICAL != "DictPublishProbe"
    orchestrator = Flock()

    artifact = await orchestrator.publish(
        {"type": "DictPublishProbe", "value": "x"}, schedule_immediately=False
    )

    assert artifact.type == CANONICAL
    assert artifact.payload == {"value": "x", "priority": 1}  # defaults filled in


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


@pytest.mark.asyncio
async def test_invalid_payload_raises_validation_error():
    orchestrator = Flock()

    with pytest.raises(ValidationError):
        await orchestrator.publish(
            {"type": "DictPublishProbe", "payload": {"priority": "high"}},
            schedule_immediately=False,
        )


@pytest.mark.asyncio
async def test_payload_is_normalized_like_a_model_publish():
    orchestrator = Flock()

    artifact = await orchestrator.publish(
        {"type": "DictPublishProbe", "value": "x", "priority": "7"},
        schedule_immediately=False,
    )

    assert artifact.payload == {"value": "x", "priority": 7}


def test_rest_publish_with_invalid_payload_returns_400():
    client = TestClient(BlackboardHTTPService(Flock()).app)

    response = client.post(
        "/api/v1/artifacts", json={"type": "DictPublishProbe", "payload": {}}
    )

    assert response.status_code == 400
    assert "value" in response.json()["detail"]


def test_rest_publish_sets_the_artifact_correlation_id():
    client = TestClient(BlackboardHTTPService(Flock()).app)

    response = client.post(
        "/api/v1/artifacts",
        json={"type": "DictPublishProbe", "payload": {"value": "c"}},
    )
    assert response.status_code == 200

    item = client.get("/api/v1/artifacts", params={"type": CANONICAL}).json()["items"][
        0
    ]
    assert item["correlation_id"], (
        "REST publishes must carry the generated correlation id"
    )
    assert "correlation_id" not in item["payload"]


def test_consumption_record_without_correlation_id_is_still_embedded():
    """A consumer of an artifact without correlation id must not make the API drop
    the whole consumptions block (union fallback to ArtifactBase)."""
    from flock.api.models import ArtifactListResponse, ArtifactWithConsumptions

    item = {
        "id": "a" * 36,
        "type": CANONICAL,
        "payload": {"value": "x"},
        "produced_by": "external",
        "visibility": {"kind": "Public"},
        "visibility_kind": "Public",
        "created_at": "2026-09-02T00:00:00+00:00",
        "correlation_id": None,
        "partition_key": None,
        "tags": [],
        "version": 1,
        "consumptions": [
            {
                "artifact_id": "a" * 36,
                "consumer": "talent_scout",
                "run_id": "r1",
                "correlation_id": None,
                "consumed_at": "2026-09-02T00:00:01+00:00",
            }
        ],
        "consumed_by": ["talent_scout"],
    }

    listed = ArtifactListResponse(
        items=[item], pagination={"limit": 50, "offset": 0, "total": 1}
    )

    assert isinstance(listed.items[0], ArtifactWithConsumptions)
    assert listed.items[0].consumed_by == ["talent_scout"]


def _component_client() -> TestClient:
    """The /api/v1/artifacts routes flock.serve() mounts (ArtifactsComponent)."""
    from fastapi import FastAPI

    from flock.components.server.artifacts.artifacts_component import (
        ArtifactComponentConfig,
        ArtifactsComponent,
    )

    app = FastAPI()
    component = ArtifactsComponent(
        name="test_artifacts", config=ArtifactComponentConfig(prefix="/api/v1/")
    )
    component.register_routes(app, Flock())
    return TestClient(app)


def test_component_publish_sets_the_artifact_correlation_id():
    client = _component_client()

    response = client.post(
        "/api/v1/artifacts",
        json={"type": "DictPublishProbe", "payload": {"value": "d"}},
    )
    assert response.status_code == 200

    item = client.get("/api/v1/artifacts", params={"type": CANONICAL}).json()["items"][
        0
    ]
    assert item["correlation_id"], "serve() publishes must carry a correlation id too"
    assert "correlation_id" not in item["payload"]


def test_component_consumption_record_without_correlation_id_is_still_embedded():
    from flock.components.server.artifacts.models import (
        ArtifactListResponse,
        ArtifactWithConsumptions,
    )

    item = {
        "id": "b" * 36,
        "type": CANONICAL,
        "payload": {"value": "x"},
        "produced_by": "external",
        "visibility": {"kind": "Public"},
        "visibility_kind": "Public",
        "created_at": "2026-09-02T00:00:00+00:00",
        "correlation_id": None,
        "partition_key": None,
        "tags": [],
        "version": 1,
        "consumptions": [
            {
                "artifact_id": "b" * 36,
                "consumer": "talent_scout",
                "run_id": "r1",
                "correlation_id": None,
                "consumed_at": "2026-09-02T00:00:01+00:00",
            }
        ],
        "consumed_by": ["talent_scout"],
    }

    listed = ArtifactListResponse(
        items=[item], pagination={"limit": 50, "offset": 0, "total": 1}
    )

    assert isinstance(listed.items[0], ArtifactWithConsumptions)
    assert listed.items[0].consumed_by == ["talent_scout"]
