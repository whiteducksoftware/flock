"""An artifact can name what it follows: an app's next step after a decision (#618)."""

from __future__ import annotations

import io
import json
from uuid import uuid4

import aiosqlite
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
from flock.core.store import SQLiteBlackboardStore
from flock.registry import flock_type


@flock_type
class FollowsStep(BaseModel):
    step: int


@flock_type
class FollowsSketch(BaseModel):
    stroke: int
    image: Image


def _png() -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (16, 16), "red").save(buffer, "PNG")
    return buffer.getvalue()


async def test_a_published_artifact_keeps_what_it_follows():
    flock = Flock()
    first = await flock.publish(FollowsStep(step=0))

    second = await flock.publish(FollowsStep(step=1), follows=[first.id])

    assert second.follows == [first.id]
    assert (await flock.store.get(second.id)).follows == [first.id]


async def test_ids_may_be_text_and_repeat():
    flock = Flock()
    first = await flock.publish(FollowsStep(step=0))

    second = await flock.publish(FollowsStep(step=1), follows=[str(first.id), first.id])

    assert second.follows == [first.id]


async def test_an_unknown_or_malformed_id_is_refused():
    flock = Flock()

    with pytest.raises(ValueError, match="no artifact"):
        await flock.publish(FollowsStep(step=1), follows=[uuid4()])
    with pytest.raises(ValueError, match="not an artifact ID"):
        await flock.publish(FollowsStep(step=1), follows=["step-0"])
    assert await flock.store.list() == []


async def test_at_most_max_follows_ids():
    flock = Flock(max_follows=2)
    earlier = [await flock.publish(FollowsStep(step=n)) for n in range(3)]

    await flock.publish(FollowsStep(step=3), follows=[a.id for a in earlier[:2]])
    with pytest.raises(ValueError, match="at most 2"):
        await flock.publish(FollowsStep(step=4), follows=[a.id for a in earlier])


def test_the_default_limit_is_twenty_and_it_must_be_positive():
    assert Flock().max_follows == 20
    with pytest.raises(ValueError, match="max_follows"):
        Flock(max_follows=0)


async def test_sqlite_keeps_what_an_artifact_follows(tmp_path):
    store = SQLiteBlackboardStore(str(tmp_path / "board.db"))
    flock = Flock(store=store)
    first = await flock.publish(FollowsStep(step=0))
    second = await flock.publish(FollowsStep(step=1), follows=[first.id])

    reopened = SQLiteBlackboardStore(str(tmp_path / "board.db"))
    assert (await reopened.get(second.id)).follows == [first.id]
    assert (await reopened.get(first.id)).follows == []
    by_id = {a.id: a for a in await reopened.list()}
    assert by_id[second.id].follows == [first.id]
    await store.close()
    await reopened.close()


async def test_an_older_sqlite_database_gains_the_column(tmp_path):
    path = str(tmp_path / "old.db")
    store = SQLiteBlackboardStore(path)
    flock = Flock(store=store)
    old = await flock.publish(FollowsStep(step=0))
    await store.close()
    # As a database written before this change: no column, schema version 4
    async with aiosqlite.connect(path) as conn:
        await conn.execute("ALTER TABLE artifacts DROP COLUMN follows")
        await conn.execute("UPDATE schema_meta SET version=4 WHERE id=1")
        await conn.commit()

    reopened = SQLiteBlackboardStore(path)
    assert (await reopened.get(old.id)).follows == []
    newer = await Flock(store=reopened).publish(FollowsStep(step=1), follows=[old.id])
    assert (await reopened.get(newer.id)).follows == [old.id]
    await reopened.close()


@pytest.fixture
def component():
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
async def test_a_rest_publish_names_what_it_follows(server, request):
    flock, client = request.getfixturevalue(server)
    first = await flock.publish(FollowsStep(step=0), correlation_id="game-1")

    response = client.post(
        "/api/v1/artifacts",
        json={
            "type": "FollowsStep",
            "payload": {"step": 1},
            "correlation_id": "game-1",
            "follows": [str(first.id)],
        },
    )

    assert response.status_code == 200, response.text
    second = next(a for a in await flock.store.list() if a.id != first.id)
    assert second.follows == [first.id]
    shown = client.get(f"/api/v1/artifacts/{second.id}").json()
    assert shown["follows"] == [str(first.id)]


@pytest.mark.parametrize("server", ["component", "service"])
def test_a_rest_publish_that_follows_nothing_known_is_a_400(server, request):
    _, client = request.getfixturevalue(server)

    for follows in ([str(uuid4())], ["step-0"]):
        response = client.post(
            "/api/v1/artifacts",
            json={"type": "FollowsStep", "payload": {"step": 1}, "follows": follows},
        )
        assert response.status_code == 400, response.text


def test_the_artifact_list_shows_what_each_follows(component):
    _, client = component
    client.post("/api/v1/artifacts", json={"type": "FollowsStep", "payload": {"step": 0}})
    first = client.get("/api/v1/artifacts").json()["items"][0]
    client.post(
        "/api/v1/artifacts",
        json={"type": "FollowsStep", "payload": {"step": 1}, "follows": [first["id"]]},
    )

    items = client.get("/api/v1/artifacts").json()["items"]

    assert sorted(item["follows"] for item in items) == [[], [first["id"]]]


async def test_an_upload_names_what_it_follows(component):
    flock, client = component
    first = await flock.publish(FollowsStep(step=0))

    response = client.post(
        "/api/v1/artifacts/upload",
        data={
            "type": "FollowsSketch",
            "payload": '{"stroke": 1}',
            "follows": json.dumps([str(first.id)]),
        },
        files={"image": ("sketch.png", _png(), "image/png")},
    )

    assert response.status_code == 200, response.text
    sketch = next(a for a in await flock.store.list() if a.id != first.id)
    assert sketch.follows == [first.id]


def test_an_upload_with_follows_that_is_no_list_is_a_400(component):
    _, client = component

    response = client.post(
        "/api/v1/artifacts/upload",
        data={"type": "FollowsSketch", "payload": '{"stroke": 1}', "follows": "not json"},
        files={"image": ("sketch.png", _png(), "image/png")},
    )

    assert response.status_code == 400


async def test_the_board_draws_an_arrow_from_what_an_artifact_follows():
    from flock.api.collector import DashboardEventCollector
    from flock.api.graph_builder import GraphAssembler
    from flock.components.server.models.graph import GraphRequest

    flock = Flock()
    first = await flock.publish(FollowsStep(step=0), correlation_id="game-2")
    second = await flock.publish(
        FollowsStep(step=1), correlation_id="game-2", follows=[first.id]
    )

    collector = DashboardEventCollector(store=flock.store)
    snapshot = await GraphAssembler(flock.store, collector, flock).build_snapshot(
        GraphRequest(view_mode="blackboard")
    )

    arrows = {(edge.source, edge.target) for edge in snapshot.edges}
    assert (str(first.id), str(second.id)) in arrows
