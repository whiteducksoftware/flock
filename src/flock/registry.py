from __future__ import annotations


"""Runtime registries for blackboard artifact and function declarations."""

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel


if TYPE_CHECKING:
    from collections.abc import Callable


class RegistryError(RuntimeError):
    """Raised when a registry operation fails."""


class TypeRegistry:
    """In-memory registry for blackboard artifact types."""

    def __init__(self) -> None:
        self._by_name: dict[str, type[BaseModel]] = {}
        self._by_cls: dict[type[BaseModel], str] = {}

    def register(self, model: type[BaseModel], name: str | None = None) -> str:
        if not issubclass(model, BaseModel):
            raise RegistryError(
                "Only Pydantic models can be registered as artifact types."
            )
        type_name = (
            name
            or getattr(model, "__flock_type__", None)
            or f"{model.__module__}.{model.__name__}"
        )
        existing_model = self._by_name.get(type_name)
        if existing_model is not None and existing_model is not model:
            self._by_cls.pop(existing_model, None)
        existing_name = self._by_cls.get(model)
        if existing_name and existing_name != type_name:
            self._by_name.pop(existing_name, None)

        self._by_name[type_name] = model
        self._by_cls[model] = type_name
        model.__flock_type__ = type_name
        return type_name

    def resolve(self, type_name: str) -> type[BaseModel]:
        try:
            return self._by_name[type_name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise RegistryError(f"Unknown artifact type '{type_name}'.") from exc

    def resolve_name(self, type_name: str) -> str:
        """
        Resolve a type name (simple or qualified) to its canonical form.

        Args:
            type_name: Simple name ("Document") or qualified ("__main__.Document")

        Returns:
            Canonical type name from registry

        Raises:
            RegistryError: Type not found or ambiguous
        """
        # If already canonical, return as-is (O(1) lookup)
        if type_name in self._by_name:
            return type_name

        # Search for models with matching simple name (O(n) scan)
        matches = []
        for canonical_name, model_cls in self._by_name.items():
            if model_cls.__name__ == type_name:
                matches.append(canonical_name)

        if len(matches) == 0:
            raise RegistryError(f"Unknown artifact type '{type_name}'.")
        if len(matches) == 1:
            return matches[0]
        raise RegistryError(
            f"Ambiguous type name '{type_name}'. Matches: {', '.join(matches)}. Use qualified name."
        )

    def name_for(self, model: type[BaseModel]) -> str:
        try:
            return self._by_cls[model]
        except KeyError as exc:
            raise RegistryError(
                f"Model '{model.__name__}' is not registered as an artifact type."
            ) from exc


class FunctionRegistry:
    """Registry for deterministic callable helpers (flock_tool)."""

    def __init__(self) -> None:
        self._callables: dict[str, Callable[..., Any]] = {}

    def register(self, func: Callable[..., Any], *, name: str | None = None) -> str:
        func_name = name or getattr(func, "__flock_tool__", None) or func.__name__
        existing = self._callables.get(func_name)
        if existing is func:
            return func_name
        self._callables[func_name] = func
        func.__flock_tool__ = func_name
        return func_name

    def resolve(self, func_name: str) -> Callable[..., Any]:
        try:
            return self._callables[func_name]
        except KeyError as exc:
            raise RegistryError(
                f"Function '{func_name}' is not registered with flock_tool."
            ) from exc


type_registry = TypeRegistry()
function_registry = FunctionRegistry()


def flock_type(model: type[BaseModel] | None = None, *, name: str | None = None) -> Any:
    """Decorator to register a Pydantic model as a blackboard artifact type."""

    def _wrap(cls: type[BaseModel]) -> type[BaseModel]:
        type_registry.register(cls, name=name)
        return cls

    if model is None:
        return _wrap
    return _wrap(model)


def flock_tool(
    func: Callable[..., Any] | None = None, *, name: str | None = None
) -> Any:
    """Decorator to register a deterministic helper function for agents."""

    def _wrap(callable_: Callable[..., Any]) -> Callable[..., Any]:
        function_registry.register(callable_, name=name)
        return callable_

    if func is None:
        return _wrap
    return _wrap(func)


__all__ = [
    "RegistryError",
    "flock_tool",
    "flock_type",
    "function_registry",
    "type_registry",
]
