"""Tests for InMemoryTokenStore GC and audit logging (Unit 7)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from flock.auth.token_models import TokenCreateRequest
from flock.auth.token_store import InMemoryTokenStore, create_token


# ---------------------------------------------------------------------------
# GC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gc_drops_expired_tokens() -> None:
    store = InMemoryTokenStore(gc_interval=1, gc_age=timedelta(days=7))

    # Token expired one minute ago
    raw, record = create_token(
        TokenCreateRequest(
            identity_name="ephemeral",
            allowed_types={"X"},
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    await store.store(record)

    removed = store._gc()  # noqa: SLF001
    assert removed == 1
    assert await store.list_tokens() == []


@pytest.mark.asyncio
async def test_gc_drops_old_revoked_tokens() -> None:
    store = InMemoryTokenStore(gc_interval=1, gc_age=timedelta(days=7))

    # Record marked as revoked AND old enough to drop
    raw, record = create_token(
        TokenCreateRequest(identity_name="old", allowed_types={"X"})
    )
    record.revoked = True
    record.created_at = datetime.now(UTC) - timedelta(days=8)
    await store.store(record)

    removed = store._gc()  # noqa: SLF001
    assert removed == 1
    assert await store.list_tokens() == []


@pytest.mark.asyncio
async def test_gc_keeps_recently_revoked_tokens() -> None:
    store = InMemoryTokenStore(gc_interval=1, gc_age=timedelta(days=7))

    raw, record = create_token(
        TokenCreateRequest(identity_name="recent", allowed_types={"X"})
    )
    record.revoked = True  # revoked, but created_at = now (recent)
    await store.store(record)

    removed = store._gc()  # noqa: SLF001
    assert removed == 0
    assert len(await store.list_tokens()) == 1


@pytest.mark.asyncio
async def test_gc_keeps_active_tokens() -> None:
    store = InMemoryTokenStore(gc_interval=1, gc_age=timedelta(days=7))

    raw, record = create_token(
        TokenCreateRequest(identity_name="active", allowed_types={"X"})
    )
    await store.store(record)

    removed = store._gc()  # noqa: SLF001
    assert removed == 0
    assert len(await store.list_tokens()) == 1


@pytest.mark.asyncio
async def test_gc_runs_periodically_during_verify() -> None:
    store = InMemoryTokenStore(gc_interval=3, gc_age=timedelta(days=7))

    # Stash one expired record
    raw_expired, expired = create_token(
        TokenCreateRequest(
            identity_name="expired",
            allowed_types={"X"},
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    await store.store(expired)

    # Verify call 1, 2 — no GC yet
    await store.verify("nonexistent_token")
    await store.verify("nonexistent_token")
    assert len(await store.list_tokens()) == 1

    # Verify call 3 → GC triggers
    await store.verify("nonexistent_token")
    assert len(await store.list_tokens()) == 0


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_on_token_creation(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="flock.audit.token")

    raw, record = create_token(
        TokenCreateRequest(identity_name="auditme", allowed_types={"X"})
    )

    matching = [r for r in caplog.records if r.message == "token_created"]
    assert len(matching) == 1
    rec = matching[0]
    assert getattr(rec, "identity_name", None) == "auditme"
    assert getattr(rec, "prefix", None) == record.token_prefix


@pytest.mark.asyncio
async def test_audit_log_on_verify_success(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="flock.audit.token")
    store = InMemoryTokenStore()

    raw, record = create_token(
        TokenCreateRequest(identity_name="verifyme", allowed_types={"X"})
    )
    await store.store(record)
    caplog.clear()

    await store.verify(raw)

    matching = [r for r in caplog.records if r.message == "token_verify_succeeded"]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_audit_log_on_verify_failure_unknown_prefix(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="flock.audit.token")
    store = InMemoryTokenStore()

    await store.verify("nonexistent_token_xxx")

    failures = [
        r
        for r in caplog.records
        if r.message == "token_verify_failed"
        and getattr(r, "reason", None) == "unknown_prefix"
    ]
    assert len(failures) == 1


@pytest.mark.asyncio
async def test_audit_log_on_revoke(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="flock.audit.token")
    store = InMemoryTokenStore()
    raw, record = create_token(
        TokenCreateRequest(identity_name="revokeme", allowed_types={"X"})
    )
    await store.store(record)
    caplog.clear()

    await store.revoke(record.token_prefix)

    matching = [r for r in caplog.records if r.message == "token_revoked"]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_audit_log_on_verify_failure_revoked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="flock.audit.token")
    store = InMemoryTokenStore()
    raw, record = create_token(
        TokenCreateRequest(identity_name="x", allowed_types={"X"})
    )
    await store.store(record)
    await store.revoke(record.token_prefix)
    caplog.clear()

    await store.verify(raw)

    failures = [
        r
        for r in caplog.records
        if r.message == "token_verify_failed"
        and getattr(r, "reason", None) == "revoked"
    ]
    assert len(failures) == 1
