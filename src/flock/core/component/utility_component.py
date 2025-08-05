# src/flock/core/component/utility_component_base.py
"""Base class for utility components in the unified component system."""

from typing import Any

from flock.core.context.context import FlockContext

# HandOffRequest removed - using agent.next_agent directly
from .agent_component_base import AgentComponent


class UtilityComponent(AgentComponent):
    """Base class for utility/enhancement components.
    
    Utility components add cross-cutting concerns to agents without being
    the primary evaluation or routing logic. They typically use the standard
    lifecycle hooks to enhance agent behavior.
    
    These components focus on concerns like:
    - Memory management  
    - Output formatting
    - Metrics collection
    - Logging and tracing
    - Input validation
    - Error handling
    - Caching
    - Rate limiting
    
    Example implementations:
    - MemoryUtilityModule (memory persistence)
    - OutputUtilityModule (result formatting)  
    - MetricsUtilityModule (performance tracking)
    - AssertionUtilityModule (result validation)
    """

    async def evaluate_core(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Utility components typically don't implement core evaluation.
        
        This default implementation passes inputs through unchanged.
        Utility components usually enhance behavior through the standard
        lifecycle hooks (on_pre_evaluate, on_post_evaluate, etc.).
        
        Override this only if your utility component needs to participate
        in the core evaluation process.
        """
        return inputs

    async def determine_next_step(
        self,
        agent: Any,
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Utility components typically don't implement routing logic.
        
        This default implementation does nothing, as utility components
        usually enhance behavior through other lifecycle hooks.
        
        Override this only if your utility component needs to influence
        workflow routing decisions by setting agent.next_agent.
        """
        pass
