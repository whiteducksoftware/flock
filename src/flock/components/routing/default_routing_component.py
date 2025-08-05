# src/flock/components/routing/default_routing_component.py
"""Default routing component implementation for the unified component architecture."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import Field

from flock.core.component.agent_component_base import AgentComponentConfig
from flock.core.component.routing_component import RoutingComponent
from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.core.registry import flock_component

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent

logger = get_logger("components.routing.default")


class DefaultRoutingConfig(AgentComponentConfig):
    """Configuration for the default routing component."""

    next_agent: str | Callable[..., str] = Field(
        default="", description="Next agent to hand off to"
    )


@flock_component(config_class=DefaultRoutingConfig)
class DefaultRoutingComponent(RoutingComponent):
    """Default routing component implementation.

    This router simply uses the configured hand_off property to determine the next agent.
    It does not perform any dynamic routing based on agent results.

    Configuration can be:
    - A string: Simple agent name to route to
    - A callable: Function that takes (context, result) and returns agent name
    """

    config: DefaultRoutingConfig = Field(
        default_factory=DefaultRoutingConfig,
        description="Default routing configuration",
    )

    def __init__(
        self,
        name: str = "default_router",
        config: DefaultRoutingConfig | None = None,
        **data,
    ):
        """Initialize the DefaultRoutingComponent.

        Args:
            name: The name of the routing component
            config: The routing configuration
        """
        if config is None:
            config = DefaultRoutingConfig()
        super().__init__(name=name, config=config, **data)

    async def determine_next_step(
        self,
        agent: "FlockAgent",
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> str | None:
        """Determine the next agent to hand off to based on configuration.

        Args:
            agent: The agent that just completed execution
            result: The output from the current agent
            context: The global execution context

        Returns:
            String agent name to route to, or None to end workflow
        """
        handoff = self.config.next_agent

        # If empty string, end the workflow
        if handoff == "":
            logger.debug("No handoff configured, ending workflow")
            return None

        # If callable, invoke it with context and result
        if callable(handoff):
            logger.debug("Invoking handoff callable")
            try:
                handoff = handoff(context, result)
            except Exception as e:
                logger.error("Error invoking handoff callable: %s", e)
                return None

        # Validate it's a string
        if not isinstance(handoff, str):
            logger.error(
                "Invalid handoff type: %s. Expected str or callable returning str",
                type(handoff),
            )
            return None

        logger.debug("Routing to agent: %s", handoff)
        return handoff
