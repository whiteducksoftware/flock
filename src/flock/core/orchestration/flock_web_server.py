# src/flock/core/orchestration/flock_web_server.py
"""Web server and CLI management functionality for Flock orchestrator."""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.api.custom_endpoint import FlockEndpoint
    from flock.core.flock import Flock
    from flock.core.flock_agent import FlockAgent

logger = get_logger("flock.web_server")


class FlockWebServer:
    """Handles web server and CLI functionality for Flock orchestrator."""

    def __init__(self, flock: "Flock"):
        self.flock = flock

    def serve(
        self,
        host: str = "127.0.0.1",
        port: int = 8344,
        server_name: str = "Flock Server",
        ui: bool = True,
        chat: bool = False,
        chat_agent: str | None = None,
        chat_message_key: str = "message",
        chat_history_key: str = "history",
        chat_response_key: str = "response",
        ui_theme: str | None = None,
        custom_endpoints: Sequence["FlockEndpoint"]
        | dict[tuple[str, list[str] | None], Callable[..., Any]]
        | None = None,
    ) -> None:
        """Launch an HTTP server that exposes the core REST API and, optionally, the browser-based UI."""
        try:
            from flock.webapp.run import start_unified_server
        except ImportError:
            logger.error(
                "Web application components not found (flock.webapp.run). "
                "Cannot start HTTP server. Ensure webapp dependencies are installed."
            )
            return

        logger.info(
            f"Attempting to start server for Flock '{self.flock.name}' on {host}:{port}. UI enabled: {ui}"
        )

        start_unified_server(
            flock_instance=self.flock,
            host=host,
            port=port,
            server_title=server_name,
            enable_ui_routes=ui,
            enable_chat_routes=chat,
            ui_theme=ui_theme,
            custom_endpoints=custom_endpoints,
        )

    def start_api(
        self,
        host: str = "127.0.0.1",
        port: int = 8344,
        server_name: str = "Flock Server",
        create_ui: bool = True,
        ui_theme: str | None = None,
        custom_endpoints: Sequence["FlockEndpoint"]
        | dict[tuple[str, list[str] | None], Callable[..., Any]]
        | None = None,
    ) -> None:
        """Deprecated: Use serve() instead."""
        import warnings

        warnings.warn(
            "start_api() is deprecated and will be removed in a future release. "
            "Use serve() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Delegate to the new serve() method (create_ui maps to ui)
        return self.serve(
            host=host,
            port=port,
            server_name=server_name,
            ui=create_ui,
            ui_theme=ui_theme,
            custom_endpoints=custom_endpoints,
        )

    def start_cli(
        self,
        start_agent: "FlockAgent | str | None" = None,
        server_name: str = "Flock CLI",
        show_results: bool = False,
        edit_mode: bool = False,
    ) -> None:
        """Starts an interactive CLI for this Flock instance."""
        try:
            from flock.cli.runner import start_flock_cli
        except ImportError:
            logger.error(
                "CLI components not found. Cannot start CLI. "
                "Ensure CLI dependencies are installed."
            )
            return

        logger.info(f"Starting CLI for Flock '{self.flock.name}'...")
        start_flock_cli(
            flock=self.flock,  # Pass the Flock instance
            server_name=server_name,
            show_results=show_results,
            edit_mode=edit_mode,
        )
