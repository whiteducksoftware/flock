"""Registry Management Module for the Flock CLI."""

import datetime
import importlib
import inspect
import os
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from flock.core.flock_registry import (
    get_registry,
)
from flock.core.logging.logging import get_logger

logger = get_logger("registry_cli")
console = Console()

# Constants for registry item types
REGISTRY_CATEGORIES = ["Agent", "Callable", "Type", "Component"]
REGISTRY_ACTIONS = [
    "View Registry Contents",
    "Add Item to Registry",
    "Remove Item from Registry",
    "Auto-Registration Scanner",
    "Export Registry",
    "Back to Main Menu",
]


def manage_registry() -> None:
    """Main function for managing the Flock Registry from the CLI."""
    while True:
        console.clear()
        console.print(
            Panel("[bold blue]Flock Registry Management[/]"), justify="center"
        )
        console.line()

        # Show registry stats
        display_registry_stats()

        action = questionary.select(
            "What would you like to do?",
            choices=REGISTRY_ACTIONS,
        ).ask()

        if action == "View Registry Contents":
            view_registry_contents()
        elif action == "Add Item to Registry":
            add_item_to_registry()
        elif action == "Remove Item from Registry":
            remove_item_from_registry()
        elif action == "Auto-Registration Scanner":
            auto_registration_scanner()
        elif action == "Export Registry":
            export_registry()
        elif action == "Back to Main Menu":
            break

        input("\nPress Enter to continue...")


def display_registry_stats() -> None:
    """Display statistics about the current registry contents."""
    registry = get_registry()

    table = Table(title="Registry Statistics")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="green")

    table.add_row("Agents", str(len(registry._agents)))
    table.add_row("Callables", str(len(registry._callables)))
    table.add_row("Types", str(len(registry._types)))
    table.add_row("Components", str(len(registry._components)))

    console.print(table)


def view_registry_contents(
    category: str | None = None, search_pattern: str | None = None
) -> None:
    """Display registry contents with filtering options."""
    registry = get_registry()

    if category is None:
        category = questionary.select(
            "Select a category to view:",
            choices=REGISTRY_CATEGORIES + ["All Categories"],
        ).ask()

    if search_pattern is None:
        search_pattern = questionary.text(
            "Enter search pattern (leave empty to show all):"
        ).ask()

    console.clear()

    if category == "All Categories" or category == "Agent":
        display_registry_section("Agents", registry._agents, search_pattern)

    if category == "All Categories" or category == "Callable":
        display_registry_section(
            "Callables", registry._callables, search_pattern
        )

    if category == "All Categories" or category == "Type":
        display_registry_section("Types", registry._types, search_pattern)

    if category == "All Categories" or category == "Component":
        display_registry_section(
            "Components", registry._components, search_pattern
        )


def display_registry_section(
    title: str, items: dict[str, Any], search_pattern: str
) -> None:
    """Display a section of registry items in a table."""
    filtered_items = {
        k: v
        for k, v in items.items()
        if not search_pattern or search_pattern.lower() in k.lower()
    }

    if not filtered_items:
        console.print(
            f"[yellow]No {title.lower()} found matching the search pattern.[/]"
        )
        return

    table = Table(title=f"Registered {title}")
    table.add_column("Name/Path", style="cyan")
    table.add_column("Type", style="green")

    # Add file path column for components
    if title == "Components":
        table.add_column("File Path", style="yellow")

    for name, item in filtered_items.items():
        item_type = type(item).__name__

        if title == "Components":
            # Try to get the file path for component classes
            file_path = (
                inspect.getfile(item) if inspect.isclass(item) else "N/A"
            )
            table.add_row(name, item_type, file_path)
        else:
            table.add_row(name, item_type)

    console.print(table)
    console.print(f"Total: {len(filtered_items)} {title.lower()}")


