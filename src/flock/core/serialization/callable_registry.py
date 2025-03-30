"""Registry system for callable objects to support serialization."""

from collections.abc import Callable


class CallableRegistry:
    """Registry for callable objects.

    This class serves as a central registry for callable objects (functions, methods)
    that can be referenced by name in serialized formats.

    This is a placeholder implementation that will be fully implemented in task US007-T004.
    """

    _registry: dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, callable_obj: Callable) -> None:
        """Register a callable object with the given name.

        Args:
            name: Unique name for the callable
            callable_obj: Function or method to register
        """
        cls._registry[name] = callable_obj

    @classmethod
    def get(cls, name: str) -> Callable:
        """Get a callable object by name.

        Args:
            name: Name of the callable to retrieve

        Returns:
            The registered callable

        Raises:
            KeyError: If no callable with the given name is registered
        """
        return cls._registry[name]

    @classmethod
    def contains(cls, name: str) -> bool:
        """Check if a callable with the given name is registered.

        Args:
            name: Name to check

        Returns:
            True if registered, False otherwise
        """
        return name in cls._registry
