"""Server component base classes - DRAFT IMPLEMENTATION SKELETON

This is a skeleton implementation to visualize the proposed architecture.
DO NOT USE IN PRODUCTION - this is a design reference only.

See docs/patterns/server_component_refactoring.md for full proposal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fastapi import FastAPI
    from flock.core import Flock


class ServerComponentConfig(BaseModel):
    """Configuration for server components.

    Example:
        >>> config = ServerComponentConfig(enabled=True)
        >>> custom_config = ServerComponentConfig.model_copy(
        ...     update={"custom_field": "value"}
        ... )
    """

    enabled: bool = Field(default=True, description="Enable this component")


class ServerComponent(BaseModel):
    """Base class for HTTP service components.

    Mirrors AgentComponent pattern for consistency. Components register routes,
    handle startup/shutdown, and can configure FastAPI.

    Lifecycle:
        1. __init__() - Component creation
        2. configure(app, orchestrator) - Configure FastAPI app (middleware, etc.)
        3. register_routes(app, orchestrator) - Add endpoints to FastAPI app
        4. on_startup(orchestrator) - Async startup tasks
        5. ... service runs ...
        6. on_shutdown(orchestrator) - Async cleanup tasks

    Priority System:
        - Lower priority numbers register first
        - Use to control route registration order
        - Static files should be LAST (highest priority)

    Example:
        >>> class MyComponent(ServerComponent):
        ...     name = "my_component"
        ...     priority = 10
        ...
        ...     async def register_routes(self, app, orchestrator):
        ...         @app.get("/my-endpoint")
        ...         async def my_endpoint():
        ...             return {"status": "ok"}
        ...
        ...     async def on_startup(self, orchestrator):
        ...         print("My component started!")
    """

    name: str | None = Field(
        default=None, description="Component name (auto-generated if None)"
    )
    config: ServerComponentConfig = Field(default_factory=ServerComponentConfig)
    priority: int = Field(
        default=0,
        description="Registration priority (lower runs first, controls route order)",
    )

    # Lifecycle hooks

    def configure(self, app: FastAPI, orchestrator: Flock) -> None:
        """Configure FastAPI app (sync - runs before server starts).

        Use this to add middleware, exception handlers, CORS, etc.
        Called in priority order during BaseHTTPService.configure().

        Args:
            app: FastAPI application instance
            orchestrator: Flock orchestrator instance

        Example:
            >>> def configure(self, app, orchestrator):
            ...     app.add_middleware(
            ...         CORSMiddleware,
            ...         allow_origins=["*"],
            ...         allow_credentials=True,
            ...         allow_methods=["*"],
            ...         allow_headers=["*"],
            ...     )
        """
        pass

    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register HTTP routes to FastAPI app.

        Called in priority order during startup. Lower priority numbers
        register first. This is where you define your endpoints.

        Args:
            app: FastAPI application instance
            orchestrator: Flock orchestrator instance

        Raises:
            NotImplementedError: Must be implemented by subclasses

        Example:
            >>> async def register_routes(self, app, orchestrator):
            ...     @app.get("/health")
            ...     async def health():
            ...         return {"status": "ok"}
            ...
            ...     @app.post("/api/v1/artifacts")
            ...     async def publish_artifact(body: dict):
            ...         await orchestrator.publish(body)
            ...         return {"status": "accepted"}
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement register_routes()"
        )

    async def on_startup(self, orchestrator: Flock) -> None:
        """Async startup hook - runs when service starts.

        Use this for async initialization like connecting to databases,
        starting background tasks, launching external processes, etc.

        Called in priority order after all routes are registered.

        Args:
            orchestrator: Flock orchestrator instance

        Example:
            >>> async def on_startup(self, orchestrator):
            ...     self.websocket_manager = WebSocketManager()
            ...     self.launcher = DashboardLauncher()
            ...     self.launcher.start()
            ...     orchestrator._websocket_manager = self.websocket_manager
        """
        pass

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Async shutdown hook - runs when service stops.

        Use this for cleanup like closing connections, stopping background
        tasks, terminating external processes, etc.

        Called in REVERSE priority order (highest to lowest) to ensure
        proper cleanup ordering.

        Args:
            orchestrator: Flock orchestrator instance

        Example:
            >>> async def on_shutdown(self, orchestrator):
            ...     if self.websocket_manager:
            ...         await self.websocket_manager.shutdown()
            ...     if self.launcher:
            ...         self.launcher.stop()
        """
        pass

    # Helper methods

    def get_dependencies(self) -> list[type[ServerComponent]]:
        """Return list of component types this component depends on.

        Used for automatic ordering validation. BaseHTTPService will
        check that all dependencies are present and enabled.

        Returns:
            List of ServerComponent subclass types

        Example:
            >>> class MyComponent(ServerComponent):
            ...     def get_dependencies(self):
            ...         return [ArtifactComponent]  # Requires artifact routes
            ...
            >>> # If ArtifactComponent is not added, configure() will raise:
            >>> # ValueError: MyComponent requires ArtifactComponent but it's not enabled
        """
        return []


