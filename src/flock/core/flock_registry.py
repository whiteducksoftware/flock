# src/flock/core/flock_registry.py
"""Centralized registry for managing Agents, Callables, Types, and Component Classes
within the Flock framework to support dynamic lookup and serialization.
"""

from __future__ import annotations  # Add this at the very top

import importlib
import inspect
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
    from flock.core.flock_agent import (
        FlockAgent,  # Import only for type checking
    )
    from flock.core.flock_evaluator import FlockEvaluator
    from flock.core.flock_module import FlockModule
    from flock.core.flock_router import FlockRouter

    COMPONENT_BASE_TYPES = (FlockModule, FlockEvaluator, FlockRouter)
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


class FlockRegistry:
    """Singleton registry for Agents, Callables (functions/methods).

    Types (Pydantic/Dataclasses used in signatures), and Component Classes
    (Modules, Evaluators, Routers).
    """

    _instance = None

    _agents: dict[str, FlockAgent]
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

    # --- Agent Registration ---
    def register_agent(self, agent: FlockAgent) -> None:
        """Registers a FlockAgent instance by its name."""
        if not hasattr(agent, "name") or not agent.name:
            logger.error(
                "Attempted to register an agent without a valid 'name' attribute."
            )
            return
        if agent.name in self._agents and self._agents[agent.name] != agent:
            logger.warning(
                f"Agent '{agent.name}' already registered. Overwriting."
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
                    f"Callable '{path_str}' already registered. Overwriting."
                )
            self._callables[path_str] = func
            logger.debug(f"Registered callable: {path_str}")
            return path_str
        return None

    def get_callable(self, path_str: str) -> Callable:
        """Retrieves a callable by its path string, attempting dynamic import if not found."""
        if path_str in self._callables:
            return self._callables[path_str]

        logger.debug(
            f"Callable '{path_str}' not in registry, attempting dynamic import."
        )
        try:
            if "." not in path_str:  # Built-ins
                builtins_module = importlib.import_module("builtins")
                if hasattr(builtins_module, path_str):
                    func = getattr(builtins_module, path_str)
                    if callable(func):
                        self.register_callable(func, path_str)  # Cache it
                        return func
                raise KeyError(f"Built-in callable '{path_str}' not found.")

            module_name, func_name = path_str.rsplit(".", 1)
            module = importlib.import_module(module_name)
            func = getattr(module, func_name)
            if callable(func):
                self.register_callable(
                    func, path_str
                )  # Cache dynamically imported
                return func
            else:
                raise TypeError(
                    f"Dynamically imported object '{path_str}' is not callable."
                )
        except (ImportError, AttributeError, KeyError, TypeError) as e:
            logger.error(
                f"Failed to dynamically load/find callable '{path_str}': {e}"
            )
            raise KeyError(
                f"Callable '{path_str}' not found or failed to load: {e}"
            ) from e

    def get_callable_path_string(self, func: Callable) -> str | None:
        """Gets the path string for a callable, registering it if necessary."""
        for path_str, registered_func in self._callables.items():
            if func == registered_func:
                return path_str
        # If not found by identity, generate path, register, and return
        return self.register_callable(func)

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
            # logger.debug(f"Registered type: {type_name}")
            return type_name
        return None

    def get_type(self, type_name: str) -> type:
        """Retrieves a registered type by its name."""
        if type_name in self._types:
            return self._types[type_name]
        else:
            # Consider adding dynamic import attempts for types if needed,
            # but explicit registration is generally safer for types.
            logger.error(f"Type '{type_name}' not found in registry.")
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
def flock_component(cls: ClassType) -> ClassType: ...
@overload
def flock_component(
    *, name: str | None = None
) -> Callable[[ClassType], ClassType]: ...


def flock_component(
    cls: ClassType | None = None, *, name: str | None = None
) -> Any:
    """Decorator to register a Flock Component class (Module, Evaluator, Router).

    Usage:
        @flock_component
        class MyModule(FlockModule): ...

        @flock_component(name="CustomRouterAlias")
        class MyRouter(FlockRouter): ...
    """
    registry = get_registry()

    def decorator(inner_cls: ClassType) -> ClassType:
        if not inspect.isclass(inner_cls):
            raise TypeError("@flock_component can only decorate classes.")
        component_name = name or inner_cls.__name__
        registry.register_component(inner_cls, name=component_name)
        return inner_cls

    if cls is None:
        # Called as @flock_component(name="...")
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
# flock_callable = flock_tool


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
def _auto_register_by_path():
    components_to_register = [
        (
            "flock.evaluators.declarative.declarative_evaluator",
            "DeclarativeEvaluator",
        ),
        ("flock.evaluators.memory.memory_evaluator", "MemoryEvaluator"),
        ("flock.modules.output.output_module", "OutputModule"),
        ("flock.modules.performance.metrics_module", "MetricsModule"),
        ("flock.modules.memory.memory_module", "MemoryModule"),
        # ("flock.modules.hierarchical.module", "HierarchicalMemoryModule"), # Uncomment if exists
        ("flock.routers.default.default_router", "DefaultRouter"),
        ("flock.routers.llm.llm_router", "LLMRouter"),
        ("flock.routers.agent.agent_router", "AgentRouter"),
    ]
    for module_path, class_name in components_to_register:
        try:
            module = importlib.import_module(module_path)
            component_class = getattr(module, class_name)
            _registry_instance.register_component(component_class)
        except (ImportError, AttributeError) as e:
            logger.warning(f"{class_name} not found for auto-registration: {e}")

    # Auto-register standard tools by scanning modules
    tool_modules = [
        "flock.core.tools.basic_tools",
        "flock.core.tools.azure_tools",
        "flock.core.tools.dev_tools.github",
        "flock.core.tools.llm_tools",
        "flock.core.tools.markdown_tools",
    ]
    for module_path in tool_modules:
        try:
            _registry_instance.register_module_components(module_path)
        except ImportError as e:
            logger.warning(
                f"Could not auto-register tools from {module_path}: {e}"
            )


# Bootstrapping the registry
# _auto_register_by_path()