def add_item_to_registry() -> None:
    """Add an item to the registry manually."""
    registry = get_registry()

    item_type = questionary.select(
        "What type of item do you want to add?",
        choices=["agent", "callable", "type", "component"],
    ).ask()

    # For component types, offer file path option
    use_file_path = False
    if item_type == "component":
        path_type = questionary.select(
            "How do you want to specify the component?",
            choices=["Module Path", "File Path"],
        ).ask()
        use_file_path = path_type == "File Path"

    if use_file_path:
        file_path = questionary.path(
            "Enter the file path to the component:", only_directories=False
        ).ask()

        if not file_path or not os.path.exists(file_path):
            console.print(f"[red]Error: File {file_path} does not exist[/]")
            return False

        module_name = questionary.text(
            "Enter the component class name in the file:"
        ).ask()

        try:
            # Use dynamic import to load the module from file path
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "temp_module", file_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, module_name):
                console.print(
                    f"[red]Error: {module_name} not found in {file_path}[/]"
                )
                return False

            item = getattr(module, module_name)
        except Exception as e:
            console.print(f"[red]Error importing from file: {e!s}[/]")
            return False
    else:
        module_path = questionary.text(
            "Enter the module path (e.g., 'your_module.submodule'):"
        ).ask()

        item_name = questionary.text(
            "Enter the item name within the module:"
        ).ask()

        try:
            # Attempt to import the module
            module = importlib.import_module(module_path)

            # Get the item from the module
            if not hasattr(module, item_name):
                console.print(
                    f"[red]Error: {item_name} not found in {module_path}[/]"
                )
                return False

            item = getattr(module, item_name)
        except Exception as e:
            console.print(f"[red]Error importing module: {e!s}[/]")
            return False

    alias = questionary.text(
        "Enter an alias (optional, press Enter to skip):"
    ).ask()

    if not alias:
        alias = None

    # Register the item based on its type
    try:
        if item_type == "agent":
            registry.register_agent(item)
            console.print(
                f"[green]Successfully registered agent: {item_name}[/]"
            )
        elif item_type == "callable":
            result = registry.register_callable(item, alias)
            console.print(
                f"[green]Successfully registered callable: {result}[/]"
            )
        elif item_type == "type":
            result = registry.register_type(item, alias)
            console.print(f"[green]Successfully registered type: {result}[/]")
        elif item_type == "component":
            result = registry.register_component(item, alias)
            # Store the file path information if we loaded from a file
            if use_file_path and hasattr(registry, "_component_file_paths"):
                # Check if the registry has component file paths attribute
                # This will be added to registry in our update
                registry._component_file_paths[result] = file_path
            console.print(
                f"[green]Successfully registered component: {result}[/]"
            )
    except Exception as e:
        console.print(f"[red]Error registering item: {e!s}[/]")
        return False

    return True


def remove_item_from_registry() -> None:
    """Remove an item from the registry."""
    registry = get_registry()

    item_type = questionary.select(
        "What type of item do you want to remove?",
        choices=["agent", "callable", "type", "component"],
    ).ask()

    # Get the appropriate dictionary based on item type
    if item_type == "agent":
        items = registry._agents
    elif item_type == "callable":
        items = registry._callables
    elif item_type == "type":
        items = registry._types
    elif item_type == "component":
        items = registry._components

    if not items:
        console.print(f"[yellow]No {item_type}s registered.[/]")
        return False

    # Create a list of items for selection
    item_names = list(items.keys())
    item_name = questionary.select(
        f"Select the {item_type} to remove:",
        choices=item_names + ["Cancel"],
    ).ask()

    if item_name == "Cancel":
        return False

    # Ask for confirmation
    confirm = questionary.confirm(
        f"Are you sure you want to remove {item_name}?",
        default=False,
    ).ask()

    if not confirm:
        console.print("[yellow]Operation cancelled.[/]")
        return False

    # Remove the item
    try:
        if item_type == "agent":
            del registry._agents[item_name]
        elif item_type == "callable":
            del registry._callables[item_name]
        elif item_type == "type":
            del registry._types[item_name]
        elif item_type == "component":
            del registry._components[item_name]

        console.print(
            f"[green]Successfully removed {item_type}: {item_name}[/]"
        )
        return True

    except Exception as e:
        console.print(f"[red]Error: {e!s}[/]")
        return False


