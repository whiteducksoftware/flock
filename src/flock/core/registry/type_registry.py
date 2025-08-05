# src/flock/core/registry/type_registry.py
"""Type registration and lookup functionality."""

import threading
from typing import Any, Literal, Mapping, Optional, Sequence, TypeVar, Union

from flock.core.logging.logging import get_logger

logger = get_logger("registry.types")


class TypeRegistry:
    """Manages type registration and lookup with thread safety."""

    def __init__(self, lock: threading.RLock):
        self._lock = lock
        self._types: dict[str, type] = {}
        self._register_core_types()

    def register_type(self, type_obj: type, name: str | None = None) -> str | None:
        """Register a class/type (Pydantic, Dataclass, etc.) used in signatures."""
        type_name = name or type_obj.__name__
        if not type_name:
            logger.error(f"Could not determine name for type: {type_obj}")
            return None

        with self._lock:
            if type_name in self._types and self._types[type_name] != type_obj:
                logger.warning(f"Type '{type_name}' already registered. Overwriting.")
            
            self._types[type_name] = type_obj
            logger.debug(f"Registered type: {type_name}")
            return type_name

    def get_type(self, type_name: str) -> type:
        """Retrieve a registered type by its name."""
        with self._lock:
            if type_name in self._types:
                return self._types[type_name]
            
            # Consider adding dynamic import attempts for types if needed,
            # but explicit registration is generally safer for types.
            logger.warning(f"Type '{type_name}' not found in registry. Will attempt to build it from builtins.")
            raise KeyError(f"Type '{type_name}' not found. Ensure it is registered.")

    def get_all_types(self) -> dict[str, type]:
        """Get all registered types."""
        with self._lock:
            return self._types.copy()

    def clear(self) -> None:
        """Clear all registered types (except core types)."""
        with self._lock:
            # Save core types
            core_types = {
                name: type_obj for name, type_obj in self._types.items()
                if type_obj in [str, int, float, bool, list, dict, tuple, set, Any, Mapping, Sequence, TypeVar, Literal, Optional, Union]
            }
            self._types.clear()
            self._types.update(core_types)
            logger.debug("Cleared all registered types (keeping core types)")

    def _register_core_types(self):
        """Register common built-in and typing types."""
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
