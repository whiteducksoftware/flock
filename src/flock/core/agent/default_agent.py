"""DefaultAgent: explicit preset agent wiring standard components.

This class replaces the need for using FlockFactory for common setups by
providing a clear, explicit Agent class that mirrors the factory's kwargs
and composes the standard components under the hood.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from flock.components.utility.metrics_utility_component import (
    MetricsUtilityComponent,
    MetricsUtilityConfig,
)
from flock.core.config.flock_agent_config import FlockAgentConfig
from flock.core.flock_agent import DynamicStr, FlockAgent
from flock.core.logging.formatters.themes import OutputTheme
from flock.core.mcp.flock_mcp_server import FlockMCPServer
from flock.workflow.temporal_config import TemporalActivityConfig


class DefaultAgent(FlockAgent):
    """Explicit agent class wiring standard evaluation + utility components.

    Components included:
    - DeclarativeEvaluationComponent (LLM evaluation)
    - OutputUtilityComponent (formatting/printing)
    - MetricsUtilityComponent (latency tracking)
    """

    def __init__(
        self,
        name: str,
        description: DynamicStr | None = None,
        model: str | None = None,
        input: DynamicStr | None = None,
        output: DynamicStr | None = None,
        tools: list[Callable[..., Any] | Any] | None = None,
        servers: list[str | FlockMCPServer] | None = None,
        tool_whitelist: list[str] | None = None,
        # Evaluation parameters
        use_cache: bool = False,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_tool_calls: int = 0,
        max_retries: int = 2,
        stream: bool = True,
        stream_callbacks: list[Callable[..., Any] | Any] | None = None,
        stream_vertical_overflow: Literal["crop", "ellipsis", "crop_above", "visible"] = "crop_above",
        include_thought_process: bool = False,
        include_reasoning: bool = False,
        # Output utility parameters
        enable_rich_tables: bool = True,
        output_theme: OutputTheme | None = None,
        no_output: bool = False,
        print_context: bool = False,
        # Agent config
        write_to_file: bool = False,
        wait_for_input: bool = False,
        # Metrics utility
        alert_latency_threshold_ms: int = 30_000,
        # Workflow
        next_agent: DynamicStr | None = None,
        temporal_activity_config: TemporalActivityConfig | None = None,
    ):
        """Initialize a DefaultAgent with standard components and configuration.

        Args:
            name: Unique identifier for the agent
            description: Human-readable description of the agent's purpose
            model: Model identifier (e.g., 'openai/gpt-4o'). Uses Flock default if None
            input: Input signature for the agent
            output: Output signature for the agent
            tools: List of callable tools the agent can use
            servers: List of MCP servers the agent can connect to
            tool_whitelist: List of tool names that this agent is allowed to use.
                          If provided, the agent will only have access to tools
                          whose names are in this list. This applies to both native
                          Python tools and MCP tools. Recommended for security and
                          to prevent tool conflicts in multi-agent workflows.
            use_cache: Whether to enable caching for evaluation
            temperature: Sampling temperature for LLM generation
            max_tokens: Maximum tokens for LLM response
            max_tool_calls: Maximum number of tool calls per evaluation
            max_retries: Maximum retries for failed LLM calls
            stream: Whether to enable streaming responses
            stream_callbacks: Optional callbacks invoked with each streaming chunk
            stream_vertical_overflow: Rich Live overflow handling ('ellipsis', 'crop', 'crop_above', 'visible')
            include_thought_process: Include reasoning in output
            include_reasoning: Include detailed reasoning steps
            enable_rich_tables: Enable rich table formatting for output
            output_theme: Theme for output formatting
            no_output: Disable output printing
            print_context: Include context in output
            write_to_file: Save outputs to file
            wait_for_input: Wait for user input after execution
            alert_latency_threshold_ms: Threshold for latency alerts
            next_agent: Next agent in workflow chain
            temporal_activity_config: Configuration for Temporal workflow execution
        """
        # Import evaluation/output components lazily to avoid heavy imports at module import time
        from flock.components.evaluation.declarative_evaluation_component import (
            DeclarativeEvaluationComponent,
            DeclarativeEvaluationConfig,
        )
        from flock.components.utility.output_utility_component import (
            OutputUtilityComponent,
            OutputUtilityConfig,
        )

        # Apply sensible defaults for special models if needed
        if model and "gpt-oss" in model:
            # Ensure defaults are generous for local OSS models
            temperature = 1.0
            max_tokens = 32_768

        # Evaluation component
        _eval_kwargs = dict(
            model=model,
            use_cache=use_cache,
            temperature=temperature,
            max_tool_calls=max_tool_calls,
            max_retries=max_retries,
            no_output=no_output,
            stream=stream,
            stream_callbacks=stream_callbacks,
            stream_vertical_overflow=stream_vertical_overflow,
            include_thought_process=include_thought_process,
            include_reasoning=include_reasoning,
        )
        if max_tokens is not None:
            _eval_kwargs["max_tokens"] = max_tokens
        eval_config = DeclarativeEvaluationConfig(**_eval_kwargs)
        evaluator = DeclarativeEvaluationComponent(
            name="default_evaluator", config=eval_config
        )

        # Output utility component
        _output_kwargs = dict(
            render_table=enable_rich_tables,
            no_output=no_output,
            print_context=print_context,
        )
        if output_theme is not None:
            _output_kwargs["theme"] = output_theme
        output_config = OutputUtilityConfig(**_output_kwargs)
        output_component = OutputUtilityComponent(
            name="output_formatter", config=output_config
        )

        # Metrics utility component
        metrics_config = MetricsUtilityConfig(
            latency_threshold_ms=alert_latency_threshold_ms
        )
        metrics_component = MetricsUtilityComponent(
            name="metrics_tracker", config=metrics_config
        )

        super().__init__(
            name=name,
            model=model,
            description=description,
            input=input,
            output=output,
            tools=tools,
            servers=servers,
            tool_whitelist=tool_whitelist,
            components=[evaluator, output_component, metrics_component],
            config=FlockAgentConfig(
                write_to_file=write_to_file,
                wait_for_input=wait_for_input,
            ),
            next_agent=next_agent,
            temporal_activity_config=temporal_activity_config,
        )
