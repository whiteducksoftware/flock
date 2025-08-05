"""Base classes and implementations for the Flock module system."""

from abc import ABC
from typing import Any, TypeVar

from pydantic import BaseModel, Field, create_model

from flock.core.context.context import FlockContext

T = TypeVar("T", bound="FlockModuleConfig")


class FlockModuleConfig(BaseModel):
    """Base configuration class for Flock modules.

    This class serves as the base for all module-specific configurations.
    Each module should define its own config class inheriting from this one.

    Example:
        class MemoryModuleConfig(FlockModuleConfig):
            file_path: str = Field(default="memory.json")
            save_after_update: bool = Field(default=True)
    """

    enabled: bool = Field(
        default=True, description="Whether the module is currently enabled"
    )

    @classmethod
    def with_fields(cls: type[T], **field_definitions) -> type[T]:
        """Create a new config class with additional fields."""
        return create_model(
            f"Dynamic{cls.__name__}", __base__=cls, **field_definitions
        )


class FlockModule(BaseModel, ABC):
    """Base class for all Flock modules.

    Modules can hook into agent lifecycle events and modify or enhance agent behavior.
    They are initialized when added to an agent and can maintain their own state.

    Each module should define its configuration requirements either by:
    1. Creating a subclass of FlockModuleConfig
    2. Using FlockModuleConfig.with_fields() to create a config class
    """

    name: str = Field(
        default="", description="Unique identifier for the module"
    )
    config: FlockModuleConfig = Field(
        default_factory=FlockModuleConfig, description="Module configuration"
    )

    # (Historic) global-module registry removed – prefer DI container instead.

    def __init__(self, **data):
        super().__init__(**data)

    async def on_initialize(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Called when the agent starts running."""
        pass

    async def on_pre_evaluate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Called before agent evaluation, can modify inputs."""
        return inputs

    async def on_post_evaluate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Called after agent evaluation, can modify results."""
        return result

    async def on_terminate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Called when the agent finishes running."""
        return result

    async def on_error(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        error: Exception | None = None,
    ) -> None:
        """Called when an error occurs during agent execution."""
        pass

    async def on_pre_server_init(self, server: Any) -> None:
        """Called before a server initializes."""
        pass

    async def on_post_server_init(self, server: Any) -> None:
        """Called after a server initialized."""
        pass

    async def on_pre_server_terminate(self, server: Any) -> None:
        """Called before a server terminates."""
        pass

    async def on_post_server_terminate(self, server: Any) -> None:
        """Called after a server terminates."""
        pass

    async def on_server_error(self, server: Any, error: Exception) -> None:
        """Called when a server errors."""
        pass

    async def on_connect(
        self,
        server: Any,
        additional_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Called before a connection is being established to a mcp server.

        use `server` (type FlockMCPServer) to modify the core behavior of the server.
        use `additional_params` to 'tack_on' additional configurations (for example additional headers for sse-clients.)

        (For example: modify the server's config)
        new_config = NewConfigObject(...)
        server.config = new_config

        Warning:
            Be very careful when modifying a server's internal state.
            If you just need to 'tack on' additional information (such as headers)
            or want to temporarily override certain configurations (such as timeouts)
            use `additional_params` instead if you can.

        (Or pass additional values downstream:)
        additional_params["headers"] = { "Authorization": "Bearer 123" }
        additional_params["read_timeout_seconds"] = 100


        Note:
            `additional_params` resets between mcp_calls.
            so there is not persistence between individual calls.
            This choice has been made to allow developers to
            dynamically switch configurations.
            (This can be used, for example, to use a module to inject oauth headers for
            individual users on a call-to-call basis. this also gives you direct control over
            managing the headers yourself. For example, checking for lifetimes on JWT-Tokens.)

        Note:
            you can access `additional_params` when you are implementing your own subclasses of
            FlockMCPClientManager and FlockMCPClient. (with self.additional_params.)

        keys which are processed for `additional_params` in the flock core code are:
        --- General ---

        "refresh_client": bool -> defaults to False. Indicates whether or not to restart a connection on a call. (can be used when headers oder api-keys change to automatically switch to a new client.)
        "read_timeout_seconds": float -> How long to wait for a connection to happen.

        --- SSE ---

        "override_headers": bool -> default False. If set to false, additional headers will be appended, if set to True, additional headers will override existing ones.
        "headers": dict[str, Any] -> Additional Headers injected in sse-clients and ws-clients
        "sse_read_timeout_seconds": float -> how long until a connection is being terminated for sse-clients.
        "url": str -> which url the server listens on (allows switching between mcp-servers with modules.)

        --- Stdio ---

        "command": str -> Command to run for stdio-servers.
        "args": list[str] -> additional paramters for stdio-servers.
        "env": dict[str, Any] -> Environment-Variables for stdio-servers.
        "encoding": str -> Encoding to use when talking to stdio-servers.
        "encoding-error-handler": str -> Encoding error handler to use when talking to stdio-servers.

        --- Websockets ---

        "url": str -> Which url the server listens on (allows switching between mcp-servers with modules.)
        """
        pass

    async def on_pre_mcp_call(
        self,
        server: Any,
        arguments: Any | None = None,
    ) -> None:
        """Called before any MCP Calls."""
        pass

    async def on_post_mcp_call(
        self,
        server: Any,
        result: Any | None = None,
    ) -> None:
        """Called after any MCP Calls."""
        pass
