"""Tests for token-based authentication (Unit 5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from flock.auth.token_models import TokenCreateRequest, TokenInfo, TokenRecord
from flock.auth.token_store import InMemoryTokenStore, create_token


# ---------------------------------------------------------------------------
# Happy path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_store_verify_roundtrip():
    """Generate token -> store -> verify with raw token -> returns correct identity."""
    store = InMemoryTokenStore()
    request = TokenCreateRequest(
        identity_name="claude-code",
        identity_labels={"external", "ci"},
        identity_tenant_id="tenant-42",
        scopes={"artifact:publish", "artifact:read"},
    )

    raw_token, record = create_token(request)
    await store.store(record)

    verified = await store.verify(raw_token)
    assert verified is not None
    assert verified.identity_name == "claude-code"
    assert verified.identity_labels == {"external", "ci"}
    assert verified.identity_tenant_id == "tenant-42"
    assert verified.scopes == {"artifact:publish", "artifact:read"}


@pytest.mark.asyncio
async def test_allowed_types_round_trip():
    """Token with allowed_types stores and retrieves correctly."""
    store = InMemoryTokenStore()
    request = TokenCreateRequest(
        identity_name="codex-agent",
        allowed_types={"BugReport", "CodeReview"},
        scopes={"artifact:publish"},
    )

    raw_token, record = create_token(request)
    await store.store(record)

    verified = await store.verify(raw_token)
    assert verified is not None
    assert verified.allowed_types == {"BugReport", "CodeReview"}


@pytest.mark.asyncio
async def test_token_resolves_to_agent_identity():
    """Verified token maps correctly to AgentIdentity fields."""
    from flock.core.visibility import AgentIdentity

    store = InMemoryTokenStore()
    request = TokenCreateRequest(
        identity_name="deploy-bot",
        identity_labels={"deployer"},
        identity_tenant_id="acme-corp",
        scopes={"artifact:publish"},
    )

    raw_token, record = create_token(request)
    await store.store(record)

    verified = await store.verify(raw_token)
    assert verified is not None

    identity = AgentIdentity(
        name=verified.identity_name,
        labels=verified.identity_labels,
        tenant_id=verified.identity_tenant_id,
    )
    assert identity.name == "deploy-bot"
    assert identity.labels == {"deployer"}
    assert identity.tenant_id == "acme-corp"


@pytest.mark.asyncio
async def test_list_tokens_returns_metadata_not_hash():
    """list_tokens returns prefix, scopes, expiry -- never hash or raw token."""
    store = InMemoryTokenStore()
    request = TokenCreateRequest(
        identity_name="agent-x",
        scopes={"artifact:read"},
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )

    raw_token, record = create_token(request)
    await store.store(record)

    token_list = await store.list_tokens()
    assert len(token_list) == 1

    info = token_list[0]
    assert isinstance(info, TokenInfo)
    assert info.token_prefix == raw_token[:8]
    assert info.scopes == {"artifact:read"}
    assert info.expires_at == datetime(2030, 1, 1, tzinfo=UTC)
    assert info.identity_name == "agent-x"

    # Ensure no hash or raw token leaks through the model
    info_dict = info.model_dump()
    assert "token_hash" not in info_dict
    assert "salt" not in info_dict


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_token_rejected():
    """Token past its expires_at is rejected."""
    store = InMemoryTokenStore()
    request = TokenCreateRequest(
        identity_name="expired-agent",
        scopes={"artifact:publish"},
        expires_at=datetime(2020, 1, 1, tzinfo=UTC),  # Already expired
    )

    raw_token, record = create_token(request)
    await store.store(record)

    verified = await store.verify(raw_token)
    assert verified is None


@pytest.mark.asyncio
async def test_revoked_token_rejected():
    """Revoked token is rejected on verify."""
    store = InMemoryTokenStore()
    request = TokenCreateRequest(
        identity_name="revoked-agent",
        scopes={"artifact:publish"},
    )

    raw_token, record = create_token(request)
    await store.store(record)

    # Revoke it
    result = await store.revoke(raw_token[:8])
    assert result is True

    # Now verify should fail
    verified = await store.verify(raw_token)
    assert verified is None


@pytest.mark.asyncio
async def test_prefix_collision_handling():
    """Tokens with wrong prefix are still checked (no false positives)."""
    store = InMemoryTokenStore()

    # Create two tokens
    req1 = TokenCreateRequest(identity_name="agent-1", scopes={"artifact:read"})
    req2 = TokenCreateRequest(identity_name="agent-2", scopes={"artifact:publish"})

    raw1, record1 = create_token(req1)
    raw2, record2 = create_token(req2)

    await store.store(record1)
    await store.store(record2)

    # Each token verifies to its own identity
    v1 = await store.verify(raw1)
    assert v1 is not None
    assert v1.identity_name == "agent-1"

    v2 = await store.verify(raw2)
    assert v2 is not None
    assert v2.identity_name == "agent-2"

    # A fabricated token fails
    fake_token = "XXXXXXXX" + "a" * 35
    verified = await store.verify(fake_token)
    assert verified is None


@pytest.mark.asyncio
async def test_token_too_short_rejected():
    """Token shorter than 8 chars is rejected immediately."""
    store = InMemoryTokenStore()
    verified = await store.verify("short")
    assert verified is None


@pytest.mark.asyncio
async def test_revoke_nonexistent_prefix():
    """Revoking a prefix that doesn't exist returns False."""
    store = InMemoryTokenStore()
    result = await store.revoke("nosuchpf")
    assert result is False


