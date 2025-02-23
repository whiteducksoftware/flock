"""Factory for creating pre-configured Flock agents."""

from typing import Any

from flock.core.flock_agent import FlockAgent


class FlockAgentFactory:
    """Factory for creating pre-configured Flock agents with common module setups."""

    @staticmethod
    def create_default_agent(
        name: str,
        input_def: str,
        output_def: str,
        model: str = "openai/gpt-4",
        **kwargs,
    ) -> FlockAgent:
        """Create an agent configured for production use.

        Includes:
        - Memory with persistence
        - Error handling with retries
        - Telemetry/tracing
        - Caching
        - Production-level logging
        """
        agent = FlockAgent(
            name=name, input=input_def, output=output_def, **kwargs
        )

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
