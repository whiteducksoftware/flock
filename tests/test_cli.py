"""Comprehensive tests for the CLI module to achieve 80%+ coverage."""

from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, Mock, patch

import pytest
import typer
from rich.console import Console
from rich.table import Table
from typer.testing import CliRunner

from flock.cli import app, demo, list_agents, main, serve
from flock.core.artifacts import Artifact


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


@pytest.fixture
def mock_console(mocker):
    """Mock Rich console for testing output."""
    return mocker.patch("flock.cli.console", spec=Console)


@pytest.fixture
def runner():
    """Create a Typer CLI test runner."""
    return CliRunner()


class TestDemoCommand:
    """Tests for the demo command."""

    def test_demo_command_imports_and_runs(self, mocker, mock_console):
        """Test that demo command properly imports and runs orchestrator."""
        # Mock the imports that happen inside the function
        mock_idea = mocker.patch("flock.examples.Idea")
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")

        # Setup mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.arun = AsyncMock()
        mock_orchestrator.run_until_idle = AsyncMock()
        mock_store = Mock()
        mock_store.list = AsyncMock(return_value=[])
        mock_orchestrator.store = mock_store

        mock_agents = {"movie": Mock()}
        mock_create.return_value = (mock_orchestrator, mock_agents)

        # Mock asyncio.run to capture the coroutine
        async_run_call = None

        def capture_async_run(coro):
            nonlocal async_run_call
            async_run_call = coro
            # Run the coroutine synchronously for testing
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        mocker.patch("asyncio.run", side_effect=capture_async_run)

        # Call demo
        demo(topic="Test Topic", genre="test genre")

        # Verify imports were used
        mock_create.assert_called_once()
        mock_idea.assert_called_once_with(topic="Test Topic", genre="test genre")

        # Verify async execution happened
        assert async_run_call is not None

        # Verify console output
        mock_console.print.assert_called_once()
        assert isinstance(mock_console.print.call_args[0][0], Table)

    def test_demo_default_parameters(self, runner, mocker):
        """Test demo with default parameters."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")
        mock_idea = mocker.patch("flock.examples.Idea")

        mock_orchestrator = Mock()
        mock_orchestrator.arun = AsyncMock()
        mock_orchestrator.run_until_idle = AsyncMock()
        mock_store = Mock()
        mock_store.list = AsyncMock(return_value=[])
        mock_orchestrator.store = mock_store

        mock_create.return_value = (mock_orchestrator, {"movie": Mock()})

        # Patch asyncio.run to execute immediately
        def run_coro(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        mocker.patch("asyncio.run", side_effect=run_coro)

        # Call via CLI to get proper default handling
        result = runner.invoke(app, ["demo"])
        assert result.exit_code == 0

        # Verify default values were used
        mock_idea.assert_called_once_with(
            topic="AI agents collaborating", genre="comedy"
        )

    def test_demo_with_artifacts(self, mocker, mock_console):
        """Test demo displays artifacts correctly."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")
        mocker.patch("flock.examples.Idea")

        mock_orchestrator = Mock()
        mock_orchestrator.arun = AsyncMock()
        mock_orchestrator.run_until_idle = AsyncMock()

        # Create test artifacts
        test_artifacts = [
            Artifact(type="Movie", payload={"title": "Test"}, produced_by="test"),
            Artifact(type="Tagline", payload={"line": "Great!"}, produced_by="test"),
        ]

        mock_store = Mock()
        mock_store.list = AsyncMock(return_value=test_artifacts)
        mock_orchestrator.store = mock_store

        mock_create.return_value = (mock_orchestrator, {"movie": Mock()})

        # Patch asyncio.run
        def run_coro(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        mocker.patch("asyncio.run", side_effect=run_coro)

        demo()

        # Verify table was created with artifacts
        mock_console.print.assert_called_once()
        table = mock_console.print.call_args[0][0]
        assert isinstance(table, Table)
        assert table.title == "Published Artifacts"

    def test_demo_cli_invocation(self, runner, mocker):
        """Test demo command via CLI runner."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")
        mocker.patch("flock.examples.Idea")

        mock_orchestrator = Mock()
        mock_orchestrator.arun = AsyncMock()
        mock_orchestrator.run_until_idle = AsyncMock()
        mock_store = Mock()
        mock_store.list = AsyncMock(return_value=[])
        mock_orchestrator.store = mock_store

        mock_create.return_value = (mock_orchestrator, {"movie": Mock()})

        def run_coro(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        mocker.patch("asyncio.run", side_effect=run_coro)

        result = runner.invoke(app, ["demo", "--topic", "Custom", "--genre", "action"])

        assert result.exit_code == 0


class TestListAgentsCommand:
    """Tests for the list_agents command."""

    def test_list_agents_displays_all_agents(self, mocker, mock_console):
        """Test that list_agents shows all registered agents."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")

        # Create mock agents with descriptions
        agent1 = Mock()
        agent1.name = "agent1"
        agent1.description = "First agent"

        agent2 = Mock()
        agent2.name = "agent2"
        agent2.description = "Second agent"

        agent3 = Mock()
        agent3.name = "agent3"
        agent3.description = None  # No description

        mock_orchestrator = Mock()
        mock_orchestrator.agents = [agent1, agent2, agent3]

        mock_create.return_value = (mock_orchestrator, {})

        list_agents()

        # Verify orchestrator was created
        mock_create.assert_called_once()

        # Verify console printed a table
        mock_console.print.assert_called_once()
        table = mock_console.print.call_args[0][0]
        assert isinstance(table, Table)
        assert table.title == "Agents"

    def test_list_agents_cli_invocation(self, runner, mocker):
        """Test list-agents command via CLI runner."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")

        agent = Mock()
        agent.name = "test"
        agent.description = "Test"

        mock_orchestrator = Mock()
        mock_orchestrator.agents = [agent]
        mock_create.return_value = (mock_orchestrator, {})

        result = runner.invoke(app, ["list-agents"])

        assert result.exit_code == 0
        mock_create.assert_called_once()

    def test_list_agents_empty_descriptions(self, mocker, mock_console):
        """Test list_agents handles agents without descriptions."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")

        agent1 = Mock()
        agent1.name = "agent1"
        agent1.description = ""

        agent2 = Mock()
        agent2.name = "agent2"
        agent2.description = None

        mock_orchestrator = Mock()
        mock_orchestrator.agents = [agent1, agent2]

        mock_create.return_value = (mock_orchestrator, {})

        list_agents()

        # Table should still be created
        mock_console.print.assert_called_once()
        table = mock_console.print.call_args[0][0]
        assert isinstance(table, Table)


