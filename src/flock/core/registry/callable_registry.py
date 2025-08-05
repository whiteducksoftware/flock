# src/flock/core/registry/callable_registry.py
"""Callable function/method registration and lookup functionality."""

import builtins
import importlib
import threading
from collections.abc import Callable
from typing import Any

from flock.core.logging.logging import get_logger

logger = get_logger("registry.callables")


class CallableRegistry:
    """Manages callable registration with smart lookup and thread safety."""

    def __init__(self, lock: threading.RLock):
        self._lock = lock
        self._callables: dict[str, Callable] = {}

    def register_callable(self, func: Callable, name: str | None = None) -> str | None:
        """Register a callable (function/method). Returns its path string identifier."""
        path_str = name or self._get_path_string(func)
        if not path_str:
            logger.warning(f"Could not register callable {getattr(func, '__name__', 'unknown')}: Unable to determine path string")
            return None

        with self._lock:
            if path_str in self._callables and self._callables[path_str] != func:
                logger.warning(f"Callable '{path_str}' already registered with a different function. Overwriting.")
            
            self._callables[path_str] = func
            logger.debug(f"Registered callable: '{path_str}' ({getattr(func, '__name__', 'unknown')})")
            return path_str

    def get_callable(self, name_or_path: str) -> Callable:
        """Retrieve a callable by its registered name or full path string.
        
        Attempts dynamic import if not found directly. Prioritizes exact match,
        then searches for matches ending with '.{name}'.
        """
        # 1. Try exact match first (covers full paths and simple names if registered that way)
        with self._lock:
            if name_or_path in self._callables:
                logger.debug(f"Found callable '{name_or_path}' directly in registry.")
                return self._callables[name_or_path]

        # 2. If not found, and it looks like a simple name, search registered paths
        if "." not in name_or_path:
            with self._lock:
                matches = []
                for path_str, func in self._callables.items():
                    # Check if path ends with ".{simple_name}" or exactly matches simple_name
                    if path_str == name_or_path or path_str.endswith(f".{name_or_path}"):
                        matches.append(func)

                if len(matches) == 1:
                    logger.debug(f"Found unique callable for simple name '{name_or_path}' via path '{self.get_callable_path_string(matches[0])}'.")
                    return matches[0]
                elif len(matches) > 1:
                    # Ambiguous simple name - require full path
                    found_paths = [self.get_callable_path_string(f) for f in matches]
                    logger.error(f"Ambiguous callable name '{name_or_path}'. Found matches: {found_paths}. Use full path string for lookup.")
                    raise KeyError(f"Ambiguous callable name '{name_or_path}'. Use full path string.")

        # 3. Attempt dynamic import if it looks like a full path
        if "." in name_or_path:
            logger.debug(f"Callable '{name_or_path}' not in registry cache, attempting dynamic import.")
            try:
                module_name, func_name = name_or_path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                func = getattr(module, func_name)
                if callable(func):
                    self.register_callable(func, name_or_path)  # Cache dynamically imported
                    logger.info(f"Successfully imported and registered module callable '{name_or_path}'")
                    return func
                else:
                    raise TypeError(f"Dynamically imported object '{name_or_path}' is not callable.")
            except (ImportError, AttributeError, TypeError) as e:
                logger.error(f"Failed to dynamically load/find callable '{name_or_path}': {e}", exc_info=False)

        # 4. Handle built-ins if not found yet (might be redundant if simple name check worked)
        elif name_or_path in builtins.__dict__:
            func = builtins.__dict__[name_or_path]
            if callable(func):
                self.register_callable(func, name_or_path)  # Cache it
                logger.info(f"Found and registered built-in callable '{name_or_path}'")
                return func

        # 5. Final failure
        logger.error(f"Callable '{name_or_path}' not found in registry or via import.")
        raise KeyError(f"Callable '{name_or_path}' not found.")

    def get_callable_path_string(self, func: Callable) -> str | None:
        """Get the path string for a callable, registering it if necessary."""
        # First try to find by direct identity
        with self._lock:
            for path_str, registered_func in self._callables.items():
                if func == registered_func:
                    logger.debug(f"Found existing path string for callable: '{path_str}'")
                    return path_str

        # If not found by identity, generate path, register, and return
        path_str = self.register_callable(func)
        if path_str:
            logger.debug(f"Generated and registered new path string for callable: '{path_str}'")
        else:
            logger.warning(f"Failed to generate path string for callable {getattr(func, '__name__', 'unknown')}")

        return path_str

    def get_all_callables(self) -> dict[str, Callable]:
        """Get all registered callables."""
        with self._lock:
            return self._callables.copy()

    def clear(self) -> None:
        """Clear all registered callables."""
        with self._lock:
            self._callables.clear()
            logger.debug("Cleared all registered callables")

    @staticmethod
    def _get_path_string(obj: Callable | type) -> str | None:
        """Generate a unique path string 'module.ClassName' or 'module.function_name'."""
        try:
            module = obj.__module__
            name = obj.__name__
            if module == "builtins":
                return name
            # Check if it's nested (basic check, might not cover all edge cases)
            if "." in name and hasattr(__import__(module).__dict__, name.split(".")[0]):
                # Likely a nested class/method - serialization might need custom handling or pickle
                logger.warning(f"Object {name} appears nested in {module}. Path string might be ambiguous.")
            return f"{module}.{name}"
        except AttributeError:
            logger.warning(f"Could not determine module/name for object: {obj}")
            return None
