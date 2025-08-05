# src/flock/core/registry/server_registry.py
"""MCP Server registration and lookup functionality."""

import threading
from typing import TYPE_CHECKING

from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.mcp.flock_mcp_server import FlockMCPServer

logger = get_logger("registry.servers")


class ServerRegistry:
    """Manages FlockMCPServerBase registration and lookup with thread safety."""

    def __init__(self, lock: threading.RLock):
        self._lock = lock
        self._servers: dict[str, FlockMCPServer] = {}

    def register_server(self, server: "FlockMCPServer") -> None:
        """Register a flock mcp server by its name."""
        if not hasattr(server.config, "name") or not server.config.name:
            logger.error("Attempted to register a server without a valid 'name' attribute.")
            return

        with self._lock:
            if server.config.name in self._servers and self._servers[server.config.name] != server:
                logger.warning(f"Server '{server.config.name}' already registered. Overwriting.")

            self._servers[server.config.name] = server
            logger.debug(f"Registered server: {server.config.name}")

    def get_server(self, name: str) -> "FlockMCPServer | None":
        """Retrieve a registered FlockMCPServer instance by name."""
        with self._lock:
            server = self._servers.get(name)
            if not server:
                logger.warning(f"Server '{name}' not found in registry.")
            return server

    def get_all_server_names(self) -> list[str]:
        """Return a list of names for all registered servers."""
        with self._lock:
            return list(self._servers.keys())

    def get_all_servers(self) -> dict[str, "FlockMCPServer"]:
        """Get all registered servers."""
        with self._lock:
            return self._servers.copy()

    def clear(self) -> None:
        """Clear all registered servers."""
        with self._lock:
            self._servers.clear()
            logger.debug("Cleared all registered servers")
