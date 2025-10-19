"""Pydantic response models for Flock REST API.

Provides proper OpenAPI schemas for all public API endpoints.
This improves API documentation and enables SDK generation.

All models maintain 100% backwards compatibility with existing wire format.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# Agent Models
# ============================================================================


class AgentSubscription(BaseModel):
    """Subscription configuration for an agent."""

    types: list[str] = Field(description="Artifact types this subscription consumes")
    mode: str = Field(
        description="Subscription mode (e.g., 'both', 'direct', 'events')"
    )


class Agent(BaseModel):
    """Single agent representation."""

    name: str = Field(description="Unique name of the agent")
    description: str = Field(default="", description="Human-readable description")
    subscriptions: list[AgentSubscription] = Field(
        description="List of subscriptions this agent listens to"
    )
    outputs: list[str] = Field(description="Artifact types this agent can produce")


class AgentListResponse(BaseModel):
    """Response for GET /api/v1/agents."""

    agents: list[Agent] = Field(description="List of all registered agents")


# ============================================================================
# Artifact Models
# ============================================================================


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


# ============================================================================
# Agent Run Models
# ============================================================================


class AgentRunInput(BaseModel):
    """Input artifact for agent run."""

    type: str = Field(description="Artifact type name")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Artifact payload data"
    )


class AgentRunRequest(BaseModel):
    """Request body for POST /api/v1/agents/{name}/run."""

    inputs: list[AgentRunInput] = Field(
        default_factory=list, description="List of input artifacts"
    )


class ProducedArtifact(BaseModel):
    """Artifact produced by agent run."""

    id: str = Field(description="Artifact ID (UUID)")
    type: str = Field(description="Artifact type name")
    payload: dict[str, Any] = Field(description="Artifact payload data")
    produced_by: str = Field(description="Name of agent that produced this")


class AgentRunResponse(BaseModel):
    """Response for POST /api/v1/agents/{name}/run."""

    artifacts: list[ProducedArtifact] = Field(
        description="Artifacts produced by the agent run"
    )


# ============================================================================
# Schema Discovery Models
# ============================================================================


class ArtifactTypeSchema(BaseModel):
    """Schema information for an artifact type."""

    model_config = {"populate_by_name": True}  # Allow using 'schema' as field name

    name: str = Field(description="Type name")
    schema_: dict[str, Any] = Field(
        alias="schema", description="JSON Schema for this type"
    )


class ArtifactTypesResponse(BaseModel):
    """Response for GET /api/artifact-types."""

    artifact_types: list[ArtifactTypeSchema] = Field(
        description="List of all registered artifact types with their schemas"
    )


# ============================================================================
# Agent History Models
# ============================================================================


class AgentHistorySummary(BaseModel):
    """Summary of agent execution history."""

    agent_id: str = Field(description="Agent identifier")
    summary: dict[str, Any] = Field(description="History summary statistics")


# ============================================================================
# Correlation Status Models
# ============================================================================


class CorrelationStatusResponse(BaseModel):
    """Response for GET /api/v1/correlations/{correlation_id}/status."""

    correlation_id: str = Field(description="The correlation ID")
    state: Literal["active", "completed", "failed", "not_found"] = Field(
        description="Workflow state: active (work pending), completed (success), failed (only errors), not_found (no artifacts)"
    )
    has_pending_work: bool = Field(
        description="Whether the orchestrator has pending work for this correlation"
    )
    artifact_count: int = Field(
        description="Total number of artifacts with this correlation_id"
    )
    error_count: int = Field(description="Number of WorkflowError artifacts")
    started_at: str | None = Field(
        None, description="Timestamp of first artifact (ISO 8601)"
    )
    last_activity_at: str | None = Field(
        None, description="Timestamp of most recent artifact (ISO 8601)"
    )


# ============================================================================
# Health & Metrics Models
# ============================================================================


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: Literal["ok"] = Field(description="Health status")


__all__ = [
    # Agent models
    "Agent",
    "AgentSubscription",
    "AgentListResponse",
    # Artifact models
    "ArtifactBase",
    "ArtifactWithConsumptions",
    "ArtifactListResponse",
    "ArtifactPublishRequest",
    "ArtifactPublishResponse",
    "ArtifactSummaryResponse",
    "PaginationInfo",
    "ConsumptionRecord",
    # Agent run models
    "AgentRunRequest",
    "AgentRunResponse",
    "ProducedArtifact",
    # Schema discovery
    "ArtifactTypesResponse",
    "ArtifactTypeSchema",
    # History
    "AgentHistorySummary",
    # Correlation status
    "CorrelationStatusResponse",
    # Health
    "HealthResponse",
]
