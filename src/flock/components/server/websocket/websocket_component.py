"""Websocket ServerComponent."""

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import Field

from flock.api.websocket import WebSocketManager
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.logging.logging import get_logger


logger = get_logger(__name__)


class WebSocketComponentConfig(ServerComponentConfig):
    """Config for the WebSocketServerComponent."""

    prefix: str = Field(
        default="/plugin/", description="Optional Prefix for the Websocket Endpoint."
    )
    tags: list[str] = Field(
        default=["WebSocket"], description="OpenAPI Tags for Endpoints."
    )
    hearbeat_interval: int = Field(
        default=120, description="Interval for WebSocket Heartbeat."
    )
    enable_heartbeat: bool = Field(
        default=False, description="Whether or not to enable the Heartbeat."
    )


class WebSocketServerComponent(ServerComponent):
    """Component for serving WebSocket-Endpoints for interacting with Flock's Blackboard.

    This Component serves real-time Dashboard Events.
    Also Handles the connection Lifecycle:
    1. Accept connection
    2. Add to WebSocketManager pool
    3. Keep connection alive
    4. Handle disconnection gracefully
    """

    name: str = Field(default="websocket", description="Name for the Component.")
    priority: int = Field(default=7, description="Registration priority.")
    config: WebSocketComponentConfig = Field(
        default_factory=WebSocketComponentConfig,
        description="Optional Config for the Component.",
    )
    _websocket_manager: WebSocketManager | None = None

    def configure(self, app, orchestrator):
        # Get the singleton instance for the WebsocketManager
        if self._websocket_manager is None:
            self._websocket_manager = WebSocketManager(
                heartbeat_interval=self.config.hearbeat_interval,
                enable_heartbeat=self.config.enable_heartbeat,
            )

    def register_routes(self, app, orchestrator):
        # Should have been handled by configure() but it is good to be cautious
        if self._websocket_manager is None:
            self._websocket_manager = WebSocketManager(
                self.config.hearbeat_interval,
                self.config.enable_heartbeat,
            )

        @app.websocket(self._join_path(self.config.prefix, "ws"))
        async def websocket_endpoint(websocket: WebSocket) -> None:
            """WebSocket endpoint for real-time BlackBoard Events.

            Handles connection lifecycle:
            1. Accept connection
            2. Add to WebSocketManager pool
            3. Keep connection alive
            4. Handle disconnection gracefully
            """
            await websocket.accept()
            await self._websocket_manager.add_client(websocket)

            try:
                # Keep connection alive and handle incoming messages
                # Dashboard/BlackBoard clients may send heartbeat responses or control messages
                while True:
                    # Wait for messages from client (pong responses, etc)
                    try:
                        data = await websocket.receive_text()
                        # Handle client messages if needed (e.g. pong response)
                        # For Phase 3, we primarily broadcast from server to client
                        logger.debug(f"Received message from client: {data[:100]}")
                    except WebSocketDisconnect:
                        logger.info("WebSocket client disconnected")
                        break
                    except Exception as ex:
                        logger.exception(
                            f"WebSocketServerComponent: Error receiving WebSocket message: {ex!s}"
                        )
                        break
            except Exception as ex:
                logger.exception(
                    f"WebSocketServerComponent: WebSocket Endpoint Error: {ex!s}"
                )
            finally:
                # Clean up: remove client from pool
                await self._websocket_manager.remove_client(websocket)

    async def on_startup_async(self, orchestrator):
        # Ensure that websocket manager is set up
        # and that pool is in a clean state
        if self._websocket_manager is None:
            self._websocket_manager = WebSocketManager(
                heartbeat_interval=self.config.hearbeat_interval,
                enable_heartbeat=self.config.enable_heartbeat,
            )
        await self._websocket_manager._clear_pool()

    async def on_shutdown_async(self, orchestrator):
        # Disconnect all clients
        if self._websocket_manager is not None:
            await self._websocket_manager.shutdown()

    def get_dependencies(self):
        # No extra dependencies
        return []
