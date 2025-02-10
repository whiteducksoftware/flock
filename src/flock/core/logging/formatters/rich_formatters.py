from typing import Any

from devtools import pprint
from temporalio import workflow

from flock.core.logging.formatters.base_formatter import BaseFormatter

with workflow.unsafe.imports_passed_through():
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.pretty import Pretty
    from rich.table import Table


def create_rich_renderable(
    value: Any,
    level: int = 0,
    max_length: int = -1,
) -> Any:
    """Recursively creates a Rich renderable for a given value.

    - If the value is a dict, return a Table representing the dict.
    - If the value is a list or tuple:
        - If all items are dicts, return a Group of subtables.
        - Otherwise, render each item recursively and either join them as text
          (if all rendered items are strings) or return a Group.
    - Otherwise, return a string (with extra newlines if it's a multi-line string).
    """
    if isinstance(value, dict):
        # Create a subtable for the dictionary.
        # You can tweak the table styles or add a title that indicates the level.
        table = Table(
            show_header=True,
            header_style="bold green",
            title=f"Subtable (Level {level})" if level > 0 else None,
            title_style="bold blue",
            border_style="bright_blue",
            show_lines=True,
        )
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        for k, v in value.items():
            table.add_row(
                str(k),
                create_rich_renderable(v, level + 1, max_length=max_length),
            )
        return table

    elif isinstance(value, list | tuple):
        # If all items are dicts, build a Group of subtables with an index.
        if all(isinstance(item, dict) for item in value):
            sub_tables = []
            for i, item in enumerate(value):
                sub_tables.append(f"[bold]Item {i + 1}[/bold]")
                sub_tables.append(
                    create_rich_renderable(
                        item, level + 1, max_length=max_length
                    )
                )
            return Group(*sub_tables)
        else:
            # For a mixed list, render each item recursively.
            rendered_items = [
                create_rich_renderable(item, level + 1, max_length=max_length)
                for item in value
            ]
            # If all items ended up as strings, join them.
            if all(isinstance(item, str) for item in rendered_items):
                return "\n".join(rendered_items)
            else:
                return Group(*rendered_items)

    else:
        if isinstance(value, str):
            if max_length > 0 and len(value) > max_length:
                omitted = len(value) - max_length
                value = (
                    value[:max_length]
                    + f"[bold bright_yellow]...(+{omitted}chars)[/bold bright_yellow]"
                )
            return f"\n{value}\n"
        else:
            pretty = Pretty(value, max_length=max_length, expand_all=True)
            return pretty


class RichTables(BaseFormatter):
    """Formats agent results in a beautiful Rich table with nested subtables."""

    def __init__(self, max_length: int = -1):
        self.max_length = max_length

    def format_result(self, result: dict[str, Any], agent_name: str) -> Panel:
        """Format an agent's result as a Rich panel containing a table."""
        # Create the main table.
        table = Table(
            show_lines=True,
            show_header=True,
            header_style="bold green",
            title=f"Agent Results: {agent_name}",
            title_style="bold blue",
            border_style="bright_blue",
        )
        table.add_column("Output", style="cyan")
        table.add_column("Value", style="green")

        # For each key/value pair, use the recursive renderable.
        for key, value in result.items():
            rich_renderable = create_rich_renderable(
                value, level=0, max_length=self.max_length
            )
            table.add_row(key, rich_renderable)

        # Wrap the table in a panel.
        return Panel(
            table,
            title="🐤🐧🐓🦆",
            title_align="left",
            border_style="blue",
            padding=(1, 2),
        )

    def display_result(
        self, result: dict[str, Any], agent_name: str, **kwargs
    ) -> None:
        """Print an agent's result using Rich formatting."""
        console = Console()
        panel = self.format_result(result=result, agent_name=agent_name)
        # pprint(result)  # Optional: Print the raw result with pprint.
        console.print(panel)

    def display_data(self, data: dict[str, Any], **kwargs) -> None:
        """Print an agent's result using Rich formatting."""
        pprint(data)
