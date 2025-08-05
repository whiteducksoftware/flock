# src/flock/core/registry/component_registry.py
"""Component class registration and lookup functionality."""

import threading
from typing import TYPE_CHECKING, Any

from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.component.agent_component_base import AgentComponent

logger = get_logger("registry.components")


class ComponentRegistry:
    """Manages component class registration and lookup with thread safety."""

    def __init__(self, lock: threading.RLock):
        self._lock = lock
        self._components: dict[str, type] = {}

    def register_component(self, component_class: type, name: str | None = None) -> str | None:
        """Register a component class (evaluation, routing, utility components)."""
        type_name = name or component_class.__name__
        if not type_name:
            logger.error(f"Could not determine name for component class: {component_class}")
            return None

        with self._lock:
            if type_name in self._components and self._components[type_name] != component_class:
                logger.warning(f"Component class '{type_name}' already registered. Overwriting.")
            
            self._components[type_name] = component_class
            logger.debug(f"Registered component class: {type_name}")
            return type_name

    def get_component(self, type_name: str) -> type:
        """Retrieve a component class by its type name."""
        with self._lock:
            if type_name in self._components:
                return self._components[type_name]
            
            logger.error(f"Component class '{type_name}' not found in registry.")
            raise KeyError(f"Component class '{type_name}' not found. Ensure it is registered.")

    def get_component_type_name(self, component_class: type) -> str | None:
        """Get the type name for a component class, registering it if necessary."""
        with self._lock:
            for type_name, registered_class in self._components.items():
                if component_class == registered_class:
                    return type_name
            # If not found, register using class name and return
            return self.register_component(component_class)

    def get_all_components(self) -> dict[str, type]:
        """Get all registered components."""
        with self._lock:
            return self._components.copy()

    def clear(self) -> None:
        """Clear all registered components."""
        with self._lock:
            self._components.clear()
            logger.debug("Cleared all registered components")
