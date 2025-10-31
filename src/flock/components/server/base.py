"""Server component base classes and configuration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic._internal._model_construction import ModelMetaclass
from typing_extensions import TypeVar

from flock.logging.auto_trace import AutoTracedMeta


T = TypeVar("T", bound="ServerComponentConfig")


class TracedModelMeta(ModelMetaclass, AutoTracedMeta):
    """Combined metaclass for Pydantic models with auto-tracing.

    This metaclass combines Pydantic's ModelMetaclass with AutoTracedMeta
    to enable both Pydantic functionality and automatic method tracing.
    """


class ServerComponentConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable this component.")
    prefix: str = Field(
        default="", description="Optional Prefix for the routes of the ServerComponent"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="OpenAPI tags to order the endpoints of the ServerComponent",
    )
    model_config: ConfigDict = ConfigDict(
        arbitrary_types_allowed=True,
    )


class ServerComponent(BaseModel):
    """Base class for server components.

    Mirrors AgentComponent pattern for consistency.
    Components register routes, handle startup/shutdown,
    and can configure FastAPI behavior.

    Lifecycle:
        1. __init__() Component creation
        2. configure(app, orchestrator) - Configure FastAPI app (middleware, etc.)
        3. register_routes(app, orchestrator) - Add endpoints to FastAPI app
        4. on_startup(orchestrator) - Async startup tasks
        5. ...service runs...
        6. on_shutdown(orchestrator) - Async cleanup tasks

    Priority System:
        - Lower priority numbers register first
        - Used to control route registration order
        - Static files should be LAST (highest priority)

    Example:
        >>> class MyServerComponent(ServerComponent):
        >>>     name = "my_component"
        >>>     priority = 10
        >>>
        >>>     async def register_routes(self, app, orchestrator):
        >>>         @app.get("/my-endpoint")
        >>>         async def my_endpoint():
        >>>             return {"status": "ok"}
        >>>         ...
    """

    name: str | None = Field(
        default=None, description="Component name (auto-generated if None)"
    )

    config: ServerComponentConfig = Field(
        default_factory=ServerComponentConfig,
        description="Configuration for the server-component.",
    )

    priority: int = Field(
        default=0,
        description="Registration priority (lower runs first, controls route order).",
    )

    def configure(self, app: Any, orchestrator: Any) -> None:
        """Configure the Component."""

    # Lifecycle Hooks
    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """Register HTTP routes to FastAPI app.

        Called in priority order during startup.
        Lower priority numbers register first.
        This is where you define your endpints.

        Args:
            app: FastAPI application instance used by flock to communicate with the 'outside'-world
            orchestrator: Flock orchestrator instance

        Raises:
            NotImplementedError: must be implemented by subclasses

        Example:
            >>> async def register_routes(self, app, orchestrator):
            >>>     @app.get("/health")
            >>>     async def health():
            >>>         return {"status": "ok"}
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement register_routes()"
        )

    async def on_startup_async(self, orchestrator: Any) -> None:
        """Async startup hook - runs when the service starts.

        Use this for async initialization like connecting to databases,
        starting background tasks, launching external processes, etc.

        Called in priority order after all routes are registered.

        Args:
            orchestrator: Flock orchestrator instance

        Example:
            >>> async def on_startup(self, orchestrator):
            >>>     self.websocket_manager = WebSocketManager()
            >>>     self.launcher = DashboardLauncher()
            >>>     self.launcher.start()
            >>>     orchestrator._websocket_manager = self.websocket_manager
        """

    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """Async shutdown hook - runs when the service stops.

        Use this for cleanup like closing connections, stopping background tasks,
        terminating external processes, etc.

        Called in REVERSE priority order (highest to lowest) to ensure proper
        cleanup ordering.

        Args:
            orchestrator: Flock orchestrator instance

        Example:
            >>> async def on_shutdown(self, orchestrator):
            >>>     if self.websocket_manager:
            >>>         await self.websocket_manager.shutdown()
            >>>     if self.launcher:
            >>>         self.launcher.stop()
        """

    # Helper methods
    def get_dependencies(self) -> list[type[ServerComponent]]:
        """Return list of component types this component depends on.

        Used for automatic ordering validation.
        Will check that all dependencies are present and enabled.

        Returns:
            List of ServerComponent subclass types

        Example:
            >>> class MyComponent(ServerComponent):
            >>>     def get_dependencies(self):
            >>>         return [ArticatComponent] # Requires Artifact routes
            ...
            >>> # If ArtifactComponent is not added, configure() will raise:
            >>> # ValueError: MyComponent requires ArtifactComponent but it's not enabled
        """
        return []

    def _join_path(self, *parts: str) -> str:
        """Join URL path parts, handling slashes correctly.

        Ensures exactly one slash between parts and no double slashes.

        Examples:
            >>> _join_path("/api/v1/", "agents")  # -> "/api/v1/agents"
            >>> _join_path("/api/v1", "agents) # -> "/api/v1/agents"
            >>> _join_path("/api/v1/", "/agents")  # -> "/api/v1/agents"
        """
        # Remove trailing slashes from all parts except the last one
        cleaned = [part.rstrip("/") for part in parts[:-1]]
        # Add the last part (keep trailing slash if present)
        if parts:
            cleaned.append(parts[-1].lstrip("/"))
        # Join with single slash
        return "/".join(cleaned)

    model_config: ConfigDict = ConfigDict(
        arbitrary_types_allowed=True,
    )
