from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class BaseFormatter(ABC):
    def __init__(self, max_length: int = 1000) -> None:
        self.max_length = max_length

    def display(
        self,
        result: dict[str, Any],
        agent_name: str,
        wait: bool = False,
    ) -> None:
        self.display_result(result, agent_name)
        if wait:
            input("Press Enter to continue...")

    @abstractmethod
    def display_result(self, result: dict[str, Any], agent_name: str) -> None:
        """Display an agent's result."""
        raise NotImplementedError

    @abstractmethod
    def display_data(self, data: dict[str, Any]) -> None:
        """Display arbitrary data."""
        raise NotImplementedError


@dataclass
class FormatterOptions:
    formatter: type[BaseFormatter] = field(default=None)
    wait_for_input: bool = field(default=False)
    max_length: int = field(default=1000)
    settings: Any | None = field(default=None)
