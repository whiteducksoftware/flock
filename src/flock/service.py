from __future__ import annotations


"""HTTP control plane for the blackboard orchestrator."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from flock.registry import type_registry


if TYPE_CHECKING:
    from flock.orchestrator import Flock


class BlackboardHTTPService:
    def __init__(self, orchestrator: Flock) -> None:
        self.orchestrator = orchestrator
        self.app = FastAPI(title="Blackboard Agents Service", version="1.0.0")
        self._register_routes()

    def _register_routes(self) -> None:
        app = self.app
        orchestrator = self.orchestrator

        @app.post("/api/v1/artifacts")
        async def publish_artifact(body: dict[str, Any]) -> dict[str, str]:
            type_name = body.get("type")
            payload = body.get("payload") or {}
            if not type_name:
                raise HTTPException(status_code=400, detail="type is required")
            try:
                await orchestrator.publish({"type": type_name, **payload})
            except Exception as exc:  # pragma: no cover - FastAPI converts
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"status": "accepted"}

        @app.get("/api/v1/artifacts/{artifact_id}")
        async def get_artifact(artifact_id: UUID) -> dict[str, Any]:
            artifact = await orchestrator.store.get(artifact_id)
            if artifact is None:
                raise HTTPException(status_code=404, detail="artifact not found")
            return {
                "id": str(artifact.id),
                "type": artifact.type,
                "payload": artifact.payload,
                "produced_by": artifact.produced_by,
                "visibility": artifact.visibility.model_dump(mode="json"),
                "created_at": artifact.created_at.isoformat(),
            }

        @app.post("/api/v1/agents/{name}/run")
        async def run_agent(name: str, body: dict[str, Any]) -> dict[str, Any]:
            try:
                agent = orchestrator.get_agent(name)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="agent not found") from exc

            inputs_data: list[dict[str, Any]] = body.get("inputs") or []
            inputs = []
            for item in inputs_data:
                type_name = item.get("type")
                payload = item.get("payload") or {}
                if not type_name:
                    raise HTTPException(status_code=400, detail="Each input requires 'type'.")
                model = type_registry.resolve(type_name)
                instance = model(**payload)
                inputs.append(instance)

            try:
                outputs = await orchestrator.direct_invoke(agent, inputs)
            except Exception as exc:
                raise HTTPException(
                    status_code=500, detail=f"Agent execution failed: {exc}"
                ) from exc

            return {
                "artifacts": [
                    {
                        "id": str(artifact.id),
                        "type": artifact.type,
                        "payload": artifact.payload,
                        "produced_by": artifact.produced_by,
                    }
                    for artifact in outputs
                ]
            }

        @app.get("/api/v1/agents")
        async def list_agents() -> dict[str, Any]:
            return {
                "agents": [
                    {
                        "name": agent.name,
                        "description": agent.description,
                        "subscriptions": [
                            {
                                "types": list(subscription.type_names),
                                "mode": subscription.mode,
                                "delivery": subscription.delivery,
                            }
                            for subscription in agent.subscriptions
                        ],
                        "outputs": [output.spec.type_name for output in agent.outputs],
                    }
                    for agent in orchestrator.agents
                ]
            }

        @app.get("/health")
        async def health() -> dict[str, str]:  # pragma: no cover - trivial
            return {"status": "ok"}

        @app.get("/metrics")
        async def metrics() -> PlainTextResponse:
            lines = [f"blackboard_{key} {value}" for key, value in orchestrator.metrics.items()]
            return PlainTextResponse("\n".join(lines))

    def run(
        self, host: str = "127.0.0.1", port: int = 8000
    ) -> None:  # pragma: no cover - manual execution
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)

    async def run_async(
        self, host: str = "127.0.0.1", port: int = 8000
    ) -> None:  # pragma: no cover - manual execution
        """Run the service asynchronously (for use within async context)."""
        import uvicorn

        config = uvicorn.Config(self.app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()


__all__ = ["BlackboardHTTPService"]
