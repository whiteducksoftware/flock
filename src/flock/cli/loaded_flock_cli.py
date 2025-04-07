"""CLI interface for working with a loaded Flock instance.

This module provides a CLI interface for a Flock instance that has already been loaded,
allowing users to execute, edit, or manage agents from the existing configuration.
"""

import questionary
from rich.console import Console
from rich.panel import Panel

from flock.cli.constants import (
    CLI_REGISTRY_MANAGEMENT,
    CLI_SETTINGS,
)
from flock.core.api import runner
from flock.core.flock import Flock
from flock.core.util.cli_helper import init_console

# Import future modules we'll create
# These will be implemented later
try:
    from flock.cli.yaml_editor import yaml_editor

    yaml_editor_available = True
except ImportError:
    yaml_editor_available = False

try:
    from flock.cli.manage_agents import manage_agents

    manage_agents_available = True
except ImportError:
    manage_agents_available = False

try:
    from flock.cli.execute_flock import execute_flock, execute_flock_batch

    execute_flock_available = True
except ImportError:
    execute_flock_available = False

try:
    from flock.cli.view_results import view_results

    view_results_available = True
except ImportError:
    view_results_available = False

# Create console instance
console = Console()


def start_loaded_flock_cli(
    flock: Flock,
    server_name: str = "Flock CLI",
    show_results: bool = False,
    edit_mode: bool = False,
) -> None:
    """Start a CLI interface with a loaded Flock instance.

    Args:
        flock: The loaded Flock instance
        server_name: Optional name for the CLI interface
        show_results: Whether to initially show results of previous runs
        edit_mode: Whether to open directly in edit mode
    """
    if not flock:
        console.print("[bold red]Error: No Flock instance provided.[/]")
        return

    agent_names = list(flock._agents.keys())

    # Directly go to specific modes if requested
    if edit_mode and yaml_editor_available:
        yaml_editor(flock)
        return

    if show_results and view_results_available:
        view_results(flock)
        return

    # Main CLI loop
    while True:
        # Initialize console for each loop iteration
        init_console()

        # Display header with Flock information
        console.print(Panel(f"[bold green]{server_name}[/]"), justify="center")
        console.print(
            f"Flock loaded with [bold cyan]{len(agent_names)}[/] agents: {', '.join(agent_names)}"
        )
        console.line()

        # Main menu choices
        choices = [
            questionary.Separator(line=" "),
            "Execute Flock",
            "Execute Flock - Batch Mode",
            "Start Web Server",
            "Start Web Server with UI",
            "Manage Agents",
            "View Results of Past Runs",
        ]

        # Add YAML Editor option if available
        if yaml_editor_available:
            choices.append("Edit YAML Configurations")

        # Add remaining options
        choices.extend([questionary.Separator(), CLI_REGISTRY_MANAGEMENT])
        choices.extend(
            [
                questionary.Separator(),
                CLI_SETTINGS,
                questionary.Separator(),
                "Exit",
            ]
        )

        # Display menu and get choice
        choice = questionary.select(
            "What would you like to do?",
            choices=choices,
        ).ask()

        # Handle menu selection
        if choice == "Execute Flock":
            if execute_flock_available:
                execute_flock(flock)
            else:
                console.print(
                    "[yellow]Execute Flock functionality not yet implemented.[/]"
                )
                input("\nPress Enter to continue...")

        elif choice == "Execute Flock - Batch Mode":
            if execute_flock_available:
                execute_flock_batch(flock)
            else:
                console.print(
                    "[yellow]Batch execution functionality not yet implemented.[/]"
                )
                input("\nPress Enter to continue...")

        elif choice == "Start Web Server":
            _start_web_server(flock, create_ui=False)

        elif choice == "Start Web Server with UI":
            _start_web_server(flock, create_ui=True)

        elif choice == "Manage Agents":
            if manage_agents_available:
                manage_agents(flock)
            else:
                console.print(
                    "[yellow]Manage Agents functionality not yet implemented.[/]"
                )
                input("\nPress Enter to continue...")

        elif choice == "View Results of Past Runs":
            if view_results_available:
                view_results(flock)
            else:
                console.print(
                    "[yellow]View Results functionality not yet implemented.[/]"
                )
                input("\nPress Enter to continue...")

        elif choice == CLI_REGISTRY_MANAGEMENT:
            from flock.cli.registry_management import manage_registry

            manage_registry()

        elif choice == "Edit YAML Configurations" and yaml_editor_available:
            yaml_editor(flock)

        elif choice == CLI_SETTINGS:
            from flock.cli.settings import settings_editor

            settings_editor()

        elif choice == "Exit":
            break

        # Pause after each action unless we're exiting
        if choice != "Exit" and not choice.startswith("Start Web Server"):
            input("\nPress Enter to continue...")


def _start_web_server(flock: Flock, create_ui: bool = False) -> None:
    """Start a web server with the loaded Flock instance.

    Args:
        flock: The loaded Flock instance
        create_ui: Whether to create a UI for the web server
    """
    host = "127.0.0.1"
    port = 8344
    server_name = "Flock API"

    # Get configuration from user
    console.print("\n[bold]Web Server Configuration[/]")

    host_input = questionary.text(
        "Host (default: 127.0.0.1):", default=host
    ).ask()
    if host_input:
        host = host_input

    port_input = questionary.text(
        "Port (default: 8344):", default=str(port)
    ).ask()
    if port_input and port_input.isdigit():
        port = int(port_input)

    server_name_input = questionary.text(
        "Server name (default: FlockName API):", default=flock.name + " API"
    ).ask()
    if server_name_input:
        server_name = server_name_input

    # Start the web server
    console.print(
        f"\nStarting web server on {host}:{port} {'with UI' if create_ui else 'without UI'}..."
    )

    # Use the Flock's start_api method
    runner.start_flock_api(
        flock=flock,
        host=host,
        port=port,
        server_name=server_name,
        create_ui=create_ui,
    )
