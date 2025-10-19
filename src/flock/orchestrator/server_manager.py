"""HTTP server management for orchestrator.

Handles service startup with optional dashboard integration.
Extracted from orchestrator.py to reduce complexity.
"""

from __future__ import annotations

import asyncio
from asyncio import Task
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
        blocking: bool = True,
    ) -> Task[None] | None:
        """Start HTTP service for the orchestrator.

        Args:
            orchestrator: The Flock orchestrator instance to serve
            dashboard: Enable real-time dashboard with WebSocket support (default: False)
            dashboard_v2: Launch the new dashboard v2 frontend (implies dashboard=True)
            host: Host to bind to (default: "127.0.0.1")
            port: Port to bind to (default: 8344)
            blocking: If True, blocks until server stops. If False, starts server
                in background and returns task handle (default: True)

        Returns:
            None if blocking=True, or Task handle if blocking=False

        Examples:
            # Basic HTTP API (no dashboard) - runs until interrupted
            await ServerManager.serve(orchestrator)

            # With dashboard (WebSocket + browser launch) - runs until interrupted
            await ServerManager.serve(orchestrator, dashboard=True)

            # Non-blocking mode - start server in background
            task = await ServerManager.serve(orchestrator, dashboard=True, blocking=False)
            # Now you can publish messages and run other logic
            await orchestrator.publish(my_message)
            await orchestrator.run_until_idle()
        """
        # If non-blocking, start server in background task
        if not blocking:
            server_task = asyncio.create_task(
                ServerManager._serve_impl(
                    orchestrator,
                    dashboard=dashboard,
                    dashboard_v2=dashboard_v2,
                    host=host,
                    port=port,
                )
            )
            # Add cleanup callback
            server_task.add_done_callback(
                lambda task: ServerManager._cleanup_server_callback(orchestrator, task)
            )
            # Store task reference for later cancellation
            orchestrator._server_task = server_task
            # Give server a moment to start
            await asyncio.sleep(0.1)
            return server_task

        # Blocking mode - run server directly with cleanup
        try:
            await ServerManager._serve_impl(
                orchestrator,
                dashboard=dashboard,
                dashboard_v2=dashboard_v2,
                host=host,
                port=port,
            )
        finally:
            # In blocking mode, manually cleanup dashboard launcher
            if (
                hasattr(orchestrator, "_dashboard_launcher")
                and orchestrator._dashboard_launcher is not None
            ):
                orchestrator._dashboard_launcher.stop()
                orchestrator._dashboard_launcher = None
        return None

    @staticmethod
    def _cleanup_server_callback(orchestrator: Flock, task: Task[None]) -> None:
        """Cleanup callback when background server task completes."""
        # Stop dashboard launcher if it was started
        if (
            hasattr(orchestrator, "_dashboard_launcher")
            and orchestrator._dashboard_launcher is not None
        ):
            try:
                orchestrator._dashboard_launcher.stop()
            except Exception as e:
                orchestrator._logger.warning(f"Failed to stop dashboard launcher: {e}")
            finally:
                orchestrator._dashboard_launcher = None

        # Clear server task reference
        if hasattr(orchestrator, "_server_task"):
            orchestrator._server_task = None

        # Log any exceptions from the task
        try:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                orchestrator._logger.error(f"Server task failed: {exc}", exc_info=exc)
        except asyncio.CancelledError:
            pass  # Normal cancellation

    @staticmethod
    async def _serve_impl(
        orchestrator: Flock,
        *,
        dashboard: bool = False,
        dashboard_v2: bool = False,
        host: str = "127.0.0.1",
        port: int = 8344,
    ) -> None:
        """Internal implementation of serve() - actual server logic."""
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
        from flock.api.service import BlackboardHTTPService

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
        # Note: Cleanup is NOT done here - it's handled by:
        # - ServerManager.serve() finally block (blocking mode)
        # - ServerManager._cleanup_server_callback() (non-blocking mode)
        await service.run_async(host=host, port=port)
