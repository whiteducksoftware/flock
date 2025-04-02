"""Load a Flock from a file."""

from pathlib import Path

import questionary
from rich.console import Console
from rich.markdown import Markdown

from flock.cli.loaded_flock_cli import start_loaded_flock_cli
from flock.core.flock import Flock


def filter(file_path) -> bool:
    """Filter function for file selection."""
    path = Path(file_path)
    if path.is_dir():
        return True
    return path.is_file() and (
        path.suffix == ".flock"
        or path.suffix == ".yaml"
        or path.suffix == ".yml"
    )


def load_flock():
    """Load a Flock from a file."""
    console = Console()

    console.print(
        "\nPlease select a *.flock, *.yaml, or *.yml file\n", style="bold green"
    )

    result = questionary.path("", file_filter=filter).ask()

    if not result:
        return

    selected_file = Path(result)
    if selected_file.is_file():
        console.print(f"Selected file: {selected_file}", style="bold green")

        try:
            flock = Flock.load_from_file(result)

            console.line()
            console.print(
                Markdown("# Flock loaded successfully"), style="bold green"
            )
            console.line()

            # Instead of just running the Flock, start our enhanced CLI
            start_loaded_flock_cli(
                flock, server_name=f"Flock - {selected_file.name}"
            )

        except Exception as e:
            console.print(f"Error loading Flock: {e!s}", style="bold red")
            input("\nPress Enter to continue...")
