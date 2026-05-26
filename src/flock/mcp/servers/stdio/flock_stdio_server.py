"""This module provides the default implementation for MCP servers using the stdio transport."""

import copy
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal

from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)
from mcp import stdio_client
from mcp.types import JSONRPCMessage
from opentelemetry import trace
from pydantic import Field

from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_server import FlockMCPServerBase
from flock.core.mcp.mcp_client import FlockMCPClientBase
from flock.core.mcp.mcp_client_manager import FlockMCPClientManagerBase
from flock.core.mcp.mcp_config import (
    FlockMCPConfigurationBase,
    FlockMCPConnectionConfigurationBase,
)
from flock.core.mcp.types.types import StdioServerParameters

logger = get_logger("mcp.stdio.server")
tracer = trace.get_tracer(__name__)


class FlockStdioConnectionConfig(FlockMCPConnectionConfigurationBase):
    """Concrete ConnectionConfig for an StdioClient."""

    # Only thing we need to override here is the concrete transport_type
    # and connection_parameters fields.
    transport_type: Literal["stdio"] = Field(
        default="stdio", description="Use the stdio transport type."
    )

    connection_parameters: StdioServerParameters = Field(
        ...,
        description="StdioServerParameters to be used for the stdio transport.",
    )


class FlockStdioConfig(FlockMCPConfigurationBase):
    """Configuration for Stdio Clients."""

    # The only thing we need to override here is the
    # concrete connection config. The rest is generic
    # enough to handle everything else.
    connection_config: FlockStdioConnectionConfig = Field(
        ..., description="Concrete Stdio Connection Configuration."
    )


class FlockStdioClient(FlockMCPClientBase):
    """Client for Stdio Servers."""

    config: FlockStdioConfig = Field(..., description="Client Configuration.")

    async def create_transport(
        self,
        params: StdioServerParameters,
        additional_params: dict[str, Any] | None = None,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[JSONRPCMessage | Exception],
            MemoryObjectSendStream[JSONRPCMessage],
        ]
    ]:
        """Return an async context manager whose __aenter__ method yields (read_stream, send_stream)."""
        # additional_params take precedence over passed config, as modules can influence
        # how to connect to a stdio server.

        # avoid modifying the config of the client as a side-effect.
        param_copy = copy.deepcopy(params)

        if additional_params:
            # If it is present, then modify server parameters based on certain keys.
            if "command" in additional_params:
                param_copy.command = additional_params.get(
                    "command", params.command
                )
            if "args" in additional_params:
                param_copy.args = additional_params.get("args", params.command)
            if "env" in additional_params:
                param_copy.env = additional_params.get("env", params.env)

            if "cwd" in additional_params:
                param_copy.cwd = additional_params.get("cwd", params.env)

            if "encoding" in additional_params:
                param_copy.encoding = additional_params.get(
                    "encoding", params.encoding
                )

            if "encoding_error_handler" in additional_params:
                param_copy.encoding_error_handler = additional_params.get(
                    "encoding_error_handler", params.encoding_error_handler
                )

        # stdio_client already is an AsyncContextManager
        return stdio_client(server=param_copy)


# Not really needed but kept here as an example.
class FlockStdioClientManager(FlockMCPClientManagerBase):
    """Manager for handling Stdio Clients."""

    client_config: FlockStdioConfig = Field(
        ..., description="Configuration for clients."
    )

    async def make_client(
        self, additional_params: dict[str, Any] | None = None
    ):
        """Create a new client instance with any additional parameters."""
        new_client = FlockStdioClient(
            config=self.client_config,
            additional_params=additional_params,
        )
        return new_client


class FlockMCPStdioServer(FlockMCPServerBase):
    """Class which represents a MCP Server using the Stdio Transport type.

    This means (most likely) that the server is a locally
    executed script.
    """

    config: FlockStdioConfig = Field(..., description="Config for the server.")

    async def initialize(self) -> FlockStdioClientManager:
        """Called when initializing the server."""
        client_manager = FlockStdioClientManager(client_config=self.config)

        return client_manager
