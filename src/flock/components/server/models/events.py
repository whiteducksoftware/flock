"""Event models for real-time dashboard.

Defines 5 core event types that capture agent execution lifecycle.
All schemas match DATA_MODEL.md specification exactly.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SubscriptionInfo(BaseModel):
    """Subscription configuration for an agent."""

    from_agents: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    mode: str = "both"  # "both" | "events" | "direct"


class VisibilitySpec(BaseModel):
    """Visibility specification for artifacts.

    Matches visibility types from flock.core.visibility module.
    """

    kind: str  # "Public" | "Private" | "Labelled" | "Tenant" | "After"
    agents: list[str] | None = None  # For Private
    required_labels: list[str] | None = None  # For Labelled
    tenant_id: str | None = None  # For Tenant


class AgentActivatedEvent(BaseModel):
    """Event emitted when agent begins consuming artifacts.

    Corresponds to on_pre_consume lifecycle hook.
    Schema per DATA_MODEL.md lines 53-66.
    """

    # Event metadata
    correlation_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    # Agent identification
    agent_name: str
    agent_id: str  # Same as agent.name (unique per orchestrator)
    run_id: str  # Context.task_id (unique per agent activation)

    # Consumption info
    consumed_types: list[str]  # Artifact types being consumed
    consumed_artifacts: list[str]  # Artifact IDs being consumed

    # Production info
    produced_types: list[str]  # Artifact types this agent can produce

    # Subscription configuration
    subscription_info: SubscriptionInfo

    # Agent metadata
    labels: list[str]
    tenant_id: str | None = None
    max_concurrency: int = 1


class MessagePublishedEvent(BaseModel):
    """Event emitted when artifact is published to blackboard.

    Corresponds to on_post_publish lifecycle hook.
    Schema per DATA_MODEL.md lines 100-115.
    """

    # Event metadata
    correlation_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    # Artifact identification
    artifact_id: str  # UUID
    artifact_type: str  # "Movie", "Tagline", etc.

    # Provenance
    produced_by: str  # agent.name or "external"

    # Content
    payload: dict[str, Any]  # Full artifact.payload

    # Access control
    visibility: VisibilitySpec
    tags: list[str] = Field(default_factory=list)
    partition_key: str | None = None
    version: int = 1

    # Flow tracking (Phase 1: empty, Phase 3: computed from subscription matching)
    consumers: list[str] = Field(default_factory=list)  # [agent.name]


class StreamingOutputEvent(BaseModel):
    """Event emitted when agent generates LLM tokens or logs.

    For Phase 1: This is optional and not fully implemented.
    Schema per DATA_MODEL.md lines 152-159.

    Phase 6 Extension: Added artifact_id for message node streaming in blackboard view.
    """

    # Event metadata
    correlation_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    # Agent identification
    agent_name: str
    run_id: str  # Context.task_id

    # Output info
    output_type: str  # "llm_token" | "log" | "stdout" | "stderr"
    content: str  # Token text or log line
    sequence: int  # Monotonic sequence for ordering
    is_final: bool = False  # True when agent completes this output stream

    # Artifact tracking (Phase 6: for message streaming preview)
    artifact_id: str | None = (
        None  # Pre-generated artifact ID for streaming message nodes
    )
    artifact_type: str | None = (
        None  # Artifact type name (e.g., "__main__.BookOutline")
    )


class AgentCompletedEvent(BaseModel):
    """Event emitted when agent execution finishes successfully.

    Corresponds to on_terminate lifecycle hook.
    Schema per DATA_MODEL.md lines 205-212.
    """

    # Event metadata
    correlation_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    # Agent identification
    agent_name: str
    run_id: str  # Context.task_id

    # Execution metrics
    duration_ms: float  # Execution time in milliseconds
    artifacts_produced: list[str] = Field(default_factory=list)  # [artifact_id]

    # Metrics and state
    metrics: dict[str, Any] = Field(
        default_factory=dict
    )  # {"tokens_used": 1234, "cost": 0.05}
    final_state: dict[str, Any] = Field(default_factory=dict)  # Context.state snapshot


class AgentErrorEvent(BaseModel):
    """Event emitted when agent execution fails.

    Corresponds to on_error lifecycle hook.
    Schema per DATA_MODEL.md lines 247-253.
    """

    # Event metadata
    correlation_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    # Agent identification
    agent_name: str
    run_id: str  # Context.task_id

    # Error details
    error_type: str  # Exception class name
    error_message: str  # Exception message
    traceback: str  # Full Python traceback
    failed_at: str  # ISO timestamp of failure


class CorrelationGroupUpdatedEvent(BaseModel):
    """Event emitted when artifact added to correlation group.

    Phase 1.2: Logic Operations UX Enhancement
    Emitted when an artifact is added to a JoinSpec correlation group
    that has not yet collected all required types.
    """

    # Event metadata
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    # Agent identification
    agent_name: str
    subscription_index: int

    # Correlation group
    correlation_key: str  # "patient_123"

    # Progress
    collected_types: dict[str, int]  # {"XRayImage": 1, "LabResults": 0}
    required_types: dict[str, int]  # {"XRayImage": 1, "LabResults": 1}
    waiting_for: list[str]  # ["LabResults"]

    # Window progress
    elapsed_seconds: float
    expires_in_seconds: float | None  # For time windows
    expires_in_artifacts: int | None  # For count windows

    # Artifact that triggered this event
    artifact_id: str
    artifact_type: str

    is_complete: bool  # Will trigger agent in next orchestrator cycle


class BatchItemAddedEvent(BaseModel):
    """Event emitted when artifact added to batch accumulator.

    Phase 1.2: Logic Operations UX Enhancement
    Emitted when an artifact is added to a BatchSpec accumulator
    that has not yet reached its flush threshold.
    """

    # Event metadata
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    # Agent identification
    agent_name: str
    subscription_index: int

    # Batch progress
    items_collected: int
    items_target: int | None  # None if no size limit
    items_remaining: int | None

    # Timeout progress
    elapsed_seconds: float
    timeout_seconds: float | None
    timeout_remaining_seconds: float | None

    # Trigger prediction
    will_flush: str  # "on_size" | "on_timeout" | "unknown"

    # Artifact that triggered this event
    artifact_id: str
    artifact_type: str


__all__ = [
    "AgentActivatedEvent",
    "AgentCompletedEvent",
    "AgentErrorEvent",
    "BatchItemAddedEvent",
    "CorrelationGroupUpdatedEvent",
    "MessagePublishedEvent",
    "StreamingOutputEvent",
    "SubscriptionInfo",
    "VisibilitySpec",
]
