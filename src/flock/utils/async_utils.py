"""Async utility decorators and helpers."""

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar


T = TypeVar("T")


class AsyncLockRequired:
    """Decorator ensuring async lock acquisition.

    This utility eliminates 15+ duplicate lock acquisition patterns
    scattered throughout orchestrator.py and agent.py.
    """

    def __init__(self, lock_attr: str = "_lock"):
        """
        Initialize decorator.

        Args:
            lock_attr: Name of lock attribute on class (default: "_lock")
        """
        self.lock_attr = lock_attr

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Apply decorator to function."""
        lock_attr = self.lock_attr  # Capture in closure

        @wraps(func)
        async def wrapper(instance: Any, *args: Any, **kwargs: Any) -> Any:
            lock = getattr(instance, lock_attr)
            async with lock:
                return await func(instance, *args, **kwargs)

        return wrapper


def async_lock_required(lock_attr: str = "_lock") -> AsyncLockRequired:
    """
    Decorator ensuring async lock acquisition.

    This decorator automatically acquires and releases an async lock
    before executing the decorated method, preventing race conditions.

    Args:
        lock_attr: Name of the lock attribute on the class (default: "_lock")

    Returns:
        AsyncLockRequired decorator instance

    Example:
        >>> class MyClass:
        ...     def __init__(self):
        ...         self._lock = asyncio.Lock()
        ...
        ...     @async_lock_required()
        ...     async def my_method(self):
        ...         # Lock automatically acquired here
        ...         await asyncio.sleep(0.1)
        ...         return "done"

        >>> obj = MyClass()
        >>> result = await obj.my_method()  # Lock acquired/released automatically
    """
    return AsyncLockRequired(lock_attr)
