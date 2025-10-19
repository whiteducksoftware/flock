from __future__ import annotations


"""HTTP control plane for the blackboard orchestrator."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

from flock.api.models import (
    Agent,
    AgentListResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentSubscription,
    ArtifactListResponse,
    ArtifactPublishRequest,
    ArtifactPublishResponse,
    ArtifactSummaryResponse,
    CorrelationStatusResponse,
    HealthResponse,
    ProducedArtifact,
)
from flock.core.store import ArtifactEnvelope, ConsumptionRecord, FilterConfig
from flock.registry import type_registry


if TYPE_CHECKING:
    from flock.core import Flock


class BlackboardHTTPService:
    def __init__(self, orchestrator: Flock) -> None:
        self.orchestrator = orchestrator
        self.app = FastAPI(
            title="Flock REST API Documentation",
            version="1.0.0",
            description="RESTful API for interacting with Flock agents and artifacts",
            openapi_tags=[
                {
                    "name": "Public API",
                    "description": "**Production-ready endpoints** for publishing artifacts, running agents, and querying data. Use these in your applications.",
                },
                {
                    "name": "Health & Metrics",
                    "description": "Monitoring endpoints for health checks and metrics collection.",
                },
            ],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        app = self.app
        orchestrator = self.orchestrator

        def _serialize_artifact(
            artifact,
            consumptions: list[ConsumptionRecord] | None = None,
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
                data["consumed_by"] = sorted({
                    record.consumer for record in consumptions
                })
            return data

        def _parse_datetime(value: str | None, label: str) -> datetime | None:
            if value is None:
                return None
            try:
                return datetime.fromisoformat(value)
            except ValueError as exc:  # pragma: no cover - FastAPI converts
                raise HTTPException(
                    status_code=400, detail=f"Invalid {label}: {value}"
                ) from exc

        def _make_filter_config(
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
                start=_parse_datetime(start, "from"),
                end=_parse_datetime(end, "to"),
            )

        @app.post(
            "/api/v1/artifacts",
            response_model=ArtifactPublishResponse,
            tags=["Public API"],
        )
        async def publish_artifact(
            body: ArtifactPublishRequest,
        ) -> ArtifactPublishResponse:
            try:
                await orchestrator.publish({"type": body.type, **body.payload})
            except Exception as exc:  # pragma: no cover - FastAPI converts
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return ArtifactPublishResponse(status="accepted")

        @app.get(
            "/api/v1/artifacts",
            response_model=ArtifactListResponse,
            tags=["Public API"],
        )
        async def list_artifacts(
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
            filters = _make_filter_config(
                type_names,
                produced_by,
                correlation_id,
                tag,
                visibility,
                start,
                end,
            )
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
                        _serialize_artifact(artifact.artifact, artifact.consumptions)
                    )
                else:
                    items.append(_serialize_artifact(artifact))
            return ArtifactListResponse(
                items=items,
                pagination={"limit": limit, "offset": offset, "total": total},
            )

        @app.get(
            "/api/v1/artifacts/summary",
            response_model=ArtifactSummaryResponse,
            tags=["Public API"],
        )
        async def summarize_artifacts(
            type_names: list[str] | None = Query(None, alias="type"),
            produced_by: list[str] | None = Query(None),
            correlation_id: str | None = None,
            tag: list[str] | None = Query(None),
            start: str | None = Query(None, alias="from"),
            end: str | None = Query(None, alias="to"),
            visibility: list[str] | None = Query(None),
        ) -> ArtifactSummaryResponse:
            filters = _make_filter_config(
                type_names,
                produced_by,
                correlation_id,
                tag,
                visibility,
                start,
                end,
            )
            summary = await orchestrator.store.summarize_artifacts(filters)
            return ArtifactSummaryResponse(summary=summary)

        @app.get("/api/v1/artifacts/{artifact_id}", tags=["Public API"])
        async def get_artifact(artifact_id: UUID) -> dict[str, Any]:
            artifact = await orchestrator.store.get(artifact_id)
            if artifact is None:
                raise HTTPException(status_code=404, detail="artifact not found")
            return _serialize_artifact(artifact)

        @app.post(
            "/api/v1/agents/{name}/run",
            response_model=AgentRunResponse,
            tags=["Public API"],
        )
        async def run_agent(name: str, body: AgentRunRequest) -> AgentRunResponse:
            try:
                agent = orchestrator.get_agent(name)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="agent not found") from exc

            inputs = []
            for item in body.inputs:
                model = type_registry.resolve(item.type)
                instance = model(**item.payload)
                inputs.append(instance)

            try:
                outputs = await orchestrator.direct_invoke(agent, inputs)
            except Exception as exc:
                raise HTTPException(
                    status_code=500, detail=f"Agent execution failed: {exc}"
                ) from exc

            return AgentRunResponse(
                artifacts=[
                    ProducedArtifact(
                        id=str(artifact.id),
                        type=artifact.type,
                        payload=artifact.payload,
                        produced_by=artifact.produced_by,
                    )
                    for artifact in outputs
                ]
            )

        @app.get(
            "/api/v1/agents", response_model=AgentListResponse, tags=["Public API"]
        )
        async def list_agents() -> AgentListResponse:
            return AgentListResponse(
                agents=[
                    Agent(
                        name=agent.name,
                        description=agent.description or "",
                        subscriptions=[
                            AgentSubscription(
                                types=list(subscription.type_names),
                                mode=subscription.mode,
                            )
                            for subscription in agent.subscriptions
                        ],
                        outputs=[output.spec.type_name for output in agent.outputs],
                    )
                    for agent in orchestrator.agents
                ]
            )

        @app.get("/api/v1/agents/{agent_id}/history-summary", tags=["Public API"])
        async def agent_history(
            agent_id: str,
            type_names: list[str] | None = Query(None, alias="type"),
            produced_by: list[str] | None = Query(None),
            correlation_id: str | None = None,
            tag: list[str] | None = Query(None),
            start: str | None = Query(None, alias="from"),
            end: str | None = Query(None, alias="to"),
            visibility: list[str] | None = Query(None),
        ) -> dict[str, Any]:
            filters = _make_filter_config(
                type_names,
                produced_by,
                correlation_id,
                tag,
                visibility,
                start,
                end,
            )
            summary = await orchestrator.store.agent_history_summary(agent_id, filters)
            return {"agent_id": agent_id, "summary": summary}

        @app.get(
            "/api/v1/correlations/{correlation_id}/status",
            response_model=CorrelationStatusResponse,
            tags=["Public API"],
        )
        async def get_correlation_status(
            correlation_id: str,
        ) -> CorrelationStatusResponse:
            """Get the status of a workflow by correlation ID.

            Returns workflow state (active/completed/failed/not_found), pending work status,
            artifact counts, error counts, and timestamps.

            This endpoint is useful for polling to check if a workflow has completed.
            """
            try:
                status = await orchestrator.get_correlation_status(correlation_id)
                return CorrelationStatusResponse(**status)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.get("/health", response_model=HealthResponse, tags=["Health & Metrics"])
        async def health() -> HealthResponse:  # pragma: no cover - trivial
            return HealthResponse(status="ok")

        @app.get("/metrics", tags=["Health & Metrics"])
        async def metrics() -> PlainTextResponse:
            lines = [
                f"blackboard_{key} {value}"
                for key, value in orchestrator.metrics.items()
            ]
            return PlainTextResponse("\n".join(lines))

    def run(
        self, host: str = "127.0.0.1", port: int = 8344
    ) -> None:  # pragma: no cover - manual execution
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)

    async def run_async(
        self, host: str = "127.0.0.1", port: int = 8344
    ) -> None:  # pragma: no cover - manual execution
        """Run the service asynchronously (for use within async context)."""
        import uvicorn

        config = uvicorn.Config(self.app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()


__all__ = ["BlackboardHTTPService"]
