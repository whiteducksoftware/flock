"""This module provides the Flock Streamable-Http functionality."""

import copy
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import timedelta
from typing import Any, Literal

import httpx
from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)
from mcp.client.streamable_http import streamablehttp_client
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
from flock.core.mcp.types.types import (
    StreamableHttpServerParameters,
)

logger = get_logger("mcp.streamable_http.server")
tracer = trace.get_tracer(__name__)

GetSessionIdCallback = Callable[[], str | None]


class FlockStreamableHttpConnectionConfig(FlockMCPConnectionConfiguration):
    """Concrete ConnectionConfig for a StreamableHttpClient."""

    # Only thing we need to override here is the concrete transport_type
    # and connection parameter fields.
    transport_type: Literal["streamable_http"] = Field(
        default="streamable_http",
        description="Use the streamable_http Transport type.",
    )

    connection_parameters: StreamableHttpServerParameters = Field(
        ..., description="Streamable HTTP Server Connection Parameters."
    )


class FlockStreamableHttpConfig(FlockMCPConfiguration):
    """Configuration for Streamable HTTP Clients."""

    # The only thing we need to override here is the
    # concrete connection config.
    # The rest is generic enough to handle everything else.
    connection_config: FlockStreamableHttpConnectionConfig = Field(
        ..., description="Concrete StreamableHttp Connection Configuration."
    )


class FlockStreamableHttpClient(FlockMCPClient):
    """Client for StreamableHttpServers."""

    config: FlockStreamableHttpConfig = Field(
        ..., description="Client configuration."
    )

    async def create_transport(
        self,
        params: StreamableHttpServerParameters,
        additional_params: dict[str, Any] | None = None,
    ) -> AbstractAsyncContextManager[
    tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
        GetSessionIdCallback,
    ],
    None,
]:
        """Return an async context manager whose __aenter__ method yields (read_stream, send_stream)."""
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
            if "auth" in additional_params and isinstance(
                additional_params.get("auth"), httpx.Auth
            ):
                param_copy.auth = additional_params.get("auth", param_copy.auth)

            if "read_timeout_seconds" in additional_params:
                param_copy.timeout = additional_params.get(
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

            if "terminate_on_close" in additional_params:
                param_copy.terminate_on_close = bool(
                    additional_params.get("terminate_on_close", True)
                )

        timeout_http = timedelta(seconds=param_copy.timeout)
        sse_timeout = timedelta(seconds=param_copy.sse_read_timeout)

        return streamablehttp_client(
            url=param_copy.url,
            headers=param_copy.headers,
            timeout=timeout_http,
            sse_read_timeout=sse_timeout,
            terminate_on_close=param_copy.terminate_on_close,
            auth=param_copy.auth,
        )


class FlockStreamableHttpClientManager(FlockMCPClientManager):
    """Manager for handling StreamableHttpClients."""

    client_config: FlockStreamableHttpConfig = Field(
        ..., description="Configuration for clients."
    )

    async def make_client(
        self, additional_params: dict[str, Any] | None = None
    ) -> FlockStreamableHttpClient:
        """Create a new client instance."""
        new_client = FlockStreamableHttpClient(
            config=self.client_config,
            additional_params=additional_params,
        )
        return new_client


class FlockStreamableHttpServer(FlockMCPServer):
    """Class which represents a MCP Server using the streamable Http Transport type."""

    config: FlockStreamableHttpConfig = Field(
        ..., description="Config for the server."
    )

    async def initialize(self) -> FlockStreamableHttpClientManager:
        """Called when initializing the server."""
        client_manager = FlockStreamableHttpClientManager(
            client_config=self.config
        )

        return client_manager
