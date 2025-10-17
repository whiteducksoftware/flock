"""WebSocket connection manager for real-time dashboard communication.

Manages WebSocket client pool, broadcasts events to all connected clients,
and implements heartbeat/ping mechanism to keep connections alive.
"""

import asyncio
import contextlib
from collections import defaultdict, deque
from typing import Union

from fastapi import WebSocket

from flock.dashboard.events import (
    AgentActivatedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    MessagePublishedEvent,
    StreamingOutputEvent,
)
from flock.logging.logging import get_logger


logger = get_logger("dashboard.websocket")

# Type alias for dashboard events
DashboardEvent = Union[
    AgentActivatedEvent,
    MessagePublishedEvent,
    StreamingOutputEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
]


class WebSocketManager:
    """Manages WebSocket connections and broadcasts dashboard events.

    Features:
    - Connection pool management (add/remove clients)
    - Broadcast events to all connected clients
    - Heartbeat/ping mechanism (DISABLED by default - causes unnecessary disconnects)
    - Graceful handling of disconnected clients during broadcast
    """

    def __init__(self, heartbeat_interval: int = 120, enable_heartbeat: bool = False):
        """Initialize WebSocket manager.

        Args:
            heartbeat_interval: Seconds between heartbeat pings (default: 120)
            enable_heartbeat: Enable heartbeat pings (default: False - disabled to prevent
                            unnecessary disconnects. WebSocket auto-reconnects on real network issues.)
        """
        self.clients: set[WebSocket] = set()
        self.heartbeat_interval = heartbeat_interval
        self.enable_heartbeat = enable_heartbeat
        self._heartbeat_task: asyncio.Task | None = None
        self._shutdown = False

        # Store streaming output events by agent_name for history (max 128344 per agent)
        self._streaming_history: dict[str, deque[StreamingOutputEvent]] = defaultdict(
            lambda: deque(maxlen=128344)
        )

    async def add_client(self, websocket: WebSocket) -> None:
        """Add WebSocket client to connection pool.

        Args:
            websocket: FastAPI WebSocket connection to add
        """
        self.clients.add(websocket)
        logger.info(f"WebSocket client added. Total clients: {len(self.clients)}")

        # Start heartbeat task if enabled and not already running
        if (
            self.enable_heartbeat
            and self._heartbeat_task is None
            and not self._shutdown
        ):
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def remove_client(self, websocket: WebSocket) -> None:
        """Remove WebSocket client from connection pool.

        Args:
            websocket: FastAPI WebSocket connection to remove
        """
        self.clients.discard(websocket)
        logger.info(f"WebSocket client removed. Total clients: {len(self.clients)}")

        # Stop heartbeat task if no clients remain
        if len(self.clients) == 0 and self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None

    async def broadcast(self, event: DashboardEvent) -> None:
        """Broadcast event to all connected clients as JSON.

        Handles disconnected clients gracefully by removing them from pool.
        Uses return_exceptions=True to prevent one client failure from affecting others.

        Args:
            event: Dashboard event to broadcast (AgentActivatedEvent, etc.)
        """
        # Store streaming output events for history (always, even if no clients)
        if isinstance(event, StreamingOutputEvent):
            self._streaming_history[event.agent_name].append(event)
            # logger.debug(
            #     f"Stored streaming event for {event.agent_name}, history size: {len(self._streaming_history[event.agent_name])}"
            # )

        # If no clients, still log but don't broadcast
        if not self.clients:
            logger.debug(
                f"No clients connected, stored event but skipping broadcast of {type(event).__name__}"
            )
            return

        # Log broadcast attempt
        # logger.debug(f"Broadcasting {type(event).__name__} to {len(self.clients)} client(s)")

        # Serialize event to JSON using Pydantic's model_dump_json
        message = event.model_dump_json()
        # logger.debug(f"Event JSON: {message[:200]}...")  # Log first 200 chars

        # Broadcast to all clients concurrently
        # Use return_exceptions=True to handle client failures gracefully
        # Use send_text() for FastAPI WebSocket (send JSON string as text)
        # CRITICAL: Add timeout to prevent deadlock when client send buffer is full
        clients_list = list(self.clients)  # Copy to avoid modification during iteration

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

        # Clean up failed clients
        for client in failed_clients:
            await self.remove_client(client)

    async def _heartbeat_loop(self) -> None:
        """Send ping to all clients every heartbeat_interval seconds.

        Keeps WebSocket connections alive and detects disconnected clients.
        Runs continuously until cancelled or all clients disconnect.
        """
        logger.info(f"Starting heartbeat loop (interval: {self.heartbeat_interval}s)")

        try:
            while not self._shutdown and len(self.clients) > 0:
                await asyncio.sleep(self.heartbeat_interval)

                if not self.clients:
                    break

                # Send ping to all clients
                ping_tasks = []
                for client in list(
                    self.clients
                ):  # Copy to avoid modification during iteration
                    ping_tasks.append(self._ping_client(client))

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
        """Start heartbeat task manually (for testing).

        In production, heartbeat is disabled by default (enable_heartbeat=False).
        Only starts if enable_heartbeat=True.
        """
        if (
            self.enable_heartbeat
            and self._heartbeat_task is None
            and not self._shutdown
        ):
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def shutdown(self) -> None:
        """Shutdown manager and close all WebSocket connections.

        Cancels heartbeat task and closes all client connections gracefully.
        """
        logger.info("Shutting down WebSocketManager")
        self._shutdown = True

        # Cancel heartbeat task
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None

        # Close all client connections
        close_tasks = []
        for client in list(self.clients):
            # Handle both real WebSocket and mock objects
            if hasattr(client, "close") and callable(client.close):
                result = client.close()
                # Only await if it's a coroutine
                if asyncio.iscoroutine(result):
                    close_tasks.append(result)

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        self.clients.clear()
        logger.info("WebSocketManager shutdown complete")

    def get_streaming_history(self, agent_name: str) -> list[StreamingOutputEvent]:
        """Get historical streaming output events for a specific agent.

        Args:
            agent_name: Name of the agent to get history for

        Returns:
            List of StreamingOutputEvent events for the agent
        """
        return list(self._streaming_history.get(agent_name, []))


__all__ = ["DashboardEvent", "WebSocketManager"]
