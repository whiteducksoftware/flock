"""Agent management functionality for the Flock CLI.

This module provides a CLI interface for managing agents within a Flock system,
including listing, adding, editing, and removing agents.
"""

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.flock_factory import FlockFactory
from flock.core.util.cli_helper import init_console

# Create console instance
console = Console()


def manage_agents(flock: Flock):
    """Agent management entry point.

    Args:
        flock: The Flock instance containing agents to manage
    """
    if not flock:
        console.print("[bold red]Error: No Flock instance provided.[/]")
        return

    while True:
        init_console()
        console.print(Panel("[bold green]Agent Manager[/]"), justify="center")

        agent_names = list(flock._agents.keys())
        console.print(f"Flock contains [bold cyan]{len(agent_names)}[/] agents")

        if agent_names:
            console.print(f"Agents: {', '.join(agent_names)}")
        else:
            console.print("[yellow]No agents in this Flock yet.[/]")

        console.line()

        # Main menu
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Separator(line=" "),
                "List All Agents",
                "Add New Agent",
                "Edit Agent",
                "Remove Agent",
                "Export Agent to YAML",
                "Import Agent from YAML",
                questionary.Separator(),
                "Back to Main Menu",
            ],
        ).ask()

        if choice == "List All Agents":
            _list_agents(flock)
        elif choice == "Add New Agent":
            _add_agent(flock)
        elif choice == "Edit Agent":
            _edit_agent(flock)
        elif choice == "Remove Agent":
            _remove_agent(flock)
        elif choice == "Export Agent to YAML":
            _export_agent(flock)
        elif choice == "Import Agent from YAML":
            _import_agent(flock)
        elif choice == "Back to Main Menu":
            break

        if choice != "Back to Main Menu":
            input("\nPress Enter to continue...")


def _list_agents(flock: Flock):
    """List all agents in the Flock.

    Args:
        flock: The Flock instance
    """
    agent_names = list(flock._agents.keys())

    if not agent_names:
        console.print("[yellow]No agents in this Flock.[/]")
        return

    # Create table for agents
    table = Table(title="Agents in Flock")
    table.add_column("Name", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Description", style="yellow")
    table.add_column("Input", style="magenta")
    table.add_column("Output", style="magenta")

    for name in agent_names:
        agent = flock._agents[name]

        # Format model nicely
        model = agent.model or flock.model or "Default"

        # Format description (truncate if too long)
        description = str(agent.description)
        if len(description) > 30:
            description = description[:27] + "..."

        # Format input/output (truncate if too long)
        input_str = str(agent.input)
        if len(input_str) > 30:
            input_str = input_str[:27] + "..."

        output_str = str(agent.output)
        if len(output_str) > 30:
            output_str = output_str[:27] + "..."

        table.add_row(
            name,
            model,
            description,
            input_str,
            output_str,
        )

    console.print(table)

    # Option to view detailed info for a specific agent
    if len(agent_names) > 0:
        view_details = questionary.confirm(
            "View detailed information for an agent?",
            default=False,
        ).ask()

        if view_details:
            agent_to_view = questionary.select(
                "Select an agent to view:",
                choices=agent_names,
            ).ask()

            if agent_to_view:
                _view_agent_details(flock._agents[agent_to_view])


def _view_agent_details(agent: FlockAgent):
    """Display detailed information about an agent.

    Args:
        agent: The agent to display details for
    """
    init_console()
    console.print(
        Panel(f"[bold green]Agent Details: {agent.name}[/]"), justify="center"
    )

    # Create a panel for each section
    basic_info = Table(show_header=False, box=None)
    basic_info.add_column("Property", style="cyan")
    basic_info.add_column("Value", style="green")

    basic_info.add_row("Name", agent.name)
    basic_info.add_row("Model", str(agent.model or "Default"))
    basic_info.add_row("Description", str(agent.description))
    basic_info.add_row("Input", str(agent.input))
    basic_info.add_row("Output", str(agent.output))
    basic_info.add_row("Write to File", str(agent.write_to_file))
    basic_info.add_row("Wait for input", str(agent.wait_for_input))

    console.print(Panel(basic_info, title="Basic Information"))

    # Evaluator info
    evaluator_info = (
        f"Type: {type(agent.evaluator).__name__ if agent.evaluator else 'None'}"
    )
    console.print(Panel(evaluator_info, title="Evaluator"))

    # Router info
    router_info = f"Type: {type(agent.handoff_router).__name__ if agent.handoff_router else 'None'}"
    console.print(Panel(router_info, title="Router"))

    # Tools
    if agent.tools:
        tool_names = [t.__name__ for t in agent.tools]
        tools_info = ", ".join(tool_names)
    else:
        tools_info = "None"

    console.print(Panel(tools_info, title="Tools"))

    # Modules
    if agent.modules:
        module_table = Table(show_header=True)
        module_table.add_column("Name", style="cyan")
        module_table.add_column("Type", style="green")
        module_table.add_column("Enabled", style="yellow")

        for name, module in agent.modules.items():
            module_table.add_row(
                name,
                type(module).__name__,
                "Yes" if module.config.enabled else "No",
            )

        console.print(Panel(module_table, title="Modules"))
    else:
        console.print(Panel("None", title="Modules"))


def _add_agent(flock: Flock):
    """Add a new agent to the Flock.

    Args:
        flock: The Flock instance to add the agent to
    """
    console.print("\n[bold]Add New Agent[/]")
    console.line()

    # Get agent name
    name = questionary.text(
        "Enter a name for the agent:",
        default="my_agent",
    ).ask()

    # Check for name conflicts
    if name in flock._agents:
        console.print(
            f"[bold red]Error: An agent named '{name}' already exists.[/]"
        )
        return

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

    # Model selection
    use_flock_model = questionary.confirm(
        f"Use Flock's default model ({flock.model or 'None'})? Select 'n' to specify a different model.",
        default=True,
    ).ask()

    if use_flock_model:
        model = None  # Use Flock's default
    else:
        default_models = [
            "openai/gpt-4o",
            "openai/gpt-3.5-turbo",
            "anthropic/claude-3-opus-20240229",
            "anthropic/claude-3-sonnet-20240229",
            "gemini/gemini-1.5-pro",
            "Other (specify)",
        ]

        model_choice = questionary.select(
            "Select a model:",
            choices=default_models,
        ).ask()

        if model_choice == "Other (specify)":
            model = questionary.text(
                "Enter the model identifier:",
                default="openai/gpt-4o",
            ).ask()
        else:
            model = model_choice

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
        model=model,
        input=input_spec,
        output=output_spec,
        use_cache=use_cache,
        enable_rich_tables=enable_rich_tables,
    )

    # Add the agent to the Flock
    flock.add_agent(agent)
    console.print(f"\n[green]✓[/] Agent '{name}' created and added to Flock!")


