# src/flock/core/serialization/serialization_utils.py
"""Utilities for recursive serialization/deserialization with callable handling."""

import importlib
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    pass

from flock.core.logging.logging import get_logger

logger = get_logger("serialization.utils")

# Remove this line to avoid circular import at module level
# FlockRegistry = get_registry()  # Get singleton instance

# --- Serialization Helper ---


def serialize_item(item: Any) -> Any:
    """Recursively prepares an item for serialization (e.g., to dict for YAML/JSON).
    Converts known callables to their path strings using FlockRegistry.
    Converts Pydantic models using model_dump.
    """
    # Import the registry lazily when needed
    from flock.core.flock_registry import get_registry

    FlockRegistry = get_registry()

    if isinstance(item, BaseModel):
        dumped = item.model_dump(mode="json", exclude_none=True)
        return serialize_item(dumped)
    elif callable(item) and not isinstance(item, type):
        path_str = FlockRegistry.get_callable_path_string(
            item
        )  # Use registry helper
        if path_str:
            return {"__callable_ref__": path_str}
        else:
            logger.warning(
                f"Could not get path string for callable {item}, storing as string."
            )
            return str(item)
    elif isinstance(item, Mapping):
        return {key: serialize_item(value) for key, value in item.items()}
    elif isinstance(item, Sequence) and not isinstance(item, str):
        return [serialize_item(sub_item) for sub_item in item]
    elif isinstance(
        item, type
    ):  # Handle type objects themselves (e.g. if stored directly)
        type_name = FlockRegistry.get_component_type_name(
            item
        )  # Check components first
        if type_name:
            return {"__component_ref__": type_name}
        type_name = FlockRegistry._get_path_string(
            item
        )  # Check regular types/classes by path
        if type_name:
            return {"__type_ref__": type_name}
        logger.warning(
            f"Could not serialize type object {item}, storing as string."
        )
        return str(item)
    else:
        # Return basic types as is
        return item


# --- Deserialization Helper ---


def deserialize_item(item: Any) -> Any:
    """Recursively processes a deserialized item (e.g., from YAML/JSON dict).
    Converts reference dicts back to actual callables or types using FlockRegistry.
    Handles nested lists and dicts.
    """
    # Import the registry lazily when needed
    from flock.core.flock_registry import get_registry

    FlockRegistry = get_registry()

    if isinstance(item, Mapping):
        if "__callable_ref__" in item and len(item) == 1:
            path_str = item["__callable_ref__"]
            try:
                return FlockRegistry.get_callable(path_str)
            except KeyError:
                logger.error(
                    f"Callable reference '{path_str}' not found during deserialization."
                )
                return None
        elif "__component_ref__" in item and len(item) == 1:
            type_name = item["__component_ref__"]
            try:
                return FlockRegistry.get_component(type_name)
            except KeyError:
                logger.error(
                    f"Component reference '{type_name}' not found during deserialization."
                )
                return None
        elif "__type_ref__" in item and len(item) == 1:
            type_name = item["__type_ref__"]
            try:
                # For general types, use get_type or fallback to dynamic import like get_callable
                # Using get_type for now, assuming it needs registration
                return FlockRegistry.get_type(type_name)
            except KeyError:
                # Attempt dynamic import as fallback if get_type fails (similar to get_callable)
                try:
                    if "." not in type_name:  # Builtins?
                        mod = importlib.import_module("builtins")
                    else:
                        module_name, class_name = type_name.rsplit(".", 1)
                        mod = importlib.import_module(module_name)
                    type_obj = getattr(mod, class_name)
                    if isinstance(type_obj, type):
                        FlockRegistry.register_type(
                            type_obj, type_name
                        )  # Cache it
                        return type_obj
                    else:
                        raise TypeError()
                except Exception:
                    logger.error(
                        f"Type reference '{type_name}' not found in registry or via dynamic import."
                    )
                    return None

        else:
            # Recursively deserialize dictionary values
            return {key: deserialize_item(value) for key, value in item.items()}
    elif isinstance(item, Sequence) and not isinstance(item, str):
        return [deserialize_item(sub_item) for sub_item in item]
    else:
        # Return basic types as is
        return item


# --- Component Deserialization Helper ---
def deserialize_component(
    data: dict | None, expected_base_type: type
) -> Any | None:
    """Deserializes a component (Module, Evaluator, Router) from its dict representation.
    Uses the 'type' field to find the correct class via FlockRegistry.
    """
    # Import the registry and COMPONENT_BASE_TYPES lazily when needed
    from flock.core.flock_registry import COMPONENT_BASE_TYPES, get_registry

    FlockRegistry = get_registry()

    if data is None:
        return None
    if not isinstance(data, dict):
        logger.error(
            f"Expected dict for component deserialization, got {type(data)}"
        )
        return None

    type_name = data.get(
        "type"
    )  # Assuming 'type' key holds the class name string
    if not type_name:
        logger.error(f"Component data missing 'type' field: {data}")
        return None

    try:
        ComponentClass = FlockRegistry.get_component(type_name)  # Use registry
        # Optional: Keep the base type check
        if COMPONENT_BASE_TYPES and not issubclass(
            ComponentClass, expected_base_type
        ):
            raise TypeError(
                f"Deserialized class {type_name} is not a subclass of {expected_base_type.__name__}"
            )

        # Recursively deserialize the data *before* passing to Pydantic constructor
        # This handles nested callables/types within the component's config/data
        deserialized_data_for_init = {}
        for k, v in data.items():
            # Don't pass the 'type' field itself to the constructor if it matches class name
            if k == "type" and v == ComponentClass.__name__:
                continue
            deserialized_data_for_init[k] = deserialize_item(v)

        # Use Pydantic constructor directly. Assumes keys match field names.
        # from_dict could be added to components for more complex logic if needed.
        return ComponentClass(**deserialized_data_for_init)

    except (KeyError, TypeError, Exception) as e:
        logger.error(
            f"Failed to deserialize component of type '{type_name}': {e}",
            exc_info=True,
        )
        return None
