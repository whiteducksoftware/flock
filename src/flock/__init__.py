"""Flock package initialization."""

from flock.cli.constants import CLI_EXIT, CLI_NOTES, CLI_THEME_BUILDER
from flock.cli.load_release_notes import load_release_notes
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
    from flock.core.util.cli_helper import init_console

    console = Console()
    while True:
        init_console()

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
                questionary.Separator(),
                CLI_NOTES,
                CLI_EXIT,
            ],
        ).ask()

        if result == CLI_LOAD_FLOCK:
            load_flock()
        if result == CLI_THEME_BUILDER:
            theme_builder()
        if result == CLI_NOTES:
            load_release_notes()
        if result == CLI_EXIT:
            break
        input("\nPress Enter to continue...\n\n")

        console.clear()


if __name__ == "__main__":
    main()
