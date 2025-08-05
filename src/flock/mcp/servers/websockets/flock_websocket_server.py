"""This module provides the default implementation for MCP servers using the websocket transport."""

import copy
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal

from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)
from mcp.client.websocket import websocket_client
from mcp.shared.message import SessionMessage
from opentelemetry import trace
from pydantic import Field

from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_server import FlockMCPServer
from flock.core.mcp.mcp_client import FlockMCPClient
from flock.core.mcp.mcp_client_manager import FlockMCPClientManager
from flock.core.mcp.mcp_config import (
    FlockMCPConfiguration,
    FlockMCPConnectionConfiguration,
)
from flock.core.mcp.types.types import WebsocketServerParameters

logger = get_logger("mcp.ws.server")
tracer = trace.get_tracer(__name__)


# Optional to provide type hints.
class FlockWSConnectionConfig(FlockMCPConnectionConfiguration):
    """Concrete ConnectionConfig for a WS Client."""

    # Only thing we need to override here is the concrete transport_type
    # and connection_parameters fields.
    transport_type: Literal["websockets"] = Field(
        default="websockets", description="Use the websockets transport type."
    )

    connection_parameters: WebsocketServerParameters = Field(
        ...,
        description="WebsocketServer parameters to be used for the websocket transport.",
    )


# Optional to provide type hints.
class FlockWSConfig(FlockMCPConfiguration):
    """Configuration for Websocket clients."""

    # The only thing we need to override here is the concrete
    # connection config. The rest is generic enough to handle
    # everything else. (This is just here so that type hints work for the
    # rest of the implementation, we could just omit this override entirely.)
    connection_config: FlockWSConnectionConfig = Field(
        ..., description="Concrete WS connection configuration"
    )


class FlockWSClient(FlockMCPClient):
    """Client for Websocket servers."""

    config: FlockWSConfig = Field(..., description="Client Configuration")

    # This one we HAVE to specify. This tells Flock
    # how to create the underlying connection.
    async def create_transport(
        self,
        params: WebsocketServerParameters,
        additional_params: dict[str, Any] | None = None,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[SessionMessage | Exception],
            MemoryObjectSendStream[SessionMessage],
        ]
    ]:
        """Return an async context manager whose __aenter__ method yields a read_stream and a send_stream."""
        # additional_params take precedence over passed config, as modules
        # can influece how to connect to a ws server.

        # avoid modifying the underlying config directly
        param_copy = copy.deepcopy(params)

        if additional_params and "url" in additional_params:
            # If present, then apply the changes in "url" to the create_transport logic.
            param_copy.url = additional_params.get("url", params.url)

        return websocket_client(
            url=param_copy.url
        )  # return the async context manager


# not really needed, but kept for type hints and as an example.
class FlockWSClientManager(FlockMCPClientManager):
    """Manager for handling websocket clients."""

    client_config: FlockWSConfig = Field(
        ..., description="Configuration for clients."
    )

    async def make_client(self, additional_params=None):
        """Create a new client instance."""
        new_client = FlockWSClient(
            config=self.client_config,
            additional_params=additional_params,
        )
        return new_client


class FlockWSServer(FlockMCPServer):
    """Class which represents an MCP Server using the websocket transport type."""

    config: FlockWSConfig = Field(..., description="Config for the server.")

    # Specify the concrete type for the server.
    async def initialize(self) -> FlockWSClientManager:
        """Called when initializing the server."""
        client_manager = FlockWSClientManager(client_config=self.config)

        return client_manager