def auto_registration_scanner() -> None:
    """Launch the auto-registration scanner interface."""
    console.clear()
    console.print(
        Panel("[bold blue]Auto-Registration Scanner[/]"), justify="center"
    )
    console.line()

    console.print(
        "This utility will scan Python files for components, types, callables (tools), and agents that can be registered."
    )
    console.print(
        "[yellow]Note: Registration is required for proper serialization and deserialization of your Flock.[/]"
    )
    console.line()

    # Target directory selection
    def path_filter(path):
        """Filter paths for selection."""
        if os.path.isdir(path):
            return True
        return path.endswith(".py")

    target_path = questionary.path(
        "Select directory to scan:", file_filter=path_filter
    ).ask()

    if not target_path or not os.path.exists(target_path):
        console.print("[red]Invalid path selected. Aborting.[/]")
        return

    is_recursive = questionary.confirm(
        "Scan recursively (include subdirectories)?", default=True
    ).ask()

    auto_register = questionary.confirm(
        "Automatically register items found during scan?", default=True
    ).ask()

    # Special callout for tools/callables
    console.print(
        "[bold blue]Tool Registration:[/] This scanner will look for functions that can be used as tools."
    )
    console.print(
        "These will be registered as callables and can be properly serialized in your Flock YAML."
    )
    console.line()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[bold green]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task_id = progress.add_task(
            "Scanning for registry items...", total=None
        )

        # Perform the scan
        results = scan_for_registry_items(
            target_path, recursive=is_recursive, auto_register=auto_register
        )

        # Mark task as complete
        progress.update(task_id, completed=1, total=1)
        console.line()

    # Display results
    console.print("[bold green]Scan Complete![/]")
    console.line()

    total_found = sum(len(items) for items in results.values())
    total_categories = sum(1 for items in results.values() if items)

    console.print(
        f"Found {total_found} items across {total_categories} categories."
    )

    # Enhanced report section
    table = Table(title="Scan Results")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Example Items", style="blue")

    for category, items in results.items():
        if items:
            examples = ", ".join(items[:3])
            if len(items) > 3:
                examples += ", ..."
            table.add_row(category, str(len(items)), examples)
        else:
            table.add_row(category, "0", "")

    console.print(table)
    console.line()

    # Callout for tools and future serialization
    if results.get("callables"):
        console.print(
            "[bold green]Note:[/] Found callable functions that can be used as tools."
        )
        console.print(
            "These functions will now be properly serialized as callable references in your Flock YAML."
        )
        console.print(
            "When sharing Flocks, ensure these callables are registered on the target system."
        )
        console.line()

    # Show details options
    if total_found > 0:
        view_details = questionary.confirm(
            "Would you like to view detailed results?", default=True
        ).ask()

        if view_details:
            view_registry_contents()  # Show the registry contents after scan


