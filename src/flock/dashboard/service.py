"""DashboardHTTPService - extends BlackboardHTTPService with WebSocket support.

Provides real-time dashboard capabilities by:
1. Mounting WebSocket endpoint at /ws
2. Serving static files for dashboard frontend
3. Integrating DashboardEventCollector with WebSocketManager
4. Supporting CORS for development mode (DASHBOARD_DEV=1)
"""

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.events import MessagePublishedEvent, VisibilitySpec
from flock.dashboard.websocket import WebSocketManager
from flock.logging.logging import get_logger
from flock.orchestrator import Flock
from flock.registry import type_registry
from flock.service import BlackboardHTTPService


logger = get_logger("dashboard.service")


class DashboardHTTPService(BlackboardHTTPService):
    """HTTP service with WebSocket support for real-time dashboard.

    Extends BlackboardHTTPService to add:
    - WebSocket endpoint at /ws for real-time event streaming
    - Static file serving for dashboard frontend
    - Integration with DashboardEventCollector
    - Optional CORS middleware for development
    """

    def __init__(
        self,
        orchestrator: Flock,
        websocket_manager: WebSocketManager | None = None,
        event_collector: DashboardEventCollector | None = None,
    ) -> None:
        """Initialize DashboardHTTPService.

        Args:
            orchestrator: Flock orchestrator instance
            websocket_manager: Optional WebSocketManager (creates new if not provided)
            event_collector: Optional DashboardEventCollector (creates new if not provided)
        """
        # Initialize base service
        super().__init__(orchestrator)

        # Initialize WebSocket manager and event collector
        self.websocket_manager = websocket_manager or WebSocketManager()
        self.event_collector = event_collector or DashboardEventCollector()

        # Integrate collector with WebSocket manager
        self.event_collector.set_websocket_manager(self.websocket_manager)

        # Configure CORS if DASHBOARD_DEV environment variable is set
        if os.environ.get("DASHBOARD_DEV") == "1":
            logger.info("DASHBOARD_DEV mode enabled - adding CORS middleware")
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Allow all origins in dev mode
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # IMPORTANT: Register API routes BEFORE static files!
        # Static file mount acts as catch-all and must be last
        self._register_control_routes()
        self._register_theme_routes()
        self._register_dashboard_routes()

        logger.info("DashboardHTTPService initialized")

    def _register_dashboard_routes(self) -> None:
        """Register WebSocket endpoint and static file serving."""
        app = self.app

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            """WebSocket endpoint for real-time dashboard events.

            Handles connection lifecycle:
            1. Accept connection
            2. Add to WebSocketManager pool
            3. Keep connection alive
            4. Handle disconnection gracefully
            """
            await websocket.accept()
            await self.websocket_manager.add_client(websocket)

            try:
                # Keep connection alive and handle incoming messages
                # Dashboard clients may send heartbeat responses or control messages
                while True:
                    # Wait for messages from client (pong responses, etc.)
                    try:
                        data = await websocket.receive_text()
                        # Handle client messages if needed (e.g., pong responses)
                        # For Phase 3, we primarily broadcast from server to client
                        logger.debug(f"Received message from client: {data[:100]}")
                    except WebSocketDisconnect:
                        logger.info("WebSocket client disconnected")
                        break
                    except Exception as e:
                        logger.warning(f"Error receiving WebSocket message: {e}")
                        break

            except Exception as e:
                logger.exception(f"WebSocket endpoint error: {e}")
            finally:
                # Clean up: remove client from pool
                await self.websocket_manager.remove_client(websocket)

        # Serve static files for dashboard frontend
        # Look for static files in dashboard directory
        dashboard_dir = Path(__file__).parent
        static_dir = dashboard_dir / "static"

        # Also check for 'dist' or 'build' directories (common build output names)
        possible_dirs = [static_dir, dashboard_dir / "dist", dashboard_dir / "build"]

        for dir_path in possible_dirs:
            if dir_path.exists() and dir_path.is_dir():
                logger.info(f"Mounting static files from: {dir_path}")
                # Mount at root to serve index.html and other frontend assets
                app.mount(
                    "/",
                    StaticFiles(directory=str(dir_path), html=True),
                    name="dashboard-static",
                )
                break
        else:
            logger.warning(
                f"No static directory found in {dashboard_dir}. "
                "Dashboard frontend will not be served. "
                "Expected directories: static/, dist/, or build/"
            )

    def _register_control_routes(self) -> None:
        """Register control API endpoints for dashboard operations."""
        app = self.app
        orchestrator = self.orchestrator

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
            """Get all registered agents.

            Returns:
                {
                    "agents": [
                        {
                            "name": "agent_name",
                            "description": "...",
                            "status": "ready",
                            "subscriptions": ["TypeA", "TypeB"],
                            "output_types": ["TypeC", "TypeD"]
                        },
                        ...
                    ]
                }
            """
            agents = []

            for agent in orchestrator.agents:
                # Extract consumed types from agent subscriptions
                consumed_types = []
                for sub in agent.subscriptions:
                    consumed_types.extend(sub.type_names)

                # Extract produced types from agent outputs
                produced_types = [output.spec.type_name for output in agent.outputs]

                agents.append(
                    {
                        "name": agent.name,
                        "description": agent.description or "",
                        "status": "ready",
                        "subscriptions": consumed_types,
                        "output_types": produced_types,
                    }
                )

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
                await self.websocket_manager.broadcast(event)

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
                raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")

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
            raise HTTPException(status_code=501, detail="Pause functionality coming in Phase 12")

        @app.post("/api/control/resume")
        async def resume_orchestrator() -> dict[str, Any]:
            """Resume orchestrator (placeholder).

            Returns:
                501 Not Implemented
            """
            raise HTTPException(status_code=501, detail="Resume functionality coming in Phase 12")

        @app.get("/api/streaming-history/{agent_name}")
        async def get_streaming_history(agent_name: str) -> dict[str, Any]:
            """Get historical streaming output for a specific agent.

            Args:
                agent_name: Name of the agent to get streaming history for

            Returns:
                {
                    "agent_name": "agent_name",
                    "events": [
                        {
                            "correlation_id": "...",
                            "timestamp": "...",
                            "agent_name": "...",
                            "run_id": "...",
                            "output_type": "llm_token",
                            "content": "...",
                            "sequence": 0,
                            "is_final": false
                        },
                        ...
                    ]
                }
            """
            try:
                history = self.websocket_manager.get_streaming_history(agent_name)
                return {
                    "agent_name": agent_name,
                    "events": [event.model_dump() for event in history],
                }
            except Exception as e:
                logger.exception(f"Failed to get streaming history for {agent_name}: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to get streaming history: {e!s}"
                )

    def _register_theme_routes(self) -> None:
        """Register theme API endpoints for dashboard customization."""
        from pathlib import Path

        import toml

        app = self.app
        themes_dir = Path(__file__).parent.parent / "themes"

        @app.get("/api/themes")
        async def list_themes() -> dict[str, Any]:
            """Get list of available theme names.

            Returns:
                {"themes": ["dracula", "nord", ...]}
            """
            try:
                if not themes_dir.exists():
                    return {"themes": []}

                theme_files = list(themes_dir.glob("*.toml"))
                theme_names = sorted([f.stem for f in theme_files])

                return {"themes": theme_names}
            except Exception as e:
                logger.exception(f"Failed to list themes: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to list themes: {e!s}")

        @app.get("/api/themes/{theme_name}")
        async def get_theme(theme_name: str) -> dict[str, Any]:
            """Get theme data by name.

            Args:
                theme_name: Name of theme (without .toml extension)

            Returns:
                {
                    "name": "dracula",
                    "data": {
                        "colors": {...}
                    }
                }
            """
            try:
                # Sanitize theme name to prevent path traversal
                theme_name = theme_name.replace("/", "").replace("\\", "").replace("..", "")

                theme_path = themes_dir / f"{theme_name}.toml"

                if not theme_path.exists():
                    raise HTTPException(status_code=404, detail=f"Theme '{theme_name}' not found")

                # Load TOML theme
                theme_data = toml.load(theme_path)

                return {"name": theme_name, "data": theme_data}
            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f"Failed to load theme '{theme_name}': {e}")
                raise HTTPException(status_code=500, detail=f"Failed to load theme: {e!s}")

    async def start(self) -> None:
        """Start the dashboard service.

        Note: For testing purposes. In production, use uvicorn.run(app).
        """
        logger.info("DashboardHTTPService started")
        # Start heartbeat if there are clients
        if len(self.websocket_manager.clients) > 0:
            await self.websocket_manager.start_heartbeat()

    async def stop(self) -> None:
        """Stop the dashboard service and clean up resources.

        Closes all WebSocket connections gracefully.
        """
        logger.info("Stopping DashboardHTTPService")
        await self.websocket_manager.shutdown()
        logger.info("DashboardHTTPService stopped")

    def get_app(self):
        """Get FastAPI application instance.

        Returns:
            FastAPI app for testing or custom server setup
        """
        return self.app


__all__ = ["DashboardHTTPService"]
