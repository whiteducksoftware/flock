"""Manages Server-Lifecycles within the larger lifecycle of Flock."""

import asyncio
from contextlib import AsyncExitStack

from anyio import Lock
from pydantic import BaseModel, ConfigDict, Field

from flock.core.mcp.flock_mcp_server import FlockMCPServerBase


class FlockServerManager(BaseModel):
    """Async-context-manager to start/stop a set of Flock MCP servers."""

    servers: list[FlockMCPServerBase] | None = Field(
        ..., exclude=True, description="The servers to manage."
    )

    stack: AsyncExitStack | None = Field(
        default=None,
        exclude=True,
        description="Central exit stack for managing the execution context of the servers.",
    )

    lock: Lock | None = Field(
        default=None, exclude=True, description="Global lock for mutex access."
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def __init__(
        self,
        servers: list[FlockMCPServerBase] | None = None,
        stack: AsyncExitStack | None = None,
        lock: asyncio.Lock | None = None,
    ) -> None:
        """Initialize the FlockServerManager with optional server, stack, and lock references."""
        super().__init__(
            servers=servers,
            stack=stack,
            lock=lock,
        )

    def add_server_sync(self, server: FlockMCPServerBase) -> None:
        """Add a server to be managed by the ServerManager.

        Note:
          IT IS CRUCIAL THAT THIS METHOD IS NOT CALLED
          WHEN THE SERVER MANAGER HAS ALREADY BEEN INTIALIZED
          (with server_manager as manager: ...)
          OTHERWISE EXECUTION WILL BREAK DOWN.
        """
        if self.servers is None:
            self.servers = []

        self.servers.append(server)

    def remove_server_sync(self, server: FlockMCPServerBase) -> None:
        """Remove a server from the list of managed servers.

        Note:
          IT IS CRUCIAL THAT THIS METHOD IS NOT CALLED
          WHEN THE SERVER MANAGER HAS ALREADY BEEN INITIALIZED
          (with server_manager as manager: ...)
          OTHERWISE EXECUTION WILL BREAK DOWN.
        """
        if self.servers and server in self.servers:
            self.servers.remove(server)

    # -- For future use: Allow adding and removal of servers during runtime ---
    async def add_server_during_runtime(
        self, server: FlockMCPServerBase
    ) -> None:
        """Add a server to the manager and, if already running, start it immediately."""
        if self.lock is None:
            self.lock = asyncio.Lock()

        async with self.lock:
            if self.servers is None:
                self.servers = []

            self.servers.append(server)

        # If we are already running in async-with, enter the context now
        if self.stack is not None:
            await self.stack.enter_async_context(server)

    async def remove_server_during_runtime(
        self, server: FlockMCPServerBase
    ) -> None:
        """Tear down and remove a server from the manager at runtime."""
        if self.lock is None:
            self.lock = asyncio.Lock()

        retrieved_server: FlockMCPServerBase | None = None

        async with self.lock:
            if not self.servers or server not in self.servers:
                return  # Skip as to not impede application flow
            else:
                try:
                    self.servers.remove(server)
                    retrieved_server = server
                except ValueError:
                    # The server is not present (a little paranoid at this point, but still...)
                    return

        # tell the server to shut down.
        if retrieved_server:
            # trigger the server's own exit hook (this closes its connection_manager, sessions, tools....)
            await retrieved_server.__aexit__(None, None, None)

    async def __aenter__(self) -> "FlockServerManager":
        """Enter the asynchronous context for the server manager."""
        if not self.stack:
            self.stack = AsyncExitStack()

        if not self.servers:
            self.servers = []

        if not self.lock:
            self.lock = asyncio.Lock()

        for srv in self.servers:
            await self.stack.enter_async_context(srv)

        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Exit the asynchronous context for the server manager."""
        # Unwind the servers in LIFO order
        if self.stack is not None:
            await self.stack.aclose()
            self.stack = None