# Example concrete components (skeletons)


class HealthComponent(ServerComponent):
    """Health check and metrics endpoints.

    Provides:
    - GET /health - Basic health check
    - GET /metrics - Prometheus-style metrics
    """

    name: str = "health"
    priority: int = 5  # Early registration (no dependencies)

    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register health and metrics routes."""

        @app.get("/health", tags=["Health"])
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/metrics", tags=["Health"])
        async def metrics() -> str:
            lines = [
                f"blackboard_{key} {value}"
                for key, value in orchestrator.metrics.items()
            ]
            return "\n".join(lines)


class ArtifactComponent(ServerComponent):
    """HTTP endpoints for artifact management.

    Provides:
    - POST /api/v1/artifacts - Publish artifacts
    - GET /api/v1/artifacts - List/query artifacts
    - GET /api/v1/artifacts/{id} - Get single artifact
    - GET /api/v1/artifacts/summary - Summary statistics
    """

    name: str = "artifact"
    priority: int = 10  # Base routes - register early

    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register artifact management routes.

        TODO: Extract actual implementation from BlackboardHTTPService
        """
        # Implementation would go here
        # See src/flock/api/service.py for current implementation
        pass


class DashboardComponent(ServerComponent):
    """WebSocket dashboard with real-time agent visualization.

    Provides:
    - WebSocket endpoint at /ws
    - Static file serving for dashboard UI
    - Real-time event streaming
    - Agent graph visualization
    """

    name: str = "dashboard"
    priority: int = 20  # After base routes (static files must be LAST!)

    # Runtime state
    websocket_manager: Any = None  # WebSocketManager
    event_collector: Any = None  # DashboardEventCollector
    launcher: Any = None  # DashboardLauncher

    def configure(self, app: FastAPI, orchestrator: Flock) -> None:
        """Configure CORS middleware if needed."""
        # Implementation would go here
        pass

    async def on_startup(self, orchestrator: Flock) -> None:
        """Initialize dashboard components."""
        # Implementation would go here
        # See src/flock/orchestrator/server_manager.py for current implementation
        pass

    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register dashboard routes (WebSocket, static files, etc.)."""
        # Implementation would go here
        # See src/flock/dashboard/service.py for current implementation
        pass

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Clean up dashboard resources."""
        # Implementation would go here
        pass


class MCPComponent(ServerComponent):
    """Model Context Protocol (MCP) server endpoints.

    Provides:
    - POST /mcp/tools/list - List available tools
    - POST /mcp/tools/call - Execute tool
    - POST /mcp/resources/list - List available resources
    - POST /mcp/resources/read - Read resource

    Exposes Flock agents and artifacts via MCP protocol for AI assistants.
    """

    name: str = "mcp"
    priority: int = 30  # After core routes

    async def register_routes(self, app: FastAPI, orchestrator: Flock) -> None:
        """Register MCP protocol endpoints."""

        @app.post("/mcp/tools/list", tags=["MCP"])
        async def list_mcp_tools() -> dict[str, Any]:
            """List available MCP tools."""
            return {
                "tools": [
                    {
                        "name": "agent_invoke",
                        "description": "Execute a Flock agent with inputs",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "agent_name": {"type": "string"},
                                "inputs": {"type": "array"},
                            },
                            "required": ["agent_name", "inputs"],
                        },
                    }
                ]
            }

        @app.post("/mcp/tools/call", tags=["MCP"])
        async def call_mcp_tool(request: dict[str, Any]) -> dict[str, Any]:
            """Execute an MCP tool."""
            tool_name = request.get("name")
            arguments = request.get("arguments", {})

            if tool_name == "agent_invoke":
                agent_name = arguments["agent_name"]
                inputs = arguments["inputs"]

                agent = orchestrator.get_agent(agent_name)
                outputs = await orchestrator.direct_invoke(agent, inputs)

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Agent {agent_name} produced {len(outputs)} artifacts",
                        }
                    ]
                }

            return {"error": f"Unknown tool: {tool_name}"}


__all__ = [
    "ServerComponent",
    "ServerComponentConfig",
    "HealthComponent",
    "ArtifactComponent",
    "DashboardComponent",
    "MCPComponent",
]
