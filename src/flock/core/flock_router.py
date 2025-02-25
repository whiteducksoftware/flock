"""Base router class for the Flock framework."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent


class HandOffRequest(BaseModel):
    """Base class for handoff returns."""

    next_agent: str | FlockAgent = Field(
        default="", description="Next agent to invoke"
    )
    input: dict[str, Any] = Field(
        default_factory=dict,
        description="Input data for the next agent",
    )
    context: FlockContext = Field(
        default=None, descrio="Override context parameters"
    )


class FlockRouterConfig(BaseModel):
    """Configuration for a router.

    This class defines the configuration parameters for a router.
    Subclasses can extend this to add additional parameters.
    """

    name: str = Field(
        default="default_router", description="Name of the router"
    )
    enabled: bool = Field(
        default=True, description="Whether the router is enabled"
    )
    confidence_threshold: float = Field(
        default=0.5,
        description="The minimum confidence score required to select an agent.",
        ge=0.0,
        le=1.0,
    )


class FlockRouter(BaseModel, ABC):
    """Base class for all routers.

    A router is responsible for determining the next agent in a workflow
    based on the current agent's output.
    """

    name: str = Field(..., description="Name of the router")
    config: FlockRouterConfig = Field(default_factory=FlockRouterConfig)

    @abstractmethod
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
        pass

    def get_model(self, agent: FlockAgent) -> str:
        """Get the model to use for routing decisions.

        Args:
            agent: The current agent

        Returns:
            The model to use
        """
        return agent.model or "openai/gpt-4o"
