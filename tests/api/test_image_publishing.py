"""Publishing artifacts with Image fields through the REST API (#511)."""

from __future__ import annotations

import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from pydantic import BaseModel, Field

from flock import Flock
from flock.components.server.artifacts.artifacts_component import (
    ArtifactComponentConfig,
    ArtifactsComponent,
)
from flock.core.image import Image
from flock.registry import flock_type, type_registry


@flock_type
class UploadPhoto(BaseModel):
    caption: str
    picture: Image


@flock_type
class UploadAlbum(BaseModel):
    title: str
    pages: list[Image] = []
    cover: Image | None = None


@flock_type
class UploadAliased(BaseModel):
    caption: str
    picture: Image = Field(alias="photo")


def _png_bytes(color: str = "red", size: tuple[int, int] = (32, 24)) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def setup():
    """The artifacts server component, as ``flock.serve()`` mounts it."""
    flock = Flock()
    app = FastAPI()
    ArtifactsComponent(
        name="artifacts", config=ArtifactComponentConfig(prefix="/api/v1/")
    ).register_routes(app, flock)
    return flock, TestClient(app)


async def _stored(flock: Flock, model: type[BaseModel]):
    return await flock.store.get_by_type(model)


def test_image_schemas_are_marked_for_the_dashboard():
    schema = UploadPhoto.model_json_schema()

    assert schema["$defs"]["Image"]["x-flock-image"] is True


async def test_json_publish_accepts_an_image_data_url(setup):
    flock, client = setup
    url = Image.from_bytes(_png_bytes()).url

    response = client.post(
        "/api/v1/artifacts",
        json={
            "type": type_registry.name_for(UploadPhoto),
            "payload": {"caption": "red", "picture": {"url": url}},
        },
    )

    assert response.status_code == 200, response.text
    (photo,) = await _stored(flock, UploadPhoto)
    assert photo.picture.url == url


def test_json_publish_rejects_a_url_that_is_not_image_data(setup):
    _, client = setup

    response = client.post(
        "/api/v1/artifacts",
        json={
            "type": type_registry.name_for(UploadPhoto),
            "payload": {
                "caption": "x",
                "picture": {"url": "https://example.com/a.png"},
            },
        },
    )

    assert response.status_code == 400
    assert "data URL" in response.text


async def test_upload_publishes_a_file_into_an_image_field(setup):
    flock, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={
            "type": type_registry.name_for(UploadPhoto),
            "payload": json.dumps({"caption": "a red rectangle"}),
        },
        files={"picture": ("red.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200, response.text
    (photo,) = await _stored(flock, UploadPhoto)
    assert photo.caption == "a red rectangle"
    assert photo.picture.mime_type == "image/jpeg"  # re-encoded, metadata dropped


async def test_repeated_files_fill_a_list_of_images(setup):
    flock, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadAlbum", "payload": json.dumps({"title": "colors"})},
        files=[
            ("pages", ("a.png", _png_bytes("red"), "image/png")),
            ("pages", ("b.png", _png_bytes("blue"), "image/png")),
            ("cover", ("c.png", _png_bytes("green"), "image/png")),
        ],
    )

    assert response.status_code == 200, response.text
    (album,) = await _stored(flock, UploadAlbum)
    assert len(album.pages) == 2
    assert album.cover is not None


def test_a_file_that_is_not_an_image_is_rejected(setup):
    _, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadPhoto", "payload": json.dumps({"caption": "x"})},
        files={"picture": ("notes.txt", b"just text", "text/plain")},
    )

    assert response.status_code == 400
    assert "picture" in response.text


def test_an_oversized_file_is_rejected(setup, monkeypatch):
    from flock.api import image_uploads

    monkeypatch.setattr(image_uploads, "MAX_IMAGE_BYTES", 100)
    _, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadPhoto", "payload": json.dumps({"caption": "x"})},
        files={"picture": ("big.png", _png_bytes(size=(200, 200)), "image/png")},
    )

    assert response.status_code == 413


def test_too_many_pixels_are_rejected_before_decoding(setup, monkeypatch):
    from flock.api import image_uploads

    monkeypatch.setattr(image_uploads, "MAX_IMAGE_PIXELS", 100)
    _, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadPhoto", "payload": json.dumps({"caption": "x"})},
        files={"picture": ("wide.png", _png_bytes(size=(50, 50)), "image/png")},
    )

    assert response.status_code == 400
    assert "pixels" in response.text


def test_files_for_fields_that_are_not_images_are_rejected(setup):
    _, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadPhoto", "payload": json.dumps({})},
        files={"caption": ("red.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert "caption" in response.text


def test_two_files_for_a_single_image_field_are_rejected(setup):
    _, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadPhoto", "payload": json.dumps({"caption": "x"})},
        files=[
            ("picture", ("a.png", _png_bytes(), "image/png")),
            ("picture", ("b.png", _png_bytes(), "image/png")),
        ],
    )

    assert response.status_code == 400


@pytest.mark.parametrize("part_name", ["photo", "picture"])
async def test_files_can_use_a_field_alias_or_its_name(setup, part_name):
    flock, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadAliased", "payload": json.dumps({"caption": "x"})},
        files={part_name: ("red.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200, response.text
    (artifact,) = await flock.store.list()
    assert artifact.payload["picture"]["url"].startswith("data:image/jpeg;base64,")


def test_too_many_files_are_rejected(setup, monkeypatch):
    from flock.api import image_uploads

    monkeypatch.setattr(image_uploads, "MAX_UPLOAD_FILES", 2)
    _, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadAlbum", "payload": json.dumps({"title": "x"})},
        files=[("pages", (f"{i}.png", _png_bytes(), "image/png")) for i in range(3)],
    )

    assert response.status_code in (400, 413)


def test_an_oversized_request_is_rejected_before_parsing(setup, monkeypatch):
    from flock.api import image_uploads

    monkeypatch.setattr(image_uploads, "MAX_IMAGE_BYTES", 100)
    monkeypatch.setattr(image_uploads, "MAX_UPLOAD_FILES", 2)
    monkeypatch.setattr(image_uploads, "MAX_FORM_BYTES", 1000)
    _, client = setup

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "UploadAlbum", "payload": json.dumps({"title": "x"})},
        files=[("pages", ("big.png", b"x" * 5000, "image/png"))],
    )

    assert response.status_code == 413
    assert "request" in response.text.lower()


def test_a_request_without_content_length_is_refused(setup):
    _, client = setup

    def body():
        yield b"--b\r\nContent-Disposition: form-data; name=type\r\n\r\nUploadPhoto\r\n--b--\r\n"

    response = client.post(
        "/api/v1/artifacts/upload",
        content=body(),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )

    assert response.status_code == 411
