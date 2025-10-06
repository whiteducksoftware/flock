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

from flock.logging.logging import get_logger
from flock.mcp.client import FlockMCPClient
from flock.mcp.config import (
    FlockMCPConfiguration,
    FlockMCPConnectionConfiguration,
)
from flock.mcp.types import StdioServerParameters


logger = get_logger("mcp.stdio.server")
tracer = trace.get_tracer(__name__)


class FlockStdioConnectionConfig(FlockMCPConnectionConfiguration):
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


class FlockStdioConfig(FlockMCPConfiguration):
    """Configuration for Stdio Clients."""

    # The only thing we need to override here is the
    # concrete connection config. The rest is generic
    # enough to handle everything else.
    connection_config: FlockStdioConnectionConfig = Field(
        ..., description="Concrete Stdio Connection Configuration."
    )


class FlockStdioClient(FlockMCPClient):
    """Client for Stdio Servers."""

    config: FlockMCPConfiguration = Field(..., description="Client Configuration.")

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
                param_copy.command = additional_params.get("command", params.command)
            if "args" in additional_params:
                param_copy.args = additional_params.get("args", params.command)
            if "env" in additional_params:
                param_copy.env = additional_params.get("env", params.env)

            if "cwd" in additional_params:
                param_copy.cwd = additional_params.get("cwd", params.env)

            if "encoding" in additional_params:
                param_copy.encoding = additional_params.get("encoding", params.encoding)

            if "encoding_error_handler" in additional_params:
                param_copy.encoding_error_handler = additional_params.get(
                    "encoding_error_handler", params.encoding_error_handler
                )

        # stdio_client already is an AsyncContextManager
        return stdio_client(server=param_copy)
