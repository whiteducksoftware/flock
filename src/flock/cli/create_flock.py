"""Create a new Flock through a guided wizard.

This module provides a wizard-like interface for creating new Flock instances,
with options for basic configuration and initial agent creation.
"""

from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

from flock.cli.loaded_flock_cli import start_loaded_flock_cli
from flock.core.flock import Flock
from flock.core.flock_factory import FlockFactory
from flock.core.util.cli_helper import init_console

# Create console instance
console = Console()


def create_flock():
    """Create a new Flock through a guided wizard."""
    init_console()
    console.print(Panel("[bold green]Create New Flock[/]"), justify="center")
    console.line()

    # Step 1: Basic Flock Configuration
    console.print("[bold]Step 1: Basic Flock Configuration[/]")
    console.line()

    # Get description
    description = questionary.text(
        "Enter a description for this Flock (optional):",
        default="",
    ).ask()

    # Default model selection
    default_models = [
        "openai/gpt-4o",
        "openai/gpt-3.5-turbo",
        "anthropic/claude-3-opus-20240229",
        "anthropic/claude-3-sonnet-20240229",
        "gemini/gemini-1.5-pro",
        "Other (specify)",
    ]

    model_choice = questionary.select(
        "Select a default model:",
        choices=default_models,
    ).ask()

    if model_choice == "Other (specify)":
        model = questionary.text(
            "Enter the model identifier:",
            default="openai/gpt-4o",
        ).ask()
    else:
        model = model_choice

    # Execution options
    enable_temporal = questionary.confirm(
        "Enable Temporal for distributed execution?",
        default=False,
    ).ask()

    # Logging configuration
    enable_logging = questionary.confirm(
        "Enable logging?",
        default=True,
    ).ask()

    # Create the Flock instance
    flock = Flock(
        model=model,
        description=description,
        enable_temporal=enable_temporal,
        enable_logging=enable_logging,
    )

    console.print("\n[green]✓[/] Flock created successfully!")
    console.line()

    # Step 2: Create Initial Agent (optional)
    create_agent = questionary.confirm(
        "Would you like to create an initial agent?",
        default=True,
    ).ask()

    if create_agent:
        _create_initial_agent(flock)

    # Step 3: Save Options
    console.print("\n[bold]Step 3: Save Options[/]")
    console.line()

    save_choice = questionary.select(
        "What would you like to do with this Flock?",
        choices=[
            "Save to YAML file",
            "Continue in CLI without saving",
            "Execute immediately",
            "Cancel and discard",
        ],
    ).ask()

    if save_choice == "Save to YAML file":
        _save_flock_to_yaml(flock)

        # Ask if user wants to continue working with this Flock
        continue_with_flock = questionary.confirm(
            "Would you like to continue working with this Flock in the CLI?",
            default=True,
        ).ask()

        if continue_with_flock:
            start_loaded_flock_cli(flock, server_name="New Flock")

    elif save_choice == "Continue in CLI without saving":
        start_loaded_flock_cli(flock, server_name="New Flock")

    elif save_choice == "Execute immediately":
        from flock.cli.execute_flock import execute_flock

        try:
            execute_flock(flock)
        except ImportError:
            console.print(
                "[yellow]Execute functionality not yet implemented.[/]"
            )
            input("\nPress Enter to continue...")
            start_loaded_flock_cli(flock, server_name="New Flock")


def _create_initial_agent(flock):
    """Create an initial agent for the Flock.

    Args:
        flock: The Flock instance to add the agent to
    """
    console.print("\n[bold]Step 2: Create Initial Agent[/]")
    console.line()

    # Get agent name
    name = questionary.text(
        "Enter a name for the agent:",
        default="my_agent",
    ).ask()

    # Get agent description
    description = questionary.text(
        "Enter a description for the agent (optional):",
        default="",
    ).ask()

    # Get input specification
    input_spec = questionary.text(
        "Enter input specification (e.g., 'query: str | The search query'):",
        default="query",
    ).ask()

    # Get output specification
    output_spec = questionary.text(
        "Enter output specification (e.g., 'result: str | The generated result'):",
        default="result",
    ).ask()

    # Additional options
    use_cache = questionary.confirm(
        "Enable caching for this agent?",
        default=True,
    ).ask()

    enable_rich_tables = questionary.confirm(
        "Enable rich table output for this agent?",
        default=True,
    ).ask()

    # Create the agent
    agent = FlockFactory.create_default_agent(
        name=name,
        description=description,
        input=input_spec,
        output=output_spec,
        use_cache=use_cache,
        enable_rich_tables=enable_rich_tables,
    )

    # Add the agent to the Flock
    flock.add_agent(agent)
    console.print(f"\n[green]✓[/] Agent '{name}' created and added to Flock!")


def _save_flock_to_yaml(flock):
    """Save the Flock to a YAML file.

    Args:
        flock: The Flock instance to save
    """
    # Get file path
    default_name = "my_flock.flock.yaml"
    file_path = questionary.text(
        "Enter file path to save Flock:",
        default=default_name,
    ).ask()

    # Ensure the file has the correct extension
    if not file_path.endswith((".yaml", ".yml")):
        file_path += ".yaml"

    # Create directory if it doesn't exist
    save_path = Path(file_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Save the Flock to YAML
        flock.to_yaml_file(file_path)
        console.print(f"\n[green]✓[/] Flock saved to {file_path}")
    except Exception as e:
        console.print(f"\n[bold red]Error saving Flock:[/] {e!s}")
