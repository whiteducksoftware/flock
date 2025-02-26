"""Default router implementation for the Flock framework."""

from collections.abc import Callable
from typing import Any

from pydantic import Field

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_router import (
    FlockRouter,
    FlockRouterConfig,
    HandOffRequest,
)
from flock.core.logging.logging import get_logger

logger = get_logger("default_router")


class DefaultRouterConfig(FlockRouterConfig):
    """Configuration for the default router."""

    hand_off: str | HandOffRequest | Callable[..., HandOffRequest] = Field(
        default="", description="Next agent to hand off to"
    )


class DefaultRouter(FlockRouter):
    """Default router implementation.

    This router simply uses the agent's hand_off property to determine the next agent.
    It does not perform any dynamic routing.
    """

    name: str = "default_router"
    config: DefaultRouterConfig = Field(
        default_factory=DefaultRouterConfig, description="Output configuration"
    )

    def __init__(
        self,
        name: str = "default_router",
        config: DefaultRouterConfig | None = None,
    ):
        """Initialize the DefaultRouter.

        Args:
            name: The name of the router
            config: The router configuration
        """
        super().__init__(
            name=name, config=config or DefaultRouterConfig(name=name)
        )

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
        handoff = self.config.hand_off
        if callable(handoff):
            handoff = handoff(context, result)
        if isinstance(handoff, str):
            handoff = HandOffRequest(next_agent=handoff, hand_off_mode="match")
        return handoff
