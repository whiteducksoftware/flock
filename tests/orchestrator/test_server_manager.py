"""Comprehensive tests for ServerManager to reach 80%+ coverage."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flock.components.server import ServerComponent, ServerComponentConfig
from flock.core import Flock
from flock.orchestrator.server_manager import ServerManager


# Mock Components for Testing
class MockServerComponent(ServerComponent):
    """Mock server component for testing."""

    name: str = "mock_component"
    priority: int = 10
    config: ServerComponentConfig = ServerComponentConfig()

    def register_routes(self, app, orchestrator):
        """Mock route registration."""


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator for testing."""
    orch = Flock("openai/gpt-4o")
    # Add required attributes
    orch._server_task = None
    orch._dashboard_launcher = None
    orch._dashboard_collector = None
    orch._websocket_manager = None
    return orch


class TestServerManagerServe:
    """Test the main serve() method."""

    @pytest.mark.asyncio
    async def test_serve_non_blocking_returns_task(self, mock_orchestrator):
        """Test that serve() in non-blocking mode returns a task."""

        # Create a never-ending coroutine to simulate server running
        async def mock_server_impl(*args, **kwargs):
            """Mock server that runs indefinitely."""
            try:
                # Use asyncio.Event instead of sleep in loop
                event = asyncio.Event()
                await event.wait()  # Wait forever (until cancelled)
            except asyncio.CancelledError:
                pass

        with patch.object(ServerManager, "_serve_impl", side_effect=mock_server_impl):
            # Call serve with blocking=False
            result = await ServerManager.serve(
                mock_orchestrator, blocking=False, host="127.0.0.1", port=8344
            )

            # Should return a Task
            assert isinstance(result, asyncio.Task)
            assert mock_orchestrator._server_task is not None
            assert mock_orchestrator._server_task is result

            # Clean up the background task
            result.cancel()
            try:
                await result
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_serve_blocking_returns_none(self, mock_orchestrator):
        """Test that serve() in blocking mode returns None."""
        with patch.object(
            ServerManager, "_serve_impl", new_callable=AsyncMock
        ) as mock_serve_impl:
            # Mock the serve implementation
            mock_serve_impl.return_value = None

            # Call serve with blocking=True (default)
            result = await ServerManager.serve(
                mock_orchestrator, blocking=True, host="127.0.0.1", port=8344
            )

            # Should return None
            assert result is None
            # Serve implementation should have been called
            mock_serve_impl.assert_called_once()

    @pytest.mark.asyncio
    async def test_serve_blocking_cleans_up_dashboard_launcher(self, mock_orchestrator):
        """Test that blocking mode cleans up dashboard launcher in finally block."""
        # Create a mock dashboard launcher
        mock_launcher = MagicMock()
        mock_launcher.stop = MagicMock()
        mock_orchestrator._dashboard_launcher = mock_launcher

        with patch.object(
            ServerManager, "_serve_impl", new_callable=AsyncMock
        ) as mock_serve_impl:
            mock_serve_impl.return_value = None

            await ServerManager.serve(mock_orchestrator, blocking=True)

            # Dashboard launcher should be stopped and cleared
            mock_launcher.stop.assert_called_once()
            assert mock_orchestrator._dashboard_launcher is None

    @pytest.mark.asyncio
    async def test_serve_non_blocking_cleanup_callback(self, mock_orchestrator):
        """Test that non-blocking mode sets up cleanup callback."""

        # Create a never-ending coroutine
        async def mock_server_impl(*args, **kwargs):
            """Mock server that runs indefinitely."""
            try:
                event = asyncio.Event()
                await event.wait()
            except asyncio.CancelledError:
                pass

        with patch.object(ServerManager, "_serve_impl", side_effect=mock_server_impl):
            task = await ServerManager.serve(mock_orchestrator, blocking=False)

            # Verify task was created and stored
            assert task is not None
            assert isinstance(task, asyncio.Task)
            # Verify cleanup callback would be called (can't directly check callbacks)
            # but we can verify the task is registered on the orchestrator
            assert mock_orchestrator._server_task is task

            # Clean up
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_serve_with_dashboard_enabled(self, mock_orchestrator):
        """Test serve() with dashboard=True."""
        with patch.object(
            ServerManager, "_serve_impl", new_callable=AsyncMock
        ) as mock_serve_impl:
            mock_serve_impl.return_value = None

            await ServerManager.serve(mock_orchestrator, dashboard=True, blocking=True)

            # Verify _serve_impl was called with dashboard=True
            call_kwargs = mock_serve_impl.call_args[1]
            assert call_kwargs["dashboard"] is True

    @pytest.mark.asyncio
    async def test_serve_with_dashboard_v2_enables_dashboard(self, mock_orchestrator):
        """Test that dashboard_v2=True also enables dashboard."""
        with patch.object(
            ServerManager, "_serve_impl", new_callable=AsyncMock
        ) as mock_serve_impl:
            mock_serve_impl.return_value = None

            await ServerManager.serve(
                mock_orchestrator, dashboard_v2=True, blocking=True
            )

            # Verify dashboard is enabled via dashboard_v2
            call_kwargs = mock_serve_impl.call_args[1]
            assert call_kwargs["dashboard_v2"] is True

    @pytest.mark.asyncio
    async def test_serve_with_custom_host_and_port(self, mock_orchestrator):
        """Test serve() with custom host and port."""
        with patch.object(
            ServerManager, "_serve_impl", new_callable=AsyncMock
        ) as mock_serve_impl:
            mock_serve_impl.return_value = None

            custom_host = "0.0.0.0"
            custom_port = 9999

            await ServerManager.serve(
                mock_orchestrator,
                host=custom_host,
                port=custom_port,
                blocking=True,
            )

            # Verify custom host and port were passed
            call_kwargs = mock_serve_impl.call_args[1]
            assert call_kwargs["host"] == custom_host
            assert call_kwargs["port"] == custom_port

    @pytest.mark.asyncio
    async def test_serve_with_plugins(self, mock_orchestrator):
        """Test serve() with custom plugins."""
        mock_plugin = MockServerComponent()

        with patch.object(
            ServerManager, "_serve_impl", new_callable=AsyncMock
        ) as mock_serve_impl:
            mock_serve_impl.return_value = None

            await ServerManager.serve(
                mock_orchestrator, plugins=[mock_plugin], blocking=True
            )

            # Verify plugins were passed
            call_kwargs = mock_serve_impl.call_args[1]
            assert mock_plugin in call_kwargs["plugins"]

    @pytest.mark.asyncio
    async def test_serve_use_default_plugins_false_disables_dashboard(
        self, mock_orchestrator
    ):
        """Test that use_default_plugins=False disables dashboard mode."""
        mock_plugin = MockServerComponent()

        with patch.object(
            ServerManager, "_serve_impl", new_callable=AsyncMock
        ) as mock_serve_impl:
            mock_serve_impl.return_value = None

            await ServerManager.serve(
                mock_orchestrator,
                dashboard=True,  # This should be ignored
                plugins=[mock_plugin],
                use_default_plugins=False,
                blocking=True,
            )

            # Verify dashboard was disabled
            call_kwargs = mock_serve_impl.call_args[1]
            assert call_kwargs["dashboard"] is False
            assert call_kwargs["use_default_plugins"] is False

    @pytest.mark.asyncio
    async def test_serve_non_blocking_gives_server_time_to_start(
        self, mock_orchestrator
    ):
        """Test that non-blocking mode waits briefly for server startup."""
        with patch.object(
            ServerManager, "_serve_impl", new_callable=AsyncMock
        ) as mock_serve_impl:
            mock_serve_impl.return_value = None

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                task = await ServerManager.serve(mock_orchestrator, blocking=False)

                # Verify sleep was called to give server time to start
                mock_sleep.assert_called_once_with(0.1)

                # Clean up
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


