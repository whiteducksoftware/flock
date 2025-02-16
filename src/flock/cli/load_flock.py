"""Load a Flock from a file."""

from pathlib import Path

import questionary
from rich.console import Console
from rich.markdown import Markdown

from flock.core.flock import Flock


def filter(file_path) -> bool:
    """Filter function for file selection."""
    path = Path(file_path)
    if path.is_dir():
        return True
    return path.is_file() and path.suffix == ".flock"


def load_flock():
    """Load a Flock from a file."""
    console = Console()

    console.print("\nPlease select a *.flock file\n", style="bold green")

    result = questionary.path("", file_filter=filter).ask()

    selected_file = Path(result)
    if selected_file.is_file():
        console.print(f"Selected file: {selected_file}", style="bold green")

        flock = Flock.load_from_file(result)

        console.line()
        console.print(Markdown("# Flock loaded...."), style="bold orange")
        console.line()

        flock.run()
