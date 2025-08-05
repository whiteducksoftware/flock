# src/flock/core/registry/component_discovery.py
"""Component discovery and auto-registration functionality."""

import importlib
import importlib.util
import inspect
import os
import pkgutil
import threading
from dataclasses import is_dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.registry.registry_hub import RegistryHub
    from flock.core.component.agent_component_base import AgentComponent

logger = get_logger("registry.discovery")


class ComponentDiscovery:
    """Handles automatic component discovery and registration."""

    def __init__(self, registry_hub: "RegistryHub"):
        self.registry_hub = registry_hub
        self._packages_to_scan = [
            "flock.tools",
            "flock.components",  # Updated to use unified components
        ]

    def discover_and_register_components(self) -> None:
        """Auto-register components from known core packages."""
        for package_name in self._packages_to_scan:
            try:
                package_spec = importlib.util.find_spec(package_name)
                if package_spec and package_spec.origin:
                    package_path_list = [os.path.dirname(package_spec.origin)]
                    logger.info(f"Recursively scanning for modules in package: {package_name} (path: {package_path_list[0]})")

                    # Use walk_packages to recursively find all modules
                    for module_loader, module_name, is_pkg in pkgutil.walk_packages(
                        path=package_path_list,
                        prefix=package_name + ".",  # Ensures module_name is fully qualified
                        onerror=lambda name: logger.warning(f"Error importing module {name} during scan.")
                    ):
                        if not is_pkg and not module_name.split('.')[-1].startswith("_"):
                            # We are interested in actual modules, not sub-packages themselves for registration
                            # And also skip modules starting with underscore (e.g. __main__.py)
                            try:
                                logger.debug(f"Attempting to auto-register components from module: {module_name}")
                                self.register_module_components(module_name)
                            except ImportError as e:
                                logger.warning(
                                    f"Could not auto-register from {module_name}: Module not found or import error: {e}"
                                )
                            except Exception as e:  # Catch other potential errors during registration
                                logger.error(
                                    f"Unexpected error during auto-registration of {module_name}: {e}",
                                    exc_info=True
                                )
                else:
                    logger.warning(f"Could not find package spec for '{package_name}' to auto-register components/tools.")
            except Exception as e:
                logger.error(f"Error while trying to dynamically register from '{package_name}': {e}", exc_info=True)

    def register_module_components(self, module_or_path: Any) -> None:
        """Scan a module (object or path string) and automatically register.

        - Functions as callables.
        - Pydantic Models and Dataclasses as types.
        - Subclasses of AgentComponent as components.
        """
        try:
            if isinstance(module_or_path, str):
                module = importlib.import_module(module_or_path)
            elif inspect.ismodule(module_or_path):
                module = module_or_path
            else:
                logger.error(
                    f"Invalid input for auto-registration: {module_or_path}. Must be module object or path string."
                )
                return

            logger.info(f"Auto-registering components from module: {module.__name__}")
            registered_count = {"callable": 0, "type": 0, "component": 0}

            for name, obj in inspect.getmembers(module):
                if name.startswith("_"):
                    continue  # Skip private/internal

                # Register Functions as Callables
                if (
                    inspect.isfunction(obj)
                    and obj.__module__ == module.__name__
                ):
                    if self.registry_hub.callables.register_callable(obj):
                        registered_count["callable"] += 1

                # Register Classes (Types and Components)
                elif inspect.isclass(obj) and obj.__module__ == module.__name__:
                    is_component = False
                    
                    # Register as Component if subclass of AgentComponent
                    try:
                        from flock.core.component.agent_component_base import AgentComponent
                        if (
                            issubclass(obj, AgentComponent)
                            and self.registry_hub.components.register_component(obj)
                        ):
                            registered_count["component"] += 1
                            is_component = True  # Mark as component
                    except ImportError:
                        # AgentComponent not available during setup
                        pass

                    # Register as Type if Pydantic Model or Dataclass
                    # A component can also be a type used in signatures
                    base_model_or_dataclass = isinstance(obj, type) and (
                        issubclass(obj, BaseModel) or is_dataclass(obj)
                    )
                    if (
                        base_model_or_dataclass
                        and self.registry_hub.types.register_type(obj)
                        and not is_component
                    ):
                        # Only increment type count if it wasn't already counted as component
                        registered_count["type"] += 1

            logger.info(
                f"Auto-registration summary for {module.__name__}: "
                f"{registered_count['callable']} callables, "
                f"{registered_count['type']} types, "
                f"{registered_count['component']} components."
            )

        except Exception as e:
            logger.error(
                f"Error during auto-registration for {module_or_path}: {e}",
                exc_info=True,
            )
