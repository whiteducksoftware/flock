"""Activity histogram of artifacts for the dashboard timeline (#572)."""

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
    FilterConfig,
    InMemoryBlackboardStore,
    SQLiteBlackboardStore,
)
from flock.core.visibility import (
    AfterVisibility,
    AgentIdentity,
    PrivateVisibility,
    PublicVisibility,
)
from flock.models.system_artifacts import WorkflowError
from flock.registry import flock_type, type_registry


@flock_type(name="HistogramItem")
class HistogramItem(BaseModel):
    n: int


START = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
END = START + timedelta(minutes=4)  # four buckets of one minute
ERROR_TYPE = type_registry.name_for(WorkflowError)


def _item(
    minute: float, *, visibility=None, type_name: str = "HistogramItem"
) -> Artifact:
    return Artifact(
        type=type_name,
        payload={"n": 1},
        produced_by="producer",
        visibility=visibility or PublicVisibility(),
        created_at=START + timedelta(minutes=minute),
    )


async def _fill(store) -> None:
    for minute in (0.1, 0.5, 1.2, 3.9):
        await store.publish(_item(minute))
    await store.publish(_item(1.5, type_name=ERROR_TYPE))
    await store.publish(_item(-1))  # before the range
    await store.publish(_item(4.5))  # after it


@pytest.fixture(params=["memory", "sqlite"])
async def store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryBlackboardStore()
        return
    sqlite = SQLiteBlackboardStore(str(tmp_path / "histogram.db"))
    await sqlite.ensure_schema()
    yield sqlite
    await sqlite.close()


async def test_the_store_counts_artifacts_and_errors_per_bucket(store):
    await _fill(store)

    counts, errors = await store.artifact_histogram(
        FilterConfig(start=START, end=END), buckets=4
    )

    assert counts == [2, 2, 0, 1]
    assert errors == [0, 1, 0, 0]


async def test_the_store_applies_the_filters(store):
    await _fill(store)

    counts, errors = await store.artifact_histogram(
        FilterConfig(type_names={"HistogramItem"}, start=START, end=END), buckets=2
    )

    assert counts == [3, 1]
    assert errors == [0, 0]


def _client(enforce_visibility: bool, orchestrator: Flock) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def identity(request, call_next):
        name = request.headers.get("x-test-agent-name")
        if name:
            request.state.identity = AgentIdentity(name=name)
        return await call_next(request)

    ArtifactsComponent(
        name="artifacts",
        config=ArtifactComponentConfig(
            prefix="/api/v1/", enforce_visibility=enforce_visibility
        ),
    ).register_routes(app, orchestrator)
    return TestClient(app)


def _query(buckets: int = 4) -> dict:
    return {"from": START.isoformat(), "to": END.isoformat(), "buckets": buckets}


async def test_the_endpoint_returns_the_histogram():
    orchestrator = Flock()
    await _fill(orchestrator.store)

    data = (
        _client(False, orchestrator)
        .get("/api/v1/artifacts/histogram", params=_query())
        .json()
    )

    assert data["counts"] == [2, 2, 0, 1]
    assert data["errors"] == [0, 1, 0, 0]
    assert data["total"] == 5
    assert data["bucket_seconds"] == 60
    assert datetime.fromisoformat(data["start"]) == START


async def test_the_histogram_counts_only_what_the_caller_may_see():
    orchestrator = Flock()
    store = orchestrator.store
    await store.publish(_item(0.2))  # public
    await store.publish(_item(0.4, visibility=PrivateVisibility(agents={"reader"})))
    await store.publish(  # embargoed until long after the range
        _item(2.5, visibility=AfterVisibility(ttl=timedelta(days=3650)))
    )
    client = _client(True, orchestrator)

    anonymous = client.get("/api/v1/artifacts/histogram", params=_query()).json()
    reader = client.get(
        "/api/v1/artifacts/histogram",
        params=_query(),
        headers={"x-test-agent-name": "reader"},
    ).json()

    assert anonymous["counts"] == [1, 0, 0, 0]
    assert reader["counts"] == [2, 0, 0, 0]


async def test_without_a_range_the_histogram_covers_the_last_hour():
    orchestrator = Flock()
    await orchestrator.store.publish(
        Artifact(type="HistogramItem", payload={"n": 1}, produced_by="producer")
    )

    data = _client(False, orchestrator).get("/api/v1/artifacts/histogram").json()

    span = datetime.fromisoformat(data["end"]) - datetime.fromisoformat(data["start"])
    assert span == timedelta(hours=1)
    assert len(data["counts"]) == 60
    assert sum(data["counts"]) == 1


@pytest.mark.parametrize(
    "params",
    [
        {"buckets": 0},
        {"buckets": 501},
        {"from": END.isoformat(), "to": START.isoformat()},
    ],
)
async def test_bad_histogram_requests_are_rejected(params):
    response = _client(False, Flock()).get("/api/v1/artifacts/histogram", params=params)

    assert response.status_code == 422
