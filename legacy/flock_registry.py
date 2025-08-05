# src/flock/core/flock_registry.py
"""Centralized registry for managing Agents, Callables, Types, and Component Classes
within the Flock framework to support dynamic lookup and serialization.
"""

from __future__ import annotations  # Add this at the very top

import builtins
import importlib
import inspect
import os
import pkgutil
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import is_dataclass
from typing import (  # Add TYPE_CHECKING
    TYPE_CHECKING,
    Any,
    Literal,
    Optional,
    TypeVar,
    Union,
    overload,
)

from pydantic import BaseModel

if TYPE_CHECKING:
    from flock.core.component.agent_component_base import AgentComponent
    from flock.core.flock_agent import (
        FlockAgent,  # Import only for type checking
    )
    from flock.core.mcp.flock_mcp_server import FlockMCPServer

    COMPONENT_BASE_TYPES = (AgentComponent,)

    IS_COMPONENT_CHECK_ENABLED = True
else:
    # Define dummy types or skip check if not type checking
    FlockAgent = Any  # Or define a dummy class
    COMPONENT_BASE_TYPES = ()
    IS_COMPONENT_CHECK_ENABLED = False

# Fallback if core types aren't available during setup
from flock.core.logging.logging import get_logger

logger = get_logger("registry")
T = TypeVar("T")
ClassType = TypeVar("ClassType", bound=type)
FuncType = TypeVar("FuncType", bound=Callable)
ConfigType = TypeVar("ConfigType", bound=BaseModel)
_COMPONENT_CONFIG_MAP: dict[type[BaseModel], type[any]] = {}


