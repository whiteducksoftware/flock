"""Module for registering and referencing callable objects in serialized formats.

This module provides a registry system that allows callable objects (functions, methods,
lambda expressions, etc.) to be referenced in serialized formats like TOML, which
cannot natively represent Python callables.

Three reference mechanisms are supported:
1. Registry references: callables explicitly registered with the registry
2. Import references: callables that can be imported from modules
3. Pickle fallback: for callables that cannot be referenced by the above methods
"""

import base64
import importlib
import inspect
import pickle
from collections.abc import Callable


class CallableRegistry:
    """Registry for storing and referencing callable objects.

    The CallableRegistry allows callable objects to be registered with a name,
    then referenced in serialized formats like TOML using a string reference.
    It also supports resolving callables from import paths and using pickle
    as a fallback for more complex callables.
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._registry: dict[str, Callable] = {}

    def register(self, name: str, callable_obj: Callable) -> None:
        """Register a callable with a given name.

        Args:
            name: A unique name to identify the callable.
            callable_obj: The callable object to register.

        Raises:
            ValueError: If the name is already registered.
        """
        if name in self._registry:
            raise ValueError(f"Callable already registered with name: {name}")

        self._registry[name] = callable_obj

    def get(self, name: str) -> Callable | None:
        """Get a callable by its registered name.

        Args:
            name: The name of the registered callable.

        Returns:
            The callable object if found, None otherwise.
        """
        return self._registry.get(name)

    def has(self, name: str) -> bool:
        """Check if a name is registered.

        Args:
            name: The name to check.

        Returns:
            True if the name is registered, False otherwise.
        """
        return name in self._registry

    def to_reference(self, callable_obj: Callable) -> str:
        """Convert a callable to a reference string.

        This method tries different strategies to create a reference:
        1. Check if the callable is in the registry
        2. Try to create an import reference if possible
        3. Fall back to pickle if necessary

        Args:
            callable_obj: The callable to convert.

        Returns:
            A string reference that can be used to reconstruct the callable.
        """
        # Strategy 1: Check if callable is in registry (by identity)
        for name, registered_callable in self._registry.items():
            if callable_obj is registered_callable:
                return f"@registry:{name}"

        # Strategy 2: Try import reference for standard functions, methods, and classes
        if self._is_importable(callable_obj):
            module = inspect.getmodule(callable_obj)
            if module and hasattr(callable_obj, "__qualname__"):
                qualname = callable_obj.__qualname__
                return f"@import:{module.__name__}:{qualname}"

        # Strategy 3: Fall back to pickle
        try:
            pickle_bytes = pickle.dumps(callable_obj)
            encoded = base64.b64encode(pickle_bytes).decode("utf-8")
            return f"@pickle:{encoded}"
        except (pickle.PicklingError, TypeError):
            # If we can't pickle, fall back to a simple string representation
            # This won't be reversible, but at least it won't crash
            return f"@unpicklable:function"

    def _is_importable(self, callable_obj: Callable) -> bool:
        """Check if a callable can be imported.

        Args:
            callable_obj: The callable to check.

        Returns:
            True if the callable can be imported, False otherwise.
        """
        # Must have a module
        if (
            not hasattr(callable_obj, "__module__")
            or callable_obj.__module__ is None
        ):
            return False

        # Must have a name
        if (
            not hasattr(callable_obj, "__name__")
            or callable_obj.__name__ == "<lambda>"
        ):
            return False

        # Must not be a local function (inside another function)
        qualname = getattr(callable_obj, "__qualname__", "")
        if "<locals>" in qualname:
            return False

        # Must be a function, method, or class
        if not (
            inspect.isfunction(callable_obj)
            or inspect.ismethod(callable_obj)
            or inspect.isclass(callable_obj)
            or inspect.isbuiltin(callable_obj)
        ):
            return False

        # If it's a method, check if it's bound to an instance
        if inspect.ismethod(callable_obj) and hasattr(callable_obj, "__self__"):
            # For instance methods, we can only reference class methods
            if not isinstance(callable_obj.__self__, type):
                return False

        return True

    def from_reference(self, reference: str) -> Callable:
        """Resolve a reference string back to a callable.

        Args:
            reference: The reference string to resolve.

        Returns:
            The callable object.

        Raises:
            ValueError: If the reference is malformed or cannot be resolved.
            ImportError: If the import reference points to a non-existent module or attribute.
        """
        if not reference.startswith("@"):
            raise ValueError(f"Invalid reference format: {reference}")

        parts = reference.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid reference format: {reference}")

        ref_type, ref_value = parts

        # Registry reference
        if ref_type == "@registry":
            if not self.has(ref_value):
                raise ValueError(
                    f"No callable registered with name: {ref_value}"
                )
            return self.get(ref_value)

        # Import reference
        elif ref_type == "@import":
            import_parts = ref_value.rsplit(":", 1)
            if len(import_parts) != 2:
                raise ValueError(f"Invalid import reference: {ref_value}")

            module_path, attr_path = import_parts
            try:
                module = importlib.import_module(module_path)
            except ImportError:
                raise ImportError(f"Could not import module: {module_path}")

            # Handle nested attributes (e.g., "Class.method")
            obj = module
            try:
                for attr in attr_path.split("."):
                    obj = getattr(obj, attr)
            except AttributeError:
                raise AttributeError(
                    f"Could not find attribute {attr_path} in module {module_path}"
                )

            if not callable(obj):
                raise ValueError(
                    f"Imported object is not callable: {ref_value}"
                )

            return obj

        # Pickle reference
        elif ref_type == "@pickle":
            try:
                pickle_bytes = base64.b64decode(ref_value)
                return pickle.loads(pickle_bytes)
            except Exception as e:
                raise ValueError(f"Failed to unpickle callable: {e}")

        # Unpicklable reference (just a placeholder, can't be reversed)
        elif ref_type == "@unpicklable":
            raise ValueError(
                f"Cannot resolve unpicklable reference: {reference}"
            )

        else:
            raise ValueError(f"Unknown reference type: {ref_type}")
