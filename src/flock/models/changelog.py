"""Changelog event models for the meta-orchestrator event stream.

The changelog is an append-only, ordered log of every blackboard state change.
Events are never modified after creation — summaries and filtered views are derived.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChangelogEventType(str, Enum):
    """Types of blackboard state changes tracked by the changelog."""

    artifact_published = "artifact_published"
    artifact_consumed = "artifact_consumed"
    agent_snapshot_updated = "agent_snapshot_updated"


class ChangelogEvent(BaseModel):
    """A single changelog entry recording a blackboard state change.

    Sequence numbers are assigned by the store on append — callers
    should leave ``seq`` at its default (0) and read the returned value.
    """

    seq: int = 0
    event_type: ChangelogEventType
    artifact_id: UUID | None = None
    artifact_type: str | None = None
    produced_by: str | None = None
    correlation_id: str | None = None
    visibility: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload_summary: dict[str, Any] = Field(default_factory=dict)


class ChangelogFilter(BaseModel):
    """Filter criteria for changelog queries.

    All fields are optional — an empty filter matches all events.
    Multiple fields are ANDed together.
    """

    artifact_types: set[str] | None = None
    produced_by: set[str] | None = None
    correlation_id: str | None = None
    event_types: set[ChangelogEventType] | None = None

    def matches(self, event: ChangelogEvent) -> bool:
        """Test whether an event passes this filter."""
        if self.artifact_types and event.artifact_type not in self.artifact_types:
            return False
        if self.produced_by and event.produced_by not in self.produced_by:
            return False
        if self.correlation_id and event.correlation_id != self.correlation_id:
            return False
        if self.event_types and event.event_type not in self.event_types:
            return False
        return True


class ChangelogQueryResult(BaseModel):
    """Result of a changelog query, including cursor bounds metadata."""

    events: list[ChangelogEvent] = Field(default_factory=list)
    oldest_available_seq: int = 0
    latest_seq: int = 0


__all__ = [
    "ChangelogEvent",
    "ChangelogEventType",
    "ChangelogFilter",
    "ChangelogQueryResult",
]
