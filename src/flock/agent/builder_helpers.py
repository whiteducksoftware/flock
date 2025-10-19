"""Helper classes for AgentBuilder fluent API.

Phase 5B: Extracted from agent.py to reduce file size and improve modularity.

This module contains three helper classes that support the fluent builder pattern:
- PublishBuilder: Enables .only_for() and .visibility() configuration sugar
- RunHandle: Represents chained agent execution (agent.run().then().execute())
- Pipeline: Represents sequential agent pipeline execution
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from flock.core.visibility import Visibility, only_for


if TYPE_CHECKING:
    from flock.core import Agent
    from flock.core.artifacts import Artifact


class PublishBuilder:
    """Helper returned by `.publishes(...)` to support `.only_for` sugar.

    This class enables method chaining after .publishes() calls, allowing
    conditional visibility configuration and delegation back to AgentBuilder.

    Examples:
        >>> agent.publishes(Report).only_for("manager", "analyst")
        >>> agent.publishes(Alert).visibility(PrivateVisibility())
    """

    def __init__(self, parent: Any, outputs: Sequence[Any]) -> None:
        """Initialize PublishBuilder.

        Args:
            parent: AgentBuilder instance to return to for chaining
            outputs: List of AgentOutput objects to configure
        """
        self._parent = parent
        self._outputs = list(outputs)

    def only_for(self, *agent_names: str) -> Any:
        """Set visibility to allow only specific agents.

        Convenience method that creates PrivateVisibility with allowlist.

        Args:
            *agent_names: Names of agents that can see these outputs

        Returns:
            Parent AgentBuilder for continued method chaining

        Example:
            >>> agent.publishes(Report).only_for("manager", "analyst")
        """
        visibility = only_for(*agent_names)
        for output in self._outputs:
            output.default_visibility = visibility
        return self._parent

    def visibility(self, value: Visibility) -> Any:
        """Set explicit visibility for published outputs.

        Args:
            value: Visibility instance (PublicVisibility, PrivateVisibility, etc.)

        Returns:
            Parent AgentBuilder for continued method chaining

        Example:
            >>> agent.publishes(Report).visibility(TenantVisibility())
        """
        for output in self._outputs:
            output.default_visibility = value
        return self._parent

    def __getattr__(self, item):
        """Delegate unknown attributes to parent AgentBuilder.

        This enables seamless chaining like:
        >>> agent.publishes(Report).only_for("alice").consumes(Task)
        """
        return getattr(self._parent, item)


class RunHandle:
    """Represents a chained run starting from a given agent.

    Enables fluent API for sequential agent execution:
    >>> await agent1.run(input).then(agent2).then(agent3).execute()

    The chain executes agents in sequence, passing outputs from one to the next.
    """

    def __init__(self, agent: Agent, inputs: list[BaseModel]) -> None:
        """Initialize RunHandle.

        Args:
            agent: First agent in the chain
            inputs: Initial inputs to process
        """
        self.agent = agent
        self.inputs = inputs
        self._chain: list[Agent] = [agent]

    def then(self, builder: Any) -> RunHandle:
        """Add another agent to the execution chain.

        Args:
            builder: AgentBuilder whose agent to add to chain

        Returns:
            self for continued chaining

        Example:
            >>> await agent1.run(task).then(agent2).then(agent3).execute()
        """
        self._chain.append(builder.agent)
        return self

    async def execute(self) -> list[Artifact]:
        """Execute the agent chain sequentially.

        Runs each agent in order, passing outputs from one as inputs to the next.

        Returns:
            Final list of artifacts from the last agent in the chain

        Example:
            >>> results = await agent1.run(input).then(agent2).execute()
        """
        orchestrator = self.agent._orchestrator
        artifacts = await orchestrator.direct_invoke(self.agent, self.inputs)
        for agent in self._chain[1:]:
            artifacts = await orchestrator.direct_invoke(agent, artifacts)
        return artifacts


class Pipeline:
    """Pipeline of agents executed in sequence.

    Alternative to RunHandle for building multi-agent pipelines:
    >>> pipeline = Pipeline([agent1, agent2, agent3])
    >>> results = await pipeline.execute()
    """

    def __init__(self, builders: Sequence[Any]) -> None:
        """Initialize Pipeline.

        Args:
            builders: Sequence of AgentBuilder instances
        """
        self.builders = list(builders)

    def then(self, builder: Any) -> Pipeline:
        """Add another agent to the pipeline.

        Args:
            builder: AgentBuilder to add

        Returns:
            self for continued chaining

        Example:
            >>> pipeline = Pipeline([agent1]).then(agent2).then(agent3)
        """
        self.builders.append(builder)
        return self

    async def execute(self) -> list[Artifact]:
        """Execute all agents in the pipeline sequentially.

        Returns:
            Final list of artifacts from the last agent

        Example:
            >>> results = await Pipeline([agent1, agent2, agent3]).execute()
        """
        orchestrator = self.builders[0].agent._orchestrator
        artifacts: list[Artifact] = []
        for builder in self.builders:
            inputs = artifacts if artifacts else []
            artifacts = await orchestrator.direct_invoke(builder.agent, inputs)
        return artifacts


__all__ = ["Pipeline", "PublishBuilder", "RunHandle"]