def scan_for_registry_items(
    target_path: str, recursive: bool = True, auto_register: bool = False
) -> dict[str, list[str]]:
    """Scan directory for potential registry items and optionally register them."""
    results = {
        "Agents": [],
        "Callables": [],
        "Types": [],
        "Components": [],
        "Potential Items": [],
    }

    registry = get_registry()
    path = Path(target_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        scan_task = progress.add_task(f"Scanning {target_path}...", total=100)

        # If path is a file, scan it directly
        if path.is_file() and path.suffix == ".py":
            module_path = get_module_path_from_file(path)
            if module_path:
                scan_python_file(path, module_path, results, auto_register)
            progress.update(scan_task, completed=100)

        # If path is a directory, scan all Python files
        elif path.is_dir():
            python_files = []
            if recursive:
                for root, _, files in os.walk(path):
                    python_files.extend(
                        [
                            Path(os.path.join(root, f))
                            for f in files
                            if f.endswith(".py")
                        ]
                    )
            else:
                python_files = [p for p in path.glob("*.py")]

            total_files = len(python_files)
            for i, file_path in enumerate(python_files):
                module_path = get_module_path_from_file(file_path)
                if module_path:
                    scan_python_file(
                        file_path, module_path, results, auto_register
                    )
                progress.update(
                    scan_task, completed=(i + 1) / total_files * 100
                )

    return results


def get_module_path_from_file(file_path: Path) -> str | None:
    """Convert a file path to a module path for import."""
    try:
        # Get absolute path
        abs_path = file_path.resolve()

        # Check if it's a Python file
        if abs_path.suffix != ".py":
            return None

        # Get the directory containing the file
        file_dir = abs_path.parent

        # Find the nearest parent directory with __init__.py
        # to determine the package root
        package_root = None
        current_dir = file_dir
        while current_dir != current_dir.parent:
            if (current_dir / "__init__.py").exists():
                if package_root is None:
                    package_root = current_dir
            else:
                # We've reached a directory without __init__.py
                # If we found a package root earlier, use that
                if package_root is not None:
                    break
            current_dir = current_dir.parent

        # If no package root was found, this file can't be imported as a module
        if package_root is None:
            return None

        # Calculate the module path
        rel_path = abs_path.relative_to(package_root.parent)
        module_path = str(rel_path.with_suffix("")).replace(os.sep, ".")

        return module_path

    except Exception as e:
        logger.error(f"Error determining module path: {e}")
        return None


def scan_python_file(
    file_path: Path,
    module_path: str,
    results: dict[str, list[str]],
    auto_register: bool,
) -> None:
    """Scan a Python file for registry-eligible items."""
    try:
        # Try to import the module
        module = importlib.import_module(module_path)

        # Scan for classes and functions
        for name, obj in inspect.getmembers(module):
            if name.startswith("_"):
                continue

            # Check for registry decorator presence
            is_registry_item = False

            # Check for classes
            if inspect.isclass(obj):
                # Check if it has a FlockAgent as a base class
                if is_flock_agent(obj):
                    if auto_register:
                        get_registry().register_agent(obj)
                    results["Agents"].append(f"{module_path}.{name}")
                    is_registry_item = True

                # Check for components
                elif has_component_base(obj):
                    if auto_register:
                        get_registry().register_component(obj)
                    results["Components"].append(f"{module_path}.{name}")
                    is_registry_item = True

                # Check for Pydantic models or dataclasses
                elif is_potential_type(obj):
                    if auto_register:
                        get_registry().register_type(obj)
                    results["Types"].append(f"{module_path}.{name}")
                    is_registry_item = True

                # If not already identified but seems like a potential candidate
                elif not is_registry_item and is_potential_registry_candidate(
                    obj
                ):
                    results["Potential Items"].append(
                        f"{module_path}.{name} (class)"
                    )

            # Check for functions (potential callables/tools)
            elif inspect.isfunction(obj) and obj.__module__ == module.__name__:
                if auto_register:
                    get_registry().register_callable(obj)
                results["Callables"].append(f"{module_path}.{name}")
                is_registry_item = True

    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not import {module_path}: {e}")
    except Exception as e:
        logger.error(f"Error scanning {file_path}: {e}")


def is_flock_agent(cls: type) -> bool:
    """Check if a class is a FlockAgent or a subclass of FlockAgent."""
    try:
        from flock.core.flock_agent import FlockAgent

        return issubclass(cls, FlockAgent)
    except (ImportError, TypeError):
        # If FlockAgent can't be imported or cls is not a class
        return False


def has_component_base(cls: type) -> bool:
    """Check if a class has a base class that looks like a Flock component."""
    try:
        # Common Flock component base classes
        component_bases = ["FlockModule", "FlockEvaluator", "FlockRouter"]
        bases = [base.__name__ for base in cls.__mro__]
        return any(base in bases for base in component_bases)
    except (AttributeError, TypeError):
        return False


def is_potential_type(cls: type) -> bool:
    """Check if a class is a Pydantic model or dataclass."""
    try:
        from pydantic import BaseModel

        return issubclass(cls, BaseModel) or is_dataclass(cls)
    except (ImportError, TypeError):
        return False


def is_potential_registry_candidate(obj: Any) -> bool:
    """Check if an object seems like it could be registry-eligible."""
    # This is a heuristic function to identify potential registry candidates
    if inspect.isclass(obj):
        # Classes with "Flock" in their name
        if "Flock" in obj.__name__:
            return True

        # Classes with docstrings mentioning certain keywords
        if obj.__doc__ and any(
            kw in obj.__doc__.lower()
            for kw in [
                "agent",
                "flock",
                "tool",
                "module",
                "evaluator",
                "router",
            ]
        ):
            return True

    elif inspect.isfunction(obj):
        # Functions with docstrings mentioning certain keywords
        if obj.__doc__ and any(
            kw in obj.__doc__.lower() for kw in ["tool", "agent", "flock"]
        ):
            return True

    return False


def export_registry() -> None:
    """Export registry contents to a file."""
    registry = get_registry()

    # Select what to export
    export_items = questionary.checkbox(
        "Select what to export:",
        choices=[
            questionary.Choice("Agents", checked=True),
            questionary.Choice("Callables (Tools)", checked=True),
            questionary.Choice("Types", checked=True),
            questionary.Choice("Components", checked=True),
            questionary.Choice("File Paths", checked=True),
        ],
    ).ask()

    if not export_items:
        console.print("[yellow]No items selected for export.[/]")
        return

    # Select export format
    export_format = questionary.select(
        "Select export format:",
        choices=["YAML", "JSON", "Python"],
    ).ask()

    # Select path type for serialization
    path_type = questionary.select(
        "How should file paths be formatted?",
        choices=[
            "absolute (full paths, best for local use)",
            "relative (relative paths, better for sharing)",
        ],
        default="absolute (full paths, best for local use)",
    ).ask()

    # Extract just the first word
    path_type = path_type.split()[0]

    console.print(
        f"\n[bold]Path type selected: [green]{path_type}[/green][/bold]"
    )
    if path_type == "relative":
        console.print(
            "Relative paths are recommended when sharing Flocks between systems.\n"
            "They'll be converted to paths relative to the current directory."
        )
    else:
        console.print(
            "Absolute paths work best for local usage but may not work correctly\n"
            "when sharing with others or moving files."
        )
    console.line()

    # Get file path for export
    file_path = questionary.path(
        "Enter file path for export:",
        default=f"flock_registry_export.{export_format.lower()}",
    ).ask()

    if not file_path:
        return

    # Prepare export data
    export_data = {}

    if "Agents" in export_items:
        export_data["agents"] = list(registry._agents.keys())

    if "Callables (Tools)" in export_items:
        export_data["callables"] = list(registry._callables.keys())

        # Add serialization format information for tools
        callable_details = {}
        for callable_name in registry._callables.keys():
            callable_obj = registry._callables[callable_name]
            file_path_value = (
                inspect.getfile(callable_obj)
                if callable_obj and inspect.isfunction(callable_obj)
                else "Unknown"
            )

            # Convert to relative path if needed
            if path_type == "relative" and file_path_value != "Unknown":
                try:
                    file_path_value = os.path.relpath(file_path_value)
                except ValueError:
                    # Keep as absolute if can't make relative
                    pass

            callable_details[callable_name] = {
                "module": callable_obj.__module__,
                "file": file_path_value,
                "type": "function"
                if inspect.isfunction(callable_obj)
                else "other_callable",
            }
        export_data["callable_details"] = callable_details

    if "Types" in export_items:
        export_data["types"] = list(registry._types.keys())

    if "Components" in export_items:
        export_data["components"] = list(registry._components.keys())

        # Include file paths if selected
        if "File Paths" in export_items and hasattr(
            registry, "_component_file_paths"
        ):
            export_data["component_file_paths"] = {}
            for component_name in registry._components.keys():
                # Get the file path if available
                if component_name in registry._component_file_paths:
                    file_path_value = registry._component_file_paths[
                        component_name
                    ]

                    # Convert to relative path if needed
                    if path_type == "relative" and file_path_value:
                        try:
                            file_path_value = os.path.relpath(file_path_value)
                        except ValueError:
                            # Keep as absolute if can't make relative
                            pass

                    export_data["component_file_paths"][component_name] = (
                        file_path_value
                    )

    # Add metadata about serialization format
    export_data["metadata"] = {
        "export_date": datetime.datetime.now().isoformat(),
        "flock_version": "0.3.41",  # Update with actual version
        "serialization_format": {
            "tools": "Callable reference names",
            "components": "Module and class names",
            "types": "Module and class names",
        },
        "path_type": path_type,
    }

    # Add serialization settings as a top-level element
    export_data["serialization_settings"] = {"path_type": path_type}

    try:
        # Export the data
        if export_format == "YAML":
            import yaml

            with open(file_path, "w") as f:
                yaml.dump(export_data, f, default_flow_style=False)
        elif export_format == "JSON":
            import json

            with open(file_path, "w") as f:
                json.dump(export_data, f, indent=2)
        elif export_format == "Python":
            with open(file_path, "w") as f:
                f.write("# Flock Registry Export\n")
                f.write(f"# Generated on {datetime.datetime.now()}\n\n")
                f.write("registry_data = ")
                f.write(repr(export_data))
                f.write("\n")

        console.print(f"[green]Registry exported to {file_path}[/]")
        console.print(f"[green]Paths formatted as: {path_type}[/]")

        # Print information about tool serialization if tools were exported
        if "Callables (Tools)" in export_items and registry._callables:
            console.print("\n[bold blue]Tool Serialization Information:[/]")
            console.print(
                "Tools in Flock are now serialized as callable references rather than dictionaries."
            )
            console.print(
                "This makes YAML files more readable and simplifies tool management."
            )
            console.print("When loading a Flock with tools:")
            console.print("  1. Tools must be registered in the registry")
            console.print("  2. The tools' modules must be importable")
            console.print(
                "  3. Tool functions have the same signature across systems"
            )

            # Show example of how a tool would appear in YAML
            if registry._callables:
                console.print("\n[bold green]Example tool in YAML:[/]")
                example_callable = next(iter(registry._callables.keys()))
                console.print(
                    f"  - {example_callable}  # Function name reference"
                )
                console.print("instead of the old format:")
                console.print(f"  - __callable_ref__: {example_callable}")

    except Exception as e:
        console.print(f"[red]Error exporting registry: {e}[/]")
        logger.error(f"Failed to export registry: {e}", exc_info=True)


if __name__ == "__main__":
    manage_registry()
