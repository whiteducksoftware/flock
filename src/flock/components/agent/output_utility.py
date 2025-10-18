"""Output formatting and display functionality for agents."""

import re
from typing import TYPE_CHECKING, Any

from pydantic import Field

from flock.components.agent.base import AgentComponent, AgentComponentConfig
from flock.logging.formatters.themed_formatter import (
    ThemedAgentResultFormatter,
)
from flock.logging.formatters.themes import OutputTheme
from flock.logging.logging import get_logger
from flock.utils.runtime import Context, EvalInputs, EvalResult


if TYPE_CHECKING:  # pragma: no cover - type checking only
    from flock.core import Agent


logger = get_logger("components.agent.output_utility")


class OutputUtilityConfig(AgentComponentConfig):
    """Configuration for output formatting and display."""

    theme: OutputTheme = Field(
        default=OutputTheme.catppuccin_mocha, description="Theme for output formatting"
    )
    render_table: bool = Field(
        default=True, description="Whether to render output as a table"
    )
    max_length: int = Field(
        default=1000, description="Maximum length for displayed output"
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


class OutputUtilityComponent(AgentComponent):
    """Utility component that handles output formatting and display."""

    config: OutputUtilityConfig = Field(
        default_factory=OutputUtilityConfig, description="Output configuration"
    )

    def __init__(
        self, name: str = "output", config: OutputUtilityConfig | None = None, **data
    ):
        if config is None:
            config = OutputUtilityConfig()
        super().__init__(name=name, config=config, **data)
        self._formatter = ThemedAgentResultFormatter(
            theme=self.config.theme,
            max_length=self.config.max_length,
            render_table=self.config.render_table,
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
        if isinstance(value, list):
            return self._format_list(value)
        if isinstance(value, str) and self.config.format_code_blocks:
            return self._format_potential_code(value)
        return str(value)

    def _format_dict(self, d: dict[str, Any], indent: int = 0) -> str:
        """Format a dictionary with proper indentation."""
        if not d:
            return "{}"

        items = []
        prefix = "  " * indent
        for key, value in d.items():
            if (
                self.config.truncate_long_values
                and isinstance(value, str)
                and len(value) > 100
            ):
                value = value[:97] + "..."
            formatted_value = self._format_value(value, key)
            items.append(f"{prefix}  {key}: {formatted_value}")

        return "{\n" + "\n".join(items) + f"\n{prefix}}}"

    def _format_list(self, lst: list[Any]) -> str:
        """Format a list with proper structure."""
        if not lst:
            return "[]"

        if len(lst) <= 3:
            return str(lst)

        # For longer lists, show first few items and count
        preview = [str(item) for item in lst[:3]]
        return f"[{', '.join(preview)}, ... ({len(lst)} total)]"

    def _format_potential_code(self, text: str) -> str:
        """Apply syntax highlighting to potential code blocks."""

        # Simple pattern matching for code blocks
        def replace_code_block(match):
            language = match.group(1) or "text"
            code = match.group(2)
            return f"[CODE:{language}]\n{code}\n[/CODE]"

        # Replace markdown-style code blocks
        return re.sub(
            r"```(\w+)?\n(.*?)\n```", replace_code_block, text, flags=re.DOTALL
        )

    async def on_post_evaluate(
        self, agent: "Agent", ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> dict[str, Any]:
        """Format and display the output."""
        logger.debug("Formatting and displaying output")

        streaming_live_handled = False
        output_queued = False
        streamed_artifact_id = None

        if ctx:
            streaming_live_handled = bool(
                ctx.get_variable("_flock_stream_live_active", False)
            )
            output_queued = bool(ctx.get_variable("_flock_output_queued", False))
            streamed_artifact_id = ctx.get_variable("_flock_streamed_artifact_id")

            if streaming_live_handled:
                ctx.state.pop("_flock_stream_live_active", None)

            if output_queued:
                ctx.state.pop("_flock_output_queued", None)

            if streamed_artifact_id:
                ctx.state.pop("_flock_streamed_artifact_id", None)

        # If streaming was handled, we need to update the final display with the real artifact ID
        if streaming_live_handled and streamed_artifact_id:
            logger.debug(
                f"Updating streamed display with final artifact ID: {streamed_artifact_id}"
            )
            # The streaming display already showed everything, we just need to update the ID
            # This is handled by a final refresh in the streaming code
            return result

        # Skip output if streaming already handled it (and no ID to update)
        if streaming_live_handled:
            logger.debug(
                "Skipping static table because streaming rendered live output."
            )
            return result

        # If output was queued due to concurrent stream, wait and then display
        if output_queued:
            # Wait for active streams to complete
            # Phase 6+7 Security Fix: Use Agent class variable instead of ctx.state
            if ctx:
                import asyncio

                from flock.core import Agent

                # Wait until no streams are active
                max_wait = 30  # seconds
                waited = 0
                while Agent._streaming_counter > 0 and waited < max_wait:
                    await asyncio.sleep(0.1)
                    waited += 0.1
                logger.debug(
                    f"Queued output displayed after waiting {waited:.1f}s for streams to complete."
                )

        logger.debug("Formatting and displaying output to console.")

        if self.config.print_context and ctx:
            # Add context snapshot if requested (be careful with large contexts)
            try:
                # Create a copy or select relevant parts to avoid modifying original result dict directly
                display_result = result.copy()
                display_result["context_snapshot"] = (
                    ctx.to_dict()
                )  # Potential performance hit
            except Exception:
                display_result = result.copy()
                display_result["context_snapshot"] = "[Error serializing context]"
            result_to_display = display_result
        else:
            result_to_display = result

        if not hasattr(self, "_formatter") or self._formatter is None:
            self._formatter = ThemedAgentResultFormatter(
                theme=self.config.theme,
                max_length=self.config.max_length,
                render_table=self.config.render_table,
            )
        model = agent.model if agent.model else ctx.get_variable("model")
        # Handle None model gracefully
        model_display = model if model is not None else "default"
        self._formatter.display_result(
            result_to_display.artifacts, agent.name + " - " + model_display
        )

        return result  # Return the original, unmodified result

    def update_theme(self, new_theme: OutputTheme) -> None:
        """Update the output theme."""
        self.config.theme = new_theme
        self._formatter = ThemedAgentResultFormatter(
            theme=self.config.theme,
            max_length=self.config.max_length,
            render_table=self.config.render_table,
        )

    def add_custom_formatter(self, key: str, formatter_name: str) -> None:
        """Add a custom formatter for a specific output key."""
        self.config.custom_formatters[key] = formatter_name


__all__ = [
    "OutputUtilityComponent",
    "OutputUtilityConfig",
]
