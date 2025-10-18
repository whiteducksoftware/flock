"""WebSocket and real-time dashboard routes."""

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.graph_builder import GraphAssembler
from flock.dashboard.models.graph import GraphRequest, GraphSnapshot
from flock.dashboard.websocket import WebSocketManager
from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from flock.core import Flock

logger = get_logger("dashboard.routes.websocket")


def register_websocket_routes(
    app: FastAPI,
    orchestrator: "Flock",
    websocket_manager: WebSocketManager,
    event_collector: DashboardEventCollector,
    graph_assembler: GraphAssembler | None,
    use_v2: bool = False,
) -> None:
    """Register WebSocket endpoint and static file serving.

    Args:
        app: FastAPI application instance
        orchestrator: Flock orchestrator instance
        websocket_manager: WebSocket manager for real-time updates
        event_collector: Dashboard event collector
        graph_assembler: Graph assembler for dashboard snapshots
        use_v2: Whether to use v2 dashboard frontend
    """

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time dashboard events.

        Handles connection lifecycle:
        1. Accept connection
        2. Add to WebSocketManager pool
        3. Keep connection alive
        4. Handle disconnection gracefully
        """
        await websocket.accept()
        await websocket_manager.add_client(websocket)

        try:
            # Keep connection alive and handle incoming messages
            # Dashboard clients may send heartbeat responses or control messages
            while True:
                # Wait for messages from client (pong responses, etc.)
                try:
                    data = await websocket.receive_text()
                    # Handle client messages if needed (e.g., pong responses)
                    # For Phase 3, we primarily broadcast from server to client
                    logger.debug(f"Received message from client: {data[:100]}")
                except WebSocketDisconnect:
                    logger.info("WebSocket client disconnected")
                    break
                except Exception as e:
                    logger.warning(f"Error receiving WebSocket message: {e}")
                    break

        except Exception as e:
            logger.exception(f"WebSocket endpoint error: {e}")
        finally:
            # Clean up: remove client from pool
            await websocket_manager.remove_client(websocket)

    if graph_assembler is not None:

        @app.post("/api/dashboard/graph", response_model=GraphSnapshot)
        async def get_dashboard_graph(request: GraphRequest) -> GraphSnapshot:
            """Return server-side assembled dashboard graph snapshot."""
            return await graph_assembler.build_snapshot(request)

    # Static file serving
    dashboard_dir = Path(__file__).parent.parent
    frontend_root = dashboard_dir.parent / ("frontend_v2" if use_v2 else "frontend")
    static_dir = dashboard_dir / ("static_v2" if use_v2 else "static")

    possible_dirs = [
        static_dir,
        frontend_root / "dist",
        frontend_root / "build",
    ]

    for dir_path in possible_dirs:
        if dir_path.exists() and dir_path.is_dir():
            logger.info(f"Mounting static files from: {dir_path}")
            # Mount at root to serve index.html and other frontend assets
            app.mount(
                "/",
                StaticFiles(directory=str(dir_path), html=True),
                name="dashboard-static",
            )
            break
    else:
        logger.warning(
            f"No static directory found for dashboard frontend (expected one of: {possible_dirs})."
        )
