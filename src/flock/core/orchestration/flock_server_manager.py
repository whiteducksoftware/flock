# src/flock/core/orchestration/flock_server_manager.py
"""Server management functionality for Flock orchestrator."""

from typing import TYPE_CHECKING

from flock.core.flock_server_manager import (
    FlockServerManager as InternalServerManager,
)
from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock import Flock
    from flock.core.mcp.flock_mcp_server import FlockMCPServer

logger = get_logger("flock.server_manager")


class FlockServerManager:
    """Handles server lifecycle management for Flock orchestrator."""

    def __init__(self, flock: "Flock"):
        self.flock = flock
        # Use the existing internal server manager
        self._internal_mgr = InternalServerManager()

    def add_server(self, server: "FlockMCPServer") -> "FlockMCPServer":
        """Adds a server instance to this Flock configuration and registry as well as set it up to be managed by internal manager."""
        from flock.core.mcp.flock_mcp_server import (
            FlockMCPServer as ConcreteFlockMCPServer,
        )
        from flock.core.registry import get_registry

        registry = get_registry()

        if not isinstance(server, ConcreteFlockMCPServer):
            raise TypeError("Provided object is not a FlockMCPServer instance.")
        if not server.config.name:
            raise ValueError("Server must have a name.")

        if server.config.name in self.flock.servers:
            raise ValueError(
                f"Server with this name already exists. Name: '{server.config.name}'"
            )

        self.flock._servers[server.config.name] = server
        registry.register_server(server)  # Register globally.

        # Prepare server to be managed by the FlockServerManager
        logger.info(f"Adding server '{server.config.name}' to managed list.")
        self._internal_mgr.add_server_sync(server=server)
        logger.info(f"Server '{server.config.name}' is now on managed list.")

        logger.info(f"Server '{server.config.name}' added to Flock '{self.flock.name}'")
        return server

    async def __aenter__(self):
        """Start all managed servers."""
        return await self._internal_mgr.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup all managed servers."""
        return await self._internal_mgr.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def servers(self) -> dict[str, "FlockMCPServer"]:
        """Returns the dictionary of servers managed by this Flock instance."""
        return self.flock._servers
