"""Flock package initialization."""

from flock.cli.constants import CLI_THEME_BUILDER
from flock.core.logging.formatters.theme_builder import theme_builder


def main():
    """Main function."""
    import questionary
    from rich.console import Console

    from flock.cli.constants import (
        CLI_CREATE_AGENT,
        CLI_CREATE_FLOCK,
        CLI_LOAD_AGENT,
        CLI_LOAD_EXAMPLE,
        CLI_LOAD_FLOCK,
        CLI_SETTINGS,
        CLI_START_ADVANCED_MODE,
        CLI_START_WEB_SERVER,
    )
    from flock.cli.load_flock import load_flock
    from flock.core.util.cli_helper import display_banner

    console = Console()

    display_banner()

    console.print("Flock Management Console\n", style="bold green")

    result = questionary.select(
        "What do you want to do?",
        choices=[
            questionary.Separator(line=" "),
            # CLI_CREATE_AGENT,
            # CLI_CREATE_FLOCK,
            # CLI_LOAD_AGENT,
            CLI_LOAD_FLOCK,
            # CLI_LOAD_EXAMPLE,
            questionary.Separator(),
            CLI_THEME_BUILDER,
            CLI_SETTINGS,
            questionary.Separator(),
            CLI_START_ADVANCED_MODE,
            CLI_START_WEB_SERVER,
            "Exit",
        ],
    ).ask()

    if result == CLI_LOAD_FLOCK:
        load_flock()
    if result == CLI_THEME_BUILDER:
        theme_builder()


if __name__ == "__main__":
    main()
