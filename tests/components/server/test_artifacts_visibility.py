"""Tests for ArtifactsComponent visibility model enforcement (Issue #417)."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from flock.components.server.artifacts.artifacts_component import (
    ArtifactComponentConfig,
    ArtifactsComponent,
)
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.store import InMemoryBlackboardStore, SQLiteBlackboardStore
from flock.core.visibility import (
    AfterVisibility,
    AgentIdentity,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
)
from flock.registry import flock_type


@flock_type(name="VisibleItem")
class VisibleItem(BaseModel):
    message: str


@flock_type(name="tests.VisibilitySummaryItem")
class VisibilitySummaryItem(BaseModel):
    message: str


def _create_test_app_and_orchestrator(enforce_visibility: bool = True, store=None):
    app = FastAPI()

    @app.middleware("http")
    async def inject_test_identity(request, call_next):
        """Model trusted auth middleware without teaching the component test headers."""
        name = request.headers.get("x-test-agent-name")
        tenant_id = request.headers.get("x-test-tenant-id")
        if request.headers.get("x-test-unrelated-identity"):
            request.state.identity = {"sub": "alice"}
        elif name or tenant_id:
            request.state.identity = AgentIdentity(
                name=name or "test-caller",
                tenant_id=tenant_id,
            )
        return await call_next(request)

    orchestrator = Flock(store=store)
    component = ArtifactsComponent(
        name="test_artifacts",
        config=ArtifactComponentConfig(
            prefix="/api/v1/",
            enforce_visibility=enforce_visibility,
        ),
    )
    component.register_routes(app, orchestrator)
    return TestClient(app), orchestrator


@pytest.mark.asyncio
async def test_artifact_visibility_unauthenticated_reads():
    """Unauthenticated requests must only see Public artifacts (fail-closed for Private/Tenant)."""
    client, orchestrator = _create_test_app_and_orchestrator(enforce_visibility=True)

    # 1. Publish Public artifact
    pub_art = await orchestrator.publish(
        VisibleItem(message="public info"),
    )

    # 2. Publish Private artifact (only for "reviewer")
    priv_art = await orchestrator.publish(
        VisibleItem(message="confidential reviewer note"),
        visibility=PrivateVisibility(agents={"reviewer"}),
    )

    # 3. Publish Tenant artifact (only for "tenant-alpha")
    tenant_art = await orchestrator.publish(
        VisibleItem(message="tenant alpha secret"),
        visibility=TenantVisibility(tenant_id="tenant-alpha"),
    )
    unscoped_labelled_art = await orchestrator.publish(
        VisibleItem(message="not public despite empty labels"),
        visibility=LabelledVisibility(required_labels=set()),
    )
    expired_unscoped_labelled_art = await orchestrator.publish(
        VisibleItem(message="still not public after delay"),
        visibility=AfterVisibility(
            ttl=timedelta(hours=1),
            then=LabelledVisibility(required_labels=set()),
        ),
    )
    expired_unscoped_labelled_art.visibility._created_at = datetime.now(
        UTC
    ) - timedelta(hours=2)
    expired_unscoped_tenant_art = await orchestrator.publish(
        VisibleItem(message="missing tenant is not public after delay"),
        visibility=AfterVisibility(
            ttl=timedelta(hours=1), then=TenantVisibility(tenant_id=None)
        ),
    )
    expired_unscoped_tenant_art.visibility._created_at = datetime.now(UTC) - timedelta(
        hours=2
    )

    # Test GET /api/v1/artifacts (unauthenticated)
    res_list = client.get("/api/v1/artifacts")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["pagination"]["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(pub_art.id)
    assert data["items"][0]["payload"]["message"] == "public info"

    # Test GET /api/v1/artifacts/{id} (unauthenticated)
    # Public artifact -> 200
    res_pub = client.get(f"/api/v1/artifacts/{pub_art.id}")
    assert res_pub.status_code == 200
    assert res_pub.json()["payload"]["message"] == "public info"

    # Private artifact -> 404 (does not disclose existence)
    res_priv = client.get(f"/api/v1/artifacts/{priv_art.id}")
    assert res_priv.status_code == 404
    assert res_priv.json()["detail"] == "artifact not found"

    # Tenant artifact -> 404
    res_tenant = client.get(f"/api/v1/artifacts/{tenant_art.id}")
    assert res_tenant.status_code == 404
    assert (
        client.get(f"/api/v1/artifacts/{unscoped_labelled_art.id}").status_code == 404
    )
    assert (
        client.get(f"/api/v1/artifacts/{expired_unscoped_labelled_art.id}").status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/artifacts/{expired_unscoped_tenant_art.id}").status_code
        == 404
    )

    # Test GET /api/v1/artifacts/summary (unauthenticated)
    res_sum = client.get("/api/v1/artifacts/summary")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()["summary"]
    assert sum_data["total"] == 1
    assert sum_data["by_visibility"] == {"Public": 1}


@pytest.mark.asyncio
async def test_unauthenticated_collection_reads_use_bounded_public_store_queries(
    mocker,
):
    """Public list and summary routes must not materialize the whole blackboard."""
    client, orchestrator = _create_test_app_and_orchestrator(enforce_visibility=True)
    await orchestrator.publish(VisibleItem(message="public"))
    query_spy = mocker.spy(orchestrator.store, "query_artifacts")
    summary_spy = mocker.spy(orchestrator.store, "summarize_artifacts")

    assert client.get("/api/v1/artifacts", params={"limit": 1}).status_code == 200
    list_filters = query_spy.call_args.args[0]
    assert query_spy.call_args.kwargs["limit"] == 1
    assert list_filters.visibility == {"Public"}

    assert client.get("/api/v1/artifacts/summary").status_code == 200
    summary_spy.assert_called_once()
    assert summary_spy.call_args.args[0].visibility == {"Public"}


@pytest.mark.asyncio
async def test_expired_after_visibility_is_included_in_anonymous_pagination():
    client, orchestrator = _create_test_app_and_orchestrator(enforce_visibility=True)
    await orchestrator.publish(VisibleItem(message="public one"))
    second_public = await orchestrator.publish(VisibleItem(message="public two"))

    expired_artifact = await orchestrator.publish(
        VisibleItem(message="embargo expired"),
        visibility=AfterVisibility(ttl=timedelta(hours=1), then=PublicVisibility()),
    )
    expired_artifact.visibility._created_at = datetime.now(UTC) - timedelta(hours=2)
    future_artifact = await orchestrator.publish(
        VisibleItem(message="still embargoed"),
        visibility=AfterVisibility(ttl=timedelta(hours=1)),
    )

    listing = client.get("/api/v1/artifacts", params={"offset": 1, "limit": 1}).json()
    assert listing["pagination"]["total"] == 3
    assert listing["items"][0]["id"] == str(second_public.id)
    assert client.get(f"/api/v1/artifacts/{expired_artifact.id}").status_code == 200
    assert client.get(f"/api/v1/artifacts/{future_artifact.id}").status_code == 404

    summary = client.get("/api/v1/artifacts/summary").json()["summary"]
    assert summary["total"] == 3
    assert summary["by_visibility"] == {"Public": 2, "After": 1}


@pytest.mark.asyncio
async def test_sqlite_anonymous_summary_coalesces_canonical_type_names(tmp_path):
    store = SQLiteBlackboardStore(str(tmp_path / "visibility-summary.db"))
    await store.ensure_schema()
    client, _ = _create_test_app_and_orchestrator(store=store)
    created_at = datetime.now(UTC) - timedelta(hours=2)

    try:
        for visibility in (
            PublicVisibility(),
            AfterVisibility(ttl=timedelta(hours=1), then=PublicVisibility()),
        ):
            await store.publish(
                Artifact(
                    type="VisibilitySummaryItem",
                    payload={"message": "visible"},
                    produced_by="test",
                    visibility=visibility,
                    created_at=created_at,
                )
            )

        anonymous = client.get("/api/v1/artifacts/summary").json()["summary"]
        authenticated = client.get(
            "/api/v1/artifacts/summary",
            headers={"X-Test-Agent-Name": "reader"},
        ).json()["summary"]

        assert anonymous["by_type"] == {"tests.VisibilitySummaryItem": 2}
        assert authenticated["by_type"] == anonymous["by_type"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_visibility_summary_is_identity_independent():
    client, orchestrator = _create_test_app_and_orchestrator()
    await orchestrator.store.publish(
        Artifact(
            type="VisibleItem",
            payload={"message": "visible"},
            produced_by="test",
            visibility=PublicVisibility(),
            created_at=datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=2))),
        )
    )

    anonymous = client.get("/api/v1/artifacts/summary").json()["summary"]
    authenticated = client.get(
        "/api/v1/artifacts/summary",
        headers={"X-Test-Agent-Name": "reader"},
    ).json()["summary"]

    assert authenticated == anonymous


@pytest.mark.parametrize("store_kind", ["memory", "sqlite"])
@pytest.mark.parametrize("scenario", ["equal", "offset", "microsecond"])
@pytest.mark.asyncio
async def test_anonymous_pagination_uses_stable_store_order(
    store_kind, scenario, tmp_path
):
    if store_kind == "sqlite":
        store = SQLiteBlackboardStore(str(tmp_path / "visibility.db"))
        await store.ensure_schema()
    else:
        store = InMemoryBlackboardStore()
    client, _ = _create_test_app_and_orchestrator(store=store)
    if scenario == "equal":
        timestamp = datetime(2022, 1, 1, tzinfo=UTC)
        specs = [(3, timestamp, False), (1, timestamp, False), (2, timestamp, True)]
        expected = (1, 2, 3)
    elif scenario == "offset":
        specs = [
            (3, datetime(2020, 1, 1, 2, tzinfo=timezone(timedelta(hours=2))), False),
            (2, datetime(2020, 1, 1, 0, 15, tzinfo=UTC), True),
            (1, datetime(2020, 1, 1, 0, 30, tzinfo=UTC), False),
        ]
        expected = (3, 2, 1)
    else:
        specs = [
            (3, datetime(2021, 1, 1, 0, 0, 0, 0, tzinfo=UTC), False),
            (2, datetime(2021, 1, 1, 0, 0, 0, 50, tzinfo=UTC), True),
            (1, datetime(2021, 1, 1, 0, 0, 0, 100, tzinfo=UTC), False),
        ]
        expected = (3, 2, 1)
    artifacts = [
        Artifact(
            id=UUID(int=artifact_id),
            type="VisibleItem",
            payload={"message": str(artifact_id)},
            produced_by="test",
            created_at=created_at,
            visibility=(
                AfterVisibility(ttl=timedelta(hours=1))
                if delayed
                else PublicVisibility()
            ),
        )
        for artifact_id, created_at, delayed in specs
    ]
    try:
        for artifact in artifacts:
            await store.publish(artifact)

        page_ids = [
            client.get(
                "/api/v1/artifacts", params={"offset": offset, "limit": 1}
            ).json()["items"][0]["id"]
            for offset in range(len(artifacts))
        ]

        assert page_ids == [str(UUID(int=value)) for value in expected]
    finally:
        if isinstance(store, SQLiteBlackboardStore):
            await store.close()


@pytest.mark.asyncio
async def test_visibility_enforcement_can_be_disabled():
    client, orchestrator = _create_test_app_and_orchestrator(enforce_visibility=False)
    private = await orchestrator.publish(
        VisibleItem(message="legacy private"),
        visibility=PrivateVisibility(agents={"reviewer"}),
    )

    headers = {"X-Test-Unrelated-Identity": "1"}
    listing = client.get("/api/v1/artifacts", headers=headers).json()
    assert listing["pagination"]["total"] == 1
    assert (
        client.get(f"/api/v1/artifacts/{private.id}", headers=headers).status_code
        == 200
    )
    assert (
        client.get("/api/v1/artifacts/summary", headers=headers).json()["summary"][
            "total"
        ]
        == 1
    )


@pytest.mark.parametrize(
    ("visibility", "expected_status"),
    [
        ({"kind": "Public"}, 200),
        ({"kind": "Private", "agents": ["reviewer"]}, 404),
        ({"kind": "Labelled", "required_labels": ["admin"]}, 404),
        ({"kind": "Tenant", "tenant_id": "tenant-alpha"}, 404),
        (
            {"kind": "After", "ttl": "PT1H", "then": {"kind": "Public"}},
            200,
        ),
        (
            AfterVisibility(
                ttl=timedelta(),
                then={"kind": "Private", "agents": ["reviewer"]},
            ),
            404,
        ),
    ],
)
@pytest.mark.asyncio
async def test_artifact_dict_visibility_is_enforced(visibility, expected_status):
    client, orchestrator = _create_test_app_and_orchestrator()
    artifact = Artifact(
        type="VisibleItem",
        payload={"message": "policy test"},
        produced_by="test",
        visibility=visibility,
        created_at=datetime.now(UTC) - timedelta(hours=2),
    )
    await orchestrator.store.publish(artifact)

    listing = client.get("/api/v1/artifacts")
    summary = client.get("/api/v1/artifacts/summary")
    detail = client.get(f"/api/v1/artifacts/{artifact.id}")

    assert listing.status_code == summary.status_code == 200
    assert detail.status_code == expected_status
    expected_total = int(expected_status == 200)
    assert listing.json()["pagination"]["total"] == expected_total
    assert summary.json()["summary"]["total"] == expected_total


@pytest.mark.parametrize(
    "visibility",
    [
        {"kind": "Unknown"},
        {"kind": "Private", "agents": [], "agentz": []},
        {"kind": "Private", "agents": "reviewer"},
        {"kind": "Labelled", "required_labels": "admin"},
        {"kind": "After", "ttl": "not-a-duration"},
        {"kind": "After", "ttl": "PT1H", "then": {"kind": "Unknown"}},
    ],
)
def test_artifact_rejects_malformed_visibility_dicts(visibility):
    with pytest.raises(ValidationError):
        Artifact(
            type="VisibleItem",
            payload={},
            produced_by="test",
            visibility=visibility,
        )


@pytest.mark.parametrize("ttl", [3600, "01:00:00"])
def test_artifact_preserves_core_valid_after_ttl(ttl):
    created_at = datetime.now(UTC)
    artifact = Artifact(
        type="VisibleItem",
        payload={},
        produced_by="test",
        visibility={"kind": "After", "ttl": ttl},
        created_at=created_at,
    )

    assert artifact.visibility.ttl == timedelta(hours=1)
    assert not ArtifactsComponent._allows_anonymous(
        artifact.visibility, now=created_at + timedelta(minutes=30)
    )


@pytest.mark.asyncio
async def test_artifact_visibility_authenticated_reads():
    """Identity established by auth middleware controls artifact access."""
    client, orchestrator = _create_test_app_and_orchestrator(enforce_visibility=True)

    pub_art = await orchestrator.publish(VisibleItem(message="public"))
    priv_art = await orchestrator.publish(
        VisibleItem(message="for reviewer only"),
        visibility=PrivateVisibility(agents={"reviewer"}),
    )
    tenant_art = await orchestrator.publish(
        VisibleItem(message="for tenant alpha"),
        visibility=TenantVisibility(tenant_id="tenant-alpha"),
    )

    # Caller identifying as agent "reviewer"
    reviewer_headers = {"X-Test-Agent-Name": "reviewer"}
    res_reviewer = client.get("/api/v1/artifacts", headers=reviewer_headers)
    assert res_reviewer.status_code == 200
    rev_data = res_reviewer.json()
    assert rev_data["pagination"]["total"] == 2
    item_ids = {item["id"] for item in rev_data["items"]}
    assert str(pub_art.id) in item_ids
    assert str(priv_art.id) in item_ids
    assert str(tenant_art.id) not in item_ids

    # Reviewer fetching private artifact by ID
    res_get_priv = client.get(
        f"/api/v1/artifacts/{priv_art.id}", headers=reviewer_headers
    )
    assert res_get_priv.status_code == 200
    assert res_get_priv.json()["payload"]["message"] == "for reviewer only"

    # Caller identifying as tenant-alpha
    tenant_headers = {"X-Test-Tenant-Id": "tenant-alpha"}
    res_tenant = client.get("/api/v1/artifacts", headers=tenant_headers)
    assert res_tenant.status_code == 200
    tenant_data = res_tenant.json()
    assert tenant_data["pagination"]["total"] == 2
    tenant_item_ids = {item["id"] for item in tenant_data["items"]}
    assert str(pub_art.id) in tenant_item_ids
    assert str(tenant_art.id) in tenant_item_ids
    assert str(priv_art.id) not in tenant_item_ids


@pytest.mark.asyncio
async def test_artifact_visibility_does_not_trust_caller_identity_headers():
    """Callers cannot grant themselves private, tenant, or labelled access."""
    client, orchestrator = _create_test_app_and_orchestrator(enforce_visibility=True)
    private = await orchestrator.publish(
        VisibleItem(message="private"),
        visibility=PrivateVisibility(agents={"reviewer"}),
    )
    tenant = await orchestrator.publish(
        VisibleItem(message="tenant"),
        visibility=TenantVisibility(tenant_id="tenant-alpha"),
    )
    labelled = await orchestrator.publish(
        VisibleItem(message="labelled"),
        visibility=LabelledVisibility(required_labels={"admin"}),
    )

    assert (
        client.get(
            f"/api/v1/artifacts/{private.id}", headers={"X-Agent-Name": "reviewer"}
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/artifacts/{tenant.id}",
            headers={"X-Tenant-Id": "tenant-alpha"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/artifacts/{labelled.id}",
            headers={"X-Agent-Labels": "admin"},
        ).status_code
        == 404
    )


@pytest.mark.asyncio
async def test_artifact_publish_with_visibility():
    """POST /api/v1/artifacts can accept and persist custom visibility."""
    client, orchestrator = _create_test_app_and_orchestrator(enforce_visibility=True)

    # Publish private artifact via REST API
    post_res = client.post(
        "/api/v1/artifacts",
        json={
            "type": "VisibleItem",
            "payload": {"message": "classified"},
            "visibility": {"kind": "Private", "agents": ["reviewer"]},
        },
    )
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "accepted"

    # Unauthenticated list should NOT see it
    unauth_list = client.get("/api/v1/artifacts").json()
    assert unauth_list["pagination"]["total"] == 0

    # Reviewer should see it
    rev_list = client.get(
        "/api/v1/artifacts", headers={"X-Test-Agent-Name": "reviewer"}
    ).json()
    assert rev_list["pagination"]["total"] == 1
    assert rev_list["items"][0]["payload"]["message"] == "classified"
    assert rev_list["items"][0]["visibility_kind"] == "Private"


@pytest.mark.parametrize(
    "visibility",
    [
        {"kind": "Public"},
        {"kind": "Private", "agents": ["reviewer"]},
        {"kind": "Labelled", "required_labels": ["admin"]},
        {"kind": "Tenant", "tenant_id": "tenant-alpha"},
        {"kind": "After", "ttl": "PT1H", "then": {"kind": "Public"}},
        {"kind": "After", "ttl": "P1H"},
        AfterVisibility(ttl=timedelta(days=1)).model_dump(mode="json"),
    ],
)
def test_artifact_publish_accepts_valid_visibility(visibility):
    client, _ = _create_test_app_and_orchestrator(enforce_visibility=True)

    response = client.post(
        "/api/v1/artifacts",
        json={
            "type": "VisibleItem",
            "payload": {"message": "valid"},
            "visibility": visibility,
        },
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "visibility",
    [
        {"kind": "private", "agents": ["reviewer"]},
        {"kind": "Unknown"},
        {"agents": ["reviewer"]},
        {"kind": "Labelled", "required_labels": []},
        {"kind": "Tenant"},
        {"kind": "After", "ttl": "not-a-duration"},
        {"kind": "After", "ttl": "PT0S"},
        {"kind": "After", "ttl": "PT1H", "then": {"kind": "Unknown"}},
        {"kind": "After", "ttl": "PT1H", "thne": {"kind": "Private"}},
    ],
)
def test_artifact_publish_rejects_invalid_visibility(visibility):
    """Malformed access rules must fail closed instead of becoming Public."""
    client, _ = _create_test_app_and_orchestrator(enforce_visibility=True)

    response = client.post(
        "/api/v1/artifacts",
        json={
            "type": "VisibleItem",
            "payload": {"message": "must not become public"},
            "visibility": visibility,
        },
    )

    assert response.status_code == 400
    assert client.get("/api/v1/artifacts").json()["pagination"]["total"] == 0


def test_artifact_publish_rejects_misspelled_visibility_field():
    client, _ = _create_test_app_and_orchestrator(enforce_visibility=True)

    response = client.post(
        "/api/v1/artifacts",
        json={
            "type": "VisibleItem",
            "payload": {"message": "must not become public"},
            "visiblity": {"kind": "Private", "agents": ["reviewer"]},
        },
    )

    assert response.status_code == 422
    assert client.get("/api/v1/artifacts").json()["pagination"]["total"] == 0
