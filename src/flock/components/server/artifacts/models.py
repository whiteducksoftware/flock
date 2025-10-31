from typing import Any, Literal

from pydantic import BaseModel, Field


class VisibilityInfo(BaseModel):
    """Artifact visibility configuration."""

    kind: str = Field(description="Visibility kind (e.g., 'Public', 'Private')")
    # Additional visibility fields added dynamically


class ArtifactBase(BaseModel):
    """Base artifact representation with common fields."""

    id: str = Field(description="Unique artifact identifier (UUID)")
    type: str = Field(description="Artifact type name")
    payload: dict[str, Any] = Field(description="Artifact payload data")
    produced_by: str = Field(description="Name of agent/source that produced this")
    visibility: dict[str, Any] = Field(description="Visibility configuration")
    visibility_kind: str = Field(description="Visibility kind (Public/Private/etc)")
    created_at: str = Field(
        description="Timestamp when artifact was created (ISO 8601)"
    )
    correlation_id: str | None = Field(
        None, description="Optional correlation ID for workflow tracking"
    )
    partition_key: str | None = Field(None, description="Optional partition key")
    tags: list[str] = Field(default_factory=list, description="List of tags")
    version: int = Field(description="Artifact version number")


class ConsumptionRecord(BaseModel):
    """Record of an artifact being consumed by an agent."""

    artifact_id: str = Field(description="ID of the artifact that was consumed")
    consumer: str = Field(description="Name of the agent that consumed it")
    run_id: str = Field(description="Run ID of the consumption")
    correlation_id: str = Field(description="Correlation ID of the consumption")
    consumed_at: str = Field(description="Timestamp of consumption (ISO 8601)")


class ArtifactWithConsumptions(ArtifactBase):
    """Artifact with consumption metadata included."""

    consumptions: list[ConsumptionRecord] = Field(
        default_factory=list, description="List of consumption records"
    )
    consumed_by: list[str] = Field(
        default_factory=list,
        description="List of unique agent names that consumed this artifact",
    )


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    limit: int = Field(description="Number of items per page")
    offset: int = Field(description="Offset into the result set")
    total: int = Field(description="Total number of items matching the query")


class ArtifactListResponse(BaseModel):
    """Response for GET /api/v1/artifacts."""

    items: list[ArtifactBase | ArtifactWithConsumptions] = Field(
        description="List of artifacts (may include consumption data if embed_meta=true)"
    )
    pagination: PaginationInfo = Field(description="Pagination information")


class ArtifactPublishRequest(BaseModel):
    """Request body for POST /api/v1/artifacts."""

    type: str = Field(description="Artifact type name")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Artifact payload data"
    )


class ArtifactPublishResponse(BaseModel):
    """Response for POST /api/v1/artifacts."""

    status: Literal["accepted"] = Field(description="Publication status")


class ArtifactSummary(BaseModel):
    """Summary statistics for artifacts."""

    # Define based on actual summary structure from store
    # This is a placeholder - update based on actual implementation


class ArtifactSummaryResponse(BaseModel):
    """Response for GET /api/v1/artifacts/summary."""

    summary: dict[str, Any] = Field(description="Summary statistics")
