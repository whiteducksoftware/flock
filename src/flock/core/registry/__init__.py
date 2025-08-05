# src/flock/core/registry/__init__.py
"""Modern thread-safe registry system using composition pattern.

This module provides a complete refactor of the FlockRegistry using
the proven composition pattern from Flock and FlockAgent refactoring.
"""


from flock.core.registry.agent_registry import AgentRegistry
from flock.core.registry.callable_registry import CallableRegistry
from flock.core.registry.component_discovery import ComponentDiscovery

# Specialized registry components (for advanced usage)
from flock.core.registry.component_registry import ComponentRegistry
from flock.core.registry.config_mapping import ConfigMapping
from flock.core.registry.decorators import (
    flock_callable,
    flock_component,
    flock_tool,
    flock_type,
)
from flock.core.registry.registry_hub import RegistryHub, get_registry
from flock.core.registry.server_registry import ServerRegistry
from flock.core.registry.type_registry import TypeRegistry

__all__ = [
    # Main API
    "RegistryHub",
    "get_registry",

    # Decorators
    "flock_component",
    "flock_tool",
    "flock_callable",
    "flock_type",

    # Specialized registries (for advanced usage)
    "ComponentRegistry",
    "CallableRegistry",
    "AgentRegistry",
    "ServerRegistry",
    "TypeRegistry",
    "ConfigMapping",
    "ComponentDiscovery",
]
