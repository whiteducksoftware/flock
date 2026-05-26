"""Load a Flock from a file."""

from pathlib import Path

import questionary
from rich.console import Console
from rich.markdown import Markdown

from flock.cli.loaded_flock_cli import start_loaded_flock_cli
from flock.core.flock import Flock
from flock.core.logging.logging import get_logger

logger = get_logger("cli.load_flock")


def filter(file_path) -> bool:
    """Filter function for file selection."""
    path = Path(file_path)
    if path.is_dir():
        return True
    return path.is_file() and (
        path.suffix == ".flock"
        or path.suffix == ".yaml"
        or path.suffix == ".yml"
    )


def load_flock():
    """Load a Flock from a file."""
    console = Console()

    console.print(
        "\nPlease select a *.flock, *.yaml, or *.yml file\n", style="bold green"
    )

    result = questionary.path("", file_filter=filter).ask()

    if not result:
        return

    selected_file = Path(result)
    if selected_file.is_file():
        console.print(f"Selected file: {selected_file}", style="bold green")

        try:
            # Try loading with detailed error handling
            try:
                logger.info(f"Attempting to load Flock from: {result}")
                flock = Flock.load_from_file(result)
            except ImportError as e:
                # Handle missing module path errors
                if "No module named" in str(e):
                    console.print(
                        f"[yellow]Warning: Module import failed: {e}[/]"
                    )
                    console.print(
                        "[yellow]Trying file path fallback mechanism...[/]"
                    )
                    # Re-try loading with fallback
                    flock = Flock.load_from_file(result)
                else:
                    raise  # Re-raise if it's not a missing module error
            except KeyError as e:
                # This could be caused by missing tool references
                if "__callable_ref__" in str(e):
                    console.print(
                        f"[yellow]Warning: Tool reference error: {e}[/]"
                    )
                    console.print(
                        "[yellow]This may be due to missing tool registrations. Attempting to scan for tools...[/]"
                    )
                    # Scan for tools and retry
                    from flock.cli.registry_management import (
                        auto_registration_scanner,
                    )

                    auto_registration_scanner()
                    # Try loading again
                    flock = Flock.load_from_file(result)
                else:
                    raise  # Re-raise if it's not a tool reference error

            console.line()
            console.print(
                Markdown("# Flock loaded successfully"), style="bold green"
            )
            console.line()

            # Instead of just running the Flock, start our enhanced CLI
            start_loaded_flock_cli(
                flock, server_name=f"Flock - {selected_file.name}"
            )

        except Exception as e:
            console.print(f"Error loading Flock: {e!s}", style="bold red")
            logger.error(f"Failed to load Flock: {e}", exc_info=True)

            # Add more detailed error information for specific errors
            if "No module named" in str(e):
                console.print(
                    "\n[yellow]This error might be due to missing module paths.[/]"
                )
                console.print(
                    "[yellow]Component references may need to be updated with file paths.[/]"
                )

                # Show the option to scan the directory for components
                fix_paths = questionary.confirm(
                    "Would you like to scan directories for components to fix missing imports?",
                    default=True,
                ).ask()

                if fix_paths:
                    from flock.cli.registry_management import (
                        auto_registration_scanner,
                    )

                    auto_registration_scanner()

                    # Try loading again
                    console.print(
                        "\n[yellow]Attempting to load Flock again...[/]"
                    )
                    try:
                        flock = Flock.load_from_file(result)
                        console.line()
                        console.print(
                            Markdown(
                                "# Flock loaded successfully after component scan"
                            ),
                            style="bold green",
                        )
                        console.line()

                        start_loaded_flock_cli(
                            flock, server_name=f"Flock - {selected_file.name}"
                        )
                        return
                    except Exception as e2:
                        console.print(
                            f"Error loading Flock after scan: {e2!s}",
                            style="bold red",
                        )

            # Handle tool reference issues
            elif "__callable_ref__" in str(e) or "callable" in str(e).lower():
                console.print(
                    "\n[yellow]This error might be due to missing tool registrations.[/]"
                )

                # Show the option to scan the directory for tools
                fix_tools = questionary.confirm(
                    "Would you like to scan directories for tools to fix missing references?",
                    default=True,
                ).ask()

                if fix_tools:
                    from flock.cli.registry_management import (
                        auto_registration_scanner,
                    )

                    console.print(
                        "\n[yellow]Scanning for tools and callables...[/]"
                    )
                    auto_registration_scanner()

                    # Try loading again
                    console.print(
                        "\n[yellow]Attempting to load Flock again...[/]"
                    )
                    try:
                        flock = Flock.load_from_file(result)
                        console.line()
                        console.print(
                            Markdown(
                                "# Flock loaded successfully after tool scan"
                            ),
                            style="bold green",
                        )
                        console.line()

                        start_loaded_flock_cli(
                            flock, server_name=f"Flock - {selected_file.name}"
                        )
                        return
                    except Exception as e2:
                        console.print(
                            f"Error loading Flock after tool scan: {e2!s}",
                            style="bold red",
                        )

            input("\nPress Enter to continue...")
