"""The inline image bound holds on every publish path, and image data follows
visibility like any other payload (#513)."""

from __future__ import annotations

import base64
import io
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from pydantic import BaseModel, ValidationError

from flock import Flock
from flock.components.server.artifacts.artifacts_component import (
    ArtifactComponentConfig,
    ArtifactsComponent,
)
from flock.core import image as image_module
from flock.core.artifacts import Artifact
from flock.core.image import Image
from flock.core.visibility import AgentIdentity, PrivateVisibility
from flock.registry import flock_type, type_registry


@flock_type
class BoundPhoto(BaseModel):
    caption: str
    picture: Image


def _png_url(size: tuple[int, int] = (64, 64)) -> str:
    return Image.from_pil(PILImage.new("RGB", size, "navy")).url


@pytest.fixture
def tiny_bound(monkeypatch):
    """A 1 KB bound, so a 64 x 64 noise picture is too large."""
    monkeypatch.setattr(image_module, "MAX_IMAGE_BYTES", 1024)


def _noisy_url() -> str:
    picture = PILImage.frombytes("RGB", (64, 64), os.urandom(64 * 64 * 3))
    buffer = io.BytesIO()
    picture.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def test_a_model_cannot_hold_an_oversized_image(tiny_bound):
    with pytest.raises(ValidationError, match="larger than"):
        BoundPhoto(caption="x", picture=Image(url=_noisy_url()))


async def test_dict_publishes_enforce_the_bound(tiny_bound):
    flock = Flock()

    with pytest.raises(ValidationError, match="larger than"):
        await flock.publish({
            "type": "BoundPhoto",
            "payload": {"caption": "x", "picture": {"url": _noisy_url()}},
        })


async def test_raw_artifacts_enforce_the_bound(tiny_bound):
    flock = Flock()
    artifact = Artifact(
        type=type_registry.name_for(BoundPhoto),
        payload={"caption": "x", "picture": {"url": _noisy_url()}},
        produced_by="external",
    )

    with pytest.raises(ValueError, match="larger than"):
        await flock.publish(artifact)
    assert await flock.store.list() == []


async def test_raw_artifacts_keep_image_like_text_that_is_not_image_data():
    flock = Flock()
    artifact = Artifact(
        type="NotesWithLinks",
        payload={
            "link": {"url": "data:image/svg+xml,<svg/>"},
            "pseudo": {"url": "data:image/😀"},
        },
        produced_by="external",
    )

    await flock.publish(artifact)

    assert len(await flock.store.list()) == 1


def test_rest_publishes_enforce_the_bound(tiny_bound):
    flock = Flock()
    app = FastAPI()
    ArtifactsComponent(
        name="artifacts", config=ArtifactComponentConfig(prefix="/api/v1/")
    ).register_routes(app, flock)
    client = TestClient(app)

    response = client.post(
        "/api/v1/artifacts",
        json={
            "type": "BoundPhoto",
            "payload": {"caption": "x", "picture": {"url": _noisy_url()}},
        },
    )

    assert response.status_code == 400
    assert "larger than" in response.text


@pytest.fixture
async def private_photo():
    """A private artifact with an image, served with visibility enforced."""
    flock = Flock()
    app = FastAPI()

    @app.middleware("http")
    async def identity_from_header(request, call_next):
        name = request.headers.get("x-test-agent")
        if name:
            request.state.identity = AgentIdentity(name=name)
        return await call_next(request)

    ArtifactsComponent(
        name="artifacts",
        config=ArtifactComponentConfig(prefix="/api/v1/", enforce_visibility=True),
    ).register_routes(app, flock)
    url = _png_url()
    artifact = await flock.publish(
        BoundPhoto(caption="secret", picture=Image(url=url)),
        visibility=PrivateVisibility(agents={"reviewer"}),
    )
    return TestClient(app), artifact, url


@pytest.mark.parametrize("images", ["full", "thumbnails"])
async def test_image_data_of_private_artifacts_stays_private(private_photo, images):
    client, artifact, url = private_photo
    base64_data = url.split(",", 1)[1]

    listing = client.get("/api/v1/artifacts", params={"images": images})
    detail = client.get(f"/api/v1/artifacts/{artifact.id}", params={"images": images})
    other = client.get(
        "/api/v1/artifacts",
        params={"images": images},
        headers={"x-test-agent": "intruder"},
    )

    assert listing.json()["items"] == []
    assert detail.status_code == 404
    assert other.json()["items"] == []
    for response in (listing, detail, other):
        assert base64_data not in response.text
        assert "thumb" not in response.text


async def test_the_allowed_agent_gets_the_image(private_photo):
    client, artifact, url = private_photo

    detail = client.get(
        f"/api/v1/artifacts/{artifact.id}", headers={"x-test-agent": "reviewer"}
    )

    assert detail.status_code == 200
    assert detail.json()["payload"]["picture"]["url"] == url


async def test_sibling_keys_do_not_hide_an_oversized_image(tiny_bound):
    flock = Flock()
    artifact = Artifact(
        type="TaggedPicture",
        payload={"shot": {"url": _noisy_url(), "label": "front"}},
        produced_by="external",
    )

    with pytest.raises(ValueError, match="larger than"):
        await flock.publish(artifact)


async def test_board_handle_publishes_enforce_the_bound(tiny_bound):
    from flock.core.orchestrator import BoardHandle

    flock = Flock()
    artifact = Artifact(
        type=type_registry.name_for(BoundPhoto),
        payload={"caption": "x", "picture": {"url": _noisy_url()}},
        produced_by="component",
    )

    with pytest.raises(ValueError, match="larger than"):
        await BoardHandle(flock).publish(artifact)
    assert await flock.store.list() == []


async def test_a_mutated_model_is_checked_when_published(tiny_bound):
    flock = Flock()
    photo = BoundPhoto(caption="x", picture=Image(url=_png_url((8, 8))))
    photo.picture.url = _noisy_url()  # bypasses validation

    with pytest.raises(ValueError, match="larger than"):
        await flock.publish(photo)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(lambda url: {"url": {"url": url}}, id="container-under-url"),
        pytest.param(lambda url: {"shot": _mutated_image(url)}, id="embedded-image"),
        pytest.param(
            lambda url: {"photo": BoundPhoto.model_construct(caption="x", picture=_mutated_image(url))},
            id="embedded-model",
        ),
    ],
)
async def test_raw_payload_shapes_cannot_hide_an_oversized_image(tiny_bound, payload):
    flock = Flock()
    artifact = Artifact(type="Odd", payload=payload(_noisy_url()), produced_by="external")

    with pytest.raises(ValueError, match="larger than"):
        await flock.publish(artifact)


def _mutated_image(url: str) -> Image:
    image = Image(url=_png_url((8, 8)))
    image.url = url  # bypasses validation
    return image
