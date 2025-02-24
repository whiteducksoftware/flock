from pathlib import Path

from flock.core.util.cli_helper import display_hummingbird


def load_release_notes():
    """Load release notes."""
    from rich.console import Console
    from rich.markdown import Markdown

    from flock.core.util.cli_helper import init_console

    console = Console()
    file_path = Path(__file__).parent / "assets" / "release_notes.md"

    init_console()
    console.print(Markdown("# *'Hummingbird'* Release Notes"))
    display_hummingbird()
    with open(file_path) as file:
        release_notes = file.read()

    
    console.print(Markdown(release_notes))
