"""MCP (Model Context Protocol) server management for orchestrator.

This module handles MCP server registration and client manager lifecycle.
Implements lazy connection establishment pattern (AD005).
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from flock.mcp import (
        FlockMCPClientManager,
        FlockMCPConfiguration,
        ServerParameters,
    )


class MCPManager:
    """Manages MCP server registration and client connections.

    Architecture Decision: AD001 - Two-Level Architecture
    MCP servers are registered at orchestrator level and assigned to agents.

    Architecture Decision: AD005 - Lazy Connection Establishment
    Connections are established only when get_mcp_manager() is first called.

    Attributes:
        _configs: Dict mapping server names to their configurations
        _client_manager: Lazy-initialized MCP client manager instance
    """

    def __init__(self) -> None:
        """Initialize the MCP manager with empty configuration."""
        self._configs: dict[str, FlockMCPConfiguration] = {}
        self._client_manager: FlockMCPClientManager | None = None

    def add_mcp(
        self,
        name: str,
        connection_params: ServerParameters,
        *,
        enable_tools_feature: bool = True,
        enable_prompts_feature: bool = True,
        enable_sampling_feature: bool = True,
        enable_roots_feature: bool = True,
        mount_points: list[str] | None = None,
        tool_whitelist: list[str] | None = None,
        read_timeout_seconds: float = 300,
        max_retries: int = 3,
        **kwargs,
    ) -> None:
        """Register an MCP server configuration.

        Args:
            name: Unique identifier for this MCP server
            connection_params: Server connection parameters
            enable_tools_feature: Enable tool execution
            enable_prompts_feature: Enable prompt templates
            enable_sampling_feature: Enable LLM sampling requests
            enable_roots_feature: Enable filesystem roots
            mount_points: Optional list of filesystem mount points
            tool_whitelist: Optional list of tool names to allow
            read_timeout_seconds: Timeout for server communications
            max_retries: Connection retry attempts

        Raises:
            ValueError: If server name already registered
        """
        if name in self._configs:
            raise ValueError(f"MCP server '{name}' is already registered.")

        # Import configuration types
        from flock.mcp import (
            FlockMCPConfiguration,
            FlockMCPConnectionConfiguration,
            FlockMCPFeatureConfiguration,
        )

        # Detect transport type
        from flock.mcp.types import (
            SseServerParameters,
            StdioServerParameters,
            StreamableHttpServerParameters,
            WebsocketServerParameters,
        )

        if isinstance(connection_params, StdioServerParameters):
            transport_type = "stdio"
        elif isinstance(connection_params, WebsocketServerParameters):
            transport_type = "websockets"
        elif isinstance(connection_params, SseServerParameters):
            transport_type = "sse"
        elif isinstance(connection_params, StreamableHttpServerParameters):
            transport_type = "streamable_http"
        else:
            transport_type = "custom"

        # Process mount points (convert paths to URIs)
        mcp_roots = None
        if mount_points:
            from pathlib import Path as PathLib

            from flock.mcp.types import MCPRoot

            mcp_roots = []
            for path in mount_points:
                # Normalize the path
                if path.startswith("file://"):
                    # Already a file URI
                    uri = path
                    # Extract path from URI for name
                    path_str = path.replace("file://", "")
                # the test:// path-prefix is used by testing servers such as the mcp-everything server.
                elif path.startswith("test://"):
                    # Already a test URI
                    uri = path
                    # Extract path from URI for name
                    path_str = path.replace("test://", "")
                else:
                    # Convert to absolute path and create URI
                    abs_path = PathLib(path).resolve()
                    uri = f"file://{abs_path}"
                    path_str = str(abs_path)

                # Extract a meaningful name (last component of path)
                name_component = (
                    PathLib(path_str).name
                    or path_str.rstrip("/").split("/")[-1]
                    or "root"
                )
                mcp_roots.append(MCPRoot(uri=uri, name=name_component))

        # Build configuration
        connection_config = FlockMCPConnectionConfiguration(
            max_retries=max_retries,
            connection_parameters=connection_params,
            transport_type=transport_type,
            read_timeout_seconds=read_timeout_seconds,
            mount_points=mcp_roots,
        )

        feature_config = FlockMCPFeatureConfiguration(
            tools_enabled=enable_tools_feature,
            prompts_enabled=enable_prompts_feature,
            sampling_enabled=enable_sampling_feature,
            roots_enabled=enable_roots_feature,
            tool_whitelist=tool_whitelist,
        )

        mcp_config = FlockMCPConfiguration(
            name=name,
            connection_config=connection_config,
            feature_config=feature_config,
        )

        self._configs[name] = mcp_config

    def get_mcp_manager(self) -> FlockMCPClientManager:
        """Get or create the MCP client manager.

        Architecture Decision: AD005 - Lazy Connection Establishment
        Connections are established only when this method is first called.

        Returns:
            FlockMCPClientManager instance

        Raises:
            RuntimeError: If no MCP servers registered
        """
        if not self._configs:
            raise RuntimeError("No MCP servers registered. Call add_mcp() first.")

        if self._client_manager is None:
            from flock.mcp import FlockMCPClientManager

            self._client_manager = FlockMCPClientManager(self._configs)

        return self._client_manager

    async def cleanup(self) -> None:
        """Clean up MCP connections.

        Called during orchestrator shutdown to properly close all MCP connections.
        """
        if self._client_manager is not None:
            await self._client_manager.cleanup_all()
            self._client_manager = None

    @property
    def configs(self) -> dict[str, FlockMCPConfiguration]:
        """Get the dictionary of MCP configurations."""
        return self._configs

    @property
    def has_configs(self) -> bool:
        """Check if any MCP servers are registered."""
        return bool(self._configs)


__all__ = ["MCPManager"]