def _edit_agent(flock: Flock):
    """Edit an existing agent in the Flock.

    Args:
        flock: The Flock instance containing the agent to edit
    """
    agent_names = list(flock._agents.keys())

    if not agent_names:
        console.print("[yellow]No agents in this Flock to edit.[/]")
        return

    # Select agent to edit
    agent_name = questionary.select(
        "Select an agent to edit:",
        choices=agent_names,
    ).ask()

    if not agent_name:
        return

    agent = flock._agents[agent_name]

    # Choose edit method
    edit_choice = questionary.select(
        "How would you like to edit this agent?",
        choices=[
            "Use Abstract Editor (Field by Field)",
            "Edit YAML Directly",
            "Cancel",
        ],
    ).ask()

    if edit_choice == "Use Abstract Editor (Field by Field)":
        # Not fully implemented yet
        console.print(
            "[yellow]Abstract editor not fully implemented. Opening YAML editor instead.[/]"
        )
        from flock.cli.yaml_editor import yaml_editor

        updated_agent = yaml_editor(agent)
        if updated_agent and isinstance(updated_agent, FlockAgent):
            flock._agents[agent_name] = updated_agent

    elif edit_choice == "Edit YAML Directly":
        from flock.cli.yaml_editor import _edit_yaml_directly

        updated_agent = _edit_yaml_directly(agent)
        if updated_agent and isinstance(updated_agent, FlockAgent):
            flock._agents[agent_name] = updated_agent
            console.print(f"\n[green]✓[/] Agent '{agent_name}' updated!")


def _remove_agent(flock: Flock):
    """Remove an agent from the Flock.

    Args:
        flock: The Flock instance containing the agent to remove
    """
    agent_names = list(flock._agents.keys())

    if not agent_names:
        console.print("[yellow]No agents in this Flock to remove.[/]")
        return

    # Select agent to remove
    agent_name = questionary.select(
        "Select an agent to remove:",
        choices=agent_names,
    ).ask()

    if not agent_name:
        return

    # Confirm deletion
    confirm = questionary.confirm(
        f"Are you sure you want to remove agent '{agent_name}'?",
        default=False,
    ).ask()

    if confirm:
        del flock._agents[agent_name]
        console.print(f"\n[green]✓[/] Agent '{agent_name}' removed from Flock!")


def _export_agent(flock: Flock):
    """Export an agent to a YAML file.

    Args:
        flock: The Flock instance containing the agent to export
    """
    agent_names = list(flock._agents.keys())

    if not agent_names:
        console.print("[yellow]No agents in this Flock to export.[/]")
        return

    # Select agent to export
    agent_name = questionary.select(
        "Select an agent to export:",
        choices=agent_names,
    ).ask()

    if not agent_name:
        return

    agent = flock._agents[agent_name]

    # Get file path
    file_path = questionary.text(
        "Enter file path to save agent:",
        default=f"{agent_name}.agent.yaml",
    ).ask()

    # Ensure the file has the correct extension
    if not file_path.endswith((".yaml", ".yml")):
        file_path += ".yaml"

    try:
        # Save the agent to YAML
        agent.to_yaml_file(file_path)
        console.print(
            f"\n[green]✓[/] Agent '{agent_name}' exported to {file_path}"
        )
    except Exception as e:
        console.print(f"\n[bold red]Error exporting agent:[/] {e!s}")


def _import_agent(flock: Flock):
    """Import an agent from a YAML file.

    Args:
        flock: The Flock instance to import the agent into
    """
    console.print("[yellow]Import functionality not yet implemented.[/]")
    # TODO: Implement agent import from YAML file
