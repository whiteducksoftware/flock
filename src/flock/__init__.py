"""Flock package initialization."""

import argparse
import os
import sys


def main():
    """Main function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Flock - Declarative LLM Orchestration at Scale"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start the web interface instead of the CLI",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Start a chat interface. If --web is also used, enables chat within the web app; otherwise, starts standalone chat.",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=None,
        help="Specify the theme name for the web interface (if --web is used).",
    )
    args = parser.parse_args()

    # If --web flag is provided, start the web server
    if args.web:
        try:
            # Set environment variable for theme if provided
            if args.theme:
                print(
                    f"INFO: Setting FLOCK_WEB_THEME environment variable to: {args.theme}"
                )
                os.environ["FLOCK_WEB_THEME"] = args.theme
            else:
                # Ensure it's not set if no theme arg is passed
                if "FLOCK_WEB_THEME" in os.environ:
                    del os.environ["FLOCK_WEB_THEME"]

            if args.chat: # --web --chat
                print("INFO: Starting web application with chat feature enabled.")
                os.environ["FLOCK_CHAT_ENABLED"] = "true"
            else: # Just --web
                print("INFO: Starting web application.")
                if "FLOCK_CHAT_ENABLED" in os.environ:
                    del os.environ["FLOCK_CHAT_ENABLED"]

            # Ensure standalone chat mode is not active
            if "FLOCK_START_MODE" in os.environ:
                 del os.environ["FLOCK_START_MODE"]

            # Import and run the standalone webapp main function
            from flock.webapp.run import main as run_webapp_main
            run_webapp_main()

        except ImportError:
            print(
                "Error: Could not import webapp components. Ensure web dependencies are installed.",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            print(f"Error starting webapp: {e}", file=sys.stderr)
            sys.exit(1)
        return

    elif args.chat: # Standalone chat mode (args.web is false)
        try:
            print("INFO: Starting standalone chat application.")
            os.environ["FLOCK_START_MODE"] = "chat"

            # Clear web-specific env vars that might conflict or not apply
            if "FLOCK_WEB_THEME" in os.environ:
                del os.environ["FLOCK_WEB_THEME"]
            if "FLOCK_CHAT_ENABLED" in os.environ:
                del os.environ["FLOCK_CHAT_ENABLED"]

            # Handle --theme if passed with --chat only
            if args.theme:
                 print(f"INFO: Standalone chat mode started with --theme '{args.theme}'. FLOCK_WEB_THEME will be set.")
                 os.environ["FLOCK_WEB_THEME"] = args.theme

            from flock.webapp.run import main as run_webapp_main
            run_webapp_main() # The webapp main needs to interpret FLOCK_START_MODE="chat"

        except ImportError:
            print("Error: Could not import webapp components for chat. Ensure web dependencies are installed.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error starting standalone chat application: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Otherwise, run the CLI interface
    import questionary
    from rich.console import Console
    from rich.panel import Panel

    from flock.cli.config import init_config_file, load_config_file
    from flock.cli.constants import (
        CLI_CFG_FILE,
        CLI_CREATE_AGENT,
        CLI_CREATE_FLOCK,
        CLI_EXIT,
        CLI_LOAD_AGENT,
        CLI_LOAD_EXAMPLE,
        CLI_LOAD_FLOCK,
        CLI_NOTES,
        CLI_REGISTRY_MANAGEMENT,
        CLI_SETTINGS,
        CLI_START_WEB_SERVER,
        CLI_THEME_BUILDER,
    )
    from flock.cli.load_flock import load_flock
    from flock.cli.load_release_notes import load_release_notes
    from flock.cli.settings import settings_editor
    from flock.core.logging.formatters.theme_builder import theme_builder
    from flock.core.util.cli_helper import init_console

    console = Console()

    # Show a welcome message on first run with the new tool serialization format
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
        elif result == CLI_NOTES:
            load_release_notes()
        elif result == CLI_EXIT:
            break
        input("\nPress Enter to continue...\n\n")

        console.clear()


if __name__ == "__main__":
    main()