# ---------------------------------------------------------------------------
# Auth handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bearer_handler_missing_header():
    """Missing Authorization header returns (False, 401)."""
    from starlette.testclient import TestClient

    from flock.auth.token_store import InMemoryTokenStore
    from flock.components.server.auth.auth_component import make_bearer_token_handler

    store = InMemoryTokenStore()
    handler = make_bearer_token_handler(store)

    # Simulate a request without Authorization header
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/artifacts",
        "headers": [],
        "query_string": b"",
        "state": {},
    }
    from starlette.requests import Request

    request = Request(scope)
    is_auth, response = await handler(request)
    assert is_auth is False
    assert response is not None
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bearer_handler_malformed_token():
    """Malformed bearer token (empty, too short) returns (False, 401)."""
    from flock.auth.token_store import InMemoryTokenStore
    from flock.components.server.auth.auth_component import make_bearer_token_handler

    store = InMemoryTokenStore()
    handler = make_bearer_token_handler(store)

    # Token too short
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/artifacts",
        "headers": [(b"authorization", b"Bearer abc")],
        "query_string": b"",
        "state": {},
    }
    from starlette.requests import Request

    request = Request(scope)
    is_auth, response = await handler(request)
    assert is_auth is False
    assert response is not None
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bearer_handler_invalid_token():
    """Valid format but non-existent token returns (False, 401)."""
    from flock.auth.token_store import InMemoryTokenStore
    from flock.components.server.auth.auth_component import make_bearer_token_handler

    store = InMemoryTokenStore()
    handler = make_bearer_token_handler(store)

    fake_token = "abcdefghijklmnopqrstuvwxyz123456789012345"
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/artifacts",
        "headers": [(b"authorization", f"Bearer {fake_token}".encode())],
        "query_string": b"",
        "state": {},
    }
    from starlette.requests import Request

    request = Request(scope)
    is_auth, response = await handler(request)
    assert is_auth is False
    assert response is not None
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bearer_handler_success_sets_identity():
    """Successful auth sets agent_identity on request.scope['state']."""
    from flock.auth.token_models import TokenCreateRequest
    from flock.auth.token_store import InMemoryTokenStore, create_token
    from flock.components.server.auth.auth_component import make_bearer_token_handler
    from flock.core.visibility import AgentIdentity

    store = InMemoryTokenStore()
    handler = make_bearer_token_handler(store)

    req = TokenCreateRequest(
        identity_name="claude-code",
        identity_labels={"external"},
        identity_tenant_id="tenant-1",
        scopes={"artifact:publish"},
    )
    raw_token, record = create_token(req)
    await store.store(record)

    scope: dict = {
        "type": "http",
        "method": "POST",
        "path": "/api/artifacts",
        "headers": [(b"authorization", f"Bearer {raw_token}".encode())],
        "query_string": b"",
        "state": {},
    }
    from starlette.requests import Request

    request = Request(scope)
    is_auth, response = await handler(request)
    assert is_auth is True
    assert response is None

    # Verify identity was set on scope state
    identity = scope["state"]["agent_identity"]
    assert isinstance(identity, AgentIdentity)
    assert identity.name == "claude-code"
    assert identity.labels == {"external"}
    assert identity.tenant_id == "tenant-1"


# ---------------------------------------------------------------------------
# Integration: handler registration on AuthenticationComponent
# ---------------------------------------------------------------------------


def test_register_bearer_token_handler_on_component():
    """bearer_token handler can be registered on AuthenticationComponent."""
    from flock.auth.token_store import InMemoryTokenStore
    from flock.components.server.auth.auth_component import (
        AuthenticationComponent,
        AuthenticationComponentConfig,
        make_bearer_token_handler,
    )

    store = InMemoryTokenStore()
    handler = make_bearer_token_handler(store)

    component = AuthenticationComponent(
        config=AuthenticationComponentConfig(default_handler="bearer_token")
    )
    component.register_handler("bearer_token", handler)

    # Handler is registered
    assert "bearer_token" in component._handlers
    assert component._handlers["bearer_token"] is handler


def test_register_duplicate_handler_raises():
    """Registering the same handler name twice raises ValueError."""
    from flock.auth.token_store import InMemoryTokenStore
    from flock.components.server.auth.auth_component import (
        AuthenticationComponent,
        AuthenticationComponentConfig,
        make_bearer_token_handler,
    )

    store = InMemoryTokenStore()
    handler = make_bearer_token_handler(store)

    component = AuthenticationComponent(
        config=AuthenticationComponentConfig(default_handler="bearer_token")
    )
    component.register_handler("bearer_token", handler)

    with pytest.raises(ValueError, match="already registered"):
        component.register_handler("bearer_token", handler)


# ---------------------------------------------------------------------------
# Token creation invariants
# ---------------------------------------------------------------------------


def test_create_token_never_stores_raw():
    """create_token returns raw token but the record only has hash + salt + prefix."""
    request = TokenCreateRequest(
        identity_name="test-agent",
        scopes={"artifact:publish"},
    )
    raw_token, record = create_token(request)

    # Raw token is urlsafe base64, ~43 chars
    assert len(raw_token) >= 32
    # Prefix matches
    assert record.token_prefix == raw_token[:8]
    # Record does NOT contain raw token
    record_dict = record.model_dump()
    assert raw_token not in str(record_dict.values())
    # Has hash and salt
    assert len(record.token_hash) == 64  # SHA-256 hex
    assert len(record.salt) == 16


def test_each_token_gets_unique_salt():
    """Each token gets its own random salt."""
    request = TokenCreateRequest(identity_name="agent", scopes={"artifact:read"})
    _, r1 = create_token(request)
    _, r2 = create_token(request)
    assert r1.salt != r2.salt
