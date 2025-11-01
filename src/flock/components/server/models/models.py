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