class TestServeCommand:
    """Tests for the serve command."""

    def test_serve_creates_and_runs_service(self, mocker):
        """Test that serve creates HTTP service and runs it."""
        # Patch the imports that happen inside the function
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")

        # We need to patch BlackboardHTTPService where it's imported in cli.py
        from flock import cli

        mock_service_cls = mocker.patch.object(cli, "BlackboardHTTPService")

        mock_orchestrator = Mock()
        mock_create.return_value = (mock_orchestrator, {})

        mock_service = Mock()
        mock_service.run = Mock()  # Ensure run is a mock
        mock_service_cls.return_value = mock_service

        serve(host="localhost", port=9000)

        # Verify service was created with orchestrator
        mock_service_cls.assert_called_once_with(mock_orchestrator)

        # Verify service.run was called with correct params
        mock_service.run.assert_called_once_with(host="localhost", port=9000)

    def test_serve_default_parameters(self, mocker):
        """Test serve with default host and port."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")

        from flock import cli

        mock_service_cls = mocker.patch.object(cli, "BlackboardHTTPService")

        mock_orchestrator = Mock()
        mock_create.return_value = (mock_orchestrator, {})

        mock_service = Mock()
        mock_service.run = Mock()
        mock_service_cls.return_value = mock_service

        serve()

        # Verify defaults were used
        mock_service.run.assert_called_once_with(host="127.0.0.1", port=8344)

    def test_serve_cli_invocation(self, runner, mocker):
        """Test serve command via CLI runner."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")

        from flock import cli

        mock_service_cls = mocker.patch.object(cli, "BlackboardHTTPService")

        mock_orchestrator = Mock()
        mock_create.return_value = (mock_orchestrator, {})

        mock_service = Mock()
        mock_service.run = Mock()
        mock_service_cls.return_value = mock_service

        result = runner.invoke(app, ["serve", "--host", "0.0.0.0", "--port", "3000"])

        assert result.exit_code == 0
        mock_service.run.assert_called_once_with(host="0.0.0.0", port=3000)


class TestMainFunction:
    """Tests for the main entry point."""

    def test_main_calls_app(self, mocker):
        """Test that main() invokes the Typer app."""
        mock_app = mocker.patch("flock.cli.app")

        main()

        mock_app.assert_called_once()

    def test_main_help_output(self, runner):
        """Test main --help displays correct information."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Blackboard Agents CLI" in result.output
        assert "demo" in result.output
        assert "list-agents" in result.output
        assert "serve" in result.output

    def test_command_help_outputs(self, runner):
        """Test individual command help texts."""
        # Test demo help
        result = runner.invoke(app, ["demo", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi(result.output)
        assert "Run the demo pipeline" in clean_output
        assert "--topic" in clean_output
        assert "--genre" in clean_output

        # Test list-agents help
        result = runner.invoke(app, ["list-agents", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi(result.output)
        assert "List registered agents" in clean_output

        # Test serve help
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi(result.output)
        assert "Run the HTTP control plane" in clean_output
        assert "--host" in clean_output
        assert "--port" in clean_output

    def test_invalid_command(self, runner):
        """Test behavior with invalid command."""
        result = runner.invoke(app, ["nonexistent"])

        assert result.exit_code != 0


class TestAsyncBehavior:
    """Tests for async execution patterns."""

    def test_demo_async_flow(self, mocker):
        """Test the async execution flow of demo."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")
        mocker.patch("flock.examples.Idea")

        mock_orchestrator = Mock()
        mock_orchestrator.arun = AsyncMock()
        mock_orchestrator.run_until_idle = AsyncMock()

        artifacts = [
            Artifact(type="Test", payload={"data": "test"}, produced_by="test")
        ]

        mock_store = Mock()
        mock_store.list = AsyncMock(return_value=artifacts)
        mock_orchestrator.store = mock_store

        mock_agents = {"movie": Mock()}
        mock_create.return_value = (mock_orchestrator, mock_agents)

        # Capture the coroutine passed to asyncio.run
        captured_coro = None

        def capture_coro(coro):
            nonlocal captured_coro
            captured_coro = coro
            # Use the synchronous test loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        with patch("asyncio.run", side_effect=capture_coro):
            demo()

        # Verify async methods were called
        mock_orchestrator.arun.assert_called_once_with(mock_agents["movie"], mocker.ANY)
        mock_orchestrator.run_until_idle.assert_called_once()
        mock_store.list.assert_called_once()


