"""YAML Editor for Flock CLI.

This module provides functionality to view, edit, and validate YAML configurations
for Flock and FlockAgent instances.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import questionary
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.util.cli_helper import init_console

# Create console instance
console = Console()


def yaml_editor(flock_or_agent: Flock | FlockAgent | None = None):
    """YAML Editor main entry point.

    Args:
        flock_or_agent: Optional Flock or FlockAgent instance to edit
    """
    init_console()
    console.print(Panel("[bold green]YAML Editor[/]"), justify="center")

    if flock_or_agent is None:
        # If no object provided, provide options to load from file
        _yaml_file_browser()
        return

    while True:
        init_console()
        console.print(Panel("[bold green]YAML Editor[/]"), justify="center")

        # Determine object type
        if isinstance(flock_or_agent, Flock):
            obj_type = "Flock"
            console.print(
                f"Editing [bold cyan]Flock[/] with {len(flock_or_agent._agents)} agents"
            )
        elif isinstance(flock_or_agent, FlockAgent):
            obj_type = "FlockAgent"
            console.print(
                f"Editing [bold cyan]FlockAgent[/]: {flock_or_agent.name}"
            )
        else:
            console.print("[bold red]Error: Unknown object type[/]")
            input("\nPress Enter to continue...")
            return

        console.line()

        choice = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Separator(line=" "),
                "View Current YAML",
                "Edit YAML Directly",
                "Abstract Editor (Visual)",
                "Validate YAML",
                "Save to File",
                questionary.Separator(),
                "Back to Main Menu",
            ],
        ).ask()

        if choice == "View Current YAML":
            _view_yaml(flock_or_agent)
        elif choice == "Edit YAML Directly":
            flock_or_agent = _edit_yaml_directly(flock_or_agent)
        elif choice == "Abstract Editor (Visual)":
            flock_or_agent = _abstract_editor(flock_or_agent)
        elif choice == "Validate YAML":
            _validate_yaml(flock_or_agent)
        elif choice == "Save to File":
            _save_to_file(flock_or_agent)
        elif choice == "Back to Main Menu":
            break

        if choice != "Back to Main Menu":
            input("\nPress Enter to continue...")


def _yaml_file_browser():
    """Browser for YAML files to load."""
    console.print("\n[bold]YAML File Browser[/]")
    console.line()

    current_dir = os.getcwd()
    console.print(f"Current directory: [cyan]{current_dir}[/]")

    # List .yaml/.yml files in current directory
    yaml_files = list(Path(current_dir).glob("*.yaml")) + list(
        Path(current_dir).glob("*.yml")
    )

    if not yaml_files:
        console.print("[yellow]No YAML files found in current directory.[/]")
        input("\nPress Enter to continue...")
        return

    # Display files
    table = Table(title="YAML Files")
    table.add_column("Filename", style="cyan")
    table.add_column("Size", style="green")
    table.add_column("Last Modified", style="yellow")

    for file in yaml_files:
        table.add_row(
            file.name, f"{file.stat().st_size} bytes", f"{file.stat().st_mtime}"
        )

    console.print(table)

    # TODO: Add file selection and loading


def _view_yaml(obj: Flock | FlockAgent):
    """View the YAML representation of an object.

    Args:
        obj: The object to view as YAML
    """
    yaml_str = obj.to_yaml()

    # Add file path information header if it's a Flock with component file paths
    if isinstance(obj, Flock) and hasattr(obj, "_component_file_paths"):
        has_file_paths = bool(getattr(obj, "_component_file_paths", {}))
        if has_file_paths:
            console.print(
                "[bold yellow]Note: This Flock contains components with file paths[/]"
            )

    # Display with syntax highlighting
    syntax = Syntax(
        yaml_str,
        "yaml",
        theme="monokai",
        line_numbers=True,
        code_width=100,
        word_wrap=True,
    )

    init_console()
    console.print(Panel("[bold green]YAML View[/]"), justify="center")
    console.print(syntax)

    # Show file path information if available
    if isinstance(obj, Flock):
        # Get registry for checking file paths
        try:
            from flock.core.flock_registry import get_registry

            registry = get_registry()

            if (
                hasattr(registry, "_component_file_paths")
                and registry._component_file_paths
            ):
                # Get component names in this Flock
                components = set()
                for agent in obj._agents.values():
                    if hasattr(agent, "module") and agent.module:
                        module_path = getattr(agent.module, "module_path", None)
                        if module_path:
                            components.add(module_path)

                # Show file paths for components in this Flock
                file_paths = []
                for component_name in components:
                    if component_name in registry._component_file_paths:
                        file_paths.append(
                            (
                                component_name,
                                registry._component_file_paths[component_name],
                            )
                        )

                if file_paths:
                    console.print("\n[bold cyan]Component File Paths:[/]")
                    table = Table()
                    table.add_column("Component", style="green")
                    table.add_column("File Path", style="yellow")

                    for component_name, file_path in file_paths:
                        table.add_row(component_name, file_path)

                    console.print(table)
        except ImportError:
            pass  # Skip if registry is not available


def _edit_yaml_directly(obj: Flock | FlockAgent) -> Flock | FlockAgent:
    """Edit the YAML representation directly using an external editor.

    Args:
        obj: The object to edit

    Returns:
        The updated object
    """
    # Convert to YAML
    yaml_str = obj.to_yaml()

    # Get file path information if it's a Flock
    component_file_paths = {}
    if isinstance(obj, Flock):
        try:
            from flock.core.flock_registry import get_registry

            registry = get_registry()

            if hasattr(registry, "_component_file_paths"):
                # Save the file paths to restore later
                component_file_paths = registry._component_file_paths.copy()
        except ImportError:
            pass

    # Create a temporary file
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w+", delete=False
    ) as tmp:
        tmp.write(yaml_str)
        tmp_path = tmp.name

    try:
        # Determine which editor to use
        editor = os.environ.get(
            "EDITOR", "notepad" if os.name == "nt" else "nano"
        )

        # Open the editor
        console.print(
            f"\nOpening {editor} to edit YAML. Save and exit when done."
        )
        subprocess.call([editor, tmp_path])

        # Read updated YAML
        with open(tmp_path) as f:
            updated_yaml = f.read()

        # Parse back to object
        try:
            if isinstance(obj, Flock):
                updated_obj = Flock.from_yaml(updated_yaml)

                # Restore file path information
                if component_file_paths:
                    from flock.core.flock_registry import get_registry

                    registry = get_registry()

                    if not hasattr(registry, "_component_file_paths"):
                        registry._component_file_paths = {}

                    # Merge the updated registry with the saved file paths
                    for (
                        component_name,
                        file_path,
                    ) in component_file_paths.items():
                        if component_name in registry._components:
                            registry._component_file_paths[component_name] = (
                                file_path
                            )

                console.print("\n[green]✓[/] YAML parsed successfully!")
                return updated_obj
            elif isinstance(obj, FlockAgent):
                updated_obj = FlockAgent.from_yaml(updated_yaml)
                console.print("\n[green]✓[/] YAML parsed successfully!")
                return updated_obj
        except Exception as e:
            console.print(f"\n[bold red]Error parsing YAML:[/] {e!s}")
            console.print("\nKeeping original object.")
            return obj

    finally:
        # Clean up the temporary file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return obj


def _abstract_editor(obj: Flock | FlockAgent) -> Flock | FlockAgent:
    """Edit object using an abstract form-based editor.

    Args:
        obj: The object to edit

    Returns:
        The updated object
    """
    console.print("\n[yellow]Abstract visual editor not yet implemented.[/]")
    console.print("Will provide a form-based editor for each field.")

    # For now, just return the original object
    return obj


def _validate_yaml(obj: Flock | FlockAgent):
    """Validate the YAML representation of an object.

    Args:
        obj: The object to validate
    """
    try:
        yaml_str = obj.to_yaml()

        # Attempt to parse with PyYAML
        yaml.safe_load(yaml_str)

        # Attempt to deserialize back to object
        if isinstance(obj, Flock):
            Flock.from_yaml(yaml_str)
        elif isinstance(obj, FlockAgent):
            FlockAgent.from_yaml(yaml_str)

        console.print("\n[green]✓[/] YAML validation successful!")
    except Exception as e:
        console.print(f"\n[bold red]YAML validation failed:[/] {e!s}")


def _save_to_file(obj: Flock | FlockAgent):
    """Save object to a YAML file.

    Args:
        obj: The object to save
    """
    # Determine default filename based on object type
    if isinstance(obj, Flock):
        default_name = "my_flock.flock.yaml"
    elif isinstance(obj, FlockAgent):
        default_name = f"{obj.name}.agent.yaml"
    else:
        default_name = "unknown.yaml"

    # Get file path
    file_path = questionary.text(
        "Enter file path to save YAML:",
        default=default_name,
    ).ask()

    # Ensure the file has the correct extension
    if not file_path.endswith((".yaml", ".yml")):
        file_path += ".yaml"

    # Create directory if it doesn't exist
    save_path = Path(file_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # For Flock instances, ask about path_type
    path_type = "absolute"  # Default
    if isinstance(obj, Flock):
        path_type_choice = questionary.select(
            "How should file paths be formatted?",
            choices=[
                "absolute (full paths, best for local use)",
                "relative (relative paths, better for sharing)",
            ],
            default="absolute (full paths, best for local use)",
        ).ask()

        # Extract just the first word
        path_type = path_type_choice.split()[0]

        console.print(
            f"[bold]Path type selected: [green]{path_type}[/green][/bold]"
        )

    try:
        # Save to file with path_type for Flock instances
        if isinstance(obj, Flock):
            obj.to_yaml_file(file_path, path_type=path_type)
            console.print(
                f"\n[green]✓[/] Saved to {file_path} with {path_type} paths"
            )
        else:
            # For FlockAgent or other types, use the original method
            with open(file_path, "w") as f:
                f.write(obj.to_yaml())
            console.print(f"\n[green]✓[/] Saved to {file_path}")
    except Exception as e:
        console.print(f"\n[bold red]Error saving file:[/] {e!s}")
