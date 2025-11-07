"""HTTP server management for orchestrator.

Handles service startup with optional dashboard integration.
Extracted from orchestrator.py to reduce complexity.
"""

from __future__ import annotations

import asyncio
import os
from asyncio import Task
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.components import ServerComponent
    from flock.core.orchestrator import Flock


class ServerManager:
    """Manages HTTP service startup for the orchestrator.

    Handles standard API mode, dashboard mode as well as custom modes
    with plugins.
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
        plugins: list[ServerComponent] | None = None,
        use_default_plugins: bool = True,
    ) -> Task[None] | None:
        """Start Server for the orchestrator.

        Args:
            orchestrator: The Flock orchestrator instance to serve
            dashboard: Enable real-time dashboard with WebSocket support (default: False)
            dashboard_v2: (DEPRECATED: Dashboardv2 will be served by default. This parameter will be removed in future releases.)
            host: Host to bind to (default: "127.0.0.1")
            port: Port to bind to (default: 8344)
            blocking: If True, blocks until server stops. If False, starts server in background and
                returns task handle (default: True)
            plugins: Additional Plugins that can modify the baseline behavior of the server.
            use_default_plugins: IF SET TO TRUE, DASHBOARD MODE WILL BE IGNORED AND NO DEFAULT PLUGINS WILL BE USED!

        Returns:
            None if blocking=True, or Task handle if blocking=False

        Examples:
            >>> # Basic HTTP API (no dashboard) - runs until interrupted
            >>> await ServerManager.serve(orchestrator)

            >>> # With dashboard (WebSocket + browser launch) - runs until interrupted
            >>> await ServerManager.serve(dashboard=True)

            >>> # With custom behavior (This will only expose the Websocket Endpoints and NOTHING else)
            >>> await ServerManager.serve(
            >>>     plugins=[
            >>>         WebSocketServerComponent
            >>>     ],
            >>>     use_default_plugins=False, # NO DEFAULT API
            >>> )
        """
        # First, check if Dev requested no default plugins
        if not use_default_plugins:
            # no dashboard mode regardless
            dashboard = False
            dashboard_v2 = False

        # If non-blocking, start server in background task
        if not blocking:
            server_task = asyncio.create_task(
                ServerManager._serve_impl(
                    orchestrator=orchestrator,
                    dashboard=dashboard,
                    dashboard_v2=dashboard_v2,
                    host=host,
                    port=port,
                    plugins=plugins,
                    use_default_plugins=use_default_plugins,
                )
            )
            # Add cleanup callback
            server_task.add_done_callback(
                lambda task: ServerManager._cleanup_server_callback(
                    orchestrator=orchestrator, task=task
                )
            )
            # Store task reference for later cancellation
            orchestrator._server_task = server_task
            # Give the server a moment to start
            await asyncio.sleep(0.1)
            return server_task

        # Blocking mode - run server directly with cleanup
        try:
            await ServerManager._serve_impl(
                orchestrator=orchestrator,
                dashboard=dashboard,
                dashboard_v2=dashboard_v2,
                host=host,
                port=port,
                plugins=plugins,
                use_default_plugins=use_default_plugins,
            )
        finally:
            # In blocking mode, manually clean up
            if (
                hasattr(orchestrator, "_dashboard_launcher")
                and orchestrator._dashboard_launcher is not None
            ):
                orchestrator._dashboard_launcher.stop()
                orchestrator._dashboard_launcher = None
        return None

    @staticmethod
    def _cleanup_server_callback(orchestrator: Flock, task: Task[None]) -> None:
        """Cleanup callback when backround server task completes."""
        # Stop dashboard launcher if it was started
        if (
            hasattr(orchestrator, "_dashboard_launcher")
            and orchestrator._dashboard_launcher is not None
        ):
            try:
                orchestrator._dashboard_launcher.stop()
            except Exception as ex:
                orchestrator._logger.warning(
                    f"Failed to stop dashboard launcher: {ex!s}"
                )
            finally:
                orchestrator._dashboard_launcher = None
        # Clear server task reference
        if hasattr(orchestrator, "_server_task"):
            orchestrator._server_task = None
        # Log any exceptions from the task
        try:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                orchestrator._logger.error(f"Server task failed: {exc!s}", exc_info=exc)
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
        plugins: list[ServerComponent] | None = None,
        use_default_plugins: bool = True,
    ) -> None:
        """Internal implementation of serve() - actual server logic."""

        # Double-check just in case
        if not use_default_plugins:
            dashboard = False
            dashboard_v2 = False
        if dashboard_v2:
            dashboard = True

        if not use_default_plugins:
            if plugins is None or len(plugins) == 0:
                # This does not make sense, so tell dev that
                raise ValueError(
                    "use_default_plugins was set to 'False', but plugins was 'None' or empty list."
                )
            await ServerManager._serve_custom(
                orchestrator=orchestrator,
                host=host,
                port=port,
                plugins=plugins,
            )
            return

        if not dashboard:
            await ServerManager._serve_standard(
                orchestrator=orchestrator,
                host=host,
                port=port,
                plugins=plugins,
            )
            return
        # Dashboard mode with WebSocket and event collection
        await ServerManager._serve_dashboard(
            orchestrator=orchestrator,
            dashboard_v2=dashboard_v2,
            host=host,
            port=port,
            plugins=plugins,
        )
        return

    @staticmethod
    async def _serve_custom(
        orchestrator: Flock, *, host: str, port: int, plugins: list[ServerComponent]
    ) -> None:
        """Serve custom API without standard plugins.

        Args:
            orchestrator: The Flock orchestrator instance
            host: Host to bind to
            port: Port to bind to
            plugins: List of plugins for custom behavior. Not optional here
        """
        from flock.api.base_service import BaseHTTPService

        service = BaseHTTPService(
            orchestrator=orchestrator,
        ).add_components(
            components=plugins,
        )
        await service.run_async(
            host=host,
            port=port,
        )

    @staticmethod
    async def _serve_standard(
        orchestrator: Flock,
        *,
        host: str,
        port: int,
        plugins: list[ServerComponent] | None,
    ) -> None:
        """Serve standard HTTP API without dashboard.

        Args:
            orchestrator: The Flock orchestrator instance
            host: Host to bind to
            port: Port to bind to
            plugins: Optional list of plugins for additional behavior
        """
        # CRITICAL: Initialize orchestrator components before starting server
        # This ensures TimerComponent and other orchestrator components are ready
        if not hasattr(orchestrator, "_orchestrator") or not orchestrator._orchestrator:
            await orchestrator._run_initialize()

        from flock.api.base_service import BaseHTTPService
        from flock.components.server import (
            AgentsServerComponent,
            AgentsServerComponentConfig,
            ArtifactComponentConfig,
            ArtifactsComponent,
            ControlRoutesComponent,
            ControlRoutesComponentConfig,
            HealthAndMetricsComponent,
        )

        # Set up standard HTTP Components for standard API
        health_and_metrics = HealthAndMetricsComponent(
            name="health_internal",
        )

        agent_endpoints = AgentsServerComponent(
            name="agents_internal",
            config=AgentsServerComponentConfig(
                enabled=True, prefix="/api/v1/", tags=["Agents", "Public API"]
            ),
        )

        control_endpoints = ControlRoutesComponent(
            name="api_internal",
            config=ControlRoutesComponentConfig(
                enabled=True, prefix="/api/", tags=["Control", "Public API"]
            ),
        )

        artifacts_endpoints = ArtifactsComponent(
            name="artifacts_internal",
            config=ArtifactComponentConfig(
                enabled=True, prefix="/api/v1/", tags=["Artifacts", "Public API"]
            ),
        )

        service = BaseHTTPService(
            orchestrator=orchestrator,
            version="0.5.0",
        ).add_components(
            components=[
                health_and_metrics,
                agent_endpoints,
                control_endpoints,
                artifacts_endpoints,
            ]
        )
        if plugins:
            for plugin in plugins:
                service = service.add_component(plugin)
        await service.run_async(
            host=host,
            port=port,
        )

    @staticmethod
    async def _serve_dashboard(
        orchestrator: Flock,
        *,
        dashboard_v2: bool,
        host: str,
        port: int,
        plugins: list[ServerComponent] | None,
    ) -> None:
        """Serve HTTP API with dashboard and WebSocket support.

        Args:
            orchestrator: The Flock orchestrator instance
            dashboard_v2: Whether to use v2 dashboard frontend
            host: host to bind to
            port: port to bind to
            plugins: Optional list for plugins to modify base behavior
        """
        # CRITICAL: Initialize orchestrator components before starting server
        # This ensures TimerComponent and other orchestrator components are ready
        if not hasattr(orchestrator, "_orchestrator") or not orchestrator._orchestrator:
            await orchestrator._run_initialize()

        from flock.api.base_service import BaseHTTPService

        # Create required components
        from flock.api.collector import DashboardEventCollector
        from flock.api.graph_builder import GraphAssembler
        from flock.api.launcher import DashboardLauncher
        from flock.api.websocket import WebSocketManager
        from flock.components.server import (
            AgentsServerComponent,
            AgentsServerComponentConfig,
            ArtifactComponentConfig,
            ArtifactsComponent,
            ControlRoutesComponent,
            ControlRoutesComponentConfig,
            CORSComponent,
            CORSComponentConfig,
            HealthAndMetricsComponent,
            StaticFilesComponentConfig,
            StaticFilesServerComponent,
            ThemesComponent,
            ThemesComponentConfig,
            TracingComponent,
            TracingComponentConfig,
            WebSocketComponentConfig,
            WebSocketServerComponent,
        )
        from flock.core import Agent

        dashboard_dev_env = os.environ.get("DASHBOARD_DEV", "0") == "1"
        heartbeat_interval_str = os.environ.get("WS_HEARTBEAT", "120")
        heartbeat_interval = str(heartbeat_interval_str)

        # Get WebSocket singleton instance
        websocket_manager = WebSocketManager(
            enable_heartbeat=dashboard_dev_env, heartbeat_interval=heartbeat_interval
        )
        event_collector = DashboardEventCollector(store=orchestrator.store)
        event_collector.set_websocket_manager(manager=websocket_manager)
        # store collector reference for agents added later
        orchestrator._dashboard_collector = event_collector
        # Store websocket manager for real-time event emission
        orchestrator._websocket_manager = websocket_manager
        # Set websocket manager on EventEmitter for dashboard updates
        orchestrator._event_emitter.set_websocket_manager(websocket_manager)

        # Set up standard HTTP Components for standard API
        health_and_metrics = HealthAndMetricsComponent(
            name="health_internal",
        )

        agent_endpoints = AgentsServerComponent(
            name="agents_internal",
            config=AgentsServerComponentConfig(
                enabled=True, prefix="/api/v1/", tags=["Agents", "Public API"]
            ),
        )

        control_endpoints = ControlRoutesComponent(
            name="api_internal",
            config=ControlRoutesComponentConfig(
                enabled=True, prefix="/api/", tags=["Control", "Public API"]
            ),
            graph_assembler=GraphAssembler(
                store=orchestrator.store,
                collector=event_collector,
                orchestrator=orchestrator,
            ),
        )

        artifacts_endpoints = ArtifactsComponent(
            name="artifacts_internal",
            config=ArtifactComponentConfig(
                enabled=True, prefix="/api/v1/", tags=["Artifacts", "Public API"]
            ),
        )

        # Basic API configuration
        service = BaseHTTPService(
            orchestrator=orchestrator,
            version="0.5.0",
        ).add_components(
            components=[
                health_and_metrics,
                agent_endpoints,
                control_endpoints,
                artifacts_endpoints,
            ]
        )

        websocket_endpoints = WebSocketServerComponent(
            name="websocket_internal",
            config=WebSocketComponentConfig(
                enabled=True,
                enable_heartbeat=dashboard_dev_env,
                hearbeat_interval=heartbeat_interval,
                prefix="/",
                tags=["WebSocket", "Public API"],
            ),
        )

        # Only add the default CorsMiddleware of no other cors middleware
        # has been configured with default values
        if (
            plugins is None or "cors" not in [plugin.name for plugin in plugins]
        ) or dashboard_dev_env:
            service = service.add_component(
                component=CORSComponent(
                    name="cors_internal",
                    config=CORSComponentConfig(
                        enabled=True,
                        prefix="",
                        tags=["CORS"],
                        allow_origins=["*"],
                        allow_credentials=True,
                        allow_methods=["*"],
                        allow_headers=["*"],
                    ),
                )
            )

        themes_endpoints = ThemesComponent(
            name="themes_internal",
            themes_dir=Path(__file__).parent.parent / "themes",
            config=ThemesComponentConfig(
                enabled=True, prefix="", tags=["Themes", "Public API"]
            ),
        )

        static_files_endpoint = StaticFilesServerComponent(
            name="static_files_internal",
            config=StaticFilesComponentConfig(
                enabled=True,
                prefix="",
                tags=["Themes", "Public API"],
                static_files_path=Path(__file__).parent.parent / "api" / "static",
            ),
        )

        tracing_endpoint = TracingComponent(
            name="tracing_internal",
            config=TracingComponentConfig(
                enabled=True, prefix="/api/", tags=["Tracing", "Public API"]
            ),
        )

        service = service.add_components(
            components=[
                websocket_endpoints,
                themes_endpoints,
                static_files_endpoint,
                tracing_endpoint,
            ]
        )

        if plugins is not None:
            for plugin in plugins:
                service = service.add_component(plugin)

        # Set class-level WebSocket broadcast wrapper (dashboard mode)
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

        # store launcher for cleanup
        orchestrator._dashboard_launcher = launcher

        # Run service (blocking call)
        # NOTE: Cleanup is not done here - it's handled by:
        # - ServerManager.serve() finally block (blocking mode)
        # - ServerManager._cleanup_server_callback() (non-blocking mode)
        await service.run_async(host=host, port=port)
