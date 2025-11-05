"""ServerComponent that serves control routes."""

from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pydantic import Field, ValidationError

from flock.api.graph_builder import GraphAssembler
from flock.api.websocket import WebSocketManager
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.components.server.models.events import MessagePublishedEvent, VisibilitySpec
from flock.components.server.models.graph import GraphRequest, GraphSnapshot
from flock.logging.logging import get_logger
from flock.registry import type_registry


logger = get_logger(__name__)


class ControlRoutesComponentConfig(ServerComponentConfig):
    """Configuration class for ControlRoutesComponent."""

    prefix: str | None = Field(
        default="/api/plugin/",
        description="Optional prefix for control routes. (Defaults to '/api/plugin)",
    )
    tags: list[str] = Field(
        default=["Control Routes"], description="Tags for OpenAPI documentation."
    )


class ControlRoutesComponent(ServerComponent):
    """Server Component that serves Control Routes."""

    name: str = "control"
    priority: int = Field(default=3, description="Registration priority. Default = 3")
    config: ControlRoutesComponentConfig = Field(
        default_factory=ControlRoutesComponentConfig,
        description="Config for the ServerComponent.",
    )
    websocket_manager: WebSocketManager = Field(
        default_factory=WebSocketManager,
        description="WebSocketManager Singleton instance for broadcasts.",
    )
    graph_assembler: GraphAssembler | None = Field(
        default=None,
        description="Optional GraphAssembler. Allows returning snapshots of the State-Graph. (used mainly for visualizing. If a headless API is desired, then this can be omitted.)",
    )

    def configure(self, app, orchestrator):
        return super().configure(app, orchestrator)

    def register_routes(self, app, orchestrator):
        """Register control API endponts for interacting with the orchestrator and (optionally) the dashboard.

        Args:
            app: FastAPI application instance
            orchestrator: Flock orchestrator instance
            websocket_manager: WebSocket manager for real-time updates
            event_collector: Dashboard event collector
        """

        @app.get(
            self._join_path(self.config.prefix, "artifact_types"), tags=self.config.tags
        )
        async def get_artifact_types() -> dict[str, Any]:
            """Get all registered artifact types with their schemas.

            Returns:
                {
                    "artifact_types": [
                        {
                            "name": "TypeName",
                            "schema": {...}
                        },
                        ...
                    ]
                }
            """
            artifact_types = []
            for type_name in type_registry._by_name:
                try:
                    model_class = type_registry.resolve(type_name)
                    # Get pydantic schema
                    schema = model_class.model_json_schema()
                    artifact_types.append({"name": type_name, "schema": schema})
                except Exception as ex:
                    logger.warning(f"Could not get schema for {type_name}: {ex!s}")
            return {"artifact_types": artifact_types}

        @app.get(self._join_path(self.config.prefix, "agents"), tags=self.config.tags)
        async def get_agents() -> dict[str, Any]:
            """Get all registered agents with logic operations state.

            Phase 1.2 Enhancement: Now includes logic_operations configuration
            and waiting state for agents using JoinSpec or BatchSpec.

            Returns:
                {
                    "agents": [
                        {
                            "name": "agent_name",
                            "description": "...",
                            "status": "ready" | "waiting" | "active",
                            "subscriptions": ["TypeA", "TypeB"],
                            "output_types": ["TypeC", "TypeD"],
                            "logic_operations": [ #New: Phase 1.2
                            {
                                "subscription_index": 0,
                                "subscription_types": ["TypeA", "TypeB"],
                                "join": {...}, # JoinSpec config
                                "batch": {...}, # BatchSpec config
                                "waiting_state": {...} # Current state
                            }
                            ]
                        }
                    ]
                }
            """
            from flock.components.server.control.helpers import (
                _build_logic_config,
                _compute_agent_status,
            )

            agents = []
            for agent in orchestrator.agents:
                # Extract consumed types from agent subscriptions
                consumed_types = []
                for sub in agent.subscriptions:
                    consumed_types.extend(sub.type_names)
                # Extract produced types from agent outputs
                produced_types = [output.spec.type_name for output in agent.outputs]
                # NEW Phase 1.2: Logic operations configuration
                logic_operations = []
                for idx, subscription in enumerate(agent.subscriptions):
                    logic_config = _build_logic_config(
                        agent, subscription, idx, orchestrator
                    )
                    if logic_config:  # Only include if has join/batch
                        logic_operations.append(logic_config)
                agent_data = {
                    "name": agent.name,
                    "description": agent.description or "",
                    "status": _compute_agent_status(
                        agent, orchestrator
                    ),  # NEW: Dynamic status
                    "subscriptions": consumed_types,
                    "output_types": produced_types,
                }
                if logic_operations:
                    agent_data["logic_operations"] = logic_operations
                agents.append(agent_data)
            return {"agents": agents}

        @app.get(self._join_path(self.config.prefix, "version"), tags=self.config.tags)
        async def get_version() -> dict[str, str]:
            """Get version information for the backend and dashboard.

            Returns:
                {
                    "backend_version": "0.1.18",
                    "package_name": "flock"
                }
            """
            from importlib.metadata import PackageNotFoundError, version

            try:
                backend_version = version("flock")
            except PackageNotFoundError:
                # Fallback version if package is not installed
                backend_version = "0.2.0-dev"
            return {"backend_version": backend_version, "package_name": "flock"}

        @app.post(
            self._join_path(self.config.prefix, "control/publish"),
            tags=self.config.tags,
        )
        async def publish_artifact(body: dict[str, Any]) -> dict[str, str]:
            """Publish artifact with correlation tracking.

            Request body:
            {
                "artifact_typ": "TypeName",
                "content": {"field": "value", ...}
            }
            Returns:
            {
                "correlation_id": "<uuid>",
                "published_at": "<iso-timestamp"
            }
            """
            # Validate required fields
            artifact_type = body.get("artifact_type")
            content = body.get("content")
            if not artifact_type:
                raise HTTPException(
                    status_code=400, detail="artifact_type is required."
                )
            if content is None:
                raise HTTPException(status_code=400, detail="content is requried.")
            try:
                # Resolve type from registry
                model_class = type_registry.resolve(artifact_type)
                # Validate content against Pydantic schema
                try:
                    instance = model_class(**content)
                except ValidationError as ex:
                    logger.exception(
                        f"ControlRoutesComponent: failed to validate body for type '{artifact_type}': {ex!s}"
                    )
                    raise HTTPException(
                        status_code=422, detail=f"Validation error: {ex!s}"
                    )
                # Generate correlation id
                correlation_id = str(uuid4())
                # Publish to orchestrator
                artifact = await orchestrator.publish(
                    instance,
                    correlation_id=correlation_id,
                    is_dashboard=True,
                )
                # Phase 11 Fix: Emit message_published event for dashboard visibility
                # This enables virtual "orchestrator" agent to appar in both AgentView and BlackboardView
                event = MessagePublishedEvent(
                    correlation_id=str(artifact.correlation_id),
                    artifact_id=str(artifact.id),
                    artifact_type=artifact.type,
                    produced_by=artifact.produced_by,  # Will be "orchestrator" or similar for non-agent publishers
                    payload=artifact.payload,
                    visibility=VisibilitySpec(
                        kind="Public"
                    ),  # Dashboard-published artifacts are public by default
                    tags=list(artifact.tags) if artifact.tags else [],
                    version=artifact.version,
                    consumers=[],  # Will be populated by subscription matching in frontend
                )
                await self.websocket_manager.broadcast(event=event)
                return {
                    "correlation_id": str(artifact.correlation_id),
                    "published_at": artifact.created_at.isoformat(),
                }
            except KeyError as ke:
                logger.exception(
                    f"ControlRoutesComponent: Unknown artifact type: {artifact_type}"
                )
                raise HTTPException(
                    status_code=422, detail=f"Unknown artifact type: {artifact_type}"
                ) from ke
            except Exception as ex:
                logger.exception(f"Error publishing artifact: {ex!s}")
                raise HTTPException(status_code=500, detail=str(ex)) from ex

        @app.post(
            self._join_path(self.config.prefix, "control/invoke"), tags=self.config.tags
        )
        async def invoke_agent(body: dict[str, Any]) -> dict[str, Any]:
            """Directly invoke a specific agent.

            Request body:
                {
                    "agent_name": "agent_name",
                    "input": {"type": "TypeName", "field": "value", ...}
                }
            Returns:
                {
                    "invocation_id": "<uuid>",
                    "result": "success",
                }
            """
            # Validate required fields
            agent_name = body.get("agent_name")
            input_data = body.get("input")
            if not agent_name:
                raise HTTPException(status_code=400, detail="agent_name is required")
            if input_data is None:
                raise HTTPException(status_code=400, detail="input is required")
            try:
                # Get agent from orchestrator
                agent = orchestrator.get_agent(agent_name)
            except KeyError:
                raise HTTPException(
                    status_code=404, detail=f"Agent not found: {agent_name}"
                )
            try:
                # Parse input type and create instance
                input_type = input_data.get("type")
                if not input_type:
                    raise HTTPException(
                        status_code=400, detail="input.type is required"
                    )
                # Resolve type from registry
                model_class = type_registry.resolve(input_type)
                # Create payload by removing 'type' key
                payload = {k: v for k, v in input_data.items() if k != "type"}
                # Validate and create instance
                try:
                    instance = model_class(**payload)
                except ValidationError as ex:
                    raise HTTPException(
                        status_code=422, detail=f"Validation error: {ex!s}"
                    )
                # Invoke agent
                outputs = await orchestrator.invoke(
                    agent,
                    instance,
                )
                # Generate invocation ID from first output or create new UUID
                invocation_id = str(outputs[0].id) if outputs else str(uuid4())
                # Extract correlation_id from first output (for filter automation)
                correlation_id = (
                    str(outputs[0].correlation_id)
                    if outputs and outputs[0].correlation_id
                    else None
                )
                return {
                    "invocation_id": invocation_id,
                    "correlation_id": correlation_id,
                    "result": "success",
                }
            except HTTPException:
                raise
            except KeyError:
                raise HTTPException(
                    status_code=422, detail=f"Unknown type: {input_type}"
                )
            except Exception as ex:
                logger.exception(f"Error invoking agent: {ex!s}")
                raise HTTPException(status_code=500, detail=str(ex))

        @app.get(
            self._join_path(self.config.prefix, "artifact-types"), tags=self.config.tags
        )
        async def get_artifact_types() -> dict[str, Any]:
            """Get all registered artifact types with their schema.

            Returns:
                {
                    "artifact_types": [
                        {
                            "name": "TypeName",
                            "schema": {...}
                        }
                    ]
                }
            """
            artifact_types = []
            for type_name in type_registry._by_name:
                try:
                    model_class = type_registry.resolve(type_name=type_name)
                    # Get Pydantic schema
                    schema = model_class.model_json_schema()
                    artifact_types.append({"name": type_name, "schema": schema})
                except Exception as ex:
                    logger.warning(f"Could not get schema for type {type_name}: {ex!s}")
            return {
                "artifact_types": artifact_types,
            }

        @app.post(
            self._join_path(self.config.prefix, "control/pause"), tags=self.config.tags
        )
        async def pause_orchestrator() -> dict[str, Any]:
            """ "Pause orchestrator (placeholder).

            Returns:
                501 Not implemented
            """
            raise HTTPException(
                status_code=501, detail="Pause functionality coming in Phase 12"
            )

        @app.post(
            self._join_path(self.config.prefix, "control/resume"), tags=self.config.tags
        )
        async def resume_orchestrator() -> dict[str, Any]:
            """Resume orchestrator (placeholder).

            Returns:
                501 Not Implemented
            """
            raise HTTPException(
                status_code=501, detail="Resume functionality coming in Phase 12"
            )

        if self.graph_assembler is not None:

            @app.post(
                self._join_path(self.config.prefix, "dashboard", "graph"),
                response_model=GraphSnapshot,
                tags=self.config.tags,
            )
            async def get_dashboard_graph(request: GraphRequest) -> GraphSnapshot:
                """Return server-side assembled dashboard graph snapshot."""
                return await self.graph_assembler.build_snapshot(request)

    async def on_startup_async(self, orchestrator):
        # No-op
        pass

    async def on_shutdown_async(self, orchestrator):
        # No-op
        pass

    def get_dependencies(self):
        # No dependencies
        return []
