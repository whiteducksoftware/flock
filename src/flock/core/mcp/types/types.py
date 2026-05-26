"""Types for Flock's MCP functionality."""

import importlib
import inspect
import os
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal

import httpx
from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)
from mcp import (
    ClientSession,
    CreateMessageResult,
    StdioServerParameters as _MCPStdioServerParameters,
)
from mcp.shared.context import RequestContext
from mcp.shared.session import RequestResponder
from mcp.types import (
    CancelledNotification as _MCPCancelledNotification,
    ClientResult,
    CreateMessageRequestParams,
    ErrorData,
    JSONRPCMessage,
    ListRootsResult,
    LoggingMessageNotification as _MCPLoggingMessageNotification,
    LoggingMessageNotificationParams as _MCPLoggingMessageNotificationParams,
    ProgressNotification as _MCPProgressNotification,
    PromptListChangedNotification as _MCPPromptListChangedNotification,
    ResourceListChangedNotification as _MCPResourceListChangedNotification,
    ResourceUpdatedNotification as _MCPResourceUpdateNotification,
    Root as _MCPRoot,
    ServerNotification as _MCPServerNotification,
    ServerRequest,
    ToolListChangedNotification as _MCPToolListChangedNotification,
)
from pydantic import AnyUrl, BaseModel, ConfigDict, Field

from flock.core.mcp.util.helpers import get_default_env
from flock.core.serialization.serializable import Serializable


class ServerNotification(_MCPServerNotification):
    """A notification message sent by the server side."""


class CancelledNotification(_MCPCancelledNotification):
    """Notification, which can be sent bei either side to indicate that it is cancelling a previously issued request."""


class ProgressNotification(_MCPProgressNotification):
    """An out-of band notification used to inform the receiver of a progress update for a long-running request."""


class LoggingMessageNotification(_MCPLoggingMessageNotification):
    """A notification message sent by the server side containing a logging message."""


class ResourceUpdatedNotification(_MCPResourceUpdateNotification):
    """A notification message sent by the server side informing a client about a change in a resource."""


class ResourceListChangedNotification(_MCPResourceListChangedNotification):
    """A notification message sent by the server side informing a client about a change in the list of resources."""


class ToolListChangedNotification(_MCPToolListChangedNotification):
    """A notification message sent by the server side informing a client about a change in the offered tools."""


class PromptListChangedNotification(_MCPPromptListChangedNotification):
    """A notification message sent by the server side informing a client about a change in the list of offered Prompts."""


class FlockLoggingMessageNotificationParams(
    _MCPLoggingMessageNotificationParams
):
    """Parameters contained within a Logging Message Notification."""


class MCPRoot(_MCPRoot):
    """Wrapper for mcp.types.Root."""


class ServerParameters(BaseModel, Serializable):
    """Base Type for server parameters."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    transport_type: Literal["stdio", "websockets", "sse", "streamable_http"] = Field(
        ...,
        description="which type of transport these connection params are used for."
    )

    def to_dict(self, path_type: str = "relative"):
        """Serialize."""
        return self.model_dump(
            exclude_defaults=False,
            exclude_none=True,
            mode="json"
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Deserialize."""
        return cls(**data)


class StdioServerParameters(_MCPStdioServerParameters, ServerParameters):
    """Base Type for Stdio Server parameters."""

    transport_type: Literal["stdio"] = Field(
        default="stdio",
        description="Use stdio params."
    )

    env: dict[str, str] | None = Field(
        default_factory=get_default_env,
        description="Environment for the MCP Server.",
    )


class WebsocketServerParameters(ServerParameters):
    """Base Type for Websocket Server params."""

    transport_type: Literal["websockets"] = Field(
        default="websockets",
        description="Use websocket params."
    )

    url: str | AnyUrl = Field(..., description="Url the server listens at.")

