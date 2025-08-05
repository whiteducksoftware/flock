# src/flock/core/registry/registry_hub.py
"""Main registry hub using composition pattern with thread safety."""

import threading
from typing import TYPE_CHECKING, Any, TypeVar

from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from flock.core.flock_agent import FlockAgent
    from flock.core.mcp.flock_mcp_server import FlockMCPServer

logger = get_logger("registry.hub")

T = TypeVar("T")
ConfigType = TypeVar("ConfigType")
ClassType = TypeVar("ClassType")


class RegistryHub:
    """Thread-safe registry hub using composition pattern.
    
    Main coordinator for all registry types following the successful
    pattern from Flock and FlockAgent refactoring.
    """

    def __init__(self):
        self._lock = threading.RLock()
        logger.debug("RegistryHub initialized with thread safety")

    # --- Lazy-loaded composition helpers (following Flock pattern) ---

    @property
    def components(self):
        """Component class registry helper."""
        if not hasattr(self, '_components_helper'):
            from flock.core.registry.component_registry import ComponentRegistry
            self._components_helper = ComponentRegistry(self._lock)
        return self._components_helper

    @property
    def callables(self):
        """Callable registry helper."""
        if not hasattr(self, '_callables_helper'):
            from flock.core.registry.callable_registry import CallableRegistry
            self._callables_helper = CallableRegistry(self._lock)
        return self._callables_helper

    @property
    def agents(self):
        """Agent registry helper."""
        if not hasattr(self, '_agents_helper'):
            from flock.core.registry.agent_registry import AgentRegistry
            self._agents_helper = AgentRegistry(self._lock)
        return self._agents_helper

    @property
    def servers(self):
        """Server registry helper."""
        if not hasattr(self, '_servers_helper'):
            from flock.core.registry.server_registry import ServerRegistry
            self._servers_helper = ServerRegistry(self._lock)
        return self._servers_helper

    @property
    def types(self):
        """Type registry helper."""
        if not hasattr(self, '_types_helper'):
            from flock.core.registry.type_registry import TypeRegistry
            self._types_helper = TypeRegistry(self._lock)
        return self._types_helper

    @property
    def config_mapping(self):
        """Config mapping helper."""
        if not hasattr(self, '_config_mapping_helper'):
            from flock.core.registry.config_mapping import ConfigMapping
            self._config_mapping_helper = ConfigMapping(self._lock)
        return self._config_mapping_helper

    @property
    def discovery(self):
        """Component discovery helper."""
        if not hasattr(self, '_discovery_helper'):
            from flock.core.registry.component_discovery import (
                ComponentDiscovery,
            )
            self._discovery_helper = ComponentDiscovery(self)
        return self._discovery_helper

    # --- High-level registry operations (delegate to helpers) ---

    def register_agent(self, agent: "FlockAgent", *, force: bool = False) -> None:
        """Register a FlockAgent instance."""
        self.agents.register_agent(agent, force=force)

    def get_agent(self, name: str) -> "FlockAgent | None":
        """Get a registered FlockAgent instance by name."""
        return self.agents.get_agent(name)

    def get_all_agent_names(self) -> list[str]:
        """Get all registered agent names."""
        return self.agents.get_all_agent_names()

    def register_server(self, server: "FlockMCPServer") -> None:
        """Register a FlockMCPServer instance."""
        self.servers.register_server(server)

    def get_server(self, name: str) -> "FlockMCPServer | None":
        """Get a registered FlockMCPServer instance by name."""
        return self.servers.get_server(name)

    def get_all_server_names(self) -> list[str]:
        """Get all registered server names."""
        return self.servers.get_all_server_names()

    def register_callable(self, func: "Callable", name: str | None = None) -> str | None:
        """Register a callable function/method."""
        return self.callables.register_callable(func, name)

    def get_callable(self, name_or_path: str) -> "Callable":
        """Get a registered callable by name or path."""
        return self.callables.get_callable(name_or_path)

    def get_callable_path_string(self, func: "Callable") -> str | None:
        """Get the path string for a callable."""
        return self.callables.get_callable_path_string(func)

    def register_type(self, type_obj: type, name: str | None = None) -> str | None:
        """Register a type (Pydantic Model, Dataclass, etc.)."""
        return self.types.register_type(type_obj, name)

    def get_type(self, type_name: str) -> type:
        """Get a registered type by name."""
        return self.types.get_type(type_name)

    def register_component(self, component_class: type, name: str | None = None) -> str | None:
        """Register a component class."""
        return self.components.register_component(component_class, name)

    def get_component(self, type_name: str) -> type:
        """Get a registered component class by name."""
        return self.components.get_component(type_name)

    def get_component_type_name(self, component_class: type) -> str | None:
        """Get the type name for a component class."""
        return self.components.get_component_type_name(component_class)

    def register_config_component_pair(self, config_cls: type[ConfigType], component_cls: type[ClassType]) -> None:
        """Register a config-to-component mapping."""
        self.config_mapping.register_config_component_pair(config_cls, component_cls)

    def get_component_class_for_config(self, config_cls: type[ConfigType]) -> type[ClassType] | None:
        """Get the component class for a config class."""
        return self.config_mapping.get_component_class_for_config(config_cls)

    def discover_and_register_components(self) -> None:
        """Auto-discover and register components from known packages."""
        self.discovery.discover_and_register_components()

    def register_module_components(self, module_or_path: Any) -> None:
        """Register components from a specific module."""
        self.discovery.register_module_components(module_or_path)

    # --- Utility methods ---

    def clear_all(self) -> None:
        """Clear all registries (useful for testing)."""
        with self._lock:
            if hasattr(self, '_agents_helper'):
                self.agents.clear()
            if hasattr(self, '_servers_helper'):
                self.servers.clear()
            if hasattr(self, '_callables_helper'):
                self.callables.clear()
            if hasattr(self, '_types_helper'):
                self.types.clear()
            if hasattr(self, '_components_helper'):
                self.components.clear()
            if hasattr(self, '_config_mapping_helper'):
                self.config_mapping.clear_config_mappings()
            logger.debug("Cleared all registries")

    def get_registry_summary(self) -> dict[str, int]:
        """Get a summary of all registries."""
        with self._lock:
            return {
                "agents": len(self.agents.get_all_agents()),
                "servers": len(self.servers.get_all_servers()),
                "callables": len(self.callables.get_all_callables()),
                "types": len(self.types.get_all_types()),
                "components": len(self.components.get_all_components()),
                "config_mappings": len(self.config_mapping.get_all_config_mappings()),
            }


# --- Global singleton instance ---
_default_registry_hub = RegistryHub()


def get_registry() -> RegistryHub:
    """Get the default thread-safe registry hub instance."""
    return _default_registry_hub
