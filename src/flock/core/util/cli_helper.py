from importlib.metadata import PackageNotFoundError, version

from rich.console import Console
from rich.syntax import Text

try:
    __version__ = version("flock-core")
except PackageNotFoundError:
    __version__ = "0.2.0"

console = Console()


def display_banner():
    """Display the Flock banner."""
    banner_text = Text(
        f"""
🦆    🐓     🐤     🐧
╭━━━━━━━━━━━━━━━━━━━━━━━━╮
│ ▒█▀▀▀ █░░ █▀▀█ █▀▀ █░█ │
│ ▒█▀▀▀ █░░ █░░█ █░░ █▀▄ │
│ ▒█░░░ ▀▀▀ ▀▀▀▀ ▀▀▀ ▀░▀ │
╰━━━━━━━━━v{__version__}━━━━━━━━━╯
🦆     🐤    🐧     🐓
""",
        justify="center",
        style="bold orange3",
    )
    console.print(banner_text)
    console.print(
        f"[italic]'Hummingbird'[/] milestone - [bold]white duck GmbH[/] - [cyan]https://whiteduck.de[/]\n"
    )


def display_banner_no_version():
    """Display the Flock banner."""
    banner_text = Text(
        f"""
🦆    🐓     🐤     🐧
╭━━━━━━━━━━━━━━━━━━━━━━━━╮
│ ▒█▀▀▀ █░░ █▀▀█ █▀▀ █░█ │
│ ▒█▀▀▀ █░░ █░░█ █░░ █▀▄ │
│ ▒█░░░ ▀▀▀ ▀▀▀▀ ▀▀▀ ▀░▀ │
╰━━━━━━━━━━━━━━━━━━━━━━━━╯
🦆     🐤    🐧     🐓
""",
        justify="center",
        style="bold orange3",
    )
    console.print(banner_text)
    console.print(f"[bold]white duck GmbH[/] - [cyan]https://whiteduck.de[/]\n")
