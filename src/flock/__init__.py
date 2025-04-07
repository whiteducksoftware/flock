"""Flock package initialization."""

from rich.panel import Panel

from flock.cli.config import init_config_file, load_config_file
from flock.cli.constants import (
    CLI_CFG_FILE,
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

    # Show a welcome message on first run with the new tool serialization format
    import os

    cfg_file = os.path.expanduser(f"~/.flock/{CLI_CFG_FILE}")
    if not os.path.exists(cfg_file):
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(cfg_file), exist_ok=True)

        init_config_file()
    else:
        # Load the config file
        load_config_file()

    feature_flag_file = os.path.expanduser("~/.flock/tool_serialization_notice")
    if not os.path.exists(feature_flag_file):
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(feature_flag_file), exist_ok=True)

        # Show the notice about the new tool serialization
        console.print(
            Panel(
                "[bold green]Flock 0.4.0b 'Magpie'- Flock CLI Management Console BETA[/]\n\n"
                "Flock now offers a tool for managing your flock:\n"
                "- Serialization and deserialization of Flock instances\n"
                "- Execution of Flock instances\n"
                "- Managing components, types, and agents via the registry management\n"
                "- Starting a web server to interact with your flock\n"
                "plannes featues: deployment on docker, kubernetes, and more!"
            ),
            justify="center",
        )
        console.line()

        # Create the flag file to prevent showing this notice again
        with open(feature_flag_file, "w") as f:
            f.write("Tool serialization notice shown")

        input("Press Enter to continue to the main menu...")
        console.clear()

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