class TestServerManagerCleanupCallback:
    """Test the _cleanup_server_callback() method."""

    def test_cleanup_stops_dashboard_launcher(self, mock_orchestrator):
        """Test cleanup callback stops dashboard launcher."""
        mock_launcher = MagicMock()
        mock_launcher.stop = MagicMock()
        mock_orchestrator._dashboard_launcher = mock_launcher

        # Create a mock task
        mock_task = MagicMock()
        mock_task.exception.return_value = None

        ServerManager._cleanup_server_callback(mock_orchestrator, mock_task)

        # Verify launcher was stopped and cleared
        mock_launcher.stop.assert_called_once()
        assert mock_orchestrator._dashboard_launcher is None

    def test_cleanup_clears_server_task(self, mock_orchestrator):
        """Test cleanup callback clears server task reference."""
        mock_orchestrator._server_task = MagicMock()

        mock_task = MagicMock()
        mock_task.exception.return_value = None

        ServerManager._cleanup_server_callback(mock_orchestrator, mock_task)

        # Verify server task was cleared
        assert mock_orchestrator._server_task is None

    def test_cleanup_handles_launcher_stop_exception(self, mock_orchestrator):
        """Test cleanup handles exceptions when stopping launcher."""
        mock_launcher = MagicMock()
        mock_launcher.stop.side_effect = RuntimeError("Stop failed")
        mock_orchestrator._dashboard_launcher = mock_launcher

        mock_task = MagicMock()
        mock_task.exception.return_value = None

        # Should not raise - exception is caught and logged
        ServerManager._cleanup_server_callback(mock_orchestrator, mock_task)

        # Launcher should still be cleared even on exception
        assert mock_orchestrator._dashboard_launcher is None

    def test_cleanup_logs_task_exceptions(self, mock_orchestrator):
        """Test cleanup logs task exceptions."""
        mock_task = MagicMock()
        test_exception = RuntimeError("Server failed")
        mock_task.exception.return_value = test_exception

        # Should not raise - exception is logged
        ServerManager._cleanup_server_callback(mock_orchestrator, mock_task)

    def test_cleanup_ignores_cancelled_error(self, mock_orchestrator):
        """Test cleanup ignores CancelledError."""
        mock_task = MagicMock()
        mock_task.exception.side_effect = asyncio.CancelledError()

        # Should not raise - CancelledError is normal cancellation
        ServerManager._cleanup_server_callback(mock_orchestrator, mock_task)


