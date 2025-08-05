# src/flock/core/registry/decorators.py
"""Registry decorators for component, tool, and type registration."""

import inspect
from collections.abc import Callable
from typing import Any, TypeVar, overload

from flock.core.registry.registry_hub import get_registry

ClassType = TypeVar("ClassType", bound=type)
FuncType = TypeVar("FuncType", bound=Callable)
ConfigType = TypeVar("ConfigType")


# --- Component Registration Decorator ---

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
        registry.register_component(inner_cls, name=component_name)

        # If config_class is provided, register the mapping
        if config_class:
            registry.register_config_component_pair(config_class, inner_cls)

        return inner_cls

    if cls is None:
        # Called as @flock_component(name="...", config_class=...)
        return decorator
    else:
        # Called as @flock_component
        return decorator(cls)


# --- Tool/Callable Registration Decorator ---

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


# Alias for clarity
flock_callable = flock_tool


# --- Type Registration Decorator ---

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
