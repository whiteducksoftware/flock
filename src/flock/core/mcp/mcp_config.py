"""Base Config for MCP Clients."""

import importlib
from typing import Any, Literal, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, create_model

from flock.core.mcp.types.types import (
    FlockListRootsMCPCallback,
    FlockLoggingMCPCallback,
    FlockMessageHandlerMCPCallback,
    FlockSamplingMCPCallback,
    MCPRoot,
    ServerParameters,
    SseServerParameters,
    StdioServerParameters,
    StreamableHttpServerParameters,
    WebsocketServerParameters,
)
from flock.core.serialization.serializable import Serializable
from flock.core.serialization.serialization_utils import (
    deserialize_item,
    serialize_item,
)

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


A = TypeVar("A", bound="FlockMCPCallbackConfiguration")
B = TypeVar("B", bound="FlockMCPConnectionConfiguration")
C = TypeVar("C", bound="FlockMCPConfiguration")
D = TypeVar("D", bound="FlockMCPCachingConfiguration")
E = TypeVar("E", bound="FlockMCPFeatureConfiguration")


class FlockMCPCachingConfiguration(BaseModel, Serializable):
    """Configuration for Caching in Clients."""

    tool_cache_max_size: float = Field(
        default=100, description="Maximum number of items in the Tool Cache."
    )

    tool_cache_max_ttl: float = Field(
        default=60,
        description="Max TTL for items in the tool cache in seconds.",
    )

    resource_contents_cache_max_size: float = Field(
        default=10,
        description="Maximum number of entries in the Resource Contents cache.",
    )

    resource_contents_cache_max_ttl: float = Field(
        default=60 * 5,
        description="Maximum number of items in the Resource Contents cache.",
    )

    resource_list_cache_max_size: float = Field(
        default=10,
        description="Maximum number of entries in the Resource List Cache.",
    )

    resource_list_cache_max_ttl: float = Field(
        default=100,
        description="Maximum TTL for entries in the Resource List Cache.",
    )

    tool_result_cache_max_size: float = Field(
        default=1000,
        description="Maximum number of entries in the Tool Result Cache.",
    )

    tool_result_cache_max_ttl: float = Field(
        default=20,
        description="Maximum TTL in seconds for entries in the Tool Result Cache.",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def to_dict(self, path_type: str = "relative"):
        """Serialize the config object."""
        return self.model_dump(
            exclude_none=True,
            mode="json",
        )

    @classmethod
    def from_dict(cls: type[D], data: dict[str, Any]) -> D:
        """Deserialize from a dict."""
        return cls(**{k: v for k, v in data.items()})

    @classmethod
    def with_fields(cls: type[D], **field_definitions) -> type[D]:
        """Create a new config class with additional fields."""
        return create_model(
            f"Dynamic{cls.__name__}", __base__=cls, **field_definitions
        )


class FlockMCPCallbackConfiguration(BaseModel, Serializable):
    """Base Configuration Class for Callbacks for Clients."""

    sampling_callback: FlockSamplingMCPCallback | None = Field(
        default=None,
        description="Callback for handling sampling requests from an external server.",
    )

    list_roots_callback: FlockListRootsMCPCallback | None = Field(
        default=None, description="Callback for handling list roots requests."
    )

    logging_callback: FlockLoggingMCPCallback | None = Field(
        default=None,
        description="Callback for handling logging messages from an external server.",
    )

    message_handler: FlockMessageHandlerMCPCallback | None = Field(
        default=None,
        description="Callback for handling messages not covered by other callbacks.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def to_dict(self, path_type: str = "relative"):
        """Serialize the object."""
        # we need to register callables.
        data: dict[str, Any] = {}
        if self.sampling_callback:
            sampling_callback_data = serialize_item(self.sampling_callback)
            data["sampling_callback"] = sampling_callback_data

        if self.list_roots_callback:
            list_roots_callback_data = serialize_item(self.list_roots_callback)
            data["list_roots_callback"] = list_roots_callback_data

        if self.logging_callback:
            logging_callback_data = serialize_item(self.logging_callback)
            data["logging_callback"] = logging_callback_data

        if self.message_handler:
            message_handler_data = serialize_item(self.message_handler)
            data["message_handler"] = message_handler_data

        return data

    @classmethod
    def from_dict(cls: type[A], data: dict[str, Any]) -> A:
        """Deserialize from a dict."""
        instance = cls()
        if data:
            if "sampling_callback" in data:
                instance.sampling_callback = deserialize_item(
                    data["sampling_callback"]
                )
            if "list_roots_callback" in data:
                instance.list_roots_callback = deserialize_item(
                    data["list_roots_callback"]
                )
            if "logging_callback" in data:
                instance.logging_callback = deserialize_item(
                    data["logging_callback"]
                )
            if "message_handler" in data:
                instance.message_handler = deserialize_item(
                    data["message_handler"]
                )

        return instance

    @classmethod
    def with_fields(cls: type[A], **field_definitions) -> type[A]:
        """Create a new config class with additional fields."""
        return create_model(
            f"Dynamic{cls.__name__}", __base__=cls, **field_definitions
        )


class FlockMCPConnectionConfiguration(BaseModel, Serializable):
    """Base Configuration Class for Connection Parameters for a client."""

    max_retries: int = Field(
        default=3,
        description="How many times to attempt to establish the connection before giving up.",
    )

    connection_parameters: ServerParameters = Field(
        ..., description="Connection parameters for the server."
    )

    transport_type: Literal[
        "stdio", "websockets", "sse", "streamable_http", "custom"
    ] = Field(..., description="Type of transport to use.")

    mount_points: list[MCPRoot] | None = Field(
        default=None, description="Initial Mountpoints to operate under."
    )

    read_timeout_seconds: float | int = Field(
        default=60 * 5, description="Read Timeout."
    )

    server_logging_level: LoggingLevel = Field(
        default="error",
        description="The logging level for logging events from the remote server.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    def to_dict(self, path_type: str = "relative") -> dict[str, Any]:
        """Serialize object to a dict."""
        exclude = ["connection_parameters"]

        data = self.model_dump(
            exclude=exclude,
            exclude_defaults=False,
            exclude_none=True,
            mode="json",
        )

        data["connection_parameters"] = self.connection_parameters.to_dict(
            path_type=path_type
        )

        return data

    @classmethod
    def from_dict(cls: type[B], data: dict[str, Any]) -> B:
        """Deserialize from dict."""
        connection_params = data.get("connection_parameters")
        connection_params_obj = None
        auth_obj: httpx.Auth | None = None
        if connection_params:
            kind = connection_params.get("transport_type", None)
            auth_spec = connection_params.get("auth", None)
            if auth_spec:
                # find the concrete implementation and
                # instantiate it.
                    # find the concrete implementation for auth and instatiate it.
                impl = auth_spec.get("implementation", None)
                params = auth_spec.get("params", None)
                if impl and params:
                        mod = importlib.import_module(impl["module_path"])
                        real_cls = getattr(mod, impl["class_name"])
                        auth_obj = real_cls(**{k: v for k, v in params.items()})

                if auth_obj:
                    connection_params["auth"] = auth_obj
                else:
                    # just to be sure
                    connection_params.pop("auth", None)
                match kind:
                    case "stdio":
                        connection_params_obj = StdioServerParameters(
                            **{k: v for k, v in connection_params.items()}
                        )
                    case "websockets":
                        connection_params_obj = WebsocketServerParameters(
                            **{k: v for k, v in connection_params.items()}
                        )
                    case "streamable_http":
                        connection_params_obj = StreamableHttpServerParameters(
                            **{k: v for k, v in connection_params.items()}
                        )
                    case "sse":
                        connection_params_obj = SseServerParameters(
                            **{k: v for k, v in connection_params.items()}
                        )
                    case _:
                        # handle custom server params
                        connection_params_obj = ServerParameters(
                            **{k: v for k, v in connection_params.items()}
                        )

        if connection_params_obj:
            data["connection_parameters"] = connection_params_obj
            return cls(**{k: v for k, v in data.items()})
        else:
            raise ValueError("No connection parameters provided.")

    @classmethod
    def with_fields(cls: type[B], **field_definitions) -> type[B]:
        """Create a new config class with additional fields."""
        return create_model(
            f"Dynamic{cls.__name__}", __base__=cls, **field_definitions
        )


class FlockMCPFeatureConfiguration(BaseModel, Serializable):
    """Base Configuration Class for switching MCP Features on and off."""

    roots_enabled: bool = Field(
        default=False,
        description="Whether or not the Roots feature is enabled for this client.",
    )

    sampling_enabled: bool = Field(
        default=False,
        description="Whether or not the Sampling feature is enabled for this client.",
    )

    tools_enabled: bool = Field(
        default=False,
        description="Whether or not the Tools feature is enabled for this client.",
    )

    prompts_enabled: bool = Field(
        default=False,
        description="Whether or not the Prompts feature is enabled for this client.",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def to_dict(self, path_type: str = "relative"):
        """Serialize the object."""
        return self.model_dump(
            mode="json",
            exclude_none=True,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Deserialize from a dict."""
        return cls(**{k: v for k, v in data.items()})

    @classmethod
    def with_fields(cls: type[E], **field_definitions) -> type[E]:
        """Create a new config class with additional fields."""
        return create_model(
            f"Dynamic{cls.__name__}", __base__=cls, **field_definitions
        )


class FlockMCPConfiguration(BaseModel, Serializable):
    """Base Configuration Class for MCP Clients.

    Each Client should implement their own config
    model by inheriting from this class.
    """

    name: str = Field(
        ..., description="Name of the server the client connects to."
    )

    connection_config: FlockMCPConnectionConfiguration = Field(
        ..., description="MCP Connection Configuration for a client."
    )

    caching_config: FlockMCPCachingConfiguration = Field(
        default_factory=FlockMCPCachingConfiguration,
        description="Configuration for the internal caches of the client.",
    )

    callback_config: FlockMCPCallbackConfiguration = Field(
        default_factory=FlockMCPCallbackConfiguration,
        description="Callback configuration for the client.",
    )

    feature_config: FlockMCPFeatureConfiguration = Field(
        default_factory=FlockMCPFeatureConfiguration,
        description="Feature configuration for the client.",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def to_dict(self, path_type: str = "relative") -> dict[str, Any]:
        """Serialize the object to a dict."""
        # each built-in type should serialize, deserialize it self.
        exclude = [
            "connection_config",
            "caching_config",
            "callback_config",
            "feature_config",
        ]

        data = self.model_dump(
            exclude=exclude,
            exclude_defaults=False,
            exclude_none=True,
            mode="json",
        )

        # add the core properties
        data["connection_config"] = self.connection_config.to_dict(path_type)
        data["caching_config"] = self.caching_config.to_dict(path_type)
        data["callback_config"] = self.callback_config.to_dict(path_type)
        data["feature_config"] = self.feature_config.to_dict(path_type)

        return data

    @classmethod
    def from_dict(cls: type[C], data: dict[str, Any]) -> C:
        """Deserialize the class."""
        connection_config = data.pop("connection_config", None)
        caching_config = data.pop("caching_config", None)
        feature_config = data.pop("feature_config", None)
        callback_config = data.pop("callback_config", None)

        instance_data: dict[str, Any] = {
            "name": data["name"]
        }

        if connection_config:
            # Forcing a square into a round hole
            try:
                config_field = cls.model_fields["connection_config"]
                config_cls = config_field.annotation
            except (AttributeError, KeyError):
                # fallback
                config_cls = FlockMCPConnectionConfiguration
            instance_data["connection_config"] = config_cls.from_dict(connection_config)
        else:
            raise ValueError(f"connection_config MUST be specified for '{data.get('name', 'unknown_server')}")

        if caching_config:
            try:
                config_field = cls.model_fields["caching_config"]
                config_cls = config_field.annotation
            except (AttributeError, KeyError):
                # fallback
                config_cls = FlockMCPCachingConfiguration
            instance_data["caching_config"] = config_cls.from_dict(caching_config)
        else:
            instance_data["caching_config"] = FlockMCPCachingConfiguration()

        if feature_config:
            try:
                config_field = cls.model_fields["feature_config"]
                config_cls = config_field.annotation
            except (AttributeError, KeyError):
                # fallback
                config_cls = FlockMCPFeatureConfiguration
            instance_data["feature_config"] = config_cls.from_dict(feature_config)
        else:
            instance_data["feature_config"] = FlockMCPFeatureConfiguration()

        if callback_config:
            try:
                config_field = cls.model_fields["callback_config"]
                config_cls = config_field.annotation
            except (AttributeError, KeyError):
                # fallback
                config_cls = FlockMCPCallbackConfiguration
            instance_data["callback_config"] = config_cls.from_dict(callback_config)
        else:
            instance_data["callback_config"] = FlockMCPCallbackConfiguration()

        return cls(**{k: v for k, v in instance_data.items()})

    @classmethod
    def with_fields(cls: type[C], **field_definitions) -> type[C]:
        """Create a new config class with additional fields."""
        return create_model(
            f"Dynamic{cls.__name__}", __base__=cls, **field_definitions
        )
