"""Tests for the /api/v1/tokens/ REST endpoints (TokenManagementComponent).

Covers: create, list, revoke tokens, plus edge cases and error paths.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from flock.auth.token_store import InMemoryTokenStore
from flock.components.server.auth.token_management_component import (
    TokenManagementComponent,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def token_store() -> InMemoryTokenStore:
    """Fresh in-memory token store for each test."""
    return InMemoryTokenStore()


@pytest.fixture
def app(token_store: InMemoryTokenStore) -> FastAPI:
    """FastAPI app with TokenManagementComponent routes registered."""
    app = FastAPI()
    component = TokenManagementComponent(token_store=token_store)
    component.register_routes(app, orchestrator=None)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Async HTTP client wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Happy path: Create token
# ---------------------------------------------------------------------------


class TestCreateToken:
    """POST /api/v1/tokens/ happy-path tests."""

    @pytest.mark.asyncio
    async def test_create_token_returns_raw_token_and_prefix(self, client: AsyncClient):
        """Should return a raw token, its 8-char prefix, and expiry info."""
        response = await client.post(
            "/api/v1/tokens/",
            json={
                "identity_name": "agent-a",
                "allowed_types": ["BugReport"],
                "ttl_hours": 24,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "token" in data
        assert len(data["token"]) > 8
        assert data["prefix"] == data["token"][:8]
        assert data["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_create_token_no_ttl_returns_null_expires(self, client: AsyncClient):
        """Token created without ttl_hours should have expires_at=null."""
        response = await client.post(
            "/api/v1/tokens/",
            json={
                "identity_name": "forever-agent",
                "allowed_types": ["CodeReview"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is None

    @pytest.mark.asyncio
    async def test_create_token_default_scopes(
        self, client: AsyncClient, token_store: InMemoryTokenStore
    ):
        """When scopes are omitted, defaults to artifact:publish + artifact:read."""
        response = await client.post(
            "/api/v1/tokens/",
            json={
                "identity_name": "default-scope-agent",
                "allowed_types": ["Report"],
            },
        )
        assert response.status_code == 201

        infos = await token_store.list_tokens()
        assert len(infos) == 1
        assert sorted(infos[0].scopes) == ["artifact:publish", "artifact:read"]

    @pytest.mark.asyncio
    async def test_create_token_custom_scopes(
        self, client: AsyncClient, token_store: InMemoryTokenStore
    ):
        """Custom scopes should override the defaults."""
        response = await client.post(
            "/api/v1/tokens/",
            json={
                "identity_name": "admin-agent",
                "allowed_types": ["Report"],
                "scopes": ["token:manage"],
            },
        )
        assert response.status_code == 201

        infos = await token_store.list_tokens()
        assert len(infos) == 1
        assert sorted(infos[0].scopes) == ["token:manage"]


# ---------------------------------------------------------------------------
# Happy path: List tokens
# ---------------------------------------------------------------------------


class TestListTokens:
    """GET /api/v1/tokens/ happy-path tests."""

    @pytest.mark.asyncio
    async def test_list_tokens_empty(self, client: AsyncClient):
        """Empty store should return an empty list."""
        response = await client.get("/api/v1/tokens/")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_tokens_returns_metadata(self, client: AsyncClient):
        """Listed tokens should include metadata but never the raw token or hash."""
        # Create two tokens
        await client.post(
            "/api/v1/tokens/",
            json={"identity_name": "agent-x", "allowed_types": ["A"]},
        )
        await client.post(
            "/api/v1/tokens/",
            json={"identity_name": "agent-y", "allowed_types": ["B"]},
        )

        response = await client.get("/api/v1/tokens/")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2

        for item in items:
            assert "prefix" in item
            assert "identity_name" in item
            assert "allowed_types" in item
            assert "scopes" in item
            assert "created_at" in item
            assert "revoked" in item
            # Must never expose sensitive data
            assert "token" not in item
            assert "token_hash" not in item
            assert "salt" not in item

    @pytest.mark.asyncio
    async def test_list_tokens_shows_revoked_status(self, client: AsyncClient):
        """After revoking a token, list should show revoked=true."""
        create_resp = await client.post(
            "/api/v1/tokens/",
            json={"identity_name": "revoke-me", "allowed_types": ["X"]},
        )
        prefix = create_resp.json()["prefix"]

        # Revoke it
        await client.delete(f"/api/v1/tokens/{prefix}")

        # List and verify
        list_resp = await client.get("/api/v1/tokens/")
        items = list_resp.json()
        assert len(items) == 1
        assert items[0]["revoked"] is True


# ---------------------------------------------------------------------------
# Happy path: Revoke token
# ---------------------------------------------------------------------------


class TestRevokeToken:
    """DELETE /api/v1/tokens/{prefix} happy-path tests."""

    @pytest.mark.asyncio
    async def test_revoke_returns_204(self, client: AsyncClient):
        """Successful revocation should return 204 No Content."""
        create_resp = await client.post(
            "/api/v1/tokens/",
            json={"identity_name": "doomed-agent", "allowed_types": ["Y"]},
        )
        prefix = create_resp.json()["prefix"]

        response = await client.delete(f"/api/v1/tokens/{prefix}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_revoke_then_verify_returns_none(
        self,
        client: AsyncClient,
        token_store: InMemoryTokenStore,
    ):
        """After revoking, verifying the raw token should return None."""
        create_resp = await client.post(
            "/api/v1/tokens/",
            json={"identity_name": "revoked-agent", "allowed_types": ["Z"]},
        )
        data = create_resp.json()
        raw_token = data["token"]
        prefix = data["prefix"]

        # Token should be valid before revocation
        record = await token_store.verify(raw_token)
        assert record is not None

        # Revoke
        await client.delete(f"/api/v1/tokens/{prefix}")

        # Token should now be invalid
        record = await token_store.verify(raw_token)
        assert record is None


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    """Error and edge case scenarios."""

    @pytest.mark.asyncio
    async def test_create_empty_identity_name_returns_422(self, client: AsyncClient):
        """Empty identity_name should be rejected by validation."""
        response = await client.post(
            "/api/v1/tokens/",
            json={"identity_name": "", "allowed_types": ["A"]},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_missing_identity_name_returns_422(self, client: AsyncClient):
        """Missing identity_name field should be rejected by validation."""
        response = await client.post(
            "/api/v1/tokens/",
            json={"allowed_types": ["A"]},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_empty_allowed_types_returns_422(self, client: AsyncClient):
        """Empty allowed_types list should be rejected by validation."""
        response = await client.post(
            "/api/v1/tokens/",
            json={"identity_name": "agent", "allowed_types": []},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_missing_allowed_types_returns_422(self, client: AsyncClient):
        """Missing allowed_types field should be rejected by validation."""
        response = await client.post(
            "/api/v1/tokens/",
            json={"identity_name": "agent"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_prefix_returns_404(self, client: AsyncClient):
        """Revoking a prefix that doesn't exist should return 404."""
        response = await client.delete("/api/v1/tokens/ZZZZZZZZ")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_no_token_store_raises_on_register(self):
        """Component without a token store should raise at route registration time."""
        app = FastAPI()
        component = TokenManagementComponent(token_store=None)
        with pytest.raises(RuntimeError, match="requires a TokenStore"):
            component.register_routes(app, orchestrator=None)
