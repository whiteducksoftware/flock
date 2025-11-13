"""Models for ServerComponents."""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# MCP Models
# ============================================================================
class AgentInformation(BaseModel):
    """Contains the name of an Agent as well as a short description of the Agent."""

    name: str = Field(..., description="Name of the Agent")
    description: str = Field(..., description="Description of the Agent.")


class AgentList(BaseModel):
    """Contains a list of all available Agents."""

    available_agents: list[AgentInformation] = Field(
        ..., description="List of all available Agents."
    )


class AgentInput(BaseModel):
    """Type annotaded input for Agents.

    For each input an Agent can have,
    this describes the type and the payload.
    """

    type: str = Field(description="Input type name")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Input payload data"
    )


class AgentInvokation(BaseModel):
    """Arguments for invoking a specific Agent."""

    name: str = Field(default="", description="Name of the Agent to invoke.")

    inputs: list[AgentInput] = Field(
        default_factory=list,
        description="List of inputs for the Agent",
    )


class ArtifactResult(BaseModel):
    """Artifact produced by an Agent."""

    id: str = Field(description="Artifact UUID")
    type: str = Field(description="Artifact type name")
    payload: dict[str, Any] = Field(description="Artifact payload data")
    produced_by: str = Field(
        description="Name of the Agent that produced this artifact"
    )


class AgentInvokationResult(BaseModel):
    """Result of a direct invokation of an Agent."""

    artifacts: list[ArtifactResult] = Field(
        default_factory=list, description="Artifacts produced by the Agent."
    )


class AgentInvokationError(BaseModel):
    """Error that resulted from an erronious invokation of an Agent."""

    message: str = Field(description="Message with the Error and Reason for failure")


# ============================================================================
# MCP Unified Response Models (Single-Type for Better Schema Generation)
# ============================================================================


class MCPAgentInvokationResponse(BaseModel):
    """Unified response for MCP agent invocation tool.

    Combines success and error states into a single model for better
    MCP tool schema generation (avoids union types that get stripped).
    """

    success: bool = Field(
        description="True if agent invocation succeeded, False if it failed"
    )
    artifacts: list[ArtifactResult] | None = Field(
        default=None,
        description="Artifacts produced by the agent (only present when success=True)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message explaining what went wrong (only present when success=False)",
    )


class MCPArtifactPublishResponse(BaseModel):
    """Unified response for MCP artifact publish tool.

    Combines success and error states into a single model.
    """

    success: bool = Field(
        description="True if artifact was published successfully, False if it failed"
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracking the triggered workflow (only present when success=True)",
    )
    published_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when artifact was published (only present when success=True)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message explaining why publication failed (only present when success=False)",
    )


class MCPWorkflowStatusResponse(BaseModel):
    """Unified response for MCP workflow status tool.

    Combines success and error states into a single model.
    """

    success: bool = Field(
        description="True if workflow status was retrieved successfully, False if it failed"
    )
    correlation_id: str | None = Field(
        default=None, description="The correlation ID (only present when success=True)"
    )
    state: str | None = Field(
        default=None,
        description="Workflow state: 'active', 'completed', 'failed', 'not_found' (only present when success=True)",
    )
    has_pending_work: bool | None = Field(
        default=None,
        description="Whether the orchestrator has pending work (only present when success=True)",
    )
    artifact_count: int | None = Field(
        default=None,
        description="Total number of artifacts with this correlation_id (only present when success=True)",
    )
    error_count: int | None = Field(
        default=None,
        description="Number of WorkflowError artifacts (only present when success=True)",
    )
    started_at: str | None = Field(
        default=None,
        description="Timestamp of first artifact ISO 8601 (only present when success=True)",
    )
    last_activity_at: str | None = Field(
        default=None,
        description="Timestamp of most recent artifact ISO 8601 (only present when success=True)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if status lookup failed (only present when success=False)",
    )


class MCPArtifactSummaryResponse(BaseModel):
    """Unified response for MCP artifact summary tool.

    Combines success and error states into a single model.
    """

    success: bool = Field(
        description="True if summary was generated successfully, False if it failed"
    )
    summary: dict[str, Any] | None = Field(
        default=None,
        description="Summary statistics about artifacts (only present when success=True)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message explaining why summary failed (only present when success=False)",
    )


class MCPArtifactTypeNamesResponse(BaseModel):
    """Unified response for MCP artifact type names tool.

    Combines success and error states into a single model.
    """

    success: bool = Field(
        description="True if type names were retrieved successfully, False if it failed"
    )
    type_names: list[str] | None = Field(
        default=None,
        description="List of all publicly visible artifact type names (only present when success=True)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message explaining why retrieval failed (only present when success=False)",
    )


class MCPArtifactSchemaResponse(BaseModel):
    """Unified response for MCP artifact schema tool.

    Combines success and error states into a single model.
    """

    success: bool = Field(
        description="True if schema was retrieved successfully, False if it failed"
    )
    type_name: str | None = Field(
        default=None,
        description="The artifact type name (only present when success=True)",
    )
    artifact_schema: dict[str, Any] | None = Field(
        default=None,
        description="Full JSON schema for the artifact type (only present when success=True)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message explaining why schema retrieval failed (only present when success=False)",
    )


class MCPArtifactListResponse(BaseModel):
    """Unified response for MCP list artifacts tool.

    Combines success and error states into a single model.
    """

    success: bool = Field(
        description="True if artifacts were listed successfully, False if it failed"
    )
    items: list[dict[str, Any]] | None = Field(
        default=None,
        description="List of artifacts with full metadata (only present when success=True)",
    )
    total: int | None = Field(
        default=None,
        description="Total number of artifacts matching query (only present when success=True)",
    )
    limit: int | None = Field(
        default=None,
        description="Number of items per page (only present when success=True)",
    )
    offset: int | None = Field(
        default=None,
        description="Offset into the result set (only present when success=True)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message explaining why listing failed (only present when success=False)",
    )


class MCPArtifactResponse(BaseModel):
    """Unified response for MCP get artifact by ID tool.

    Combines success and error states into a single model.
    """

    success: bool = Field(
        description="True if artifact was retrieved successfully, False if it failed"
    )
    artifact: dict[str, Any] | None = Field(
        default=None,
        description="Complete artifact data including payload and metadata (only present when success=True)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message explaining why retrieval failed (only present when success=False)",
    )



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
    """Contains a list of all available Agents."""

    agents: list[Agent] = Field(description="List of all registered agents")


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


__all__ = [
    "Agent",
    "AgentList",
    "AgentRunInput",
    "AgentRunRequest",
    "AgentRunResponse",
    "AgentSubscription",
    "CorrelationStatusResponse",
    "ProducedArtifact",
]
