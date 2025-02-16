"""Flock package initialization."""

import questionary
from rich.console import Console

from flock.core.util.cli_helper import display_banner

console = Console()


def main():
    """Main function."""
    display_banner()

    console.print("Flock Management Console\n", style="bold green")

    questionary.select(
        "What do you want to do?",
        choices=[
            questionary.Separator(line=" "),
            "1. Create an agent",
            "2. Create a flock",
            "3. Load an agent",
            "4. Load a *.flock file",
            questionary.Separator(),
            "Start advanced mode (coming soon)",
            "Start web server (coming soon)",
            "Exit",
        ],
    ).ask()


if __name__ == "__main__":
    main()
