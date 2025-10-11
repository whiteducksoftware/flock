"""Integration tests for orchestrator.serve(dashboard=True) functionality."""

import asyncio
import contextlib
from unittest.mock import Mock, patch

import pytest

from flock.dashboard.collector import DashboardEventCollector


@pytest.fixture
def sample_agent(orchestrator):
    """Create a sample agent for testing."""
    # Use AgentBuilder pattern
    agent_builder = orchestrator.agent("sample_agent")
    agent_builder.description("Sample agent for testing")
    # Build the agent (this adds it to orchestrator)
    return orchestrator.get_agent("sample_agent")


class TestOrchestratorDashboardIntegration:
    """Test orchestrator.serve(dashboard=True) integration."""

    @patch("flock.service.BlackboardHTTPService")
    async def test_serve_without_dashboard(self, mock_service_class, orchestrator):
        """Test serve() works without dashboard parameter (backward compatibility)."""
        # Mock the standard service to avoid port binding
        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        # serve() is an async coroutine, not a function that returns a service
        # It blocks until interrupted, so we just verify it can be called
        serve_task = asyncio.create_task(orchestrator.serve())

        # Give it a moment to start
        await asyncio.sleep(0.1)

        # Cancel the task to avoid hanging
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass  # Expected

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.service.BlackboardHTTPService")
    async def test_serve_with_dashboard_false(
        self, mock_service_class, mock_launcher_class, orchestrator
    ):
        """Test serve(dashboard=False) doesn't start dashboard."""
        # Mock the standard service to avoid port binding
        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        serve_task = asyncio.create_task(orchestrator.serve(dashboard=False))

        # Give it a moment to start
        await asyncio.sleep(0.1)

        # Dashboard launcher should NOT be created
        mock_launcher_class.assert_not_called()

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    async def test_serve_with_dashboard_true(
        self, mock_service_class, mock_launcher_class, orchestrator, sample_agent
    ):
        """Test serve(dashboard=True) creates and starts dashboard launcher."""
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        # Mock the service to avoid actually running it
        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))  # Blocking call
        mock_service_class.return_value = mock_service

        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))

        # Give it a moment to start
        await asyncio.sleep(0.1)

        # Dashboard launcher should be created and started
        mock_launcher_class.assert_called_once()
        mock_launcher.start.assert_called_once()

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    async def test_dashboard_collector_injected_into_agents(
        self, mock_service_class, mock_launcher_class, orchestrator, sample_agent
    ):
        """Test DashboardEventCollector is injected into all agents when dashboard=True."""
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        # Mock the service
        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        # Before serve, agent should not have collector
        initial_utilities_count = len(sample_agent.utilities)

        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # After serve, agent should have collector injected
        assert len(sample_agent.utilities) == initial_utilities_count + 1

        # First utility should be DashboardEventCollector
        collector = sample_agent.utilities[0]
        assert isinstance(collector, DashboardEventCollector)

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    async def test_multiple_agents_all_get_collector(
        self, mock_service_class, mock_launcher_class, orchestrator
    ):
        """Test DashboardEventCollector is injected into all registered agents."""
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        # Create multiple agents using builder pattern
        orchestrator.agent("agent1").description("First agent")
        orchestrator.agent("agent2").description("Second agent")

        agent1 = orchestrator.get_agent("agent1")
        agent2 = orchestrator.get_agent("agent2")

        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # Both agents should have collector
        assert isinstance(agent1.utilities[0], DashboardEventCollector)
        assert isinstance(agent2.utilities[0], DashboardEventCollector)

        # Should be the SAME collector instance (shared across agents)
        assert agent1.utilities[0] is agent2.utilities[0]

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    async def test_websocket_manager_set_on_collector(
        self, mock_service_class, mock_launcher_class, orchestrator, sample_agent
    ):
        """Test WebSocketManager is set on DashboardEventCollector."""
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # Get the collector from the agent
        collector = sample_agent.utilities[0]

        # WebSocketManager should be set on collector
        assert collector._websocket_manager is not None

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    async def test_dashboard_collector_receives_events(
        self, mock_service_class, mock_launcher_class, orchestrator
    ):
        """Test that DashboardEventCollector is set up correctly to receive events."""
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        # Create agent using builder pattern
        orchestrator.agent("publishing_agent").description("Test publishing agent")
        agent = orchestrator.get_agent("publishing_agent")

        # Start service with dashboard
        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # Get collector
        collector = agent.utilities[0]

        # Collector should be configured
        assert isinstance(collector, DashboardEventCollector)
        assert collector._websocket_manager is not None
        # Events buffer should be initialized
        assert hasattr(collector, "_events")

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    async def test_dashboard_launcher_port_configuration(
        self, mock_service_class, mock_launcher_class, orchestrator
    ):
        """Test dashboard launcher receives correct port from service."""
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        # serve() should pass port to launcher (default 8344)
        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # Launcher should be initialized with port 8344
        mock_launcher_class.assert_called_once_with(port=8344)

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    @patch.dict("os.environ", {"DASHBOARD_DEV": "1"})
    async def test_dashboard_dev_mode_env_var(
        self, mock_service_class, mock_launcher_class, orchestrator
    ):
        """Test DASHBOARD_DEV=1 environment variable enables dev mode."""
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # Launcher should be created (dev mode is handled internally)
        mock_launcher_class.assert_called_once()

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.service.BlackboardHTTPService")
    async def test_backward_compatibility_no_dashboard_parameter(
        self, mock_service_class, orchestrator
    ):
        """Test existing code without dashboard parameter still works."""
        # Mock the standard service to avoid port binding
        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        # This should work without errors
        serve_task = asyncio.create_task(orchestrator.serve())
        await asyncio.sleep(0.1)

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    async def test_agent_added_after_serve_behavior(
        self, mock_service_class, mock_launcher_class, orchestrator
    ):
        """Test behavior of agents added after serve(dashboard=True).

        Note: In current implementation, agents must be added BEFORE serve(dashboard=True)
        to receive the event collector. This test documents that behavior.
        """
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        # Start service first
        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # Verify collector is stored for potential future use
        assert hasattr(orchestrator, "_dashboard_collector")
        assert isinstance(orchestrator._dashboard_collector, DashboardEventCollector)

        # Add agent after serve using builder pattern
        orchestrator.agent("late_agent").description("Late agent")
        late_agent = orchestrator.get_agent("late_agent")

        # Current behavior: Late agents DON'T automatically get collector
        # This is documented behavior - agents should be added before serve(dashboard=True)
        # If this changes in the future, this test will catch the behavior change
        assert len(late_agent.utilities) == 0

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task


class TestDashboardServiceIntegration:
    """Test DashboardHTTPService integration."""

    @patch("flock.dashboard.launcher.DashboardLauncher")
    @patch("flock.dashboard.service.DashboardHTTPService")
    async def test_dashboard_service_starts_with_orchestrator(
        self, mock_service_class, mock_launcher_class, orchestrator
    ):
        """Test DashboardHTTPService extends BlackboardHTTPService correctly."""
        mock_launcher = Mock()
        mock_launcher_class.return_value = mock_launcher

        mock_service = Mock()
        mock_service.run_async = Mock(return_value=asyncio.sleep(10))
        mock_service_class.return_value = mock_service

        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # Service should have been created
        mock_service_class.assert_called_once()

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task

    async def test_websocket_endpoint_available(self, orchestrator):
        """Test /ws WebSocket endpoint is available with dashboard=True."""
        # This is a basic test that serve() can be called
        # (Actual endpoint testing requires running server, validated in E2E)
        serve_task = asyncio.create_task(orchestrator.serve(dashboard=True))
        await asyncio.sleep(0.1)

        # Cleanup
        serve_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serve_task
