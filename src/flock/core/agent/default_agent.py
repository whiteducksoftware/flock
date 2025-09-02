"""DefaultAgent: explicit preset agent wiring standard components.

This class replaces the need for using FlockFactory for common setups by
providing a clear, explicit Agent class that mirrors the factory's kwargs
and composes the standard components under the hood.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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
        # Evaluation parameters
        use_cache: bool = False,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_tool_calls: int = 0,
        max_retries: int = 2,
        stream: bool = False,
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
            stream=stream,
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
            components=[evaluator, output_component, metrics_component],
            config=FlockAgentConfig(
                write_to_file=write_to_file,
                wait_for_input=wait_for_input,
            ),
            next_agent=next_agent,
            temporal_activity_config=temporal_activity_config,
        )
