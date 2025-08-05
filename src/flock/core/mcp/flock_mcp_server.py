"""FlockMCPServer is the core, declarative base class for all types of MCP-Servers in the Flock framework."""

import asyncio
import importlib
import inspect
import os
from abc import ABC, abstractmethod
from typing import Any, Literal, TypeVar

from dspy import Tool as DSPyTool
from opentelemetry import trace
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from flock.core.component.agent_component_base import AgentComponent
from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_tool import FlockMCPTool
from flock.core.mcp.mcp_client_manager import FlockMCPClientManager
from flock.core.mcp.mcp_config import FlockMCPConfiguration
from flock.core.serialization.serializable import Serializable
from flock.core.serialization.serialization_utils import (
    deserialize_component,
    serialize_item,
)

logger = get_logger("mcp.server")
tracer = trace.get_tracer(__name__)
T = TypeVar("T", bound="FlockMCPServer")

LoggingLevel = Literal[
    "debug",
    "info",
    "notice",
    "warning",
    "error",
    "critical",
    "alert",
    "emergency",
]


class FlockMCPServer(BaseModel, Serializable, ABC):
    """Base class for all Flock MCP Server Types.

    Servers serve as an abstraction-layer between the underlying MCPClientSession
    which is the actual connection between Flock and a (remote) MCP-Server.

    Servers hook into the lifecycle of their assigned agents and take care
    of establishing sessions, getting and converting tools and other functions
    without agents having to worry about the details.

    Tools (if provided) will be injected into the list of tools of any attached
    agent automatically.

    Servers provide lifecycle-hooks (`initialize`, `get_tools`, `get_prompts`, `list_resources`, `get_resource_contents`, `set_roots`, etc)
    which allow modules to hook into them. This can be used to modify data or
    pass headers from authentication-flows to a server.

    Each Server should define its configuration requirements either by:
    1. Creating a subclass of FlockMCPServerConfig
    2. Using FlockMCPServerConfig.with_fields() to create a config class.
    """

    config: FlockMCPConfiguration = Field(
        ..., description="Config for clients connecting to the server."
    )

    initialized: bool = Field(
        default=False,
        exclude=True,
        description="Whether or not this Server has already initialized.",
    )

    components: dict[str, AgentComponent] = Field(
        default={},
        description="Dictionary of unified agent components attached to this Server.",
    )

    # --- Underlying ConnectionManager ---
    # (Manages a pool of ClientConnections and does the actual talking to the MCP Server)
    # (Excluded from Serialization)
    client_manager: FlockMCPClientManager | None = Field(
        default=None,
        exclude=True,
        description="Underlying Connection Manager. Handles the actual underlying connections to the server.",
    )

    condition: asyncio.Condition = Field(
        default_factory=asyncio.Condition,
        exclude=True,
        description="Condition for asynchronous operations.",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def add_component(self, component: AgentComponent) -> None:
        """Add a unified component to this server."""
        if not component.name:
            logger.error("Component must have a name to be added.")
            return
        if self.components and component.name in self.components:
            logger.warning(f"Overwriting existing component: {component.name}")

        self.components[component.name] = component
        logger.debug(
            f"Added component '{component.name}' to server {self.config.name}"
        )
        return

    def remove_component(self, component_name: str) -> None:
        """Remove a component from this server."""
        if component_name in self.components:
            del self.components[component_name]
            logger.debug(
                f"Removed component '{component_name}' from server '{self.config.name}'"
            )
        else:
            logger.warning(
                f"Component '{component_name}' not found on server '{self.config.name}'"
            )
        return

    def get_component(self, component_name: str) -> AgentComponent | None:
        """Get a component by name."""
        return self.components.get(component_name)

    def get_enabled_components(self) -> list[AgentComponent]:
        """Get a list of currently enabled components attached to this server."""
        return [c for c in self.components.values() if c.config.enabled]

    @abstractmethod
    async def initialize(self) -> FlockMCPClientManager:
        """Called when initializing the server."""
        pass

    async def call_tool(
        self, agent_id: str, run_id: str, name: str, arguments: dict[str, Any]
    ) -> Any:
        """Call a tool via the MCP Protocol on the client's server."""
        with tracer.start_as_current_span("server.call_tool") as span:
            span.set_attribute("agent_id", agent_id)
            span.set_attribute("run_id", run_id)
            span.set_attribute("tool.name", name)
            span.set_attribute("arguments", str(arguments))
            if not self.initialized or not self.client_manager:
                async with self.condition:
                    await self.pre_init()
                    self.client_manager = await self.initialize()
                    self.initialized = True
                    await self.post_init()
            async with self.condition:
                try:
                    additional_params: dict[str, Any] = {
                        "refresh_client": False,
                        "override_headers": False,
                    }  # initialize the additional params as an empty dict.

                    await self.before_connect(
                        additional_params=additional_params
                    )
                    pre_call_args = {
                        "agent_id": agent_id,
                        "run_id": run_id,
                        "tool_name": name,
                        "arguments": arguments,
                    }
                    pre_call_args.update(additional_params)
                    await self.pre_mcp_call(pre_call_args)
                    result = await self.client_manager.call_tool(
                        agent_id=agent_id,
                        run_id=run_id,
                        name=name,
                        arguments=arguments,
                        additional_params=additional_params,
                    )
                    # re-set addtional-params, just to be sure.
                    await self.post_mcp_call(result=result)
                    return result
                except Exception as mcp_error:
                    logger.error(
                        "Error during server.call_tool",
                        server=self.config.name,
                        error=str(mcp_error),
                    )
                    span.record_exception(mcp_error)
                    return None

    async def get_tools(self, agent_id: str, run_id: str) -> list[DSPyTool]:
        """Retrieves a list of available tools from this server."""
        with tracer.start_as_current_span("server.get_tools") as span:
            span.set_attribute("server.name", self.config.name)
            span.set_attribute("agent_id", agent_id)
            span.set_attribute("run_id", run_id)
            if not self.initialized or not self.client_manager:
                async with self.condition:
                    await self.pre_init()
                    self.client_manager = await self.initialize()
                    self.initialized = True
                    await self.post_init()

            async with self.condition:
                try:
                    await self.pre_mcp_call()
                    additional_params: dict[str, Any] = {}
                    additional_params = await self.before_connect(
                        additional_params=additional_params
                    )
                    result: list[
                        FlockMCPTool
                    ] = await self.client_manager.get_tools(
                        agent_id=agent_id,
                        run_id=run_id,
                        additional_params=additional_params,
                    )
                    converted_tools = [
                        t.as_dspy_tool(server=self) for t in result
                    ]
                    await self.post_mcp_call(result=converted_tools)
                    return converted_tools
                except Exception as e:
                    logger.error(
                        f"Unexpected Exception ocurred while trying to get tools from server '{self.config.name}': {e}"
                    )
                    await self.on_error(error=e)
                    span.record_exception(e)
                    return []
                finally:
                    self.condition.notify()

    async def before_connect(
        self, additional_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Run before_connect hooks on modules."""
        logger.debug(
            f"Running before_connect hooks for modules in server '{self.config.name}'."
        )
        with tracer.start_as_current_span("server.before_connect") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                if not additional_params:
                    additional_params = {}
                for module in self.get_enabled_components():
                    additional_params = await module.on_connect(
                        server=self, additional_params=additional_params
                    )
            except Exception as module_error:
                logger.error(
                    "Error during before_connect",
                    server=self.config.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def pre_init(self) -> None:
        """Run pre-init hooks on modules."""
        logger.debug(
            f"Running pre-init hooks for modules in server '{self.config.name}'"
        )
        with tracer.start_as_current_span("server.pre_init") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                for module in self.get_enabled_components():
                    await module.on_pre_server_init(self)
            except Exception as module_error:
                logger.error(
                    "Error during pre_init",
                    server=self.config.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def post_init(self) -> None:
        """Run post-init hooks on modules."""
        logger.debug(
            f"Running post_init hooks for modules in server '{self.config.name}'"
        )
        with tracer.start_as_current_span("server.post_init") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                for module in self.get_enabled_components():
                    await module.on_post_server_init(self)
            except Exception as module_error:
                logger.error(
                    "Error during post_init",
                    server=self.config.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def pre_terminate(self) -> None:
        """Run pre-terminate hooks on modules."""
        logger.debug(
            f"Running post_init hooks for modules in server: '{self.config.name}'"
        )
        with tracer.start_as_current_span("server.pre_terminate") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                for module in self.get_enabled_components():
                    await module.on_pre_server_terminate(self)
            except Exception as module_error:
                logger.error(
                    "Error during pre_terminate",
                    server=self.config.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def post_terminate(self) -> None:
        """Run post-terminate hooks on modules."""
        logger.debug(
            f"Running post_terminate hooks for modules in server: '{self.config.name}'"
        )
        with tracer.start_as_current_span("server.post_terminate") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                for module in self.get_enabled_components():
                    await module.on_post_server_terminate(server=self)
            except Exception as module_error:
                logger.error(
                    "Error during post_terminate",
                    server=self.config.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def on_error(self, error: Exception) -> None:
        """Run on_error hooks on modules."""
        logger.debug(
            f"Running on_error hooks for modules in server '{self.config.name}'"
        )
        with tracer.start_as_current_span("server.on_error") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                for module in self.get_enabled_components():
                    await module.on_server_error(server=self, error=error)
            except Exception as module_error:
                logger.error(
                    "Error during on_error",
                    server=self.config.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def pre_mcp_call(self, arguments: Any | None = None) -> None:
        """Run pre_mcp_call-hooks on modules."""
        logger.debug(
            f"Running pre_mcp_call hooks for modules in server '{self.config.name}'"
        )
        with tracer.start_as_current_span("server.pre_mcp_call") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                for module in self.get_enabled_components():
                    await module.on_pre_mcp_call(
                        server=self, arguments=arguments
                    )
            except Exception as module_error:
                logger.error(
                    f"Error during pre_mcp_call: {module_error}",
                    server=self.config.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def post_mcp_call(self, result: Any) -> None:
        """Run Post MCP_call hooks on modules."""
        logger.debug(
            f"Running post_mcp_call hooks for modules in server '{self.config.name}'"
        )
        with tracer.start_as_current_span("server.post_mcp_call") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                for module in self.get_enabled_components():
                    await module.on_post_mcp_call(server=self, result=result)
            except Exception as module_error:
                logger.error(
                    "Error during post_mcp_call",
                    server=self.config.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    # --- Async Methods ---
    async def __aenter__(self) -> "FlockMCPServer":
        """Enter the asynchronous context for the server."""
        # Spin up the client-manager
        with tracer.start_as_current_span("server.__aenter__") as span:
            span.set_attribute("server.name", self.config.name)
            logger.info(f"server.__aenter__", server=self.config.name)
            try:
                await self.pre_init()
                self.client_manager = await self.initialize()
                await self.post_init()
                self.initialized = True
            except Exception as server_error:
                logger.error(
                    f"Error during __aenter__ for server '{self.config.name}'",
                    server=self.config.name,
                    error=server_error,
                )
                span.record_exception(server_error)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the asynchronous context for the server."""
        # tell the underlying client-manager to terminate connections
        # and unwind the clients.
        with tracer.start_as_current_span("server.__aexit__") as span:
            span.set_attribute("server.name", self.config.name)
            try:
                await self.pre_terminate()
                if self.initialized and self.client_manager:
                    # means we ran through the initialize()-method
                    # and the client manager is present
                    await self.client_manager.close_all()
                    self.client_manager = None
                    self.initialized = False
                await self.post_terminate()
                return
            except Exception as server_error:
                logger.error(
                    f"Error during __aexit__ for server '{self.config.name}'",
                    server=self.config.name,
                    error=server_error,
                )
                await self.on_error(error=server_error)
                span.record_exception(server_error)

    # --- Serialization Implementation ---
    def to_dict(self, path_type: str = "relative") -> dict[str, Any]:
        """Convert instance to dictionary representation suitable for serialization."""
        from flock.core.registry import get_registry

        registry = get_registry()

        exclude = ["modules", "config"]

        logger.debug(f"Serializing server '{self.config.name}' to dict.")
        # Use Pydantic's dump, exclued manually handled fields.
        data = self.model_dump(
            exclude=exclude,
            mode="json",  # Use json mode for better handling of standard types by Pydantic
            exclude_none=True,  # Exclude None values for cleaner output
        )

        # --- Let the config handle its own serialization ---
        config_data = self.config.to_dict(path_type=path_type)
        data["config"] = config_data


        builtin_by_transport = {}

        try:
            from flock.mcp.servers.sse.flock_sse_server import FlockSSEServer
            from flock.mcp.servers.stdio.flock_stdio_server import (
                FlockMCPStdioServer,
            )
            from flock.mcp.servers.streamable_http.flock_streamable_http_server import (
                FlockStreamableHttpServer,
            )
            from flock.mcp.servers.websockets.flock_websocket_server import (
                FlockWSServer,
            )

            builtin_by_transport = {
                "stdio": FlockMCPStdioServer,
                "streamable_http": FlockStreamableHttpServer,
                "sse": FlockSSEServer,
                "websockets": FlockWSServer,
            }
        except ImportError:
            builtin_by_transport = {}

        # --- Only emit full impl for non-builtins ---
        transport = getattr(
            self.config.connection_config, "transport_type", None
        )
        builtin_cls = builtin_by_transport.get(transport)

        if type(self) is not builtin_cls:
            file_path = inspect.getsourcefile(type(self))
            if path_type == "relative":
                file_path = os.path.relpath(file_path)
            data["implementation"] = {
                "class_name": type(self).__name__,
                "module_path": type(self).__module__,
                "file_path": file_path,
            }

        logger.debug(
            f"Base server data for '{self.config.name}': {list(data.keys())}"
        )
        serialized_modules = {}

        def add_serialized_component(component: Any, field_name: str):
            if component:
                comp_type = type(component)
                type_name = registry.get_component_type_name(
                    comp_type
                )  # Get registered name

                if type_name:
                    try:
                        serialized_component_data = serialize_item(component)

                        if not isinstance(serialized_component_data, dict):
                            logger.error(
                                f"Serialization of component {type_name} for field '{field_name}' did not result in a dictionary. Got: {type(serialized_component_data)}"
                            )
                            serialized_modules[field_name] = {
                                "type": type_name,
                                "name": getattr(component, "name", "unknown"),
                                "error": "serialization_failed_non_dict",
                            }
                        else:
                            serialized_component_data["type"] = type_name
                            serialized_modules[field_name] = (
                                serialized_component_data
                            )
                            logger.debug(
                                f"Successfully serialized component for field '{field_name}' (type: {type_name})"
                            )
                    except Exception as e:
                        logger.error(
                            f"Failed to serialize component {type_name} for field '{field_name}': {e}",
                            exc_info=True,
                        )

                else:
                    logger.warning(
                        f"Cannot serialize unregistered component {comp_type.__name__} for field '{field_name}'"
                    )

        serialized_modules = {}
        for module in self.modules.values():
            add_serialized_component(module, module.name)

        if serialized_modules:
            data["modules"] = serialized_modules
            logger.debug(
                f"Added {len(serialized_modules)} modules to server '{self.config.name}'"
            )

        def _clean(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: _clean(v)
                    for k, v in obj.items()
                    if v is not None
                    and not (isinstance(v, list | dict) and len(v) == 0)
                }
            if isinstance(obj, list):
                return [
                    _clean(v)
                    for v in obj
                    if v is not None
                    and not (isinstance(v, dict | list) and len(v) == 0)
                ]
            return obj

        data = _clean(data)
        return data

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize the server from a dictionary, including components."""
        logger.debug(
            f"Deserializing server from dict. Keys: {list(data.keys())}"
        )

        builtin_by_transport = {}

        try:
            from flock.mcp.servers.sse.flock_sse_server import FlockSSEServer
            from flock.mcp.servers.stdio.flock_stdio_server import (
                FlockMCPStdioServer,
            )
            from flock.mcp.servers.streamable_http.flock_streamable_http_server import (
                FlockStreamableHttpServer,
            )
            from flock.mcp.servers.websockets.flock_websocket_server import (
                FlockWSServer,
            )

            builtin_by_transport = {
                "stdio": FlockMCPStdioServer,
                "sse": FlockSSEServer,
                "streamable_http": FlockStreamableHttpServer,
                "websockets": FlockWSServer,
            }
        except ImportError:
            builtin_by_transport = {}

        # find custom impl or built-in
        impl = data.pop("implementation", None)
        if impl:
            mod = importlib.import_module(impl["module_path"])
            real_cls = getattr(mod, impl["class_name"])
        else:
            # built-in: inspect transport_type in data["config"]
            transport = data["config"]["connection_config"]["transport_type"]
            real_cls = builtin_by_transport.get(transport, cls)

        # deserialize the config:
        config_data = data.pop("config", None)
        if config_data:
            # Forcing a square into a round hole
            # pretty ugly, but gets the job done.
            try:
                config_field = real_cls.model_fields["config"]
                config_cls = config_field.annotation
            except (AttributeError, KeyError):
                # fallback if Pydantic v1 or missing
                config_cls = FlockMCPConfiguration
            config_object = config_cls.from_dict(config_data)
            data["config"] = config_object

        # now construct
        server = real_cls(**{k: v for k, v in data.items() if k not in ["modules", "components"]})

        # re-hydrate components (both legacy modules and new components)
        for cname, cdata in data.get("components", {}).items():
            server.add_component(deserialize_component(cdata, AgentComponent))

        # Handle legacy modules for backward compatibility during transition
        for mname, mdata in data.get("modules", {}).items():
            logger.warning(f"Legacy module '{mname}' found during deserialization - consider migrating to unified components")
            # Skip legacy modules during migration

        # --- Separate Data ---
        component_configs = {}
        server_data = {}
        component_keys = ["modules"]

        for key, value in data.items():
            if key in component_keys and value is not None:
                component_configs[key] = value
            else:
                server_data[key] = value

        logger.info(f"Successfully deserialized server '{server.config.name}'")
        return server
