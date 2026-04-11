"""Token models for bearer-token authentication."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenRecord(BaseModel):
    """Internal record for a stored token. Never expose raw token or hash externally."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    token_hash: str = Field(description="SHA-256 hex digest of salt + raw token bytes")
    salt: bytes = Field(description="Per-token 16-byte random salt")
    identity_name: str = Field(description="Agent identity name this token maps to")
    identity_labels: set[str] = Field(
        default_factory=set, description="Labels for the agent identity"
    )
    identity_tenant_id: str | None = Field(
        default=None, description="Tenant ID for the agent identity"
    )
    allowed_types: set[str] = Field(
        default_factory=set,
        description="Artifact types the token can read/publish (e.g. BugReport, CodeReview)",
    )
    scopes: set[str] = Field(
        default_factory=set,
        description="Permission scopes (e.g. artifact:publish, artifact:read, token:manage)",
    )
    created_at: datetime = Field(description="When the token was created")
    expires_at: datetime | None = Field(
        default=None, description="When the token expires (None = never)"
    )
    revoked: bool = Field(default=False, description="Whether the token has been revoked")
    token_prefix: str = Field(
        description="First 8 chars of the raw token for prefix-indexed lookup"
    )


class TokenCreateRequest(BaseModel):
    """Request to create a new token."""

    identity_name: str = Field(description="Agent identity name for the token")
    identity_labels: set[str] = Field(
        default_factory=set, description="Labels for the agent identity"
    )
    identity_tenant_id: str | None = Field(
        default=None, description="Tenant ID for the agent identity"
    )
    allowed_types: set[str] = Field(
        default_factory=set, description="Artifact types this token grants access to"
    )
    scopes: set[str] = Field(
        default_factory=set, description="Permission scopes for the token"
    )
    expires_at: datetime | None = Field(
        default=None, description="Optional expiration time"
    )


class TokenInfo(BaseModel):
    """Public metadata about a token. Never includes hash or raw token."""

    token_prefix: str = Field(description="First 8 chars of the raw token")
    identity_name: str = Field(description="Agent identity name")
    identity_labels: set[str] = Field(default_factory=set)
    identity_tenant_id: str | None = None
    allowed_types: set[str] = Field(default_factory=set)
    scopes: set[str] = Field(default_factory=set)
    created_at: datetime = Field(description="When the token was created")
    expires_at: datetime | None = Field(default=None)
    revoked: bool = Field(default=False)
