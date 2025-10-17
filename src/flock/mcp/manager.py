"""MCP Client Manager for Connection Pooling and Lifecycle Management.

This module provides the FlockMCPClientManager class which manages MCP client
connections with per-(agent_id, run_id) isolation and lazy connection establishment.

Architecture Decisions:
- AD004: Per-(agent_id, run_id) Connection Isolation
  Each unique (agent_id, run_id) pair gets its own set of isolated MCP connections
- AD005: Lazy Connection Establishment
  Connections are only established when first requested
- AD007: Graceful Degradation on MCP Failures
  Failures to connect to individual servers don't prevent agent execution
"""

import asyncio
from typing import Any

from flock.logging.logging import get_logger
from flock.mcp.client import FlockMCPClient
from flock.mcp.config import FlockMCPConfiguration


logger = get_logger(__name__)


class FlockMCPClientManager:
    """Manages MCP client connections with per-(agent_id, run_id) isolation.

    This manager implements lazy connection pooling where clients are only
    initialized when first requested. Each unique (agent_id, run_id) pair
    gets its own set of isolated MCP connections.

    Architecture Decision: AD004 - Per-(agent_id, run_id) Connection Isolation

    Example:
        ```python
        # Initialize manager with configurations
        configs = {
            "filesystem": FlockMCPConfiguration(
                name="filesystem",
                connection_config=connection_config,
                feature_config=feature_config,
            )
        }
        manager = FlockMCPClientManager(configs)

        # Get client for specific agent and run
        client = await manager.get_client("filesystem", "agent_1", "run_123")

        # Get all tools for agent
        tools = await manager.get_tools_for_agent(
            "agent_1", "run_123", {"filesystem"}
        )

        # Cleanup after run completes
        await manager.cleanup_run("agent_1", "run_123")
        ```
    """

    def __init__(self, configs: dict[str, FlockMCPConfiguration]):
        """Initialize the manager with MCP server configurations.

        Args:
            configs: Dictionary mapping server names to their configurations
        """
        self._configs = configs
        # Pool structure: (agent_id, run_id) → server_name → FlockMCPClient
        self._pool: dict[tuple[str, str], dict[str, FlockMCPClient]] = {}
        self._lock = asyncio.Lock()

    async def get_client(
        self,
        server_name: str,
        agent_id: str,
        run_id: str,
        mount_points: list[str] | None = None,
    ) -> FlockMCPClient:
        """Get or create an MCP client for the given context.

        Architecture Decision: AD005 - Lazy Connection Establishment
        Connections are only established when first requested.

        Args:
            server_name: Name of the MCP server
            agent_id: Agent requesting the client
            run_id: Current run identifier

        Returns:
            FlockMCPClient instance ready for use

        Raises:
            ValueError: If server_name not registered
        """
        if server_name not in self._configs:
            raise ValueError(
                f"MCP server '{server_name}' not registered. "
                f"Available servers: {list(self._configs.keys())}"
            )

        key = (agent_id, run_id)

        async with self._lock:
            # Check if we have a client pool for this (agent, run)
            if key not in self._pool:
                self._pool[key] = {}

            # Check if we have a client for this server
            if server_name not in self._pool[key]:
                logger.info(
                    f"Creating new MCP client for server '{server_name}' "
                    f"(agent={agent_id}, run={run_id})"
                )
                config = self._configs[server_name]
                # MCP-ROOTS: Override mount points if provided
                if mount_points:
                    from flock.mcp.types import MCPRoot

                    # Create MCPRoot objects from paths
                    roots = [
                        MCPRoot(uri=f"file://{path}", name=path.split("/")[-1])
                        for path in mount_points
                    ]
                    logger.info(
                        f"Setting {len(roots)} mount point(s) for server '{server_name}' "
                        f"(agent={agent_id}, run={run_id}): {[r.uri for r in roots]}"
                    )
                    # Clone config with new mount points
                    from copy import deepcopy

                    config = deepcopy(config)
                    config.connection_config.mount_points = roots

                # Instantiate the correct concrete client class based on transport type
                # Lazy import to avoid requiring all dependencies
                transport_type = config.connection_config.transport_type
                if transport_type == "stdio":
                    from flock.mcp.servers.stdio.flock_stdio_server import (
                        FlockStdioClient,
                    )

                    client = FlockStdioClient(config=config)
                elif transport_type == "sse":
                    from flock.mcp.servers.sse.flock_sse_server import (
                        FlockSSEClient,
                    )

                    client = FlockSSEClient(config=config)
                elif transport_type == "websocket":
                    from flock.mcp.servers.websockets.flock_websocket_server import (
                        FlockWSClient,
                    )

                    client = FlockWSClient(config=config)
                elif transport_type == "streamable_http":
                    from flock.mcp.servers.streamable_http.flock_streamable_http_server import (
                        FlockStreamableHttpClient,
                    )

                    client = FlockStreamableHttpClient(config=config)
                else:
                    raise ValueError(
                        f"Unsupported transport type: {transport_type}. "
                        f"Supported types: stdio, sse, websocket, streamable_http"
                    )

                await client._connect()
                self._pool[key][server_name] = client

            return self._pool[key][server_name]

    async def get_tools_for_agent(
        self,
        agent_id: str,
        run_id: str,
        server_names: set[str],
        server_mounts: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        """Get all tools from specified servers for an agent.

        Architecture Decision: AD003 - Tool Namespacing
        All tools are returned with format: {server}__{tool}

        Args:
            agent_id: Agent requesting tools
            run_id: Current run identifier
            server_names: Set of MCP server names to fetch tools from
            server_mounts: Optional dict mapping server names to mount points

        Returns:
            Dictionary mapping namespaced tool names to tool definitions

        Note:
            Architecture Decision: AD007 - Graceful Degradation
            If a server fails to load, we log the error and continue with
            other servers rather than failing the entire operation.
        """
        tools = {}
        server_mounts = server_mounts or {}

        for server_name in server_names:
            try:
                # Get mount points specific to this server
                mount_points = server_mounts.get(server_name)

                client = await self.get_client(
                    server_name, agent_id, run_id, mount_points=mount_points
                )
                server_tools = await client.get_tools(agent_id, run_id)

                # Apply namespacing: AD003
                for tool in server_tools:
                    namespaced_name = f"{server_name}__{tool.name}"
                    tools[namespaced_name] = {
                        "server_name": server_name,
                        "original_name": tool.name,
                        "tool": tool,
                        "client": client,
                    }

                logger.debug(
                    f"Loaded {len(server_tools)} tools from server '{server_name}' "
                    f"for agent {agent_id}"
                )

            except Exception as e:
                # Architecture Decision: AD007 - Graceful Degradation
                logger.exception(
                    f"Failed to load tools from MCP server '{server_name}': {e}. "
                    f"Agent {agent_id} will continue without these tools."
                )
                # Continue loading other servers
                continue

        return tools

    async def cleanup_run(self, agent_id: str, run_id: str) -> None:
        """Clean up all MCP connections for a completed run.

        Args:
            agent_id: Agent identifier
            run_id: Run identifier to clean up
        """
        key = (agent_id, run_id)

        async with self._lock:
            if key in self._pool:
                logger.info(f"Cleaning up MCP connections for run {run_id}")
                clients = self._pool[key]

                # Disconnect all clients for this run
                for server_name, client in clients.items():
                    try:
                        await client.disconnect()
                        logger.debug(f"Disconnected from MCP server '{server_name}'")
                    except Exception as e:
                        logger.warning(f"Error disconnecting from '{server_name}': {e}")

                # Remove from pool
                del self._pool[key]

    async def cleanup_all(self) -> None:
        """Clean up all MCP connections (orchestrator shutdown)."""
        async with self._lock:
            logger.info("Shutting down all MCP connections")

            for _key, clients in self._pool.items():
                for server_name, client in clients.items():
                    try:
                        await client.disconnect()
                    except Exception as e:
                        logger.warning(f"Error disconnecting from '{server_name}': {e}")

            self._pool.clear()
            logger.info("All MCP connections closed")

    def list_servers(self) -> dict[str, dict[str, Any]]:
        """List all registered MCP servers with their configurations.

        Returns:
            Dictionary mapping server names to configuration metadata
        """
        return {
            name: {
                "transport_type": config.connection_config.transport_type,
                "tools_enabled": config.feature_config.tools_enabled,
                "prompts_enabled": config.feature_config.prompts_enabled,
                "sampling_enabled": config.feature_config.sampling_enabled,
            }
            for name, config in self._configs.items()
        }
