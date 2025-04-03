"""Flock package initialization."""

from rich.panel import Panel

from flock.cli.constants import (
    CLI_EXIT,
    CLI_NOTES,
    CLI_REGISTRY_MANAGEMENT,
    CLI_THEME_BUILDER,
)
from flock.cli.load_release_notes import load_release_notes
from flock.cli.settings import settings_editor
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
        CLI_START_WEB_SERVER,
    )
    from flock.cli.load_flock import load_flock
    from flock.core.util.cli_helper import init_console

    console = Console()
    while True:
        init_console()

        # console.print("Flock Management Console\n", style="bold green")
        console.print(
            Panel("[bold green]Flock Management Console[/]"), justify="center"
        )
        console.line()

        result = questionary.select(
            "What do you want to do?",
            choices=[
                questionary.Separator(line=" "),
                # CLI_CREATE_AGENT,
                CLI_CREATE_FLOCK,
                # CLI_LOAD_AGENT,
                CLI_LOAD_FLOCK,
                # CLI_LOAD_EXAMPLE,
                questionary.Separator(),
                CLI_REGISTRY_MANAGEMENT,
                questionary.Separator(),
                CLI_THEME_BUILDER,
                CLI_SETTINGS,
                questionary.Separator(),
                CLI_NOTES,
                CLI_EXIT,
            ],
        ).ask()

        if result == CLI_LOAD_FLOCK:
            load_flock()
        elif result == CLI_CREATE_FLOCK:
            # This will be implemented in a separate create_flock.py
            from flock.cli.create_flock import create_flock

            create_flock()
        elif result == CLI_THEME_BUILDER:
            theme_builder()
        elif result == CLI_REGISTRY_MANAGEMENT:
            # Import registry management when needed
            from flock.cli.registry_management import manage_registry

            manage_registry()
        elif result == CLI_SETTINGS:
            settings_editor()
        elif result == CLI_START_WEB_SERVER:
            # Simple web server without a loaded Flock - could create a new one
            console.print(
                "[yellow]Web server without loaded Flock not yet implemented.[/]"
            )
            input("\nPress Enter to continue...")
        elif result == CLI_NOTES:
            load_release_notes()
        elif result == CLI_EXIT:
            break
        input("\nPress Enter to continue...\n\n")

        console.clear()


if __name__ == "__main__":
    main()
