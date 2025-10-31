"""ServerComponent that provides Endpoints for interacting with Agents."""

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.components.server.models.models import (
    Agent,
    AgentListResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentSubscription,
    CorrelationStatusResponse,
    ProducedArtifact,
)
from flock.core.store import FilterConfig
from flock.logging.logging import get_logger
from flock.registry import type_registry


logger = get_logger(__name__)


class AgentsServerComponentConfig(ServerComponentConfig):
    """Configuration class for Agents Component."""

    prefix: str = Field(
        default="/api/v1/plugin/",
        description="Optional prefix for Endpoints. Defaults to (and should stay at) '/api/v1/",
    )
    tags: list[str] = Field(
        default=["Agents", "Public API"], description="A list of tags for OpenAPI spec."
    )


class AgentsServerComponent(ServerComponent):
    """ServerComponent that adds Endpoints for interacting with Agents.

    Provided Endpoints:
    - POST self.config.prefix/agents/{name}/run -> run the agent with agent_name directly
    - GET self.config.prefix/agents -> Returns a list of all available agents
    - GET self.config.prefix/agents/{agent_id}/history-summary -> Returns a summary of the history of the agent
    - GET self.config.prefix/correlations/{correlation_id}/status -> Get the status of a workflow by correlation ID
    """

    name: str = "agents"
    priority: int = Field(
        default=5, description="Registration Priority (defaults to 5)"
    )

    def _parse_datetime(self, value: str | None, label: str) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:  # pragma: no cover - FastAPI converts
            raise HTTPException(
                status_code=400, detail=f"Invalid {label}:{value}"
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

    def configure(self, app: FastAPI, orchestrator):
        return super().configure(app, orchestrator)

    def register_routes(self, app, orchestrator):
        """Register the routes this component provides."""

        # TODO: relevant for MCP-component in the future
        @app.post(
            self._join_path(self.config.prefix, "agents/{name}/run"),
            tags=self.config.tags,
            response_model=AgentRunResponse,
        )
        async def run_agent(name: str, body: AgentRunRequest) -> AgentRunRequest:
            """Invoke an agent directly."""
            try:
                agent = orchestrator.get_agent(name)
            except KeyError as ex:
                logger.exception(f"AgentsComponent: Failed to invoke agent: {ex!s}")
                raise HTTPException(status_code=404, detail="agent not found") from ex
            inputs = []
            for item in body.inputs:
                model = type_registry.resolve(item.type)
                instance = model(**item.payload)
                inputs.append(instance)
            try:
                outputs = await orchestrator.direct_invoke(agent, inputs)
            except Exception as exc:
                logger.exception(
                    f"AgentsComponent: Agent execution for agent {agent.name} failed: {exc!s}"
                )
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
            self._join_path(self.config.prefix, "agents"),
            response_model=AgentListResponse,
            tags=self.config.tags,
        )
        async def list_agents() -> AgentListResponse:
            """List available Agents."""
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

        @app.get(
            self._join_path(self.config.prefix, "agents/{agent_id}/history-summary"),
            tags=self.config.tags,
        )
        async def agent_histroy(
            agent_id: str,
            type_names: list[str] | None = Query(None, alias="type"),
            produced_by: list[str] | None = Query(None),
            correlation_id: str | None = None,
            tag: list[str] | None = Query(None),
            start: str | None = Query(None, alias="from"),
            end: str | None = Query(None, alias="to"),
            visibility: list[str] | None = Query(None),
        ) -> dict[str, Any]:
            """Get a summary of the history of an agent."""
            filters = self._make_filter_config(
                type_names=type_names,
                produced_by=produced_by,
                correlation_id=correlation_id,
                tags=tag,
                visibility=visibility,
                start=start,
                end=end,
            )
            summary = await orchestrator.store.agent_history_summary(
                agent_id,
                filters,
            )
            return {
                "agent_id": agent_id,
                "summary": summary,
            }

        # TODO: relevant for MCP-Component in the future
        @app.get(
            self._join_path(self.config.prefix, "correlations/{correlation_id}/status"),
            response_model=CorrelationStatusResponse,
            tags=self.config.tags,
        )
        async def get_correlation_status(
            correlation_id: str,
        ) -> CorrelationStatusResponse:
            """Get the status of a workflow by correlation ID.

            Returns workflow state (active/completed/failed/not_found),
            pending work status, artifact coungs, error counts, and timestamps.
            This endpoint is useful for polling to check if a workflow has completed.
            """
            try:
                status = await orchestrator.get_correlation_status(correlation_id)
                return CorrelationStatusResponse(**status)
            except ValueError as exc:
                logger.exception(
                    f"AgentsServerComponent: failed to retrieve correlation status: {exc!s}"
                )
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def on_shutdown_async(self, orchestrator):
        # No-op
        pass

    async def on_startup_async(self, orchestrator):
        # No-op
        pass

    def get_dependencies(self):
        # No dependencies
        return []
