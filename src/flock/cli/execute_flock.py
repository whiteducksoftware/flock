"""Execute a Flock instance with a selected agent.

This module provides functionality to execute a Flock instance with
a selected agent and input configuration.
"""

import json

import questionary
from rich.console import Console
from rich.panel import Panel

from flock.core.flock import Flock
from flock.core.util.cli_helper import init_console

# Create console instance
console = Console()


def execute_flock(flock: Flock):
    """Execute a Flock instance.

    Args:
        flock: The Flock instance to execute
    """
    if not flock:
        console.print("[bold red]Error: No Flock instance provided.[/]")
        return

    agent_names = list(flock._agents.keys())

    if not agent_names:
        console.print("[yellow]No agents in this Flock to execute.[/]")
        return

    init_console()
    console.print(Panel("[bold green]Execute Flock[/]"), justify="center")

    # Step 1: Select start agent
    console.print("\n[bold]Step 1: Select Start Agent[/]")

    start_agent_name = questionary.select(
        "Select an agent to start with:",
        choices=agent_names,
    ).ask()

    if not start_agent_name:
        return

    start_agent = flock._agents[start_agent_name]

    # Step 2: Configure input
    console.print("\n[bold]Step 2: Configure Input[/]")

    # Parse input schema
    input_fields = _parse_input_schema(start_agent.input)

    # If we couldn't parse any fields, ask for generic input
    if not input_fields:
        raw_input = questionary.text(
            "Enter input (JSON format):",
            default="{}",
        ).ask()

        try:
            input_data = json.loads(raw_input)
        except json.JSONDecodeError:
            console.print("[bold red]Error: Invalid JSON input.[/]")
            return
    else:
        # Otherwise, ask for each field
        input_data = {}

        for field, info in input_fields.items():
            field_type = info.get("type", "str")
            description = info.get("description", "")
            prompt = f"Enter value for '{field}'"

            if description:
                prompt += f" ({description})"

            prompt += ":"

            value = questionary.text(prompt).ask()

            # Convert value to appropriate type
            if field_type == "int":
                try:
                    value = int(value)
                except ValueError:
                    console.print(
                        f"[yellow]Warning: Could not convert value to int, using as string.[/]"
                    )

            input_data[field] = value

    # Step 3: Run Options
    console.print("\n[bold]Step 3: Run Options[/]")

    # Logging options
    enable_logging = questionary.confirm(
        "Enable detailed logging?",
        default=False,
    ).ask()

    # Preview input
    console.print("\n[bold]Input Preview:[/]")
    console.print(json.dumps(input_data, indent=2))

    # Confirm execution
    confirm = questionary.confirm(
        "Execute Flock with this configuration?",
        default=True,
    ).ask()

    if not confirm:
        return

    # Execute the Flock
    console.print("\n[bold]Executing Flock...[/]")

    try:
        # Handle logging settings
        if enable_logging:
            # Enable logging through the logging configuration method
            flock._configure_logging(True)

        # Run the Flock
        result = flock.run(
            start_agent=start_agent_name,
            input=input_data,
        )

        # Display result
        console.print("\n[bold green]Execution Complete![/]")

        if result and enable_logging:
            console.print("\n[bold]Result:[/]")
            if isinstance(result, dict):
                # Display as formatted JSON
                console.print(json.dumps(result, indent=2))
            else:
                # Display as plain text
                console.print(str(result))

    except Exception as e:
        console.print(f"\n[bold red]Error during execution:[/] {e!s}")


def _parse_input_schema(input_schema: str) -> dict[str, dict[str, str]]:
    """Parse the input schema string into a field dictionary.

    Args:
        input_schema: The input schema string (e.g., "query: str | The search query")

    Returns:
        A dictionary mapping field names to field info (type, description)
    """
    if not input_schema:
        return {}

    fields = {}

    try:
        # Split by comma for multiple fields
        for field_def in input_schema.split(","):
            field_def = field_def.strip()

            # Check for type hint with colon
            if ":" in field_def:
                field_name, rest = field_def.split(":", 1)
                field_name = field_name.strip()
                rest = rest.strip()

                # Check for description with pipe
                if "|" in rest:
                    field_type, description = rest.split("|", 1)
                    fields[field_name] = {
                        "type": field_type.strip(),
                        "description": description.strip(),
                    }
                else:
                    fields[field_name] = {"type": rest.strip()}
            else:
                # Just a field name without type hint
                if "|" in field_def:
                    field_name, description = field_def.split("|", 1)
                    fields[field_name.strip()] = {
                        "description": description.strip()
                    }
                else:
                    fields[field_def.strip()] = {}

    except Exception as e:
        console.print(
            f"[yellow]Warning: Could not parse input schema: {e!s}[/]"
        )
        return {}

    return fields
