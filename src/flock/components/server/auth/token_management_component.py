"""ServerComponent for token management REST endpoints.

Provides CRUD-style endpoints under ``/api/v1/tokens/`` for creating,
listing, and revoking bearer tokens programmatically.

Note: Rate limiting is deferred -- it should be added here (or via
middleware) before exposing these endpoints in production.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from flock.auth.token_models import TokenCreateRequest
from flock.auth.token_store import TokenStore, create_token
from flock.components.server.base import ServerComponent, ServerComponentConfig


# ---------------------------------------------------------------------------
# Request / Response schemas (REST-layer only -- distinct from internal models)
# ---------------------------------------------------------------------------

_DEFAULT_SCOPES = ["artifact:publish", "artifact:read"]


class TokenCreateBody(BaseModel):
    """REST request body for ``POST /api/v1/tokens/``."""

    identity_name: str = Field(
        ..., min_length=1, description="Agent identity name for the token."
    )
    identity_labels: list[str] = Field(
        default_factory=list, description="Labels for the agent identity."
    )
    identity_tenant_id: str | None = Field(
        default=None, description="Optional tenant ID."
    )
    allowed_types: list[str] = Field(
        ..., min_length=1, description="Artifact types the token can access."
    )
    scopes: list[str] | None = Field(
        default=None,
        description="Permission scopes. Defaults to artifact:publish + artifact:read.",
    )
    ttl_hours: float | None = Field(
        default=None,
        ge=0,
        description="Time-to-live in hours. None means the token never expires.",
    )


class TokenCreateResponse(BaseModel):
    """REST response for ``POST /api/v1/tokens/``."""

    token: str = Field(description="Raw bearer token (shown once only).")
    prefix: str = Field(description="First 8 characters of the token.")
    expires_at: str | None = Field(
        default=None, description="ISO-8601 expiry timestamp, or null if never."
    )


class TokenListItem(BaseModel):
    """A single token entry returned by ``GET /api/v1/tokens/``."""

    prefix: str
    identity_name: str
    allowed_types: list[str]
    scopes: list[str]
    created_at: str
    expires_at: str | None
    revoked: bool


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------


class TokenManagementComponentConfig(ServerComponentConfig):
    """Configuration for the token management component."""

    prefix: str = Field(
        default="/api/v1/tokens", description="Base path for token management endpoints."
    )
    tags: list[str] = Field(
        default=["Token Management"],
        description="OpenAPI tags for the token management endpoints.",
    )


class TokenManagementComponent(ServerComponent):
    """REST endpoints for creating, listing, and revoking bearer tokens.

    The component receives a :class:`TokenStore` via its constructor and
    delegates all persistence to it.  Endpoints are intentionally left
    unauthenticated for now -- auth gating will be added when the full
    auth middleware is wired in.

    Note: Rate limiting should be applied to these endpoints before
    production use (see component-level docstring).
    """

    name: str = Field(
        default="token_management", description="Name for the component."
    )
    priority: int = Field(
        default=15,
        description="Registration priority.  After auth middleware (~7) but before most other components.",
    )
    config: TokenManagementComponentConfig = Field(
        default_factory=TokenManagementComponentConfig,
        description="Token management configuration.",
    )

    # Injected dependency -- stored as a private attribute so Pydantic
    # doesn't try to serialise/validate it.
    _token_store: TokenStore | None = None

    def __init__(self, token_store: TokenStore | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._token_store = token_store

    # -- Lifecycle ------------------------------------------------------------

    def configure(self, app: Any, orchestrator: Any) -> None:
        """No middleware needed."""

    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """Register ``/api/v1/tokens/`` endpoints on *app*."""

        store = self._token_store
        if store is None:
            raise RuntimeError(
                "TokenManagementComponent requires a TokenStore instance. "
                "Pass one via token_store= in the constructor."
            )

        prefix = self.config.prefix.rstrip("/")
        tags = self.config.tags

        # TODO: Add rate limiting before production use.

        @app.post(
            f"{prefix}/",
            response_model=TokenCreateResponse,
            status_code=201,
            tags=tags,
        )
        async def create_token_endpoint(body: TokenCreateBody) -> TokenCreateResponse:
            """Create a new bearer token.

            The raw token is returned **once** in this response and cannot be
            retrieved afterwards.
            """
            scopes = body.scopes if body.scopes is not None else list(_DEFAULT_SCOPES)

            expires_at: datetime | None = None
            if body.ttl_hours is not None:
                expires_at = datetime.now(UTC) + timedelta(hours=body.ttl_hours)

            request = TokenCreateRequest(
                identity_name=body.identity_name,
                identity_labels=set(body.identity_labels),
                identity_tenant_id=body.identity_tenant_id,
                allowed_types=set(body.allowed_types),
                scopes=set(scopes),
                expires_at=expires_at,
            )

            raw_token, record = create_token(request)
            await store.store(record)

            return TokenCreateResponse(
                token=raw_token,
                prefix=record.token_prefix,
                expires_at=record.expires_at.isoformat() if record.expires_at else None,
            )

        @app.get(
            f"{prefix}/",
            response_model=list[TokenListItem],
            tags=tags,
        )
        async def list_tokens_endpoint() -> list[TokenListItem]:
            """List all tokens (metadata only -- never exposes hashes)."""
            infos = await store.list_tokens()
            return [
                TokenListItem(
                    prefix=info.token_prefix,
                    identity_name=info.identity_name,
                    allowed_types=sorted(info.allowed_types),
                    scopes=sorted(info.scopes),
                    created_at=info.created_at.isoformat(),
                    expires_at=info.expires_at.isoformat() if info.expires_at else None,
                    revoked=info.revoked,
                )
                for info in infos
            ]

        @app.delete(
            f"{prefix}/{{prefix_id}}",
            status_code=204,
            tags=tags,
        )
        async def revoke_token_endpoint(prefix_id: str) -> None:
            """Revoke a token by its 8-character prefix (soft-delete)."""
            revoked = await store.revoke(prefix_id)
            if not revoked:
                raise HTTPException(status_code=404, detail="Token prefix not found.")

    async def on_startup_async(self, orchestrator: Any) -> None:
        """No async startup needed."""

    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """No async shutdown needed."""

    def get_dependencies(self) -> list[type[ServerComponent]]:
        """No hard dependencies."""
        return []
