from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GraphTimeRangePreset(str, Enum):
    LAST_5_MIN = "last5min"
    LAST_10_MIN = "last10min"
    LAST_1_HOUR = "last1hour"
    ALL = "all"
    CUSTOM = "custom"


class GraphTimeRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    preset: GraphTimeRangePreset = GraphTimeRangePreset.LAST_10_MIN
    start: datetime | None = None
    end: datetime | None = None


class GraphFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    correlation_id: str | None = None
    time_range: GraphTimeRange = Field(default_factory=GraphTimeRange)
    artifact_types: list[str] = Field(default_factory=list, alias="artifactTypes")
    producers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    visibility: list[str] = Field(default_factory=list)


class GraphRequestOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    include_statistics: bool = Field(default=True, alias="includeStatistics")
    label_offset_strategy: str = Field(default="stack", alias="labelOffsetStrategy")
    limit: int = 500


class GraphRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    view_mode: Literal["agent", "blackboard"] = Field(alias="viewMode")
    filters: GraphFilters = Field(default_factory=GraphFilters)
    options: GraphRequestOptions = Field(default_factory=GraphRequestOptions)


class GraphPosition(BaseModel):
    x: float = 0.0
    y: float = 0.0


class GraphMarker(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str = "arrowclosed"
    width: float = 20.0
    height: float = 20.0


class GraphNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: Literal["agent", "message"]
    data: dict[str, Any] = Field(default_factory=dict)
    position: GraphPosition | None = None
    hidden: bool = False


class GraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    source: str
    target: str
    type: Literal[
        "message_flow", "transformation", "pending_join", "pending_batch"
    ]  # Phase 1.5: Added pending edge types
    label: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    marker_end: GraphMarker | None = Field(default=None, alias="markerEnd")
    hidden: bool = False


class GraphAgentMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total: int = 0
    by_type: dict[str, int] = Field(default_factory=dict, alias="byType")


class GraphStatistics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    produced_by_agent: dict[str, GraphAgentMetrics] = Field(
        default_factory=dict, alias="producedByAgent"
    )
    consumed_by_agent: dict[str, GraphAgentMetrics] = Field(
        default_factory=dict, alias="consumedByAgent"
    )
    artifact_summary: dict[str, Any] = Field(
        default_factory=dict, alias="artifactSummary"
    )


class GraphArtifact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    artifact_id: str = Field(alias="artifactId")
    artifact_type: str = Field(alias="artifactType")
    produced_by: str = Field(alias="producedBy")
    consumed_by: list[str] = Field(default_factory=list, alias="consumedBy")
    published_at: datetime = Field(alias="publishedAt")
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, alias="correlationId")
    visibility_kind: str | None = Field(default=None, alias="visibilityKind")
    tags: list[str] = Field(default_factory=list)


class GraphRun(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    agent_name: str = Field(alias="agentName")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    status: Literal["active", "completed", "error"] = "active"
    consumed_artifacts: list[str] = Field(
        default_factory=list, alias="consumedArtifacts"
    )
    produced_artifacts: list[str] = Field(
        default_factory=list, alias="producedArtifacts"
    )
    duration_ms: float | None = Field(default=None, alias="durationMs")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = Field(default=None, alias="errorMessage")


class GraphState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    consumptions: dict[str, list[str]] = Field(default_factory=dict)
    runs: list[GraphRun] = Field(default_factory=list)
    agent_status: dict[str, str] = Field(default_factory=dict, alias="agentStatus")


class GraphSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    generated_at: datetime = Field(alias="generatedAt")
    view_mode: Literal["agent", "blackboard"] = Field(alias="viewMode")
    filters: GraphFilters
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    statistics: GraphStatistics | None = None
    total_artifacts: int = Field(alias="totalArtifacts", default=0)
    truncated: bool = False
