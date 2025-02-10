from dataclasses import dataclass
from typing import Any

from flock.core.logging.formatters.base_formatter import (
    BaseFormatter,
    FormatterOptions,
)
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter
from flock.core.logging.formatters.rich_formatters import RichTables
from flock.core.logging.formatters.themed_formatter import (
    ThemedAgentResultFormatter,
)


@dataclass
class FormatterOptions:
    formatter: type[BaseFormatter]
    wait_for_input: bool = False
    settings: dict[str, Any] | None = None


class FormatterFactory:
    _formatter_map = {
        PrettyPrintFormatter: PrettyPrintFormatter,
        RichTables: RichTables,
        ThemedAgentResultFormatter: ThemedAgentResultFormatter,
    }

    @staticmethod
    def create_formatter(options: FormatterOptions) -> BaseFormatter:
        formatter_cls = options.formatter
        max_length = options.max_length
        if formatter_cls in FormatterFactory._formatter_map:
            formatter = FormatterFactory._formatter_map[formatter_cls]
            if options.settings:
                return formatter(max_length=max_length, **options.settings)
            return formatter(max_length=max_length)
        raise ValueError(f"Unknown formatter: {formatter_cls}")
