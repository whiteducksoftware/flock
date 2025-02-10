from rich.console import Console
from rich.syntax import Text

console = Console()


def display_banner():
    """Display the Flock banner."""
    banner_text = Text(
        """
    🦆    🐓      🦆
▒█▀▀▀ █░░ █▀▀█ █▀▀ █░█   
▒█▀▀▀ █░░ █░░█ █░░ █▀▄ 🐧
▒█░░░ ▀▀▀ ▀▀▀▀ ▀▀▀ ▀░▀  
  🦆    🐤  🐧  🐓
""",
        justify="center",
        style="bold orange3",
    )
    console.print(banner_text)
    console.print(
        f"[bold]v0.2.1[/] - [bold]white duck GmbH[/] - [cyan]https://whiteduck.de[/]\n"
    )
