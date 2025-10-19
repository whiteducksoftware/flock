"""Artifact modelling utilities."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from flock.core.visibility import Visibility, ensure_visibility
from flock.registry import type_registry


class Artifact(BaseModel):
    """Typed artifact stored on the blackboard."""

    id: UUID = Field(default_factory=uuid4)
    type: str
    payload: dict[str, Any]
    produced_by: str
    correlation_id: UUID | None = None
    partition_key: str | None = None
    tags: set[str] = Field(default_factory=set)
    visibility: Visibility = Field(default_factory=lambda: ensure_visibility(None))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1

    def model_dump_payload(self) -> dict[str, Any]:  # pragma: no cover - convenience
        return dict(self.payload)


class ArtifactSpec(BaseModel):
    """Wiring description used for validation on publish."""

    type_name: str
    model: type[BaseModel]

    @classmethod
    def from_model(cls, model: type[BaseModel]) -> ArtifactSpec:
        type_name = type_registry.register(model)
        return cls(type_name=type_name, model=model)

    def build(
        self,
        *,
        produced_by: str,
        data: dict[str, Any],
        visibility: Visibility | None = None,
        correlation_id: UUID | None = None,
        partition_key: str | None = None,
        tags: set[str] | None = None,
        version: int = 1,
        artifact_id: UUID | None = None,  # Phase 6: Optional pre-generated ID
    ) -> Artifact:
        payload_model = self.model(**data)
        artifact_kwargs = {
            "type": self.type_name,
            "payload": payload_model.model_dump(),
            "produced_by": produced_by,
            "visibility": ensure_visibility(visibility),
            "correlation_id": correlation_id,
            "partition_key": partition_key,
            "tags": tags or set(),
            "version": version,
        }

        # Phase 6: Use pre-generated ID if provided (for streaming message preview)
        if artifact_id is not None:
            artifact_kwargs["id"] = artifact_id

        return Artifact(**artifact_kwargs)


class ArtifactEnvelope(BaseModel):
    """Envelope passed to components/engines during evaluation."""

    artifact: Artifact
    state: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "Artifact",
    "ArtifactEnvelope",
    "ArtifactSpec",
]