class TestErrorHandling:
    """Tests for error conditions and edge cases."""

    def test_demo_handles_orchestrator_error(self, mocker, mock_console):
        """Test demo handles errors during orchestration."""
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")
        mocker.patch("flock.examples.Idea")

        mock_orchestrator = Mock()
        mock_orchestrator.arun = AsyncMock(
            side_effect=RuntimeError("Orchestration failed")
        )

        mock_create.return_value = (mock_orchestrator, {"movie": Mock()})

        # The error should propagate through asyncio.run
        with pytest.raises(RuntimeError, match="Orchestration failed"):

            def run_coro(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

            with patch("asyncio.run", side_effect=run_coro):
                demo()

    def test_serve_handles_service_error(self, mocker):
        """Test serve handles errors in service creation."""
        # Patch all the necessary components
        mock_create = mocker.patch("flock.examples.create_demo_orchestrator")
        mock_uvicorn = mocker.patch("uvicorn.run")

        mock_orchestrator = Mock()
        mock_create.return_value = (mock_orchestrator, {})

        # Mock the service creation to fail
        mock_service_cls = mocker.patch("flock.cli.BlackboardHTTPService")
        mock_service_cls.side_effect = ValueError("Service error")

        # The error should be raised when BlackboardHTTPService is instantiated
        with pytest.raises(ValueError, match="Service error"):
            serve()


class TestSQLiteCommands:
    """Tests for SQLite store utilities."""

    def test_init_sqlite_store_command(self, runner, mocker, tmp_path):
        db_path = tmp_path / "board.db"
        store_cls = mocker.patch("flock.cli.SQLiteBlackboardStore")
        store_instance = Mock()
        store_instance.ensure_schema = AsyncMock()
        store_instance.close = AsyncMock()
        store_cls.return_value = store_instance

        result = runner.invoke(app, ["init-sqlite-store", str(db_path)])

        assert result.exit_code == 0
        store_cls.assert_called_once_with(str(db_path))
        store_instance.ensure_schema.assert_awaited_once()
        store_instance.close.assert_awaited_once()

    def test_sqlite_maintenance_command(self, runner, mocker, tmp_path):
        db_path = tmp_path / "board.db"
        store_cls = mocker.patch("flock.cli.SQLiteBlackboardStore")
        store_instance = Mock()
        store_instance.ensure_schema = AsyncMock()
        store_instance.delete_before = AsyncMock(return_value=5)
        store_instance.vacuum = AsyncMock()
        store_instance.close = AsyncMock()
        store_cls.return_value = store_instance

        result = runner.invoke(
            app,
            [
                "sqlite-maintenance",
                str(db_path),
                "--delete-before",
                "2025-01-01T00:00:00+00:00",
                "--vacuum",
            ],
        )

        assert result.exit_code == 0
        store_instance.ensure_schema.assert_awaited_once()
        store_instance.delete_before.assert_awaited_once()
        store_instance.vacuum.assert_awaited_once()
        store_instance.close.assert_awaited_once()


class TestModuleStructure:
    """Tests for module-level attributes and exports."""

    def test_cli_app_is_typer(self):
        """Test that app is a Typer instance."""
        from flock.cli import app

        assert isinstance(app, typer.Typer)

    def test_console_is_rich_console(self):
        """Test that console is a Rich Console."""
        from flock.cli import console

        assert isinstance(console, Console)

    def test_module_exports(self):
        """Test __all__ exports."""
        from flock import cli

        assert hasattr(cli, "__all__")
        assert "app" in cli.__all__
        assert "main" in cli.__all__

    def test_commands_registered(self):
        """Test that all commands are registered with the app."""
        from flock.cli import app

        # Get registered command names
        # Typer uses callback name or function name
        command_names = [cmd.callback.__name__ for cmd in app.registered_commands]

        assert "demo" in command_names
        assert "list_agents" in command_names
        assert "serve" in command_names
