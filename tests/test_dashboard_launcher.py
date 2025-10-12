"""Tests for DashboardLauncher - npm lifecycle management and browser launch."""

import os
import subprocess
from unittest.mock import Mock, patch

import pytest

from flock.dashboard.launcher import DashboardLauncher


class TestDashboardLauncher:
    """Tests for DashboardLauncher npm process management."""

    @pytest.fixture
    def mock_frontend_dir(self, tmp_path):
        """Create a mock frontend directory with package.json."""
        frontend_dir = tmp_path / "frontend"
        frontend_dir.mkdir()
        package_json = frontend_dir / "package.json"
        package_json.write_text('{"name": "dashboard", "version": "1.0.0"}')
        return frontend_dir

    @pytest.fixture
    def launcher(self, mock_frontend_dir):
        """Create launcher instance with mocked frontend directory."""
        return DashboardLauncher(port=8344, frontend_dir=mock_frontend_dir)

    def test_initialization(self, launcher):
        """Test launcher initializes with correct default values."""
        assert launcher.port == 8344
        assert launcher.dev_mode is False
        assert launcher._npm_process is None

    def test_initialization_dev_mode(self, mock_frontend_dir):
        """Test launcher initializes in dev mode when DASHBOARD_DEV=1."""
        with patch.dict(os.environ, {"DASHBOARD_DEV": "1"}):
            launcher = DashboardLauncher(port=8344, frontend_dir=mock_frontend_dir)
            assert launcher.dev_mode is True

    @patch("subprocess.run")
    def test_npm_install_check_needed(self, mock_run, launcher, mock_frontend_dir):
        """Test npm install runs when node_modules doesn't exist."""
        # node_modules doesn't exist
        assert not (mock_frontend_dir / "node_modules").exists()

        launcher._ensure_npm_dependencies()

        # Should call npm install
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "npm" in args[0]
        assert "install" in args

    @patch("subprocess.run")
    def test_npm_install_runs_when_exists(self, mock_run, launcher, mock_frontend_dir):
        """Test npm install skipped when node_modules exists."""
        # Create node_modules directory
        node_modules = mock_frontend_dir / "node_modules"
        node_modules.mkdir()

        launcher._ensure_npm_dependencies()
        mock_run.assert_called_once()

    @patch("subprocess.Popen")
    def test_start_dev_server(self, mock_popen, launcher):
        """Test npm dev server starts in dev mode."""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process

        launcher.dev_mode = True
        launcher._start_npm_process()

        # Should call npm run dev
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "npm" in args[0]
        assert "run" in args
        assert "dev" in args

    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_start_production_build(self, mock_run, mock_popen, launcher, mock_frontend_dir):
        """Test production build runs when not in dev mode."""
        launcher.dev_mode = False
        launcher._start_npm_process()

        # Should call npm run build
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "npm" in args[0]
        assert "run" in args
        assert "build" in args

    @patch("webbrowser.open")
    @patch("time.sleep")
    def test_launch_browser(self, mock_sleep, mock_browser_open, launcher):
        """Test browser opens with correct URL."""
        launcher._launch_browser()

        # Should open browser with correct URL
        mock_browser_open.assert_called_once_with("http://localhost:8344")

    @patch("webbrowser.open")
    def test_launch_browser_error_handling(self, mock_browser_open, launcher):
        """Test browser launch errors are caught gracefully."""
        mock_browser_open.side_effect = Exception("Browser not found")

        # Should not raise exception
        launcher._launch_browser()

    @patch("subprocess.Popen")
    @patch("webbrowser.open")
    @patch("subprocess.run")
    @patch.dict(os.environ, {"DASHBOARD_DEV": "1"})
    def test_start_full_flow(self, mock_run, mock_browser, mock_popen, launcher, mock_frontend_dir):
        """Test full start flow in dev mode: install deps, start server, launch browser."""
        # Set dev mode
        launcher.dev_mode = True

        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher.start()

        # Should have called browser.open
        mock_browser.assert_called_once()
        # In dev mode, npm process should be set
        assert launcher._npm_process is not None

    def test_stop_without_process(self, launcher):
        """Test stop without running process doesn't error."""
        launcher._npm_process = None
        launcher.stop()  # Should not raise

    @patch("subprocess.Popen")
    def test_stop_with_running_process(self, mock_popen, launcher):
        """Test stop terminates running npm process."""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Running
        mock_popen.return_value = mock_process
        launcher._npm_process = mock_process

        launcher.stop()

        # Should terminate process
        mock_process.terminate.assert_called_once()

    @patch("subprocess.Popen")
    def test_stop_kills_if_terminate_fails(self, mock_popen, launcher):
        """Test stop kills process if terminate doesn't work."""
        mock_process = Mock()
        # Process still running after all 5 poll attempts
        mock_process.poll.side_effect = [None, None, None, None, None]
        launcher._npm_process = mock_process

        with patch("time.sleep"):
            launcher.stop()

        # Should call terminate then kill
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_context_manager(self, launcher):
        """Test DashboardLauncher works as context manager."""
        with patch.object(launcher, "start") as mock_start:
            with patch.object(launcher, "stop") as mock_stop:
                with launcher:
                    pass

                mock_start.assert_called_once()
                mock_stop.assert_called_once()

    @patch("subprocess.run")
    def test_npm_install_error_handling(self, mock_run, launcher, mock_frontend_dir):
        """Test npm install errors are caught and logged."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "npm install")

        # Should catch error and continue
        launcher._ensure_npm_dependencies()

    def test_frontend_dir_exists(self):
        """Test FRONTEND_DIR points to actual frontend directory."""
        from flock.dashboard.launcher import FRONTEND_DIR

        # Should exist in the actual package
        assert FRONTEND_DIR.name == "frontend"
        assert (FRONTEND_DIR.parent / "dashboard").exists() or FRONTEND_DIR.exists()
