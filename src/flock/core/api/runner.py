# src/flock/api/runner.py
"""Provides functionality to start the Flock API server."""

from typing import TYPE_CHECKING

from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock import Flock

logger = get_logger("api.runner")


def start_flock_api(
    flock: "Flock",
    host: str = "127.0.0.1",
    port: int = 8344,
    server_name: str = "Flock API",
    create_ui: bool = False,
) -> None:
    """Start a REST API server for the given Flock instance."""
    try:
        # Import API class locally to avoid making it a hard dependency for core flock
        from flock.core.api import FlockAPI
    except ImportError:
        logger.error(
            "API components not found. Cannot start API. "
            "Ensure 'fastapi' and 'uvicorn' are installed."
        )
        return

    logger.info(
        f"Preparing to start API server for Flock '{flock.name}' on {host}:{port} {'with UI' if create_ui else 'without UI'}"
    )
    api_instance = FlockAPI(flock)  # Pass the Flock instance to the API
    api_instance.start(
        host=host, port=port, server_name=server_name, create_ui=create_ui
    )