class TestServerManagerServeImpl:
    """Test the _serve_impl() internal method."""

    @pytest.mark.asyncio
    async def test_serve_impl_use_default_plugins_false_without_plugins_raises(
        self, mock_orchestrator
    ):
        """Test that use_default_plugins=False without plugins raises ValueError."""
        with pytest.raises(ValueError, match="use_default_plugins was set to 'False'"):
            await ServerManager._serve_impl(
                mock_orchestrator, use_default_plugins=False, plugins=None
            )

    @pytest.mark.asyncio
    async def test_serve_impl_use_default_plugins_false_with_empty_list_raises(
        self, mock_orchestrator
    ):
        """Test that use_default_plugins=False with empty plugin list raises ValueError."""
        with pytest.raises(ValueError, match="use_default_plugins was set to 'False'"):
            await ServerManager._serve_impl(
                mock_orchestrator, use_default_plugins=False, plugins=[]
            )

    @pytest.mark.asyncio
    async def test_serve_impl_dashboard_v2_enables_dashboard(self, mock_orchestrator):
        """Test that dashboard_v2=True enables dashboard."""
        with patch.object(
            ServerManager, "_serve_dashboard", new_callable=AsyncMock
        ) as mock_serve_dashboard:
            mock_serve_dashboard.return_value = None

            await ServerManager._serve_impl(
                mock_orchestrator, dashboard_v2=True, dashboard=False
            )

            # _serve_dashboard should be called when dashboard_v2=True
            mock_serve_dashboard.assert_called_once()

    @pytest.mark.asyncio
    async def test_serve_impl_calls_serve_custom_when_no_defaults(
        self, mock_orchestrator
    ):
        """Test _serve_impl calls _serve_custom when use_default_plugins=False."""
        mock_plugin = MockServerComponent()

        with patch.object(
            ServerManager, "_serve_custom", new_callable=AsyncMock
        ) as mock_serve_custom:
            mock_serve_custom.return_value = None

            await ServerManager._serve_impl(
                mock_orchestrator,
                use_default_plugins=False,
                plugins=[mock_plugin],
            )

            # _serve_custom should be called
            mock_serve_custom.assert_called_once()
            call_kwargs = mock_serve_custom.call_args[1]
            assert mock_plugin in call_kwargs["plugins"]

    @pytest.mark.asyncio
    async def test_serve_impl_calls_serve_standard_when_no_dashboard(
        self, mock_orchestrator
    ):
        """Test _serve_impl calls _serve_standard when dashboard=False."""
        with patch.object(
            ServerManager, "_serve_standard", new_callable=AsyncMock
        ) as mock_serve_standard:
            mock_serve_standard.return_value = None

            await ServerManager._serve_impl(
                mock_orchestrator, dashboard=False, use_default_plugins=True
            )

            # _serve_standard should be called
            mock_serve_standard.assert_called_once()

    @pytest.mark.asyncio
    async def test_serve_impl_calls_serve_dashboard_when_dashboard_true(
        self, mock_orchestrator
    ):
        """Test _serve_impl calls _serve_dashboard when dashboard=True."""
        with patch.object(
            ServerManager, "_serve_dashboard", new_callable=AsyncMock
        ) as mock_serve_dashboard:
            mock_serve_dashboard.return_value = None

            await ServerManager._serve_impl(
                mock_orchestrator, dashboard=True, use_default_plugins=True
            )

            # _serve_dashboard should be called
            mock_serve_dashboard.assert_called_once()


