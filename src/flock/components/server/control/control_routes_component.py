"""ServerComponent that serves control routes."""

from typing import Any
from uuid import uuid4
from fastapi import HTTPException
from pydantic import Field, ValidationError
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.components.server.models.events import MessagePublishedEvent, VisibilitySpec
from flock.dashboard.websocket import WebSocketManager
from flock.logging.logging import get_logger
from flock.registry import type_registry

logger = get_logger(__name__)

class ControlRoutesComponentConfig(ServerComponentConfig):
    """Configuration class for ControlRoutesComponent."""
    prefix: str | None = Field(
        default="/api/",
        description="Optional prefix for control routes. (Defaults to '/api/)"
    )
    tags: list[str] = Field(
        default=["Control Routes"],
        description="Tags for OpenAPI documentation."
    )

class ControlRoutesComponent(ServerComponent):
    """Server Component that serves Control Routes."""
    name: str = "control"
    priority: int = Field(
        default=3,
        description="Registration priority. Default = 3"
    )
    config: ControlRoutesComponentConfig = Field(
        default_factory=ControlRoutesComponentConfig,
        description="Config for the ServerComponent."
    )
    websocket_manager: WebSocketManager = Field(
        default_factory=WebSocketManager,
        description="WebSocketManager Singleton instance for broadcasts."
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
        @app.get(self.config.prefix+"artifact_types", tags=self.config.tags)
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
                    artifact_types.append({
                        "name": type_name,
                        "schema": schema
                    })
                except Exception as ex:
                    logger.warning(f"Could not get schema for {type_name}: {ex!s}")
            return {
                "artifact_types": artifact_types
            }

        @app.get(self.config.prefix+"agents", tags=self.config.tags)
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
                    if logic_config: # Only include if has join/batch
                        logic_operations.append(logic_config)
                agent_data = {
                    "name": agent.name,
                    "description": agent.description or "",
                    "status": _compute_agent_status(
                        agent, orchestrator
                    ), # NEW: Dynamic status
                    "subscriptions": consumed_types,
                    "output_types": produced_types,
                }
                if logic_operations:
                    agent_data["logic_operations"] = logic_operations
            return {"agents": agents}

        @app.get(self.config.prefix+"version", tags=self.config.tags)
        async def get_version() -> dict[str, str]:
            """Get version information for the backend and dashboard.

            Returns:
                {
                    "backend_version": "0.1.18",
                    "package_name": "flock-flow"
                }
            """
            from importlib.metadata import PackageNotFoundError, version

            try:
                backend_version = version("flock-flow")
            except PackageNotFoundError:
                # Fallback version if package is not installed
                backend_version = "0.2.0-dev"
            return {"backend_version": backend_version, "package_name": "flock-flow"}

        @app.post(self.config.prefix+"control/publish", tags=self.config.tags)
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
                    status_code=400,
                    detail="artifact_type is required."
                )
            if content is None:
                raise HTTPException(
                    status_code=400,
                    detail="content is requried."
                )
            try:
                # Resolve type from registry
                model_class = type_registry.resolve(artifact_type)
                # Validate content against Pydantic schema
                try:
                    instance = model_class(**content)
                except ValidationError as ex:
                    logger.error(f"ControlRoutesComponent: failed to validate body for type '{artifact_type}': {ex!s}")
                    raise HTTPException(
                        status_code=422,
                        detail=f"Validation error: {ex!s}"
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
                    produced_by=artifact.produced_by, # Will be "orchestrator" or similar for non-agent publishers
                    payload=artifact.payload,
                    visibility=VisibilitySpec(
                        kind="Public"
                    ), # Dashboard-published artifacts are public by default
                    tags=list(artifact.tags) if artifact.tags else [],
                    version=artifact.version,
                    consumers=[], # Will be populated by subscription matching in frontend
                )
                await self.websocket_manager.broadcast(
                    event=event
                )
                return {
                    "correlation_id": str(artifact.correlation_id),
                    "published_at": artifact.created_at.isoformat(),
                }

    async def on_startup_async(self, orchestrator):
        return await super().on_startup_async(orchestrator)

    async def on_shutdown_async(self, orchestrator):
        return await super().on_shutdown_async(orchestrator)

    def get_dependencies(self):
        # No dependencies
        return []
