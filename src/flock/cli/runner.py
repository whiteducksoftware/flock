# src/flock/cli/runner.py
"""Provides functionality to start the Flock CLI."""

from typing import TYPE_CHECKING

from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock import Flock

logger = get_logger("cli.runner")


def start_flock_cli(
    flock: "Flock",
    server_name: str = "Flock CLI",
    show_results: bool = False,
    edit_mode: bool = False,
) -> None:
    """Start a CLI interface for the given Flock instance."""
    try:
        # Import CLI function locally
        from flock.cli.loaded_flock_cli import start_loaded_flock_cli
    except ImportError:
        logger.error(
            "CLI components not found. Cannot start CLI. "
            "Ensure the CLI modules are properly installed/available."
        )
        return

    logger.info(
        f"Starting CLI interface for loaded Flock instance '{flock.name}' ({len(flock.agents)} agents)"
    )

    # Pass the Flock instance to the CLI entry point
    start_loaded_flock_cli(
        flock=flock,
        server_name=server_name,
        show_results=show_results,
        edit_mode=edit_mode,
    )
