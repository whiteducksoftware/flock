"""Factory for creating pre-configured Flock agents."""

from collections.abc import Callable
from typing import Any

from flock.core.flock_agent import FlockAgent
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
        input_def: str | Callable[..., str] | None = None,
        output_def: str | Callable[..., str] | None = None,
        model: str | Callable[..., str] | None = "openai/gpt-4o",
        tools: list[Callable[..., Any] | Any] | None = None,
        hand_off: str | Callable[..., Any] | None = None,
    ) -> FlockAgent:
        """Creates a default FlockAgent with some common modules.

        Includes:
        - Telemetry/tracing
        - Caching
        - Logging
        """
        eval_config = DefaultEvaluatorConfig(model=model)

        evaluator = DefaultEvaluator(
            name="default_evaluator", config=eval_config
        )
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
        output_config = OutputModuleConfig()
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
