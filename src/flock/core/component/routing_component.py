# src/flock/core/component/routing_component_base.py
"""Base class for routing components in the unified component system."""

from abc import abstractmethod
from typing import Any

from flock.core.context.context import FlockContext

from .agent_component_base import AgentComponent


class RoutingComponent(AgentComponent):
    """Base class for routing components.
    
    Routing components determine the next step in a workflow based on the
    current agent's output. They implement workflow orchestration logic
    and can enable complex multi-agent patterns.
    
    Each agent should have at most one routing component. If no routing
    component is present, the workflow ends after this agent.
    
    Example implementations:
    - ConditionalRoutingModule (rule-based routing)
    - LLMRoutingModule (AI-powered routing decisions)
    - DefaultRoutingModule (simple next-agent routing)
    - ListGeneratorRoutingModule (dynamic agent creation)
    """

    @abstractmethod
    async def determine_next_step(
        self,
        agent: Any,
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> str | Any | None:
        """Determine the next agent in the workflow - MUST be implemented.
        
        This method analyzes the agent's result and determines what agent
        should execute next. The result will be stored in agent.next_agent
        for the orchestrator to process.
        
        Args:
            agent: The agent that just completed execution
            result: Result from the agent's evaluation (after post-processing)
            context: Execution context with workflow state
            
        Returns:
            String (agent name), FlockAgent instance, or None to end workflow
            
        Raises:
            NotImplementedError: Must be implemented by concrete classes
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement determine_next_step()"
        )

    async def evaluate_core(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Routing components typically don't modify evaluation - pass through.
        
        Routing components usually don't implement core evaluation logic,
        they focus on workflow decisions. This default implementation
        passes inputs through unchanged.
        
        Override this if your routing component also needs to modify
        the evaluation process.
        """
        return inputs
