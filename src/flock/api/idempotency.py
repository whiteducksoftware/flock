"""Idempotency layer for REST API endpoints.

Provides caching of responses based on X-Idempotency-Key header to prevent
duplicate request processing.

Spec: 001-sync-idempotent-rest
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fastapi import Header
from starlette.responses import Response


@dataclass
class CachedResponse:
    """Cached HTTP response for idempotency."""

    status_code: int
    body: bytes
    headers: dict[str, str]
    created_at: datetime


class IdempotencyStore(Protocol):
    """Protocol for idempotency stores."""

    async def get(self, key: str) -> CachedResponse | None:
        """Get cached response by key."""
        ...

    async def set(self, key: str, response: CachedResponse, ttl: int) -> None:
        """Store response with TTL in seconds."""
        ...

    async def delete(self, key: str) -> None:
        """Delete cached response."""
        ...


class InMemoryIdempotencyStore:
    """In-memory idempotency store with TTL support.

    Simple implementation for single-instance deployments.
    For distributed deployments, use a Redis-based implementation.
    """

    def __init__(self, default_ttl: int = 86400) -> None:
        """Initialize store with default TTL (24 hours)."""
        self._cache: dict[str, tuple[CachedResponse, datetime]] = {}
        self._default_ttl = default_ttl

    async def get(self, key: str) -> CachedResponse | None:
        """Get cached response if not expired."""
        if key in self._cache:
            response, expires_at = self._cache[key]
            if datetime.now(UTC) < expires_at:
                return response
            # Expired, clean up
            del self._cache[key]
        return None

    async def set(
        self, key: str, response: CachedResponse, ttl: int | None = None
    ) -> None:
        """Store response with TTL."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = datetime.now(UTC) + timedelta(seconds=effective_ttl)
        self._cache[key] = (response, expires_at)

    async def delete(self, key: str) -> None:
        """Delete cached response."""
        self._cache.pop(key, None)

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        now = datetime.now(UTC)
        expired_keys = [
            key for key, (_, expires_at) in self._cache.items() if now >= expires_at
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


class IdempotencyCacheHitError(Exception):
    """Raised when idempotency cache is hit."""

    def __init__(self, cached_response: CachedResponse) -> None:
        self.cached_response = cached_response
        super().__init__("Idempotency cache hit")


# Module-level store instance (singleton for simplicity)
_idempotency_store: InMemoryIdempotencyStore | None = None


def get_idempotency_store() -> InMemoryIdempotencyStore:
    """Get or create the global idempotency store."""
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = InMemoryIdempotencyStore()
    return _idempotency_store


async def check_idempotency(
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
) -> str | None:
    """FastAPI dependency to check idempotency cache.

    If a cached response exists for the key, raises IdempotencyCacheHit.
    Otherwise, returns the key for later caching.
    """
    if idempotency_key is None:
        return None

    store = get_idempotency_store()
    cached = await store.get(idempotency_key)
    if cached:
        raise IdempotencyCacheHitError(cached)
    return idempotency_key


async def cache_response(
    key: str,
    response: Response,
    body: bytes,
    ttl: int = 86400,
) -> None:
    """Cache a response for the given idempotency key."""
    store = get_idempotency_store()

    # Extract headers as dict
    headers = dict(response.headers) if hasattr(response, "headers") else {}

    cached = CachedResponse(
        status_code=response.status_code,
        body=body,
        headers=headers,
        created_at=datetime.now(UTC),
    )
    await store.set(key, cached, ttl)


def make_cached_response(cached: CachedResponse) -> Response:
    """Create a Starlette Response from cached data."""
    return Response(
        content=cached.body,
        status_code=cached.status_code,
        headers=cached.headers,
        media_type=cached.headers.get("content-type", "application/json"),
    )


__all__ = [
    "CachedResponse",
    "IdempotencyCacheHitError",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "cache_response",
    "check_idempotency",
    "get_idempotency_store",
    "make_cached_response",
]
