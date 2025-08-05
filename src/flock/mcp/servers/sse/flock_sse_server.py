"""This module provides the Flock SSE Server functionality."""

import copy
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal

import httpx
from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)
from mcp.client.sse import sse_client
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
from flock.core.mcp.types.types import SseServerParameters

logger = get_logger("mcp.sse.server")
tracer = trace.get_tracer(__name__)


class FlockSSEConnectionConfig(FlockMCPConnectionConfiguration):
    """Concrete ConnectionConfig for an SSEClient."""

    # Only thing we need to override here is the concrete transport_type
    # and connection_parameters fields.
    transport_type: Literal["sse"] = Field(
        default="sse", description="Use the sse transport type."
    )

    connection_parameters: SseServerParameters = Field(
        ..., description="SSE Server Connection Parameters."
    )


class FlockSSEConfig(FlockMCPConfiguration):
    """Configuration for SSE Clients."""

    # The only thing we need to override here is the concrete
    # connection config. The rest is generic enough to handle
    # everything else.
    connection_config: FlockSSEConnectionConfig = Field(
        ..., description="Concrete SSE Connection Configuration."
    )


class FlockSSEClient(FlockMCPClient):
    """Client for SSE Servers."""

    config: FlockSSEConfig = Field(..., description="Client configuration.")

    async def create_transport(
        self,
        params: SseServerParameters,
        additional_params: dict[str, Any] | None = None,
    ) -> AbstractAsyncContextManager[
        tuple[
            MemoryObjectReceiveStream[SessionMessage | Exception],
            MemoryObjectSendStream[SessionMessage],
        ]
    ]:
        """Return an async context manager whose __aenter__ method yields (read_stream, send_stream)."""
        # avoid modifying the config of the client as a side-effect.
        param_copy = copy.deepcopy(params)

        if additional_params:
            override_headers = bool(
                additional_params.get("override_headers", False)
            )
            if "headers" in additional_params:
                if override_headers:
                    param_copy.headers = additional_params.get(
                        "headers", params.headers
                    )
                else:
                    param_copy.headers.update(
                        additional_params.get("headers", {})
                    )
            if "read_timeout_seconds" in additional_params:
                param_copy.timeout =  additional_params.get(
                    "read_timeout_seconds", params.timeout
                )

            if "sse_read_timeout" in additional_params:
                param_copy.sse_read_timeout = additional_params.get(
                    "sse_read_timeout",
                    params.sse_read_timeout,
                )
            if "url" in additional_params:
                param_copy.url = additional_params.get(
                    "url",
                    params.url,
                )

            if "auth" in additional_params and isinstance(
                additional_params.get("auth"), httpx.Auth
            ):
                param_copy.auth = additional_params.get("auth", param_copy.auth)

        return sse_client(
            url=param_copy.url,
            auth=param_copy.auth,
            headers=param_copy.headers,
            timeout=float(param_copy.timeout),
            sse_read_timeout=float(param_copy.sse_read_timeout),
        )


class FlockSSEClientManager(FlockMCPClientManager):
    """Manager for handling SSE Clients."""

    client_config: FlockSSEConfig = Field(
        ..., description="Configuration for clients."
    )

    async def make_client(
        self, additional_params: dict[str, Any]
    ) -> FlockSSEClient:
        """Create a new client instance."""
        new_client = FlockSSEClient(
            config=self.client_config, additional_params=additional_params
        )
        return new_client


class FlockSSEServer(FlockMCPServer):
    """Class which represents a MCP Server using the SSE Transport type."""

    config: FlockSSEConfig = Field(..., description="Config for the server.")

    async def initialize(self) -> FlockSSEClientManager:
        """Called when initializing the server."""
        client_manager = FlockSSEClientManager(
            client_config=self.config,
        )

        return client_manager
