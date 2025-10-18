"""Control API routes for dashboard operations."""

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from flock.core import Flock
from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.events import MessagePublishedEvent, VisibilitySpec
from flock.dashboard.websocket import WebSocketManager
from flock.logging.logging import get_logger
from flock.registry import type_registry


logger = get_logger("dashboard.routes.control")


def register_control_routes(
    app: FastAPI,
    orchestrator: Flock,
    websocket_manager: WebSocketManager,
    event_collector: DashboardEventCollector,
) -> None:
    """Register control API endpoints for dashboard operations.

    Args:
        app: FastAPI application instance
        orchestrator: Flock orchestrator instance
        websocket_manager: WebSocket manager for real-time updates
        event_collector: Dashboard event collector
    """

    @app.get("/api/artifact-types")
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
                # Get Pydantic schema
                schema = model_class.model_json_schema()
                artifact_types.append({"name": type_name, "schema": schema})
            except Exception as e:
                logger.warning(f"Could not get schema for {type_name}: {e}")

        return {"artifact_types": artifact_types}

    @app.get("/api/agents")
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
                        "logic_operations": [  # NEW: Phase 1.2
                            {
                                "subscription_index": 0,
                                "subscription_types": ["TypeA", "TypeB"],
                                "join": {...},  # JoinSpec config
                                "batch": {...},  # BatchSpec config
                                "waiting_state": {...}  # Current state
                            }
                        ]
                    },
                    ...
                ]
            }
        """
        from flock.dashboard.routes.helpers import (
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

    @app.get("/api/version")
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
            # Fallback version if package not installed
            backend_version = "0.2.0-dev"

        return {"backend_version": backend_version, "package_name": "flock-flow"}

    @app.post("/api/control/publish")
    async def publish_artifact(body: dict[str, Any]) -> dict[str, str]:
        """Publish artifact with correlation tracking.

        Request body:
            {
                "artifact_type": "TypeName",
                "content": {"field": "value", ...}
            }

        Returns:
            {
                "correlation_id": "<uuid>",
                "published_at": "<iso-timestamp>"
            }
        """
        # Validate required fields
        artifact_type = body.get("artifact_type")
        content = body.get("content")

        if not artifact_type:
            raise HTTPException(status_code=400, detail="artifact_type is required")
        if content is None:
            raise HTTPException(status_code=400, detail="content is required")

        try:
            # Resolve type from registry
            model_class = type_registry.resolve(artifact_type)

            # Validate content against Pydantic schema
            try:
                instance = model_class(**content)
            except ValidationError as e:
                raise HTTPException(status_code=422, detail=f"Validation error: {e!s}")

            # Generate correlation ID
            correlation_id = str(uuid4())

            # Publish to orchestrator
            artifact = await orchestrator.publish(
                instance, correlation_id=correlation_id, is_dashboard=True
            )

            # Phase 11 Fix: Emit message_published event for dashboard visibility
            # This enables virtual "orchestrator" agent to appear in both Agent View and Blackboard View
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
                partition_key=artifact.partition_key,
                version=artifact.version,
                consumers=[],  # Will be populated by subscription matching in frontend
            )
            await websocket_manager.broadcast(event)

            return {
                "correlation_id": str(artifact.correlation_id),
                "published_at": artifact.created_at.isoformat(),
            }

        except KeyError:
            raise HTTPException(
                status_code=422, detail=f"Unknown artifact type: {artifact_type}"
            )
        except Exception as e:
            logger.exception(f"Error publishing artifact: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/control/invoke")
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
                "result": "success"
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
                raise HTTPException(status_code=400, detail="input.type is required")

            # Resolve type from registry
            model_class = type_registry.resolve(input_type)

            # Create payload by removing 'type' key
            payload = {k: v for k, v in input_data.items() if k != "type"}

            # Validate and create instance
            try:
                instance = model_class(**payload)
            except ValidationError as e:
                raise HTTPException(status_code=422, detail=f"Validation error: {e!s}")

            # Invoke agent
            outputs = await orchestrator.invoke(agent, instance)

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
            raise HTTPException(status_code=422, detail=f"Unknown type: {input_type}")
        except Exception as e:
            logger.exception(f"Error invoking agent: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/control/pause")
    async def pause_orchestrator() -> dict[str, Any]:
        """Pause orchestrator (placeholder).

        Returns:
            501 Not Implemented
        """
        raise HTTPException(
            status_code=501, detail="Pause functionality coming in Phase 12"
        )

    @app.post("/api/control/resume")
    async def resume_orchestrator() -> dict[str, Any]:
        """Resume orchestrator (placeholder).

        Returns:
            501 Not Implemented
        """
        raise HTTPException(
            status_code=501, detail="Resume functionality coming in Phase 12"
        )
