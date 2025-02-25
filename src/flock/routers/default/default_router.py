"""Default router implementation for the Flock framework."""

from typing import Any

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent, HandOffRequest
from flock.core.flock_router import FlockRouter, FlockRouterConfig
from flock.core.logging.logging import get_logger
from flock.core.registry.agent_registry import Registry

logger = get_logger("default_router")


class DefaultRouterConfig(FlockRouterConfig):
    """Configuration for the default router."""

    pass  # No additional parameters needed for now


class DefaultRouter(FlockRouter):
    """Default router implementation.

    This router simply uses the agent's hand_off property to determine the next agent.
    It does not perform any dynamic routing.
    """

    def __init__(
        self,
        registry: Registry,
        name: str = "default_router",
        config: DefaultRouterConfig | None = None,
    ):
        """Initialize the DefaultRouter.

        Args:
            registry: The agent registry containing all available agents
            name: The name of the router
            config: The router configuration
        """
        super().__init__(
            name=name, config=config or DefaultRouterConfig(name=name)
        )
        self.registry = registry

    async def route(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        context: FlockContext,
    ) -> HandOffRequest:
        """Determine the next agent to hand off to based on the current agent's output.

        Args:
            current_agent: The agent that just completed execution
            result: The output from the current agent
            context: The global execution context

        Returns:
            A HandOff object containing the next agent and input data
        """
        # If the agent has a hand_off property, use it
        if hasattr(current_agent, "hand_off") and current_agent.hand_off:
            if isinstance(current_agent.hand_off, str):
                # If hand_off is a string, it's the name of the next agent
                next_agent = current_agent.hand_off
                next_input = self._create_next_input(
                    current_agent, result, next_agent
                )
                return HandOffRequest(next_agent=next_agent, input=next_input)
            elif callable(current_agent.hand_off):
                # If hand_off is a callable, call it to get the HandOff object
                try:
                    handoff_data = current_agent.hand_off(context, result)
                    if isinstance(handoff_data.next_agent, FlockAgent):
                        handoff_data.next_agent = handoff_data.next_agent.name
                    return handoff_data
                except Exception as e:
                    logger.error(
                        "Handoff function error",
                        agent=current_agent.name,
                        error=str(e),
                    )
                    return HandOffRequest(next_agent="", input={})
            elif isinstance(current_agent.hand_off, HandOffRequest):
                # If hand_off is a HandOff object, use it directly
                handoff_data = current_agent.hand_off
                if isinstance(handoff_data.next_agent, FlockAgent):
                    handoff_data.next_agent = handoff_data.next_agent.name
                return handoff_data
            else:
                logger.error(
                    "Unsupported hand_off type",
                    agent=current_agent.name,
                    type=type(current_agent.hand_off),
                )
                return HandOffRequest(next_agent="", input={})

        # If the agent doesn't have a hand_off property, return an empty HandOff
        return HandOffRequest(next_agent="", input={})

    def _create_next_input(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        next_agent_name: str,
    ) -> dict[str, Any]:
        """Create the input for the next agent, including the previous agent's output.

        Args:
            current_agent: The agent that just completed execution
            result: The output from the current agent
            next_agent_name: The name of the next agent

        Returns:
            Input dictionary for the next agent
        """
        # Start with an empty input
        next_input = {}

        # Add a special field for the previous agent's output
        next_input["previous_agent_output"] = {
            "agent_name": current_agent.name,
            "result": result,
        }

        # Get the next agent
        next_agent = self.registry.get_agent(next_agent_name)
        if not next_agent:
            logger.error(
                f"Next agent '{next_agent_name}' not found in registry"
            )
            return next_input

        # Try to map the current agent's output to the next agent's input
        # This is a simple implementation that could be enhanced with more sophisticated mapping
        for key in result:
            # If the next agent expects this key, add it directly
            if key in next_agent.input:
                next_input[key] = result[key]

        return next_input
