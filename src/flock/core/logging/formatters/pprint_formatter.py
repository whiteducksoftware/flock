from typing import Any

from flock.core.logging.formatters.base_formatter import BaseFormatter


class PrettyPrintFormatter(BaseFormatter):
    def display_result(
        self, result: dict[str, Any], agent_name: str, **kwargs
    ) -> None:
        """Print an agent's result using Rich formatting."""
        from devtools import pformat
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        s = pformat(result, highlight=False)

        console.print(Panel(s, title=agent_name, highlight=True))

    def display_data(self, data: dict[str, Any], **kwargs) -> None:
        """Print an agent's result using Rich formatting."""
        from devtools import sprint

        sprint(data, sprint.green)
