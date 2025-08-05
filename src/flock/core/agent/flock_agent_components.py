"""Component management functionality for FlockAgent."""

from typing import TYPE_CHECKING, Any

from flock.core.component.evaluation_component import EvaluationComponent
from flock.core.component.routing_component import RoutingComponent
from flock.core.component.utility_component import UtilityComponent
from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.component.agent_component_base import AgentComponent
    from flock.core.flock_agent import FlockAgent

logger = get_logger("agent.components")


class FlockAgentComponents:
    """Helper class for managing unified components on FlockAgent."""

    def __init__(self, agent: "FlockAgent"):
        self.agent = agent

    def add_component(self, component: "AgentComponent") -> None:
        """Add a unified component to this agent."""
        if not component.name:
            logger.error("Component must have a name to be added.")
            return

        # Check if component with same name already exists
        existing = self.get_component(component.name)
        if existing:
            logger.warning(f"Overwriting existing component: {component.name}")
            self.agent.components.remove(existing)

        self.agent.components.append(component)
        logger.debug(f"Added component '{component.name}' to agent '{self.agent.name}'")

    def remove_component(self, component_name: str) -> None:
        """Remove a component from this agent."""
        component = self.get_component(component_name)
        if component:
            self.agent.components.remove(component)
            logger.debug(f"Removed component '{component_name}' from agent '{self.agent.name}'")
        else:
            logger.warning(f"Component '{component_name}' not found on agent '{self.agent.name}'")

    def get_component(self, component_name: str) -> "AgentComponent | None":
        """Get a component by name."""
        for component in self.agent.components:
            if component.name == component_name:
                return component
        return None

    def get_enabled_components(self) -> list["AgentComponent"]:
        """Get a list of currently enabled components attached to this agent."""
        return [c for c in self.agent.components if c.config.enabled]

    def get_components_by_type(self, component_type: type) -> list["AgentComponent"]:
        """Get all components of a specific type."""
        return [c for c in self.agent.components if isinstance(c, component_type)]

    def get_evaluation_components(self) -> list[EvaluationComponent]:
        """Get all evaluation components."""
        return self.get_components_by_type(EvaluationComponent)

    def get_routing_components(self) -> list[RoutingComponent]:
        """Get all routing components."""
        return self.get_components_by_type(RoutingComponent)

    def get_utility_components(self) -> list[UtilityComponent]:
        """Get all utility components."""
        return self.get_components_by_type(UtilityComponent)

    def get_primary_evaluator(self) -> EvaluationComponent | None:
        """Get the primary evaluation component (first one found)."""
        evaluators = self.get_evaluation_components()
        return evaluators[0] if evaluators else None

    def get_primary_router(self) -> RoutingComponent | None:
        """Get the primary routing component (first one found)."""
        routers = self.get_routing_components()
        return routers[0] if routers else None

    # Legacy compatibility methods (delegate to new unified approach)
    def add_module(self, module: Any) -> None:
        """DEPRECATED: Use add_component() instead."""
        logger.warning("add_module is deprecated - use add_component() instead")
        if hasattr(module, 'name'):
            self.add_component(module)

    def get_module(self, module_name: str) -> Any | None:
        """DEPRECATED: Use get_component() instead."""
        logger.warning("get_module is deprecated - use get_component() instead")
        return self.get_component(module_name)

    def get_evaluator(self) -> Any | None:
        """DEPRECATED: Use get_primary_evaluator() instead."""
        logger.warning("get_evaluator is deprecated - use get_primary_evaluator() instead")
        return self.get_primary_evaluator()

    def get_router(self) -> Any | None:
        """DEPRECATED: Use get_primary_router() instead."""
        logger.warning("get_router is deprecated - use get_primary_router() instead")
        return self.get_primary_router()
