"""Endpoints: where sinks deliver, and the secrets they deliver with.

An endpoint names a base URL with its authentication, signing, headers,
timeout, retries and rate limit, so a sink says only ``"myapp:/billing"``.
Secrets are named by their environment variable and read for each request:
they never appear in a sink's configuration, its receipts or its trace.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from flock.decisions.budget import RequestBudget


class MissingSecretError(Exception):
    """The environment variable that holds a secret is not set."""

    def __init__(self, env: str) -> None:
        super().__init__(f"Environment variable {env} is not set")
        self.env = env


def _secret(env: str) -> str:
    value = os.environ.get(env)
    if not value:
        raise MissingSecretError(env)
    return value


@dataclass(frozen=True)
class Bearer:
    """``Authorization: Bearer <secret>``."""

    env: str

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {_secret(self.env)}"}


@dataclass(frozen=True)
class Header:
    """The secret in a header of its own, e.g. ``Header("X-Api-Key", env=...)``."""

    name: str
    env: str

    def headers(self) -> dict[str, str]:
        return {self.name: _secret(self.env)}


@dataclass(frozen=True)
class Hmac:
    """An HMAC-SHA256 signature of the body, as webhook deliveries sign theirs
    (``X-Flock-Signature: sha256=<hex>``)."""

    env: str
    header: str = "X-Flock-Signature"

    def headers(self, body: bytes) -> dict[str, str]:
        # As flock.api.webhooks.sign_payload, without importing the API layer
        digest = hmac.new(_secret(self.env).encode(), body, hashlib.sha256)
        return {self.header: f"sha256={digest.hexdigest()}"}


class Endpoint:
    """A system that sinks deliver to.

    Args:
        url: Base URL; a sink's path is appended (``"myapp:/billing"``).
        auth: ``Bearer(env=...)`` or ``Header(name, env=...)``.
        sign: ``Hmac(env=...)`` signs every body.
        headers: Further headers, without secrets.
        timeout: Seconds per request.
        retries: Retries after a timeout, a connection error, HTTP 408, 429
            or 5xx; 0 fails on the first.
        rate_limit: Request budget shared by every sink of the endpoint,
            ``"N/s"``, ``"N/min"`` or ``"N/h"``.
    """

    def __init__(
        self,
        url: str,
        *,
        auth: Bearer | Header | None = None,
        sign: Hmac | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        retries: int = 5,
        rate_limit: str | None = None,
    ) -> None:
        if urlsplit(url).scheme not in ("http", "https"):
            raise ValueError(
                f"Endpoint URL must start with http:// or https://: {url!r}"
            )
        if retries < 0:
            raise ValueError(f"retries must be >= 0, got {retries}")
        self.url = url.rstrip("/")
        self.auth = auth
        self.sign = sign
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.retries = retries
        self.rate_limit = rate_limit
        try:
            self.budget = RequestBudget.parse(rate_limit) if rate_limit else None
        except ValueError:
            raise ValueError(
                f"Invalid rate limit {rate_limit!r}; use 'N/s', 'N/min' or 'N/h', "
                "for example '100/min'."
            ) from None
        # One client per event loop keeps connections alive between deliveries
        self._client: httpx.AsyncClient | None = None
        self._client_loop: asyncio.AbstractEventLoop | None = None

    def __repr__(self) -> str:
        parts = [repr(self.url)]
        if self.auth is not None:
            parts.append(f"auth={self.auth!r}")
        if self.sign is not None:
            parts.append(f"sign={self.sign!r}")
        if self.rate_limit is not None:
            parts.append(f"rate_limit={self.rate_limit!r}")
        return f"Endpoint({', '.join(parts)})"

    def http(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._client is None or self._client_loop is not loop:
            self._client = httpx.AsyncClient(timeout=self.timeout)
            self._client_loop = loop
        return self._client


@dataclass(frozen=True)
class Target:
    """Where a sink delivers: an endpoint and the path on it."""

    declared: str  # as the sink names it, "myapp:/billing"
    endpoint: Endpoint
    path: str

    @property
    def url(self) -> str:
        return self.endpoint.url + self.path

    @property
    def label(self) -> str:
        """The path for an endpoint's target, host and path for a URL."""
        if "://" in self.declared:
            parts = urlsplit(self.declared)
            return parts.netloc + parts.path
        return self.path


def resolve_target(target: str, endpoints: dict[str, Endpoint]) -> Target:
    """``"name:/path"`` on a known endpoint, or a full ``http(s)://`` URL."""
    if target.startswith(("http://", "https://")):
        return Target(target, Endpoint(target), "")
    name, sep, path = target.partition(":")
    if not sep or not path.startswith("/"):
        raise ValueError(
            f"Sink target {target!r}: use 'endpoint:/path' (e.g. 'myapp:/billing') "
            "or a full http(s):// URL."
        )
    if name not in endpoints:
        known = ", ".join(sorted(endpoints)) or "none"
        raise ValueError(
            f"Sink target {target!r} names unknown endpoint {name!r}; "
            f"Flock(endpoints=...) defines: {known}."
        )
    return Target(target, endpoints[name], path)


__all__ = [
    "Bearer",
    "Endpoint",
    "Header",
    "Hmac",
    "MissingSecretError",
    "Target",
    "resolve_target",
]
