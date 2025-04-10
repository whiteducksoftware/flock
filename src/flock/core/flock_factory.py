"""Factory for creating pre-configured Flock agents."""

from collections.abc import Callable
from typing import Any

from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.themes import OutputTheme
from flock.evaluators.declarative.declarative_evaluator import (
    DeclarativeEvaluator,
    DeclarativeEvaluatorConfig,
)
from flock.modules.output.output_module import OutputModule, OutputModuleConfig
from flock.modules.performance.metrics_module import (
    MetricsModule,
    MetricsModuleConfig,
)


class FlockFactory:
    """Factory for creating pre-configured Flock agents with common module setups."""

    @staticmethod
    def create_default_agent(
        name: str,
        description: str | Callable[..., str] | None = None,
        model: str | Callable[..., str] | None = None,
        input: str | Callable[..., str] | None = None,
        output: str | Callable[..., str] | None = None,
        tools: list[Callable[..., Any] | Any] | None = None,
        use_cache: bool = True,
        enable_rich_tables: bool = False,
        output_theme: OutputTheme = OutputTheme.abernathy,
        wait_for_input: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        alert_latency_threshold_ms: int = 30000,
        no_output: bool = False,
        print_context: bool = False,
        write_to_file: bool = False,
        stream: bool = False,
    ) -> FlockAgent:
        """Creates a default FlockAgent.

        The default agent includes a declarative evaluator with the following modules:
        - OutputModule

        It also includes often needed configurations like cache usage, rich tables, and output theme.
        """
        eval_config = DeclarativeEvaluatorConfig(
            model=model,
            use_cache=use_cache,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )

        evaluator = DeclarativeEvaluator(name="default", config=eval_config)
        agent = FlockAgent(
            name=name,
            input=input,
            output=output,
            tools=tools,
            model=model,
            description=description,
            evaluator=evaluator,
            write_to_file=write_to_file,
            wait_for_input=wait_for_input,
        )
        output_config = OutputModuleConfig(
            render_table=enable_rich_tables,
            theme=output_theme,
            no_output=no_output,
            print_context=print_context,
        )
        output_module = OutputModule("output", config=output_config)

        metrics_config = MetricsModuleConfig(
            latency_threshold_ms=alert_latency_threshold_ms
        )
        metrics_module = MetricsModule("metrics", config=metrics_config)

        agent.add_module(output_module)
        agent.add_module(metrics_module)
        return agent
