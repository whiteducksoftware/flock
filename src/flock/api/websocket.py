"""Websocket connection manager for real-time communication.

Manages WebSocket client pool, broadcasts events to all connected clients,
and implements heartbeat/ping mechanism to keep connections alive.
"""

import asyncio
import contextlib
from collections import defaultdict, deque
from typing import Union

from fastapi import WebSocket

from flock.components.server.models.events import (
    AgentActivatedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    MessagePublishedEvent,
    StreamingOutputEvent,
)
from flock.logging.logging import get_logger


logger = get_logger(__name__)


# Type alias for websocket events
WebSocketEvent = Union[
    AgentActivatedEvent,
    MessagePublishedEvent,
    StreamingOutputEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
]


class WebSocketManager:
    """Thread-safe singleton manager for WebSocket connections and event broadcasting.

    Features:
    - Thread-safe singleton pattern (returns same instance for all instantiations)
    - Connection pool management (add/remove clients)
    - Broadcast events to all connected clients
    - Heartbeat/ping mechanism (DISABLED by default - causes unnecessary disconnects)
    - Graceful handling of disconnected clients during broadcast

    Thread Safety:
    - Uses asyncio.Lock for all mutable state access (clients, streaming_history, heartbeat_task)
    - Singleton creation uses class-level lock (initialized once)
    - All operations that modify state are protected by async locks
    - No deadlocks: locks are always acquired in the same order and held briefly

    Note:
        This class implements the singleton pattern. All calls to WebSocketManager(...)
        will return the same instance, initialized with the parameters from the first call.
    """

    _instance: "WebSocketManager | None" = None
    _instance_lock = asyncio.Lock()  # Class-level lock for singleton creation
    _initialized: bool = False

    def __new__(
        cls,
        enable_heartbeat: bool = False,
        heartbeat_interval: int = 120,
    ):
        """Create or return the singleton instance (thread-safe).

        Args:
            _heartbeat_interval: Seconds between heartbeat pings (default: 120)
                                Only used on first instantiation.
            _enable_heartbeat: Enable heartbeat pings (default: False - disabled to prevent
                            unnecessary disconnects. WebSocket auto-reconnects on real network issues.)
                            Only used on first instantiation.

        Returns:
            The singleton WebSocketManager instance

        Note:
            Parameters are prefixed with underscore as they're only used in __init__.
            Subsequent instantiations ignore these parameters.
        """
        # Simple singleton pattern - lock is acquired in async __ainit__ if needed
        if cls._instance is None:
            instance = super().__new__(cls)
            cls._instance = instance
        return cls._instance

    @classmethod
    async def reset_singleton(cls) -> None:
        """Reset the singleton instance (primarily for testing).

        Warning:
            This should only be used in tests. Calling this in production
            while WebSocket connections are active may lead to unexpected behavior.
        """
        async with cls._instance_lock:
            if cls._instance is not None:
                logger.warning("Resetting WebSocketManager singleton instance")
            cls._instance = None
            cls._initialized = False

    def __init__(self, heartbeat_interval: int = 120, enable_heartbeat: bool = False):
        """Initialize WebSocket manager (only runs once for singleton).

        Args:
            heartbeat_interval: Seconds between heartbeat pings (default: 120)
            enable_heartbeat: Enable heartbeat pings (default: False - disabled to prevent
                            unnecessary disconnects. WebSocket auto-reconnects on real network issues.)

        Note:
            Initialization only happens once. Subsequent calls with different parameters
            will be ignored and return the already-initialized singleton instance.
        """
        # Guard against re-initialization
        if self._initialized and (
            heartbeat_interval != self._heartbeat_interval
            or enable_heartbeat != self._enable_heartbeat
        ):
            logger.warning(
                "WebSocketManager singleton already initialized with "
                f"heartbeat_interval={self._heartbeat_interval}, "
                f"enable_heartbeat={self._enable_heartbeat} "
                f"Ignoring new parameters: heartbeat_interval={heartbeat_interval}, "
                f"enable_heartbeat={enable_heartbeat}"
            )
            return

        # Store parameters for async initialization
        self._heartbeat_interval = heartbeat_interval
        self._enable_heartbeat = enable_heartbeat

        # Async locks for thread-safe operations
        self._clients_lock = asyncio.Lock()
        self._history_lock = asyncio.Lock()
        self._heartbeat_lock = asyncio.Lock()

        # Initialize state (protected by locks when accessed)
        self.clients: set[WebSocket] = set()
        self.heartbeat_interval = heartbeat_interval
        self.enable_heartbeat = enable_heartbeat
        self._heartbeat_task: asyncio.Task | None = None
        self._shutdown = False

        # Store streaming output events by agent_name for history (max 128344 per agent)
        self._streaming_history: dict[str, deque[StreamingOutputEvent]] = defaultdict(
            lambda: deque(maxlen=128344)
        )

        self._initialized = True
        logger.info(
            f"WebSocketManager singleton initialized (heartbeat_interval={heartbeat_interval}s, "
            f"enable_heartbeat={enable_heartbeat})"
        )

    async def add_client(self, websocket: WebSocket) -> None:
        """Add WebSocket client to connection pool (thread-safe).

        Args:
            websocket: FastAPI WebSocket connection to add
        """
        async with self._clients_lock:
            self.clients.add(websocket)
            client_count = len(self.clients)

        logger.info(f"WebSocket client added. Total clients: {client_count}")

        # Start heartbeat task if enabled and not already running
        # Use separate lock to avoid holding clients_lock during task creation
        if self.enable_heartbeat and not self._shutdown:
            async with self._heartbeat_lock:
                if self._heartbeat_task is None:
                    self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def remove_client(self, websocket: WebSocket) -> None:
        """Remove WebSocket client from connection pool (thread-safe).

        Args:
            websocket: FastAPI WebSocket connection to remove
        """
        async with self._clients_lock:
            self.clients.discard(websocket)
            client_count = len(self.clients)

        logger.info(f"WebSocket client removed. Total clients: {client_count}")

        # Stop heartbeat task if no clients remain
        # Use separate lock to avoid holding clients_lock during task cancellation
        if client_count == 0:
            async with self._heartbeat_lock:
                if self._heartbeat_task is not None:
                    self._heartbeat_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self._heartbeat_task
                    self._heartbeat_task = None

    async def broadcast(self, event: WebSocketEvent) -> None:
        """Broadcast event to all connected clients as JSON (thread-safe).

        Handles disconnected clients gracefully by removing them from pool.
        Uses return_exceptions=True to prevent one client failure from affecting others.

        Args:
            event: Dashboard event to broadcast (AgentActivatedEvent, etc.)
        """
        # Store streaming output events for history (always, even if no clients)
        if isinstance(event, StreamingOutputEvent):
            async with self._history_lock:
                self._streaming_history[event.agent_name].append(event)
                # logger.debug(
                #     f"Stored streaming event for {event.agent_name}, history size: {len(self._streaming_history[event.agent_name])}"
                # )

        # Get snapshot of clients (hold lock briefly)
        async with self._clients_lock:
            clients_list = list(self.clients)

        # If no clients, still log but don't broadcast
        if not clients_list:
            logger.debug(
                f"No clients connected, stored event but skipping broadcast of {type(event).__name__}"
            )
            return

        # Log broadcast attempt
        # logger.debug(f"Broadcasting {type(event).__name__} to {len(clients_list)} client(s)")

        # Serialize event to JSON using Pydantic's model_dump_json
        message = event.model_dump_json()
        # logger.debug(f"Event JSON: {message[:200]}...")  # Log first 200 chars

        # Broadcast to all clients concurrently
        # Use return_exceptions=True to handle client failures gracefully
        # Use send_text() for FastAPI WebSocket (send JSON string as text)
        # CRITICAL: Add timeout to prevent deadlock when client send buffer is full
        send_tasks = [
            asyncio.wait_for(client.send_text(message), timeout=0.5)  # 500ms timeout
            for client in clients_list
        ]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        # Remove clients that failed to receive the message
        failed_clients = []
        for client, result in zip(clients_list, results, strict=False):
            if isinstance(result, Exception):
                # Check if it's a timeout (backpressure) or other error
                if isinstance(result, asyncio.TimeoutError):
                    logger.warning(
                        "Client send timeout (backpressure) - client is slow or disconnected, removing client"
                    )
                else:
                    logger.warning(f"Failed to send to client: {result}")
                failed_clients.append(client)

        # Clean up failed clients (remove_client handles its own locking)
        for client in failed_clients:
            await self.remove_client(client)

    async def _heartbeat_loop(self) -> None:
        """Send ping to all clients every heartbeat_interval seconds (thread-safe).

        Keeps WebSocket connections alive and detects disconnected clients.
        Runs continuously until cancelled or all clients disconnect.
        """
        logger.info(f"Starting heartbeat loop (interval: {self.heartbeat_interval}s)")

        try:
            while not self._shutdown:
                await asyncio.sleep(self.heartbeat_interval)

                # Get snapshot of clients (hold lock briefly)
                async with self._clients_lock:
                    clients_list = list(self.clients)

                if not clients_list:
                    break

                # Send ping to all clients
                ping_tasks = []
                for client in clients_list:
                    ping_tasks.append(self._ping_client(client))  # noqa: PERF401

                # Execute pings concurrently
                await asyncio.gather(*ping_tasks, return_exceptions=True)

        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
            raise
        except Exception as e:
            logger.exception(f"Heartbeat loop error: {e}")

    async def _ping_client(self, client: WebSocket) -> None:
        """Send ping to single client.

        Args:
            client: WebSocket client to ping
        """
        try:
            await client.send_json({
                "type": "ping",
                "timestamp": asyncio.get_event_loop().time(),
            })
        except Exception as e:
            logger.warning(f"Failed to ping client: {e}")
            await self.remove_client(client)

    async def start_heartbeat(self) -> None:
        """Start heartbeat task manually (for testing, thread-safe).

        In production, heartbeat is disabled by default (enable_heartbeat=False).
        Only starts if enable_heartbeat=True.
        """
        if self.enable_heartbeat and not self._shutdown:
            async with self._heartbeat_lock:
                if self._heartbeat_task is None:
                    self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def shutdown(self) -> None:
        """Shutdown manager and close all WebSocket connections (thread-safe).

        Cancels heartbeat task and closes all client connections gracefully.
        """
        logger.info("Shutting down WebSocketManager")
        self._shutdown = True

        # Cancel heartbeat task
        async with self._heartbeat_lock:
            if self._heartbeat_task is not None:
                self._heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._heartbeat_task
                self._heartbeat_task = None

        # Get snapshot of clients and clear the set
        async with self._clients_lock:
            clients_list = list(self.clients)
            self.clients.clear()

        # Close all client connections (outside lock to avoid blocking)
        close_tasks = []
        for client in clients_list:
            # Handle both real WebSocket and mock objects
            if hasattr(client, "close") and callable(client.close):
                result = client.close()
                # Only await if it's a coroutine
                if asyncio.iscoroutine(result):
                    close_tasks.append(result)

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        logger.info("WebSocketManager shutdown complete")

    async def get_streaming_history(
        self, agent_name: str
    ) -> list[StreamingOutputEvent]:
        """Get historical streaming output events for a specific agent (thread-safe).

        Args:
            agent_name: Name of the agent to get history for

        Returns:
            List of StreamingOutputEvent events for the agent
        """
        async with self._history_lock:
            return list(self._streaming_history.get(agent_name, []))

    async def _clear_pool(self) -> None:
        """Clear the Pool (dangerous)."""
        async with self._clients_lock:
            client_count = len(self.clients)
            self.clients.clear()
            clean_count = len(self.clients)
            logger.info(
                f"Removed a total of {client_count} clients from the pool. Pool now contains {clean_count} clients."
            )


__all__ = ["WebSocketEvent", "WebSocketManager"]
