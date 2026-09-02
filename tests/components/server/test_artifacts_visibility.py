"""Tests for ArtifactsComponent visibility model enforcement (Issue #417)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from flock.components.server.artifacts.artifacts_component import (
    ArtifactComponentConfig,
    ArtifactsComponent,
)
from flock.core import Flock
from flock.core.visibility import PrivateVisibility, TenantVisibility
from flock.registry import flock_type


@flock_type(name="VisibleItem")
class VisibleItem(BaseModel):
    message: str


def _create_test_app_and_orchestrator(enforce_visibility: bool = True):
    app = FastAPI()
    orchestrator = Flock()
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

    # Test GET /api/v1/artifacts/summary (unauthenticated)
    res_sum = client.get("/api/v1/artifacts/summary")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()["summary"]
    assert sum_data["total"] == 1
    assert sum_data["by_visibility"] == {"Public": 1}


@pytest.mark.asyncio
async def test_artifact_visibility_authenticated_reads():
    """Requests with identity headers must see artifacts matching their identity."""
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
    reviewer_headers = {"X-Agent-Name": "reviewer"}
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
    tenant_headers = {"X-Tenant-Id": "tenant-alpha"}
    res_tenant = client.get("/api/v1/artifacts", headers=tenant_headers)
    assert res_tenant.status_code == 200
    tenant_data = res_tenant.json()
    assert tenant_data["pagination"]["total"] == 2
    tenant_item_ids = {item["id"] for item in tenant_data["items"]}
    assert str(pub_art.id) in tenant_item_ids
    assert str(tenant_art.id) in tenant_item_ids
    assert str(priv_art.id) not in tenant_item_ids


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
        "/api/v1/artifacts", headers={"X-Agent-Name": "reviewer"}
    ).json()
    assert rev_list["pagination"]["total"] == 1
    assert rev_list["items"][0]["payload"]["message"] == "classified"
    assert rev_list["items"][0]["visibility_kind"] == "Private"
