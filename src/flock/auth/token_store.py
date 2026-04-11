"""TokenStore protocol and in-memory implementation."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime
from typing import Protocol

from flock.auth.token_models import TokenCreateRequest, TokenInfo, TokenRecord


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

    return raw_token, record


class InMemoryTokenStore:
    """In-memory token store keyed by prefix for O(1) candidate narrowing."""

    def __init__(self) -> None:
        # Dict keyed by token_prefix -> list of records (handles prefix collisions)
        self._records: dict[str, list[TokenRecord]] = {}

    async def store(self, record: TokenRecord) -> None:
        """Store a token record."""
        if record.token_prefix not in self._records:
            self._records[record.token_prefix] = []
        self._records[record.token_prefix].append(record)

    async def verify(self, raw_token: str) -> TokenRecord | None:
        """Verify a raw token. Returns record if valid, None if invalid/expired/revoked."""
        if len(raw_token) < 8:
            return None

        prefix = raw_token[:8]
        candidates = self._records.get(prefix)
        if not candidates:
            return None

        for record in candidates:
            computed_hash = _hash_token(record.salt, raw_token)
            if secrets.compare_digest(computed_hash, record.token_hash):
                # Found matching record -- check validity
                if record.revoked:
                    return None
                if record.expires_at is not None and datetime.now(UTC) >= record.expires_at:
                    return None
                return record

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
