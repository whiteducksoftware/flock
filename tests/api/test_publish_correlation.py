"""A REST publish can name its correlation: one game, one drawing, one run (#618)."""

from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from pydantic import BaseModel

from flock import Flock
from flock.components.server.artifacts.artifacts_component import (
    ArtifactComponentConfig,
    ArtifactsComponent,
)
from flock.core.image import Image
from flock.registry import flock_type


@flock_type
class CorrelatedMove(BaseModel):
    step: int


@flock_type
class CorrelatedSketch(BaseModel):
    stroke: int
    image: Image


def _png() -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (16, 16), "red").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def component():
    """The artifacts server component, as ``flock.serve()`` mounts it."""
    flock = Flock()
    app = FastAPI()
    ArtifactsComponent(
        name="artifacts", config=ArtifactComponentConfig(prefix="/api/v1/")
    ).register_routes(app, flock)
    return flock, TestClient(app)


@pytest.fixture
def service():
    from flock.api.service import BlackboardHTTPService

    flock = Flock()
    return flock, TestClient(BlackboardHTTPService(flock).app)


@pytest.mark.parametrize("server", ["component", "service"])
async def test_a_publish_joins_the_correlation_it_names(server, request):
    flock, client = request.getfixturevalue(server)

    for step in (1, 2):
        response = client.post(
            "/api/v1/artifacts",
            json={
                "type": "CorrelatedMove",
                "payload": {"step": step},
                "correlation_id": "game-7",
            },
        )
        assert response.status_code == 200, response.text

    assert [a.correlation_id for a in await flock.store.list()] == ["game-7", "game-7"]


@pytest.mark.parametrize("server", ["component", "service"])
async def test_without_one_every_publish_starts_its_own(server, request):
    flock, client = request.getfixturevalue(server)

    for step in (1, 2):
        client.post(
            "/api/v1/artifacts",
            json={"type": "CorrelatedMove", "payload": {"step": step}},
        )

    first, second = (a.correlation_id for a in await flock.store.list())
    assert first and second and first != second


async def test_an_upload_joins_the_correlation_it_names(component):
    flock, client = component

    response = client.post(
        "/api/v1/artifacts/upload",
        data={
            "type": "CorrelatedSketch",
            "payload": '{"stroke": 1}',
            "correlation_id": "drawing-3",
        },
        files={"image": ("sketch.png", _png(), "image/png")},
    )

    assert response.status_code == 200, response.text
    (artifact,) = await flock.store.list()
    assert artifact.correlation_id == "drawing-3"


@pytest.mark.parametrize("correlation_id", ["", "x" * 257])
def test_a_correlation_id_is_not_empty_nor_huge(component, correlation_id):
    _, client = component

    response = client.post(
        "/api/v1/artifacts",
        json={
            "type": "CorrelatedMove",
            "payload": {"step": 1},
            "correlation_id": correlation_id,
        },
    )

    assert response.status_code == 422


def test_an_upload_with_an_empty_correlation_id_is_rejected(component):
    _, client = component

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "CorrelatedSketch", "payload": '{"stroke": 1}', "correlation_id": ""},
        files={"image": ("sketch.png", _png(), "image/png")},
    )

    assert response.status_code == 400
    assert "correlation_id" in response.json()["detail"]
