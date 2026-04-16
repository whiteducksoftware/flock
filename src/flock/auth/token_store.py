"""TokenStore protocol and in-memory implementation."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol

from flock.auth.token_models import TokenCreateRequest, TokenInfo, TokenRecord

logger = logging.getLogger(__name__)

# Audit-log child logger — separate name so operators can route it to its
# own sink (file, syslog, structured pipeline) without changing all flock logs.
audit_logger = logging.getLogger("flock.audit.token")


class TokenStore(Protocol):
    """Protocol for token storage backends."""

    async def store(self, record: TokenRecord) -> None:
        """Store a token record."""
        ...

    async def verify(self, raw_token: str) -> TokenRecord | None:
        """Verify a raw token. Returns record if valid, None if invalid/expired/revoked."""
        ...

    async def revoke(self, prefix: str) -> bool:
        """Revoke a token by prefix. Returns True if found and revoked."""
        ...

    async def list_tokens(self) -> list[TokenInfo]:
        """List all tokens (metadata only, never hashes)."""
        ...


def _hash_token(salt: bytes, raw_token: str) -> str:
    """Hash a raw token with the given salt. Returns hex digest."""
    token_bytes = raw_token.encode("utf-8")
    return hashlib.sha256(salt + token_bytes).hexdigest()


def create_token(request: TokenCreateRequest) -> tuple[str, TokenRecord]:
    """Generate a new token and its record.

    Returns:
        Tuple of (raw_token, record). The raw token must be given to the caller
        exactly once -- it cannot be recovered from the record.
    """
    raw_token = secrets.token_urlsafe(32)
    salt = os.urandom(16)
    token_hash = _hash_token(salt, raw_token)
    token_prefix = raw_token[:8]

    record = TokenRecord(
        token_hash=token_hash,
        salt=salt,
        identity_name=request.identity_name,
        identity_labels=request.identity_labels,
        identity_tenant_id=request.identity_tenant_id,
        allowed_types=request.allowed_types,
        scopes=request.scopes,
        created_at=datetime.now(UTC),
        expires_at=request.expires_at,
        revoked=False,
        token_prefix=token_prefix,
    )

    audit_logger.info(
        "token_created",
        extra={
            "event": "token_created",
            "prefix": token_prefix,
            "identity_name": request.identity_name,
            "scopes": sorted(request.scopes) if request.scopes else [],
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
        },
    )
    return raw_token, record


class InMemoryTokenStore:
    """In-memory token store keyed by prefix for O(1) candidate narrowing.

    Includes a lightweight GC sweep that runs every ``gc_interval``
    verify calls and drops revoked tokens older than ``gc_age`` and
    expired tokens past their TTL.  Bounded growth without a background task.
    """

    def __init__(
        self,
        *,
        gc_interval: int = 100,
        gc_age: timedelta = timedelta(days=7),
    ) -> None:
        # Dict keyed by token_prefix -> list of records (handles prefix collisions)
        self._records: dict[str, list[TokenRecord]] = {}
        self._gc_interval = max(1, gc_interval)
        self._gc_age = gc_age
        self._verify_calls_since_gc = 0

    async def store(self, record: TokenRecord) -> None:
        """Store a token record."""
        if record.token_prefix not in self._records:
            self._records[record.token_prefix] = []
        self._records[record.token_prefix].append(record)

    async def verify(self, raw_token: str) -> TokenRecord | None:
        """Verify a raw token. Returns record if valid, None if invalid/expired/revoked."""
        # Periodic GC sweep — keeps the in-memory dict bounded under churn.
        self._verify_calls_since_gc += 1
        if self._verify_calls_since_gc >= self._gc_interval:
            self._verify_calls_since_gc = 0
            self._gc()

        if len(raw_token) < 8:
            return None

        prefix = raw_token[:8]
        candidates = self._records.get(prefix)
        if not candidates:
            audit_logger.info(
                "token_verify_failed",
                extra={
                    "event": "token_verify_failed",
                    "prefix": prefix,
                    "reason": "unknown_prefix",
                },
            )
            return None

        for record in candidates:
            computed_hash = _hash_token(record.salt, raw_token)
            if secrets.compare_digest(computed_hash, record.token_hash):
                # Found matching record -- check validity
                if record.revoked:
                    audit_logger.info(
                        "token_verify_failed",
                        extra={
                            "event": "token_verify_failed",
                            "prefix": prefix,
                            "identity_name": record.identity_name,
                            "reason": "revoked",
                        },
                    )
                    return None
                if record.expires_at is not None and datetime.now(UTC) >= record.expires_at:
                    audit_logger.info(
                        "token_verify_failed",
                        extra={
                            "event": "token_verify_failed",
                            "prefix": prefix,
                            "identity_name": record.identity_name,
                            "reason": "expired",
                        },
                    )
                    return None
                audit_logger.info(
                    "token_verify_succeeded",
                    extra={
                        "event": "token_verify_succeeded",
                        "prefix": prefix,
                        "identity_name": record.identity_name,
                    },
                )
                return record

        audit_logger.info(
            "token_verify_failed",
            extra={
                "event": "token_verify_failed",
                "prefix": prefix,
                "reason": "hash_mismatch",
            },
        )
        return None

    async def revoke(self, prefix: str) -> bool:
        """Revoke all tokens matching a prefix. Returns True if any were revoked."""
        candidates = self._records.get(prefix)
        if not candidates:
            return False

        revoked_any = False
        for record in candidates:
            if not record.revoked:
                record.revoked = True
                revoked_any = True

        if revoked_any:
            audit_logger.info(
                "token_revoked",
                extra={"event": "token_revoked", "prefix": prefix},
            )
        return revoked_any

    async def list_tokens(self) -> list[TokenInfo]:
        """List all tokens (metadata only)."""
        result: list[TokenInfo] = []
        for records in self._records.values():
            for record in records:
                result.append(
                    TokenInfo(
                        token_prefix=record.token_prefix,
                        identity_name=record.identity_name,
                        identity_labels=record.identity_labels,
                        identity_tenant_id=record.identity_tenant_id,
                        allowed_types=record.allowed_types,
                        scopes=record.scopes,
                        created_at=record.created_at,
                        expires_at=record.expires_at,
                        revoked=record.revoked,
                    )
                )
        return result

    def _gc(self) -> int:
        """Drop revoked tokens older than gc_age and expired tokens.

        Returns the number of records removed.  Called automatically every
        ``gc_interval`` verify() calls; can also be invoked directly by tests.
        """
        now = datetime.now(UTC)
        cutoff = now - self._gc_age
        removed = 0
        empty_prefixes: list[str] = []
        for prefix, records in self._records.items():
            kept: list[TokenRecord] = []
            for r in records:
                # Drop revoked records older than the cutoff
                if r.revoked and r.created_at < cutoff:
                    removed += 1
                    continue
                # Drop expired tokens
                if r.expires_at is not None and now >= r.expires_at:
                    removed += 1
                    continue
                kept.append(r)
            if kept:
                self._records[prefix] = kept
            else:
                empty_prefixes.append(prefix)
        for prefix in empty_prefixes:
            del self._records[prefix]
        if removed:
            audit_logger.info(
                "token_gc",
                extra={"event": "token_gc", "removed": removed},
            )
        return removed
