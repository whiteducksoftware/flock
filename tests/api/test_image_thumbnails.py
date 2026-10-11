"""The dashboard gets thumbnails instead of full images (#512)."""

from __future__ import annotations

import io
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from pydantic import BaseModel

from flock import Flock
from flock.api.collector import DashboardEventCollector
from flock.components.server.artifacts.artifacts_component import (
    ArtifactComponentConfig,
    ArtifactsComponent,
)
from flock.core.artifacts import Artifact
from flock.core.image import Image
from flock.core.store import InMemoryBlackboardStore
from flock.registry import flock_type, type_registry
from flock.utils.runtime import Context


@flock_type
class ThumbPhoto(BaseModel):
    caption: str
    picture: Image


def _picture(size: tuple[int, int] = (800, 600)) -> Image:
    return Image.from_pil(PILImage.new("RGB", size, "teal"))


def _side(url: str) -> int:
    with PILImage.open(io.BytesIO(Image(url=url).to_bytes())) as picture:
        return max(picture.size)


@pytest.fixture
async def served():
    flock = Flock()
    app = FastAPI()
    ArtifactsComponent(
        name="artifacts", config=ArtifactComponentConfig(prefix="/api/v1/")
    ).register_routes(app, flock)
    picture = _picture()
    artifact = await flock.publish(ThumbPhoto(caption="teal", picture=picture))
    return TestClient(app), artifact, picture


def _check_thumbnail_item(item: dict, picture: Image) -> None:
    assert item["payload"]["caption"] == "teal"
    assert item["payload"]["picture"].startswith("🖼 image/jpeg")
    (image,) = item["images"]
    assert image["path"] == "picture"
    assert image["mime"] == "image/jpeg"
    assert image["bytes"] > 0
    assert _side(image["thumb"]) <= 160
    assert picture.base64_data not in str(item)


async def test_lists_carry_full_images_by_default(served):
    client, _, picture = served

    (item,) = client.get("/api/v1/artifacts").json()["items"]

    assert item["payload"]["picture"]["url"] == picture.url
    assert item.get("images") is None


@pytest.mark.parametrize("embed_meta", [False, True])
async def test_lists_can_carry_thumbnails_instead(served, embed_meta):
    client, _, picture = served

    response = client.get(
        "/api/v1/artifacts",
        params={"images": "thumbnails", "embed_meta": str(embed_meta).lower()},
    )

    (item,) = response.json()["items"]
    _check_thumbnail_item(item, picture)


async def test_a_single_artifact_can_carry_thumbnails_or_the_full_image(served):
    client, artifact, picture = served

    full = client.get(f"/api/v1/artifacts/{artifact.id}").json()
    thumbs = client.get(
        f"/api/v1/artifacts/{artifact.id}", params={"images": "thumbnails"}
    ).json()

    assert full["payload"]["picture"]["url"] == picture.url
    _check_thumbnail_item(thumbs, picture)


async def test_websocket_events_carry_thumbnails_not_images(orchestrator):
    collector = DashboardEventCollector(store=InMemoryBlackboardStore())
    agent = orchestrator.agent("camera")._agent
    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=str(uuid4()),
    )
    picture = _picture()
    artifact = Artifact(
        type=type_registry.name_for(ThumbPhoto),
        payload={"caption": "teal", "picture": picture.model_dump()},
        produced_by="camera",
        correlation_id=ctx.correlation_id,
    )

    await collector.on_post_publish(agent, ctx, artifact)

    (event,) = collector.events
    assert event.payload["picture"].startswith("🖼 image/jpeg")
    assert event.images[0]["path"] == "picture"
    assert _side(event.images[0]["thumb"]) <= 160
    assert picture.base64_data not in event.model_dump_json()


def test_summaries_carry_path_segments_for_any_key():
    """Keys with dots or brackets stay unambiguous as segments (#512)."""
    from flock.api.thumbnails import image_summaries

    payload = {"photos": {"front.view": _picture((40, 30)).model_dump()}, "list": []}

    (summary,) = image_summaries(payload)

    assert summary["keys"] == ["photos", "front.view"]


async def test_events_build_thumbnails_off_the_event_loop(orchestrator, monkeypatch):
    import threading

    from flock.api import thumbnails

    threads: list[str] = []
    original = thumbnails.thumbnail

    def recording(url: str):
        threads.append(threading.current_thread().name)
        return original(url)

    monkeypatch.setattr(thumbnails, "thumbnail", recording)
    collector = DashboardEventCollector(store=InMemoryBlackboardStore())
    agent = orchestrator.agent("camera2")._agent
    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=str(uuid4()),
    )
    artifact = Artifact(
        type=type_registry.name_for(ThumbPhoto),
        payload={"caption": "teal", "picture": _picture().model_dump()},
        produced_by="camera2",
        correlation_id=ctx.correlation_id,
    )

    await collector.on_post_publish(agent, ctx, artifact)

    assert threads
    assert threading.main_thread().name not in threads


def test_reported_sizes_ignore_base64_padding():
    from flock.api.thumbnails import image_summaries

    picture = _picture((40, 30))
    (summary,) = image_summaries({"picture": picture.model_dump()})

    assert summary["bytes"] == len(picture.to_bytes())