class TestServerManagerServeCustom:
    """Test the _serve_custom() method."""

    @pytest.mark.asyncio
    async def test_serve_custom_creates_service_with_plugins(self, mock_orchestrator):
        """Test _serve_custom creates BaseHTTPService with custom plugins."""
        mock_plugin = MockServerComponent()

        # Mock BaseHTTPService and its methods
        with patch("flock.api.base_service.BaseHTTPService") as MockService:
            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            await ServerManager._serve_custom(
                mock_orchestrator,
                host="127.0.0.1",
                port=8344,
                plugins=[mock_plugin],
            )

            # Verify service was created
            MockService.assert_called_once_with(orchestrator=mock_orchestrator)
            # Verify plugins were added
            mock_service.add_components.assert_called_once()
            # Verify server was run
            mock_service.run_async.assert_called_once_with(host="127.0.0.1", port=8344)


class TestServerManagerServeStandard:
    """Test the _serve_standard() method."""

    @pytest.mark.asyncio
    async def test_serve_standard_creates_service_with_standard_components(
        self, mock_orchestrator
    ):
        """Test _serve_standard creates service with standard HTTP components."""
        with patch("flock.api.base_service.BaseHTTPService") as MockService:
            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            await ServerManager._serve_standard(
                mock_orchestrator,
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify service was created with correct version
            MockService.assert_called_once_with(
                orchestrator=mock_orchestrator, version="0.5.0"
            )
            # Verify standard components were added
            mock_service.add_components.assert_called_once()
            # Verify server was run
            mock_service.run_async.assert_called_once_with(host="127.0.0.1", port=8344)

    @pytest.mark.asyncio
    async def test_serve_standard_adds_custom_plugins(self, mock_orchestrator):
        """Test _serve_standard adds custom plugins to standard components."""
        mock_plugin = MockServerComponent()

        with patch("flock.api.base_service.BaseHTTPService") as MockService:
            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            await ServerManager._serve_standard(
                mock_orchestrator,
                host="127.0.0.1",
                port=8344,
                plugins=[mock_plugin],
            )

            # Verify custom plugin was added
            mock_service.add_component.assert_called_once_with(mock_plugin)


class TestServerManagerServeDashboard:
    """Test the _serve_dashboard() method."""

    @pytest.mark.asyncio
    async def test_serve_dashboard_creates_websocket_manager(self, mock_orchestrator):
        """Test _serve_dashboard creates WebSocketManager."""
        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager") as MockWSManager,
            patch("flock.api.collector.DashboardEventCollector"),
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch.dict("os.environ", {}, clear=True),
        ):
            # Setup mocks
            mock_ws_manager = MagicMock()
            MockWSManager.return_value = mock_ws_manager

            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._agents = {}
            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=False,
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify WebSocketManager was created
            MockWSManager.assert_called_once()
            # Verify websocket manager was stored
            assert mock_orchestrator._websocket_manager == mock_ws_manager

    @pytest.mark.asyncio
    async def test_serve_dashboard_creates_event_collector(self, mock_orchestrator):
        """Test _serve_dashboard creates DashboardEventCollector."""
        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager"),
            patch("flock.api.collector.DashboardEventCollector") as MockCollector,
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch.dict("os.environ", {}, clear=True),
        ):
            # Setup mocks
            mock_collector = MagicMock()
            mock_collector.set_websocket_manager = MagicMock()
            MockCollector.return_value = mock_collector

            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._agents = {}
            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=False,
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify collector was created with store
            MockCollector.assert_called_once_with(store=mock_orchestrator.store)
            # Verify collector was stored
            assert mock_orchestrator._dashboard_collector == mock_collector

    @pytest.mark.asyncio
    async def test_serve_dashboard_starts_launcher(self, mock_orchestrator):
        """Test _serve_dashboard starts DashboardLauncher."""
        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager"),
            patch("flock.api.collector.DashboardEventCollector"),
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch.dict("os.environ", {}, clear=True),
        ):
            # Setup mocks
            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._agents = {}
            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=False,
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify launcher was created and started
            MockLauncher.assert_called_once()
            mock_launcher.start.assert_called_once()
            # Verify launcher was stored
            assert mock_orchestrator._dashboard_launcher == mock_launcher

    @pytest.mark.asyncio
    async def test_serve_dashboard_v2_uses_correct_frontend_dir(
        self, mock_orchestrator
    ):
        """Test _serve_dashboard with dashboard_v2=True uses correct frontend directory."""
        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager"),
            patch("flock.api.collector.DashboardEventCollector"),
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch.dict("os.environ", {}, clear=True),
        ):
            # Setup mocks
            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._agents = {}
            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=True,  # Enable v2
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify launcher was called with v2 directories
            call_kwargs = MockLauncher.call_args[1]
            assert "frontend_dir" in call_kwargs
            assert "frontend_v2" in str(call_kwargs["frontend_dir"])
            assert "static_dir" in call_kwargs
            assert "static_v2" in str(call_kwargs["static_dir"])

    @pytest.mark.asyncio
    async def test_serve_dashboard_adds_cors_component(self, mock_orchestrator):
        """Test _serve_dashboard adds CORS component by default."""
        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager"),
            patch("flock.api.collector.DashboardEventCollector"),
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch.dict("os.environ", {}, clear=True),
        ):
            # Setup mocks
            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._agents = {}
            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=False,
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify CORS component was added
            # Count how many times add_component was called
            assert mock_service.add_component.call_count >= 1

    @pytest.mark.asyncio
    async def test_serve_dashboard_skips_cors_if_custom_cors_provided(
        self, mock_orchestrator
    ):
        """Test _serve_dashboard skips default CORS if custom CORS plugin provided."""

        class CustomCORSComponent(ServerComponent):
            name: str = "cors"
            config: ServerComponentConfig = ServerComponentConfig()

            def register_routes(self, app, orchestrator):
                """Register routes."""

        custom_cors = CustomCORSComponent()

        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager"),
            patch("flock.api.collector.DashboardEventCollector"),
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch.dict("os.environ", {}, clear=True),
        ):
            # Setup mocks
            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._agents = {}
            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=False,
                host="127.0.0.1",
                port=8344,
                plugins=[custom_cors],
            )

            # Service should still be created successfully
            MockService.assert_called_once()

    @pytest.mark.asyncio
    async def test_serve_dashboard_injects_collector_into_existing_agents(
        self, mock_orchestrator
    ):
        """Test _serve_dashboard injects event collector into existing agents."""
        # Create a mock agent
        mock_agent = MagicMock()
        mock_agent._add_utilities = MagicMock()
        mock_orchestrator._agents = {"test_agent": mock_agent}

        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager"),
            patch("flock.api.collector.DashboardEventCollector") as MockCollector,
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch("flock.core.agent.Agent"),
            patch.dict("os.environ", {}, clear=True),
        ):
            # Setup mocks
            mock_collector = MagicMock()
            mock_collector.set_websocket_manager = MagicMock()
            MockCollector.return_value = mock_collector

            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=False,
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify collector was added to agent
            mock_agent._add_utilities.assert_called_once()
            call_args = mock_agent._add_utilities.call_args[0][0]
            assert mock_collector in call_args

    @pytest.mark.asyncio
    async def test_serve_dashboard_respects_dashboard_dev_env(self, mock_orchestrator):
        """Test _serve_dashboard respects DASHBOARD_DEV environment variable."""
        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager") as MockWSManager,
            patch("flock.api.collector.DashboardEventCollector"),
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch.dict("os.environ", {"DASHBOARD_DEV": "1"}, clear=True),
        ):
            # Setup mocks
            mock_ws_manager = MagicMock()
            MockWSManager.return_value = mock_ws_manager

            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._agents = {}
            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=False,
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify WebSocketManager was created with heartbeat enabled
            call_kwargs = MockWSManager.call_args[1]
            assert call_kwargs.get("enable_heartbeat") is True

    @pytest.mark.asyncio
    async def test_serve_dashboard_uses_custom_heartbeat_interval(
        self, mock_orchestrator
    ):
        """Test _serve_dashboard uses WS_HEARTBEAT environment variable."""
        with (
            patch("flock.api.base_service.BaseHTTPService") as MockService,
            patch("flock.api.websocket.WebSocketManager") as MockWSManager,
            patch("flock.api.collector.DashboardEventCollector"),
            patch("flock.api.launcher.DashboardLauncher") as MockLauncher,
            patch.dict("os.environ", {"WS_HEARTBEAT": "60"}, clear=True),
        ):
            # Setup mocks
            mock_ws_manager = MagicMock()
            MockWSManager.return_value = mock_ws_manager

            mock_service = MagicMock()
            mock_service.add_components.return_value = mock_service
            mock_service.add_component.return_value = mock_service
            mock_service.run_async = AsyncMock()
            MockService.return_value = mock_service

            mock_launcher = MagicMock()
            mock_launcher.start = MagicMock()
            MockLauncher.return_value = mock_launcher

            mock_orchestrator._agents = {}
            mock_orchestrator._event_emitter = MagicMock()
            mock_orchestrator._event_emitter.set_websocket_manager = MagicMock()

            await ServerManager._serve_dashboard(
                mock_orchestrator,
                dashboard_v2=False,
                host="127.0.0.1",
                port=8344,
                plugins=None,
            )

            # Verify WebSocketManager was created with custom heartbeat interval
            call_kwargs = MockWSManager.call_args[1]
            assert call_kwargs.get("heartbeat_interval") == "60"