class FlockRegistry:
    """Singleton registry for Agents, Callables (functions/methods) and MCP Servers.

    Types (Pydantic/Dataclasses used in signatures), and Component Classes
    (Modules, Evaluators, Routers).
    """

    _instance = None

    _agents: dict[str, FlockAgent]
    _servers: dict[str, FlockMCPServer]
    _callables: dict[str, Callable]
    _types: dict[str, type]
    _components: dict[str, type]  # For Module, Evaluator, Router classes

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
            # logger.info("FlockRegistry instance created.")
        return cls._instance

    def _initialize(self):
        """Initialize the internal dictionaries."""
        self._agents = {}
        self._servers = {}
        self._callables = {}
        self._types = {}
        self._components = {}
        # logger.debug("FlockRegistry initialized internal stores.")
        # Auto-register core Python types
        self._register_core_types()

    def _register_core_types(self):
        """Registers common built-in and typing types."""
        core_types = [
            str,
            int,
            float,
            bool,
            list,
            dict,
            tuple,
            set,
            Any,
            Mapping,
            Sequence,
            TypeVar,
            Literal,
            Optional,
            Union,  # Common typing generics
        ]
        for t in core_types:
            try:
                self.register_type(t)
            except Exception as e:
                logger.error(f"Failed to auto-register core type {t}: {e}")

    @staticmethod
    def register_config_component_pair(
        config_cls: type[ConfigType], component_cls: type[ClassType]
    ):
        """Explicitly registers the mapping between a config and component class."""
        # Component config validation can be added here if needed
        # Add more checks if needed (e.g., component_cls inherits from Module/Router/Evaluator)

        if (
            config_cls in _COMPONENT_CONFIG_MAP
            and _COMPONENT_CONFIG_MAP[config_cls] != component_cls
        ):
            logger.warning(
                f"Config class {config_cls.__name__} already mapped to {_COMPONENT_CONFIG_MAP[config_cls].__name__}. Overwriting with {component_cls.__name__}."
            )

        _COMPONENT_CONFIG_MAP[config_cls] = component_cls
        logger.debug(
            f"Registered config mapping: {config_cls.__name__} -> {component_cls.__name__}"
        )

    @staticmethod
    def get_component_class_for_config(
        config_cls: type[ConfigType],
    ) -> type[ClassType] | None:
        """Looks up the Component Class associated with a Config Class."""
        return _COMPONENT_CONFIG_MAP.get(config_cls)

    # --- Path String Generation ---
    @staticmethod
    def _get_path_string(obj: Callable | type) -> str | None:
        """Generates a unique path string 'module.ClassName' or 'module.function_name'."""
        try:
            module = obj.__module__
            name = obj.__name__
            if module == "builtins":
                return name
            # Check if it's nested (basic check, might not cover all edge cases)
            if "." in name and hasattr(sys.modules[module], name.split(".")[0]):
                # Likely a nested class/method - serialization might need custom handling or pickle
                logger.warning(
                    f"Object {name} appears nested in {module}. Path string might be ambiguous."
                )
            return f"{module}.{name}"
        except AttributeError:
            logger.warning(f"Could not determine module/name for object: {obj}")
            return None

    # --- Server Registration ---
    def register_server(self, server: FlockMCPServer) -> None:
        """Registers a flock mcp server by its name."""
        if not hasattr(server.config, "name") or not server.config.name:
            logger.error(
                "Attempted to register a server without a valid 'name' attribute."
            )
            return
        if (
            server.config.name in self._servers
            and self._servers[server.config.name] != server
        ):
            logger.warning(
                f"Server '{server.config.name}' already registered. Overwriting."
            )
        self._servers[server.config.name] = server
        logger.debug(f"Registered server: {server.config.name}")

    def get_server(self, name: str) -> FlockMCPServer | None:
        """Retrieves a registered FlockMCPServer instance by name."""
        server = self._servers.get(name)
        if not server:
            logger.warning(f"Server '{name}' not found in registry.")
        return server

    def get_all_server_names(self) -> list[str]:
        """Returns a list of names for all registered servers."""
        return list(self._servers.keys())

    # --- Agent Registration ---
    def register_agent(self, agent: FlockAgent, *, force: bool = False) -> None:
        """Registers a FlockAgent instance by its name.

        Args:
            agent: The agent instance to register.
            force: If True, allow overwriting an existing **different** agent registered under the same name.
                   If False and a conflicting registration exists, a ValueError is raised.
        """
        if not hasattr(agent, "name") or not agent.name:
            logger.error(
                "Attempted to register an agent without a valid 'name' attribute."
            )
            return

        if agent.name in self._agents and self._agents[agent.name] is not agent:
            # Same agent already registered → silently ignore; different instance → error/force.
            if not force:
                raise ValueError(
                    f"Agent '{agent.name}' already registered with a different instance. "
                    "Pass force=True to overwrite the existing registration."
                )
            logger.warning(
                f"Overwriting existing agent '{agent.name}' registration due to force=True."
            )

        self._agents[agent.name] = agent
        logger.debug(f"Registered agent: {agent.name}")

    def get_agent(self, name: str) -> FlockAgent | None:
        """Retrieves a registered FlockAgent instance by name."""
        agent = self._agents.get(name)
        if not agent:
            logger.warning(f"Agent '{name}' not found in registry.")
        return agent

    def get_all_agent_names(self) -> list[str]:
        """Returns a list of names of all registered agents."""
        return list(self._agents.keys())

    # --- Callable Registration ---
    def register_callable(
        self, func: Callable, name: str | None = None
    ) -> str | None:
        """Registers a callable (function/method). Returns its path string identifier."""
        path_str = name or self._get_path_string(func)
        if path_str:
            if (
                path_str in self._callables
                and self._callables[path_str] != func
            ):
                logger.warning(
                    f"Callable '{path_str}' already registered with a different function. Overwriting."
                )
            self._callables[path_str] = func
            logger.debug(f"Registered callable: '{path_str}' ({func.__name__})")
            return path_str
        logger.warning(
            f"Could not register callable {func.__name__}: Unable to determine path string"
        )
        return None

    def get_callable(self, name_or_path: str) -> Callable:
        """Retrieves a callable by its registered name or full path string.
        Attempts dynamic import if not found directly. Prioritizes exact match,
        then searches for matches ending with '.{name}'.
        """
        # 1. Try exact match first (covers full paths and simple names if registered that way)
        if name_or_path in self._callables:
            logger.debug(
                f"Found callable '{name_or_path}' directly in registry."
            )
            return self._callables[name_or_path]

        # 2. If not found, and it looks like a simple name, search registered paths
        if "." not in name_or_path:
            matches = []
            for path_str, func in self._callables.items():
                # Check if path ends with ".{simple_name}" or exactly matches simple_name
                if path_str == name_or_path or path_str.endswith(
                    f".{name_or_path}"
                ):
                    matches.append(func)

            if len(matches) == 1:
                logger.debug(
                    f"Found unique callable for simple name '{name_or_path}' via path '{self.get_callable_path_string(matches[0])}'."
                )
                return matches[0]
            elif len(matches) > 1:
                # Ambiguous simple name - require full path
                found_paths = [
                    self.get_callable_path_string(f) for f in matches
                ]
                logger.error(
                    f"Ambiguous callable name '{name_or_path}'. Found matches: {found_paths}. Use full path string for lookup."
                )
                raise KeyError(
                    f"Ambiguous callable name '{name_or_path}'. Use full path string."
                )
            # else: Not found by simple name search in registry, proceed to dynamic import

        # 3. Attempt dynamic import if it looks like a full path
        if "." in name_or_path:
            logger.debug(
                f"Callable '{name_or_path}' not in registry cache, attempting dynamic import."
            )
            try:
                module_name, func_name = name_or_path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                func = getattr(module, func_name)
                if callable(func):
                    self.register_callable(
                        func, name_or_path
                    )  # Cache dynamically imported
                    logger.info(
                        f"Successfully imported and registered module callable '{name_or_path}'"
                    )
                    return func
                else:
                    raise TypeError(
                        f"Dynamically imported object '{name_or_path}' is not callable."
                    )
            except (ImportError, AttributeError, TypeError) as e:
                logger.error(
                    f"Failed to dynamically load/find callable '{name_or_path}': {e}",
                    exc_info=False,
                )
                # Fall through to raise KeyError
        # 4. Handle built-ins if not found yet (might be redundant if simple name check worked)
        elif name_or_path in builtins.__dict__:
            func = builtins.__dict__[name_or_path]
            if callable(func):
                self.register_callable(func, name_or_path)  # Cache it
                logger.info(
                    f"Found and registered built-in callable '{name_or_path}'"
                )
                return func

        # 5. Final failure
        logger.error(
            f"Callable '{name_or_path}' not found in registry or via import."
        )
        raise KeyError(f"Callable '{name_or_path}' not found.")

    def get_callable_path_string(self, func: Callable) -> str | None:
        """Gets the path string for a callable, registering it if necessary."""
        # First try to find by direct identity
        for path_str, registered_func in self._callables.items():
            if func == registered_func:
                logger.debug(
                    f"Found existing path string for callable: '{path_str}'"
                )
                return path_str

        # If not found by identity, generate path, register, and return
        path_str = self.register_callable(func)
        if path_str:
            logger.debug(
                f"Generated and registered new path string for callable: '{path_str}'"
            )
        else:
            logger.warning(
                f"Failed to generate path string for callable {func.__name__}"
            )

        return path_str

    # --- Type Registration ---
    def register_type(
        self, type_obj: type, name: str | None = None
    ) -> str | None:
        """Registers a class/type (Pydantic, Dataclass, etc.) used in signatures."""
        type_name = name or type_obj.__name__
        if type_name:
            if type_name in self._types and self._types[type_name] != type_obj:
                logger.warning(
                    f"Type '{type_name}' already registered. Overwriting."
                )
            self._types[type_name] = type_obj
            logger.debug(f"Registered type: {type_name}")
            return type_name
        return None

    def get_type(self, type_name: str) -> type:
        """Retrieves a registered type by its name."""
        if type_name in self._types:
            return self._types[type_name]
        else:
            # Consider adding dynamic import attempts for types if needed,
            # but explicit registration is generally safer for types.
            logger.warning(f"Type '{type_name}' not found in registry. Will attempt to build it from builtins.")
            raise KeyError(
                f"Type '{type_name}' not found. Ensure it is registered."
            )

    # --- Component Class Registration ---
    def register_component(
        self, component_class: type, name: str | None = None
    ) -> str | None:
        """Registers a component class (Module, Evaluator, Router)."""
        type_name = name or component_class.__name__
        if type_name:
            # Optional: Add check if it's a subclass of expected bases
            # if COMPONENT_BASE_TYPES and not issubclass(component_class, COMPONENT_BASE_TYPES):
            #     logger.warning(f"Registering class '{type_name}' which is not a standard Flock component type.")
            if (
                type_name in self._components
                and self._components[type_name] != component_class
            ):
                logger.warning(
                    f"Component class '{type_name}' already registered. Overwriting."
                )
            self._components[type_name] = component_class
            logger.debug(f"Registered component class: {type_name}")
            return type_name
        return None

    def get_component(self, type_name: str) -> type:
        """Retrieves a component class by its type name."""
        if type_name in self._components:
            return self._components[type_name]
        else:
            # Dynamic import attempts similar to get_callable could be added here if desired,
            # targeting likely module locations based on type_name conventions.
            logger.error(
                f"Component class '{type_name}' not found in registry."
            )
            raise KeyError(
                f"Component class '{type_name}' not found. Ensure it is registered."
            )

    def get_component_type_name(self, component_class: type) -> str | None:
        """Gets the type name for a component class, registering it if necessary."""
        for type_name, registered_class in self._components.items():
            if component_class == registered_class:
                return type_name
        # If not found, register using class name and return
        return self.register_component(component_class)

    # --- Auto-Registration ---
    def register_module_components(self, module_or_path: Any) -> None:
        """Scans a module (object or path string) and automatically registers.

        - Functions as callables.
        - Pydantic Models and Dataclasses as types.
        - Subclasses of FlockModule, FlockEvaluator, FlockRouter as components.
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

            logger.info(
                f"Auto-registering components from module: {module.__name__}"
            )
            registered_count = {"callable": 0, "type": 0, "component": 0}

            for name, obj in inspect.getmembers(module):
                if name.startswith("_"):
                    continue  # Skip private/internal

                # Register Functions as Callables
                if (
                    inspect.isfunction(obj)
                    and obj.__module__ == module.__name__
                ):
                    if self.register_callable(obj):
                        registered_count["callable"] += 1

                # Register Classes (Types and Components)
                elif inspect.isclass(obj) and obj.__module__ == module.__name__:
                    is_component = False
                    # Register as Component if subclass of base types
                    if (
                        COMPONENT_BASE_TYPES
                        and issubclass(obj, COMPONENT_BASE_TYPES)
                        and self.register_component(obj)
                    ):
                        registered_count["component"] += 1
                        is_component = True  # Mark as component

                    # Register as Type if Pydantic Model or Dataclass
                    # A component can also be a type used in signatures
                    base_model_or_dataclass = isinstance(obj, type) and (
                        issubclass(obj, BaseModel) or is_dataclass(obj)
                    )
                    if (
                        base_model_or_dataclass
                        and self.register_type(obj)
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


# --- Initialize Singleton ---
_registry_instance = FlockRegistry()


# --- Convenience Access ---
# Provide a function to easily get the singleton instance
def get_registry() -> FlockRegistry:
    """Returns the singleton FlockRegistry instance."""
    return _registry_instance


# Type hinting for decorators to preserve signature
@overload
def flock_component(cls: ClassType) -> ClassType: ...  # Basic registration


@overload
def flock_component(
    *, name: str | None = None, config_class: type[ConfigType] | None = None
) -> Callable[[ClassType], ClassType]: ...  # With options


def flock_component(
    cls: ClassType | None = None,
    *,
    name: str | None = None,
    config_class: type[ConfigType] | None = None,
) -> Any:
    """Decorator to register a Flock Component class and optionally link its config class."""
    registry = get_registry()

    def decorator(inner_cls: ClassType) -> ClassType:
        if not inspect.isclass(inner_cls):
            raise TypeError("@flock_component can only decorate classes.")

        component_name = name or inner_cls.__name__
        registry.register_component(
            inner_cls, name=component_name
        )  # Register component by name

        # If config_class is provided, register the mapping
        if config_class:
            FlockRegistry.register_config_component_pair(
                config_class, inner_cls
            )

        return inner_cls

    if cls is None:
        # Called as @flock_component(name="...", config_class=...)
        return decorator
    else:
        # Called as @flock_component
        return decorator(cls)


# Type hinting for decorators
@overload
def flock_tool(func: FuncType) -> FuncType: ...


@overload
def flock_tool(
    *, name: str | None = None
) -> Callable[[FuncType], FuncType]: ...


def flock_tool(func: FuncType | None = None, *, name: str | None = None) -> Any:
    """Decorator to register a callable function/method as a Tool (or general callable).

    Usage:
        @flock_tool
        def my_web_search(query: str): ...

        @flock_tool(name="utils.calculate_pi")
        def compute_pi(): ...
    """
    registry = get_registry()

    def decorator(inner_func: FuncType) -> FuncType:
        if not callable(inner_func):
            raise TypeError("@flock_tool can only decorate callables.")
        # Let registry handle default name generation if None
        registry.register_callable(inner_func, name=name)
        return inner_func

    if func is None:
        # Called as @flock_tool(name="...")
        return decorator
    else:
        # Called as @flock_tool
        return decorator(func)


# Alias for clarity if desired
flock_callable = flock_tool


@overload
def flock_type(cls: ClassType) -> ClassType: ...


@overload
def flock_type(
    *, name: str | None = None
) -> Callable[[ClassType], ClassType]: ...


def flock_type(cls: ClassType | None = None, *, name: str | None = None) -> Any:
    """Decorator to register a Type (Pydantic Model, Dataclass) used in signatures.

    Usage:
        @flock_type
        class MyDataModel(BaseModel): ...

        @flock_type(name="UserInput")
        @dataclass
        class UserQuery: ...
    """
    registry = get_registry()

    def decorator(inner_cls: ClassType) -> ClassType:
        if not inspect.isclass(inner_cls):
            raise TypeError("@flock_type can only decorate classes.")
        type_name = name or inner_cls.__name__
        registry.register_type(inner_cls, name=type_name)
        return inner_cls

    if cls is None:
        # Called as @flock_type(name="...")
        return decorator
    else:
        # Called as @flock_type
        return decorator(cls)


# --- Auto-register known core components and tools ---
def _auto_register_by_path(self):
    # List of base packages to scan for components and tools
    packages_to_scan = [
        "flock.tools",
        "flock.evaluators",
        "flock.modules",
        "flock.routers",
    ]

    for package_name in packages_to_scan:
        try:
            package_spec = importlib.util.find_spec(package_name)
            if package_spec and package_spec.origin:
                package_path_list = [os.path.dirname(package_spec.origin)]
                logger.info(f"Recursively scanning for modules in package: {package_name} (path: {package_path_list[0]})")

                # Use walk_packages to recursively find all modules
                for module_loader, module_name, is_pkg in pkgutil.walk_packages(
                    path=package_path_list,
                    prefix=package_name + ".", # Ensures module_name is fully qualified
                    onerror=lambda name: logger.warning(f"Error importing module {name} during scan.")
                ):
                    if not is_pkg and not module_name.split('.')[-1].startswith("_"):
                        # We are interested in actual modules, not sub-packages themselves for registration
                        # And also skip modules starting with underscore (e.g. __main__.py)
                        try:
                            logger.debug(f"Attempting to auto-register components from module: {module_name}")
                            _registry_instance.register_module_components(module_name)
                        except ImportError as e:
                            logger.warning(
                                f"Could not auto-register from {module_name}: Module not found or import error: {e}"
                            )
                        except Exception as e: # Catch other potential errors during registration
                            logger.error(
                                f"Unexpected error during auto-registration of {module_name}: {e}",
                                exc_info=True
                            )
            else:
                logger.warning(f"Could not find package spec for '{package_name}' to auto-register components/tools.")
        except Exception as e:
            logger.error(f"Error while trying to dynamically register from '{package_name}': {e}", exc_info=True)

# Bootstrapping the registry
# _auto_register_by_path() # Commented out or removed

# Make the registration function public and rename it
FlockRegistry.discover_and_register_components = _auto_register_by_path
