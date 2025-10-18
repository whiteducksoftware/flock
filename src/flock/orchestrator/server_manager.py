"""HTTP server management for orchestrator.

Handles service startup with optional dashboard integration.
Extracted from orchestrator.py to reduce complexity.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.core.orchestrator import Flock


class ServerManager:
    """Manages HTTP service startup for the orchestrator.

    Handles both standard API mode and dashboard mode with WebSocket support.
    """

    @staticmethod
    async def serve(
        orchestrator: Flock,
        *,
        dashboard: bool = False,
        dashboard_v2: bool = False,
        host: str = "127.0.0.1",
        port: int = 8344,
    ) -> None:
        """Start HTTP service for the orchestrator (blocking).

        Args:
            orchestrator: The Flock orchestrator instance to serve
            dashboard: Enable real-time dashboard with WebSocket support (default: False)
            dashboard_v2: Launch the new dashboard v2 frontend (implies dashboard=True)
            host: Host to bind to (default: "127.0.0.1")
            port: Port to bind to (default: 8344)

        Examples:
            # Basic HTTP API (no dashboard) - runs until interrupted
            await ServerManager.serve(orchestrator)

            # With dashboard (WebSocket + browser launch) - runs until interrupted
            await ServerManager.serve(orchestrator, dashboard=True)
        """
        if dashboard_v2:
            dashboard = True

        if not dashboard:
            # Standard service without dashboard
            await ServerManager._serve_standard(orchestrator, host=host, port=port)
            return

        # Dashboard mode with WebSocket and event collection
        await ServerManager._serve_dashboard(
            orchestrator, dashboard_v2=dashboard_v2, host=host, port=port
        )

    @staticmethod
    async def _serve_standard(orchestrator: Flock, *, host: str, port: int) -> None:
        """Serve standard HTTP API without dashboard.

        Args:
            orchestrator: The Flock orchestrator instance
            host: Host to bind to
            port: Port to bind to
        """
        from flock.service import BlackboardHTTPService

        service = BlackboardHTTPService(orchestrator)
        await service.run_async(host=host, port=port)

    @staticmethod
    async def _serve_dashboard(
        orchestrator: Flock, *, dashboard_v2: bool, host: str, port: int
    ) -> None:
        """Serve HTTP API with dashboard and WebSocket support.

        Args:
            orchestrator: The Flock orchestrator instance
            dashboard_v2: Whether to use v2 dashboard frontend
            host: Host to bind to
            port: Port to bind to
        """
        from flock.core import Agent
        from flock.dashboard.collector import DashboardEventCollector
        from flock.dashboard.launcher import DashboardLauncher
        from flock.dashboard.service import DashboardHTTPService
        from flock.dashboard.websocket import WebSocketManager

        # Create dashboard components
        websocket_manager = WebSocketManager()
        event_collector = DashboardEventCollector(store=orchestrator.store)
        event_collector.set_websocket_manager(websocket_manager)
        await event_collector.load_persistent_snapshots()

        # Store collector reference for agents added later
        orchestrator._dashboard_collector = event_collector
        # Store websocket manager for real-time event emission (Phase 1.2)
        orchestrator._websocket_manager = websocket_manager
        # Phase 5A: Set websocket manager on EventEmitter for dashboard updates
        orchestrator._event_emitter.set_websocket_manager(websocket_manager)

        # Phase 6+7: Set class-level WebSocket broadcast wrapper (dashboard mode)
        async def _broadcast_wrapper(event):
            """Isolated broadcast wrapper - no reference chain to orchestrator."""
            return await websocket_manager.broadcast(event)

        Agent._websocket_broadcast_global = _broadcast_wrapper

        # Inject event collector into all existing agents
        for agent in orchestrator._agents.values():
            # Add dashboard collector with priority ordering handled by agent
            agent._add_utilities([event_collector])

        # Start dashboard launcher (npm process + browser)
        launcher_kwargs: dict[str, Any] = {"port": port}
        if dashboard_v2:
            dashboard_pkg_dir = Path(__file__).parent.parent / "dashboard"
            launcher_kwargs["frontend_dir"] = dashboard_pkg_dir.parent / "frontend_v2"
            launcher_kwargs["static_dir"] = dashboard_pkg_dir / "static_v2"

        launcher = DashboardLauncher(**launcher_kwargs)
        launcher.start()

        # Create dashboard HTTP service
        service = DashboardHTTPService(
            orchestrator=orchestrator,
            websocket_manager=websocket_manager,
            event_collector=event_collector,
            use_v2=dashboard_v2,
        )

        # Store launcher for cleanup
        orchestrator._dashboard_launcher = launcher

        # Run service (blocking call)
        try:
            await service.run_async(host=host, port=port)
        finally:
            # Cleanup on exit
            launcher.stop()
