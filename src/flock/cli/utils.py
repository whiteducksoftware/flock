# src/pilot_rules/collector/utils.py
import datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Create a shared console instance for consistent styling
console = Console()


def get_file_metadata(file_path: str) -> dict[str, Any]:
    """Extract metadata from a file."""
    metadata = {
        "path": file_path,
        "size_bytes": 0,
        "line_count": 0,
        "last_modified": "Unknown",
        "created": "Unknown",
    }

    try:
        p = Path(file_path)
        stats = p.stat()
        metadata["size_bytes"] = stats.st_size
        metadata["last_modified"] = datetime.datetime.fromtimestamp(
            stats.st_mtime
        ).strftime("%Y-%m-%d %H:%M:%S")
        # ctime is platform dependent (creation on Windows, metadata change on Unix)
        # Use mtime as a reliable fallback for "created" if ctime is older than mtime
        ctime = stats.st_ctime
        mtime = stats.st_mtime
        best_ctime = ctime if ctime <= mtime else mtime  # Heuristic
        metadata["created"] = datetime.datetime.fromtimestamp(
            best_ctime
        ).strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Attempt to read as text, fallback for binary or encoding issues
            with p.open("r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                metadata["line_count"] = len(content.splitlines())
        except (OSError, UnicodeDecodeError) as read_err:
            # Handle cases where reading might fail (binary file, permissions etc.)
            console.print(
                f"[yellow]⚠ Warning:[/yellow] Could not read content/count lines for [cyan]{file_path}[/cyan]: [red]{read_err}[/red]"
            )
            metadata["line_count"] = 0  # Indicate unreadable or binary

    except Exception as e:
        console.print(
            f"[yellow]⚠ Warning:[/yellow] Could not get complete metadata for [cyan]{file_path}[/cyan]: [red]{e}[/red]"
        )

    return metadata


# --- Rich Formatting Utilities ---


def print_header(title: str, style: str = "blue") -> None:
    """Print a styled header with a panel."""
    console.rule()
    console.print(
        Panel.fit(f"[bold {style}]{title}[/bold {style}]", border_style=style)
    )


def print_subheader(title: str, style: str = "cyan") -> None:
    """Print a styled subheader."""
    console.print(f"[bold {style}]== {title} ==[/bold {style}]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str, exit_code: int | None = None) -> None:
    """Print an error message and optionally exit."""
    console.print(f"[bold red]✗ ERROR:[/bold red] {message}")
    if exit_code is not None:
        exit(exit_code)


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠ Warning:[/yellow] {message}")


def create_progress() -> Progress:
    """Create a standardized progress bar."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(complete_style="green", finished_style="green"),
        TextColumn("[bold]{task.completed}/{task.total}"),
        console=console,
    )


def create_task_table(title: str) -> Table:
    """Create a standardized table for displaying task information."""
    table = Table(
        title=title, show_header=True, header_style="bold cyan", box=box.ROUNDED
    )
    return table


def print_file_stats(files: list[str], title: str = "File Statistics") -> None:
    """Print statistics about a list of files."""
    if not files:
        console.print("[yellow]No files found to display statistics.[/yellow]")
        return

    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Statistic", style="cyan")
    table.add_column("Value", style="green")

    extensions = {Path(f).suffix.lower() for f in files if Path(f).suffix}
    total_size = sum(get_file_metadata(f).get("size_bytes", 0) for f in files)
    total_lines = sum(get_file_metadata(f).get("line_count", 0) for f in files)

    table.add_row("Total Files", str(len(files)))
    table.add_row("Total Size", f"{total_size / 1024:.2f} KB")
    table.add_row("Total Lines", str(total_lines))
    table.add_row(
        "Extensions", ", ".join(sorted(extensions)) if extensions else "None"
    )

    console.print(table)
