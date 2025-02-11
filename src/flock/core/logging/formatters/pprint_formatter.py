import json
from typing import Any

from flock.core.logging.formatters.base_formatter import BaseFormatter


class PrettyPrintFormatter(BaseFormatter):
    def display_result(
        self, result: dict[str, Any], agent_name: str, **kwargs
    ) -> None:
        """Print an agent's result using Rich formatting."""
        from rich.console import Console
        from rich.json import JSON

        console = Console()

        console.print(agent_name)
        console.print(JSON(json.dumps(result)))

    def display_data(self, data: dict[str, Any], **kwargs) -> None:
        """Print an agent's result using Rich formatting."""
        from devtools import pprint

        pprint(data)
