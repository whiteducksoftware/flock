"""ServerComponent used to interact with artifacts on the Blackboard."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, Query
from pydantic import Field
from starlette.requests import Request

from flock.components.server.artifacts.models import (
    ArtifactListResponse,
    ArtifactPublishRequest,
    ArtifactPublishResponse,
    ArtifactSummaryResponse,
)
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.core.artifacts import Artifact
from flock.core.store import ArtifactEnvelope, ConsumptionRecord, FilterConfig
from flock.core.visibility import AgentIdentity
from flock.storage.artifact_aggregator import ArtifactAggregator
from flock.utils.visibility_utils import deserialize_visibility


class ArtifactComponentConfig(ServerComponentConfig):
    """Configuration for Artifacts Component."""

    prefix: str = Field(
        default="/api/v1/plugin/", description="Optional prefix for all endpoints"
    )
    tags: list[str] = Field(
        default=["Artifacts"],
        description="A list of tags to pass to the endpoints to be listed under.",
    )
    enforce_visibility: bool = Field(
        default=True,
        description="Whether to enforce the Visibility model (Public/Private/Tenant/Labelled) on artifact endpoints.",
    )
    default_identity: AgentIdentity | None = Field(
        default=None,
        description="Optional default identity to use when no caller identity can be resolved.",
    )


class ArtifactsComponent(ServerComponent):
    """ServerComponent that provides Endpoints to interact with artifacts on the Blackboard"""

    name: str = "artifacts"
    config: ArtifactComponentConfig = Field(
        default_factory=ArtifactComponentConfig,
        description="Configuration for the artifact component.",
    )
    priority: int = Field(default=1, description="Registration priority. Default = 1")

    def _serialize_artifact(
        self, artifact, consumptions: list[ConsumptionRecord] | None = None
    ) -> dict[str, Any]:
        data = {
            "id": str(artifact.id),
            "type": artifact.type,
            "payload": artifact.payload,
            "produced_by": artifact.produced_by,
            "visibility": artifact.visibility.model_dump(mode="json"),
            "visibility_kind": getattr(artifact.visibility, "kind", "Unknown"),
            "created_at": artifact.created_at.isoformat(),
            "correlation_id": str(artifact.correlation_id)
            if artifact.correlation_id
            else None,
            "partition_key": artifact.partition_key,
            "tags": sorted(artifact.tags),
            "version": artifact.version,
        }
        if consumptions is not None:
            data["consumptions"] = [
                {
                    "artifact_id": str(record.artifact_id),
                    "consumer": record.consumer,
                    "run_id": record.run_id,
                    "correlation_id": record.correlation_id,
                    "consumed_at": record.consumed_at.isoformat(),
                }
                for record in consumptions
            ]
            data["consumed_by"] = sorted({record.consumer for record in consumptions})
        return data

    def _parse_datetime(
        self,
        value: str | None,
        label: str,
    ) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:  # pragma: no cover - FastAPI converts
            raise HTTPException(
                status_code=400, detail=f"Invalid {label}: {value}"
            ) from exc

    def _make_filter_config(
        self,
        type_names: list[str] | None,
        produced_by: list[str] | None,
        correlation_id: str | None,
        tags: list[str] | None,
        visibility: list[str] | None,
        start: str | None,
        end: str | None,
    ) -> FilterConfig:
        return FilterConfig(
            type_names=set(type_names) if type_names else None,
            produced_by=set(produced_by) if produced_by else None,
            correlation_id=correlation_id,
            tags=set(tags) if tags else None,
            visibility=set(visibility) if visibility else None,
            start=self._parse_datetime(start, "from"),
            end=self._parse_datetime(end, "to"),
        )

    def _resolve_identity(self, request: Request) -> AgentIdentity:
        """Resolve caller into an AgentIdentity for visibility enforcement."""
        # 1. From request.state (e.g. set by auth middleware or prior component)
        state_ident = getattr(request.state, "identity", None) or getattr(
            request.state, "agent_identity", None
        )
        if isinstance(state_ident, AgentIdentity):
            return state_ident
        if isinstance(state_ident, dict):
            return AgentIdentity(**state_ident)

        # 2. From request headers
        agent_name = request.headers.get("x-agent-name") or request.headers.get(
            "x-flock-agent-name"
        )
        tenant_id = request.headers.get("x-tenant-id") or request.headers.get(
            "x-flock-tenant-id"
        )
        raw_labels = request.headers.get("x-agent-labels") or request.headers.get(
            "x-flock-agent-labels"
        )
        if agent_name or tenant_id or raw_labels:
            labels = (
                {label.strip() for label in raw_labels.split(",") if label.strip()}
                if raw_labels
                else set()
            )
            return AgentIdentity(
                name=agent_name or "anonymous",
                labels=labels,
                tenant_id=tenant_id,
            )

        # 3. Configured default identity, or anonymous
        if self.config.default_identity is not None:
            return self.config.default_identity

        return AgentIdentity(name="__anonymous__", labels=set(), tenant_id=None)

    def configure(self, app, orchestrator):
        # No - op
        pass

    def register_routes(self, app, orchestrator):
        @app.post(
            self._join_path(self.config.prefix, "artifacts"),
            response_model=ArtifactPublishResponse,
            tags=self.config.tags,
        )
        async def publish_artifact(
            body: ArtifactPublishRequest,
        ) -> ArtifactPublishResponse:
            # A generated correlation id ties the cascade this publish triggers
            # together; it is artifact metadata, not payload.
            try:
                visibility = None
                if body.visibility is not None:
                    visibility = deserialize_visibility(body.visibility)
                tags = set(body.tags) if body.tags else None
                await orchestrator.publish(
                    {"type": body.type, "payload": body.payload},
                    correlation_id=str(uuid4()),
                    visibility=visibility,
                    tags=tags,
                    partition_key=body.partition_key,
                )
            except Exception as exc:  # pragma: no cover - FastAPI converts
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return ArtifactPublishResponse(status="accepted")

        @app.get(
            self._join_path(self.config.prefix, "artifacts"),
            response_model=ArtifactListResponse,
            tags=self.config.tags,
        )
        async def list_artifacts(
            request: Request,
            type_names: list[str] | None = Query(None, alias="type"),
            produced_by: list[str] | None = Query(None),
            correlation_id: str | None = None,
            tag: list[str] | None = Query(None),
            start: str | None = Query(None, alias="from"),
            end: str | None = Query(None, alias="to"),
            visibility: list[str] | None = Query(None),
            limit: int = Query(50, ge=1, le=500),
            offset: int = Query(0, ge=0),
            embed_meta: bool = Query(False, alias="embed_meta"),
        ) -> ArtifactListResponse:
            identity = self._resolve_identity(request)
            filters = self._make_filter_config(
                type_names=type_names,
                produced_by=produced_by,
                correlation_id=correlation_id,
                tags=tag,
                visibility=visibility,
                start=start,
                end=end,
            )

            if not self.config.enforce_visibility:
                artifacts, total = await orchestrator.store.query_artifacts(
                    filters,
                    limit=limit,
                    offset=offset,
                    embed_meta=embed_meta,
                )
                items: list[dict[str, Any]] = []
                for artifact in artifacts:
                    if isinstance(artifact, ArtifactEnvelope):
                        items.append(
                            self._serialize_artifact(
                                artifact.artifact, artifact.consumptions
                            )
                        )
                    else:
                        items.append(self._serialize_artifact(artifact))
                return ArtifactListResponse(
                    items=items,
                    pagination={"limit": limit, "offset": offset, "total": total},
                )

            # Query all matching records and filter by allowed visibility for caller
            all_envelopes, _ = await orchestrator.store.query_artifacts(
                filters,
                limit=0,
                offset=0,
                embed_meta=embed_meta,
            )
            visible_artifacts = []
            for item in all_envelopes:
                art = item.artifact if isinstance(item, ArtifactEnvelope) else item
                if art.visibility.allows(identity):
                    visible_artifacts.append(item)

            total = len(visible_artifacts)
            paged_slice = visible_artifacts[offset : offset + limit]

            items = []
            for artifact in paged_slice:
                if isinstance(artifact, ArtifactEnvelope):
                    items.append(
                        self._serialize_artifact(
                            artifact.artifact, artifact.consumptions
                        )
                    )
                else:
                    items.append(self._serialize_artifact(artifact))

            return ArtifactListResponse(
                items=items,
                pagination={"limit": limit, "offset": offset, "total": total},
            )

        @app.get(
            self._join_path(self.config.prefix, "artifacts/summary"),
            response_model=ArtifactSummaryResponse,
            tags=self.config.tags,
        )
        async def summarize_artifacts(
            request: Request,
            type_names: list[str] | None = Query(None, alias="type"),
            produced_by: list[str] | None = Query(None),
            correlation_id: str | None = None,
            tag: list[str] | None = Query(None),
            start: str | None = Query(None, alias="from"),
            end: str | None = Query(None, alias="to"),
            visibility: list[str] | None = Query(None),
        ) -> ArtifactSummaryResponse:
            identity = self._resolve_identity(request)
            filters = self._make_filter_config(
                type_names=type_names,
                produced_by=produced_by,
                correlation_id=correlation_id,
                tags=tag,
                visibility=visibility,
                start=start,
                end=end,
            )

            if not self.config.enforce_visibility:
                summary = await orchestrator.store.summarize_artifacts(filters)
                return ArtifactSummaryResponse(summary=summary)

            # Query all matching artifacts and compute summary solely across visible items
            artifacts, _ = await orchestrator.store.query_artifacts(
                filters=filters,
                limit=0,
                offset=0,
                embed_meta=False,
            )
            allowed = [
                a
                for a in artifacts
                if isinstance(a, Artifact) and a.visibility.allows(identity)
            ]
            is_full_window = filters.start is None and filters.end is None
            summary = ArtifactAggregator().build_summary(
                allowed, len(allowed), is_full_window
            )
            return ArtifactSummaryResponse(summary=summary)

        @app.get(
            self._join_path(self.config.prefix, "artifacts/{artifact_id}"),
            tags=self.config.tags,
        )
        async def get_artifact(artifact_id: UUID, request: Request) -> dict[str, Any]:
            artifact = await orchestrator.store.get(artifact_id)
            if artifact is None:
                raise HTTPException(status_code=404, detail="artifact not found")
            identity = self._resolve_identity(request)
            if self.config.enforce_visibility and not artifact.visibility.allows(
                identity
            ):
                raise HTTPException(status_code=404, detail="artifact not found")
            return self._serialize_artifact(artifact)
