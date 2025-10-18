"""DashboardHTTPService - extends BlackboardHTTPService with WebSocket support.

Provides real-time dashboard capabilities by:
1. Mounting WebSocket endpoint at /ws
2. Serving static files for dashboard frontend
3. Integrating DashboardEventCollector with WebSocketManager
4. Supporting CORS for development mode (DASHBOARD_DEV=1)
"""

import os
from typing import Any

from fastapi.middleware.cors import CORSMiddleware

from flock.api.service import BlackboardHTTPService
from flock.core import Flock
from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.graph_builder import GraphAssembler
from flock.dashboard.routes import (
    register_control_routes,
    register_theme_routes,
    register_trace_routes,
    register_websocket_routes,
)
from flock.dashboard.websocket import WebSocketManager
from flock.logging.logging import get_logger


logger = get_logger("dashboard.service")


class DashboardHTTPService(BlackboardHTTPService):
    """HTTP service with WebSocket support for real-time dashboard.

    Extends BlackboardHTTPService to add:
    - WebSocket endpoint at /ws for real-time event streaming
    - Static file serving for dashboard frontend
    - Integration with DashboardEventCollector
    - Optional CORS middleware for development
    """

    def __init__(
        self,
        orchestrator: Flock,
        websocket_manager: WebSocketManager | None = None,
        event_collector: DashboardEventCollector | None = None,
        *,
        use_v2: bool = False,
    ) -> None:
        """Initialize DashboardHTTPService.

        Args:
            orchestrator: Flock orchestrator instance
            websocket_manager: Optional WebSocketManager (creates new if not provided)
            event_collector: Optional DashboardEventCollector (creates new if not provided)
            use_v2: Whether to use v2 dashboard frontend
        """
        # Initialize base service
        super().__init__(orchestrator)

        # Initialize WebSocket manager and event collector
        self.websocket_manager = websocket_manager or WebSocketManager()
        self.event_collector = event_collector or DashboardEventCollector(
            store=self.orchestrator.store
        )
        self.use_v2 = use_v2

        # Integrate collector with WebSocket manager
        self.event_collector.set_websocket_manager(self.websocket_manager)

        # Graph assembler powers both dashboards by default
        self.graph_assembler: GraphAssembler | None = GraphAssembler(
            self.orchestrator.store, self.event_collector, self.orchestrator
        )

        # Configure CORS if DASHBOARD_DEV environment variable is set
        if os.environ.get("DASHBOARD_DEV") == "1":
            logger.info("DASHBOARD_DEV mode enabled - adding CORS middleware")
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Allow all origins in dev mode
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # IMPORTANT: Register API routes BEFORE static files!
        # Static file mount acts as catch-all and must be last
        self._register_all_routes()

        logger.info("DashboardHTTPService initialized")

    def _register_all_routes(self) -> None:
        """Register all dashboard routes using route modules.

        Routes are organized into focused modules:
        - control: Control API endpoints (publish, invoke, agents, etc.)
        - traces: Trace-related endpoints (OpenTelemetry, history, etc.)
        - themes: Theme management endpoints
        - websocket: WebSocket and real-time dashboard endpoints

        Route registration order matters - static files must be last!
        """
        # Register control routes (artifact types, agents, version, publish, invoke)
        register_control_routes(
            app=self.app,
            orchestrator=self.orchestrator,
            websocket_manager=self.websocket_manager,
            event_collector=self.event_collector,
        )

        # Register trace routes (traces, services, stats, query, streaming, history)
        register_trace_routes(
            app=self.app,
            orchestrator=self.orchestrator,
            websocket_manager=self.websocket_manager,
            event_collector=self.event_collector,
        )

        # Register theme routes (list, get)
        register_theme_routes(app=self.app)

        # Register WebSocket endpoint and static files (must be last!)
        register_websocket_routes(
            app=self.app,
            orchestrator=self.orchestrator,
            websocket_manager=self.websocket_manager,
            event_collector=self.event_collector,
            graph_assembler=self.graph_assembler,
            use_v2=self.use_v2,
        )

    async def start(self) -> None:
        """Start the dashboard service.

        Note: For testing purposes. In production, use uvicorn.run(app).
        """
        logger.info("DashboardHTTPService started")
        # Start heartbeat if there are clients
        if len(self.websocket_manager.clients) > 0:
            await self.websocket_manager.start_heartbeat()

    async def stop(self) -> None:
        """Stop the dashboard service and clean up resources.

        Closes all WebSocket connections gracefully.
        """
        logger.info("Stopping DashboardHTTPService")
        await self.websocket_manager.shutdown()
        logger.info("DashboardHTTPService stopped")

    def get_app(self) -> Any:
        """Get FastAPI application instance.

        Returns:
            FastAPI app for testing or custom server setup
        """
        return self.app


__all__ = ["DashboardHTTPService"]
