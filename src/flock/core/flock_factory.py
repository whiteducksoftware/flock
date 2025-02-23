"""Factory for creating pre-configured Flock agents."""

from collections.abc import Callable
from typing import Any

from flock.core.flock_agent import FlockAgent, HandOff
from flock.core.logging.formatters.themes import OutputTheme
from flock.evaluators.dspy.default import (
    DefaultEvaluator,
    DefaultEvaluatorConfig,
)
from flock.modules.output.output_module import OutputModule, OutputModuleConfig


class FlockFactory:
    """Factory for creating pre-configured Flock agents with common module setups."""

    @staticmethod
    def create_default_agent(
        name: str,
        description: str | Callable[..., str] | None = None,
        model: str | Callable[..., str] | None = "openai/gpt-4o",
        input_def: str | Callable[..., str] | None = None,
        output_def: str | Callable[..., str] | None = None,
        tools: list[Callable[..., Any] | Any] | None = None,
        hand_off: str | HandOff | Callable[..., HandOff] | None = None,
        use_cache: bool = True,
        enable_rich_tables: bool = False,
        output_theme: OutputTheme = OutputTheme.abernathy,
    ) -> FlockAgent:
        """Creates a default FlockAgent with some common modules.

        Includes:
        - Telemetry/tracing
        - Caching
        - Logging
        """
        eval_config = DefaultEvaluatorConfig(model=model, use_cache=use_cache)

        evaluator = DefaultEvaluator(name="default", config=eval_config)
        agent = FlockAgent(
            name=name,
            input=input_def,
            output=output_def,
            tools=tools,
            hand_off=hand_off,
            model=model,
            description=description,
            evaluator=evaluator,
        )
        output_config = OutputModuleConfig(
            render_table=enable_rich_tables, theme=output_theme
        )
        output_module = OutputModule("output", config=output_config)

        agent.add_module(output_module)

        return agent

    @staticmethod
    def create_custom_agent(
        name: str,
        input_def: str,
        output_def: str,
        modules: list[dict[str, Any]],
        **kwargs,
    ) -> FlockAgent:
        """Create an agent with custom module configuration.

        Args:
            modules: List of dicts with module specs:
                    [{"type": ModuleClass, "config": {...}}, ...]
        """
        agent = FlockAgent(
            name=name, input=input_def, output=output_def, **kwargs
        )

        for module_spec in modules:
            module_type = module_spec["type"]
            module_config = module_spec.get("config", {})
            agent.add_module(module_type(config=module_config))

        return agent
