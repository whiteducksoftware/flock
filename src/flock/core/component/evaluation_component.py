# src/flock/core/component/evaluation_component_base.py
"""Base class for evaluation components in the unified component system."""

from abc import abstractmethod
from typing import Any

from flock.core.context.context import FlockContext

from .agent_component_base import AgentComponent


class EvaluationComponent(AgentComponent):
    """Base class for evaluation components.
    
    Evaluation components implement the core intelligence/logic of an agent.
    They are responsible for taking inputs and producing outputs using some
    evaluation strategy (e.g., DSPy, direct LLM calls, deterministic logic).
    
    Each agent should have exactly one primary evaluation component.
    
    Example implementations:
    - DeclarativeEvaluationComponent (DSPy-based)
    - ScriptEvaluationComponent (Python script-based)
    - LLMEvaluationComponent (direct LLM API)
    """

    @abstractmethod
    async def evaluate_core(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Core evaluation logic - MUST be implemented by concrete classes.
        
        This is the heart of the agent's intelligence. It takes the processed
        inputs (after all on_pre_evaluate hooks) and produces the agent's output.
        
        Args:
            agent: The agent being executed
            inputs: Input data for evaluation (after pre-processing)
            context: Execution context with variables, history, etc.
            tools: Available callable tools for the agent
            mcp_tools: Available MCP server tools
            
        Returns:
            Evaluation result as a dictionary
            
        Raises:
            NotImplementedError: Must be implemented by concrete classes
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement evaluate_core()"
        )
