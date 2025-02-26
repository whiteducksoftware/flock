"""Base router class for the Flock framework."""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

from flock.core.context.context import FlockContext


class HandOffRequest(BaseModel):
    """Base class for handoff returns."""

    next_agent: str = Field(default="", description="Next agent to invoke")
    # match = use the output fields of the current agent that also exists as input field of the next agent
    # add = add the output of the current agent to the input of the next agent
    hand_off_mode: Literal["match", "add"] = Field(default="match")
    override_next_agent: Any | None = Field(
        default=None,
        description="Override the next agent to hand off to",
    )
    override_context: FlockContext | None = Field(
        default=None, descrio="Override context parameters"
    )


class FlockRouterConfig(BaseModel):
    """Configuration for a router.

    This class defines the configuration parameters for a router.
    Subclasses can extend this to add additional parameters.
    """

    enabled: bool = Field(
        default=True, description="Whether the router is enabled"
    )
    agents: list[str] | None = Field(
        default=None,
        description="List of agents to choose from",
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
        current_agent: Any,
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