class StreamableHttpServerParameters(ServerParameters):
    """Base Type for StreamableHttp params."""

    transport_type: Literal["streamable_http"] = Field(
        default="streamable_http",
        description="Use streamable http params."
    )

    url: str | AnyUrl = Field(
        ...,
        description="The url the server listens at."
    )

    headers: dict[str, Any] | None = Field(
        default=None,
        description="Additional headers to pass to the client."
    )

    timeout: float | int = Field(
        default=5,
        description="Http Timeout",
    )

    sse_read_timeout: float | int = Field(
        default=60*5,
        description="How long the client will wait before disconnecting from the server."
    )

    terminate_on_close: bool = Field(
        default=True,
        description="Terminate connection on close"
    )

    auth: httpx.Auth | None = Field(
        default=None,
        description="Httpx Auth Scheme"
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Deserialize the object from a dict."""
        # find and import the concrete implementation for
        # the auth object
        auth_obj: httpx.Auth | None = None
        auth_impl = data.pop("auth", None)
        if auth_impl:
            # find the concrete implementation
            impl = auth_impl.pop("implementation", None)
            params = auth_impl.pop("params", None)
            if impl:
                mod = importlib.import_module(impl["module_path"])
                real_cls = getattr(mod, impl["classname"])
                if params:
                    auth_obj = real_cls(**{k: v for k, v in params.items()})
                else:
                    # assume that the implementation handles it.
                    auth_obj = real_cls()
            else:
                raise ValueError("No concrete implementation for auth provided.")

        data["auth"] = auth_obj
        return cls(**{k: v for k, v in data.items()})

    def to_dict(self, path_type = "relative"):
        """Serialize the object."""
        exclude = ["auth"]

        data = self.model_dump(
            exclude=exclude,
            exclude_defaults=False,
            exclude_none=True,
        )

        # inject implentation info for auth
        if self.auth is not None:
            file_path = inspect.getsourcefile(type(self.auth))
            if path_type == "relative":
                file_path = os.path.relpath(file_path)
            try:
                # params should be primitive types, keeping with the
                # declarative approach of flock.
                params = {
                    k: getattr(self.auth, k)
                    for k in getattr(self.auth, "__dict__", {})
                    if not k.startswith("_")
                }
            except Exception:
                params = None

        data["auth"] = {
            "implementation": {
                "class_name": type(self.auth).__name__,
                "module_path": type(self.auth).__module__,
                "file_path": file_path,
            },
            "params": params,
        }

        return data

class SseServerParameters(ServerParameters):
    """Base Type for SSE Server params."""

    transport_type: Literal["sse"] = Field(
        default="sse",
        description="Use sse server params."
    )

    url: str | AnyUrl = Field(..., description="The url the server listens at.")

    headers: dict[str, Any] | None = Field(
        default=None, description="Additional Headers to pass to the client."
    )

    timeout: float | int = Field(default=5, description="Http Timeout")

    sse_read_timeout: float | int = Field(
        default=60 * 5,
        description="How long the client will wait before disconnecting from the server.",
    )

    auth: httpx.Auth | None = Field(
        default=None,
        description="Httpx Auth Scheme."
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Deserialize the object from a dict."""
        # find and import the concrete implementation for
        # the auth object.
        auth_obj: httpx.Auth | None = None
        auth_impl = data.pop("auth", None) # get the specs for the auth class
        if auth_impl:
            # find the concrete implementation
            impl = auth_impl.pop("implementation", None)
            params = auth_impl.pop("params", None)
            if impl:
                mod = importlib.import_module(impl["module_path"])
                real_cls = getattr(mod, impl["class_name"])
                if params:
                    auth_obj = real_cls(**{k: v for k, v in params.items()})
                else:
                    # assume that implementation handles it
                    auth_obj = real_cls()
            else:
                raise ValueError("No concrete implementation for auth provided.")

        data["auth"] = auth_obj
        return cls(**{k: v for k, v in data.items()})

    def to_dict(self, path_type = "relative"):
        """Serialize the object."""
        exclude = ["auth"]

        data = self.model_dump(
            exclude=exclude,
            exclude_defaults=False,
            exclude_none=True,
        )

        # inject implentation info for auth
        if self.auth is not None:
            file_path = inspect.getsourcefile(type(self.auth))
            if path_type == "relative":
                file_path = os.path.relpath(file_path)
            try:
                # params should be primitive types, keeping with the
                # declarative approach of flock.
                params = {
                    k: getattr(self.auth, k)
                    for k in getattr(self.auth, "__dict__", {})
                    if not k.startswith("_")
                }
            except Exception:
                params = None

        data["auth"] = {
            "implementation": {
                "class_name": type(self.auth).__name__,
                "module_path": type(self.auth).__module__,
                "file_path": file_path,
            },
            "params": params,
        }

        return data

MCPCLientInitFunction = Callable[
    ...,
    AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[JSONRPCMessage | Exception],
            MemoryObjectSendStream[JSONRPCMessage],
        ]
    ],
]


FlockSamplingMCPCallback = Callable[
    [RequestContext, CreateMessageRequestParams],
    Awaitable[CreateMessageResult | ErrorData],
]


FlockListRootsMCPCallback = Callable[
    [RequestContext[ClientSession, Any]],
    Awaitable[ListRootsResult | ErrorData],
]

FlockLoggingMCPCallback = Callable[
    [FlockLoggingMessageNotificationParams],
    Awaitable[None],
]

FlockMessageHandlerMCPCallback = Callable[
    [
        RequestResponder[ServerRequest, ClientResult]
        | ServerNotification
        | Exception
    ],
    Awaitable[None],
]
