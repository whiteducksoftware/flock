"""Output formatting and display functionality for agents."""

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import Field

if TYPE_CHECKING:
    from flock.core import FlockAgent

from flock.core.context.context import FlockContext
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.logging.formatters.themed_formatter import (
    ThemedAgentResultFormatter,
)
from flock.core.logging.formatters.themes import OutputTheme
from flock.core.logging.logging import get_logger
from flock.core.serialization.json_encoder import FlockJSONEncoder

# from flock.core.logging.formatters.themes import OutputTheme
# from flock.core.logging.logging import get_logger
# from flock.core.serialization.json_encoder import FlockJSONEncoder

logger = get_logger("module.output")


class OutputModuleConfig(FlockModuleConfig):
    """Configuration for output formatting and display."""

    theme: OutputTheme = Field(
        default=OutputTheme.afterglow, description="Theme for output formatting"
    )
    render_table: bool = Field(
        default=False, description="Whether to render output as a table"
    )
    max_length: int = Field(
        default=1000, description="Maximum length for displayed output"
    )
    wait_for_input: bool = Field(
        default=False,
        description="Whether to wait for user input after display",
    )
    write_to_file: bool = Field(
        default=False, description="Whether to save output to file"
    )
    output_dir: str = Field(
        default="output/", description="Directory for saving output files"
    )
    truncate_long_values: bool = Field(
        default=True, description="Whether to truncate long values in display"
    )
    show_metadata: bool = Field(
        default=True, description="Whether to show metadata like timestamps"
    )
    format_code_blocks: bool = Field(
        default=True,
        description="Whether to apply syntax highlighting to code blocks",
    )
    custom_formatters: dict[str, str] = Field(
        default_factory=dict,
        description="Custom formatters for specific output types",
    )
    no_output: bool = Field(
        default=False,
        description="Whether to suppress output",
    )
    print_context: bool = Field(
        default=False,
        description="Whether to print the context",
    )


class OutputModule(FlockModule):
    """Module that handles output formatting and display."""

    name: str = "output"
    config: OutputModuleConfig = Field(
        default_factory=OutputModuleConfig, description="Output configuration"
    )

    def __init__(self, name: str, config: OutputModuleConfig):
        super().__init__(name=name, config=config)
        if self.config.write_to_file:
            os.makedirs(self.config.output_dir, exist_ok=True)
        self._formatter = ThemedAgentResultFormatter(
            theme=self.config.theme,
            max_length=self.config.max_length,
            render_table=self.config.render_table,
            wait_for_input=self.config.wait_for_input,
        )

    def _format_value(self, value: Any, key: str) -> str:
        """Format a single value based on its type and configuration."""
        # Check for custom formatter
        if key in self.config.custom_formatters:
            formatter_name = self.config.custom_formatters[key]
            if hasattr(self, f"_format_{formatter_name}"):
                return getattr(self, f"_format_{formatter_name}")(value)

        # Default formatting based on type
        if isinstance(value, dict):
            return self._format_dict(value)
        elif isinstance(value, list):
            return self._format_list(value)
        elif isinstance(value, str) and self.config.format_code_blocks:
            return self._format_potential_code(value)
        else:
            return str(value)

    def _format_dict(self, d: dict[str, Any], indent: int = 0) -> str:
        """Format a dictionary with proper indentation."""
        lines = []
        for k, v in d.items():
            formatted_value = self._format_value(v, k)
            if (
                self.config.truncate_long_values
                and len(formatted_value) > self.config.max_length
            ):
                formatted_value = (
                    formatted_value[: self.config.max_length] + "..."
                )
            lines.append(f"{'  ' * indent}{k}: {formatted_value}")
        return "\n".join(lines)

    def _format_list(self, lst: list[Any]) -> str:
        """Format a list with proper indentation."""
        return "\n".join(f"- {self._format_value(item, '')}" for item in lst)

    def _format_potential_code(self, text: str) -> str:
        """Format text that might contain code blocks."""
        import re

        def replace_code_block(match):
            code = match.group(2)
            lang = match.group(1) if match.group(1) else ""
            # Here you could add syntax highlighting
            return f"```{lang}\n{code}\n```"

        # Replace code blocks with formatted versions
        text = re.sub(
            r"```(\w+)?\n(.*?)\n```", replace_code_block, text, flags=re.DOTALL
        )
        return text

    def _save_output(self, agent_name: str, result: dict[str, Any]) -> None:
        """Save output to file if configured."""
        if not self.config.write_to_file:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{agent_name}_output_{timestamp}.json"
        filepath = os.path.join(self.config.output_dir, filename)

        output_data = {
            "agent": agent_name,
            "timestamp": timestamp,
            "output": result,
        }

        if self.config.show_metadata:
            output_data["metadata"] = {
                "formatted_at": datetime.now().isoformat(),
                "theme": self.config.theme.value,
                "max_length": self.config.max_length,
            }

        try:
            with open(filepath, "w") as f:
                json.dump(output_data, f, indent=2, cls=FlockJSONEncoder)
        except Exception as e:
            logger.warning(f"Failed to save output to file: {e}")

    async def post_evaluate(
        self,
        agent: "FlockAgent",
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Format and display the output."""
        logger.debug("Formatting and displaying output")
        if self.config.no_output:
            return result
        if self.config.print_context:
            result["context"] = context
        # Display the result using the formatter
        self._formatter.display_result(result, agent.name)

        # Save to file if configured
        self._save_output(agent.name, result)

        return result

    def update_theme(self, new_theme: OutputTheme) -> None:
        """Update the output theme."""
        self.config.theme = new_theme
        self._formatter = ThemedAgentResultFormatter(
            theme=self.config.theme,
            max_length=self.config.max_length,
            render_table=self.config.render_table,
            wait_for_input=self.config.wait_for_input,
            write_to_file=self.config.write_to_file,
        )

    def add_custom_formatter(self, key: str, formatter_name: str) -> None:
        """Add a custom formatter for a specific output key."""
        self.config.custom_formatters[key] = formatter_name

    def get_output_files(self) -> list[str]:
        """Get list of saved output files."""
        if not self.config.write_to_file:
            return []

        return [
            f
            for f in os.listdir(self.config.output_dir)
            if f.endswith("_output.json")
        ]
