"""DashboardLauncher - manages npm lifecycle and browser launch for the dashboard.

This module handles:
- npm dependency installation (first run)
- npm dev server (DASHBOARD_DEV=1) or production build
- Automatic browser launch
- Process cleanup on shutdown
"""

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


# Frontend directory location (adjacent to this dashboard package)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


class DashboardLauncher:
    """Manages dashboard frontend lifecycle.

    Responsibilities:
    - Ensure npm dependencies installed
    - Start npm dev server (dev mode) or build for production
    - Launch browser automatically
    - Clean up npm processes on shutdown

    Usage:
        launcher = DashboardLauncher(port=8344)
        launcher.start()  # Starts npm and opens browser
        # ... orchestrator runs ...
        launcher.stop()  # Cleanup

    Or as context manager:
        with DashboardLauncher(port=8344):
            # orchestrator.serve() runs
            pass  # Automatically cleaned up
    """

    def __init__(
        self,
        port: int = 8344,
        frontend_dir: Path | None = None,
        static_dir: Path | None = None,
    ):
        """Initialize dashboard launcher.

        Args:
            port: HTTP port where dashboard will be served (default: 8344)
            frontend_dir: Optional frontend directory path (defaults to FRONTEND_DIR)
        """
        self.port = port
        self.frontend_dir = frontend_dir or FRONTEND_DIR
        self.static_dir = static_dir or Path(__file__).parent / "static"
        self.dev_mode = os.getenv("DASHBOARD_DEV", "0") == "1"
        self._npm_process: subprocess.Popen | None = None

    def _ensure_npm_dependencies(self) -> None:
        """Ensure npm dependencies are installed.

        Runs 'npm install'.
        """

        print(f"[Dashboard] Installing npm dependencies in {self.frontend_dir}...")
        try:
            subprocess.run(
                [self._get_npm_command(), "install"],
                cwd=self.frontend_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            print("[Dashboard] npm dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"[Dashboard] Warning: npm install failed: {e.stderr}")
            print("[Dashboard] Continuing anyway, dashboard may not work correctly")
        except FileNotFoundError:
            print("[Dashboard] Error: npm not found. Please install Node.js and npm.")
            print("[Dashboard] Dashboard will not be available.")

    def _get_npm_command(self) -> str:
        """Get npm command (npm or npm.cmd on Windows)."""
        return "npm.cmd" if sys.platform == "win32" else "npm"

    def _start_npm_process(self) -> None:
        """Start npm dev server or production build based on mode."""
        if self.dev_mode:
            self._start_dev_server()
        else:
            self._build_production()

    def _start_dev_server(self) -> None:
        """Start npm dev server for hot-reload development."""
        print(
            f"[Dashboard] Starting dev server (DASHBOARD_DEV=1) on port {self.port}..."
        )

        try:
            self._npm_process = subprocess.Popen(
                [self._get_npm_command(), "run", "dev"],
                cwd=self.frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            print(f"[Dashboard] Dev server started (PID: {self._npm_process.pid})")
        except FileNotFoundError:
            print("[Dashboard] Error: npm not found. Dev server not started.")

    def _build_production(self) -> None:
        """Build frontend for production (static files)."""
        print("[Dashboard] Building frontend for production...")

        try:
            subprocess.run(
                [self._get_npm_command(), "run", "build"],
                cwd=self.frontend_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            print("[Dashboard] Production build completed")

            # Copy build output from frontend/dist to src/flock/dashboard/static
            self._copy_build_output()

        except subprocess.CalledProcessError as e:
            print(f"[Dashboard] Warning: Production build failed: {e.stderr}")
            print("[Dashboard] Dashboard may not be available")
        except FileNotFoundError:
            print("[Dashboard] Error: npm not found. Build skipped.")

    def _copy_build_output(self) -> None:
        """Copy built frontend files from frontend/dist to dashboard/static."""
        import shutil

        source_dir = self.frontend_dir / "dist"
        target_dir = self.static_dir

        if not source_dir.exists():
            print(f"[Dashboard] Warning: Build output not found at {source_dir}")
            return

        # Remove old static files if they exist
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Copy dist to static
        print(f"[Dashboard] Copying build output from {source_dir} to {target_dir}")
        shutil.copytree(source_dir, target_dir)
        print(f"[Dashboard] Static files ready at {target_dir}")

    def _launch_browser(self) -> None:
        """Launch browser to dashboard URL after brief delay.

        Waits 2 seconds to allow server to start before opening browser.
        Catches errors gracefully (e.g., headless environments).
        """
        # Wait for server to start
        time.sleep(2)

        dashboard_url = f"http://localhost:{self.port}"
        print(f"[Dashboard] Opening browser to {dashboard_url}...")

        try:
            webbrowser.open(dashboard_url)
            print("[Dashboard] Browser launched successfully")
        except Exception as e:
            print(f"[Dashboard] Could not launch browser: {e}")
            print(f"[Dashboard] Please open {dashboard_url} manually")

    def start(self) -> None:
        """Start dashboard: install deps, start npm, launch browser.

        This method:
        1. Ensures npm dependencies are installed
        2. Starts npm dev server (dev mode) or builds production
        3. Launches browser to dashboard URL
        """
        print(f"[Dashboard] Starting dashboard on port {self.port}")
        print(f"[Dashboard] Mode: {'DEVELOPMENT' if self.dev_mode else 'PRODUCTION'}")
        print(f"[Dashboard] Frontend directory: {self.frontend_dir}")

        # Step 1: Ensure dependencies installed
        self._ensure_npm_dependencies()

        # Step 2: Start npm process
        self._start_npm_process()

        # Step 3: Launch browser
        self._launch_browser()

    def stop(self) -> None:
        """Stop dashboard and cleanup npm processes.

        Attempts graceful termination, falls back to kill if needed.
        """
        if self._npm_process is None:
            return

        print("[Dashboard] Stopping npm process...")

        try:
            # Try graceful termination first
            self._npm_process.terminate()

            # Wait up to 5 seconds for process to exit
            for _ in range(5):
                if self._npm_process.poll() is not None:
                    print("[Dashboard] npm process stopped gracefully")
                    return
                time.sleep(1)

            # Force kill if still running
            print("[Dashboard] npm process did not stop gracefully, forcing kill...")
            self._npm_process.kill()
            self._npm_process.wait(timeout=2)
            print("[Dashboard] npm process killed")

        except Exception as e:
            print(f"[Dashboard] Error stopping npm process: {e}")

        finally:
            self._npm_process = None

    def __enter__(self):
        """Context manager entry: start dashboard."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: stop dashboard."""
        self.stop()
        return False  # Don't suppress exceptions
