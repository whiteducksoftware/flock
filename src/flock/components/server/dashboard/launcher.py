"""DashboardLauncher - manages npm lifecycle and browser launch for the dashboard.

This module handles:
- npm dependency installation (first run)
- npm dev server (DASHBOARD_DEV=1) or production build
- Automatic browser launch
- Process cleanup on shutdown
"""

from pathlib import Path
from flock.logging.logging import get_logger

logger = get_logger(__name__)
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "frontend"

class DashboardLauncher:
    """Manages dashboard frontend lifecycle.

    Responsibilities:
    - Ensure npm dependencies installed
    - Start npm dev server (dev mode) or build for production
    - Launch browser automatically
    - Clean up npm processes on shutdown

    Usage:
        >>> launcher = DashboardLauncher(port=8344)
        >>> launcher.start() # Starts npm and opens browser
        >>> ... # orchestrator runs
        >>> launcher.stop() # cleanup
        >>> # Or as context manager
        >>> with DashboardLauncher(port=8344)
        >>>     # orchestrator.serve() runs...
        >>>     pass # Automatically cleaned up
    """

    def __init__(
        self,
        port: int = 8344,
        frontend_dir: Path | None = None,
        static_dir: Path | None = None
    ) -> None:
        """Initialize dashboard launcher.

        Args:
            port: HTTP port where dashboard will be served (default: 8344)
            frontend_dir: Optional frontend directory path (defaults to FRONTEND_DIR)
        """