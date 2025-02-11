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
        """
        🦆   🐓   🐤    🦆
    ╭━━━━━━━━━━━━━━━━━━━━━━━━╮
🐓  │ ▒█▀▀▀ █░░ █▀▀█ █▀▀ █░█ │  🐧
    │ ▒█▀▀▀ █░░ █░░█ █░░ █▀▄ │
🐧  │ ▒█░░░ ▀▀▀ ▀▀▀▀ ▀▀▀ ▀░▀ │  🐓
    ╰━━━━━━━━━━━━━━━━━━━━━━━━╯
        🦆     🐤    🐧     🐓
""",
        justify="center",
        style="bold orange3",
    )
    console.print(banner_text)
    console.print(
        f"[bold]v{__version__}[/] - [bold]white duck GmbH[/] - [cyan]https://whiteduck.de[/]\n"
    )
