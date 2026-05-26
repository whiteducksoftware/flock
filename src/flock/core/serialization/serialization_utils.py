# src/flock/core/serialization/serialization_utils.py
"""Utilities for recursive serialization/deserialization with callable handling."""

import ast
import builtins
import importlib
import sys
import types
import typing
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    pass

from flock.core.flock_registry import get_registry
from flock.core.logging.logging import get_logger

logger = get_logger("serialization.utils")

# Remove this line to avoid circular import at module level
# FlockRegistry = get_registry()  # Get singleton instance

# --- Serialization Helper ---

# src/flock/util/hydrator.py (or import from serialization_utils)


def _format_type_to_string(type_hint: type) -> str:
    """Converts a Python type object back into its string representation."""
    # This needs to handle various typing scenarios (List, Dict, Union, Optional, Literal, custom types)
    origin = typing.get_origin(type_hint)
    args = typing.get_args(type_hint)

    # Handle common cases first
    if origin is list or origin is list:
        if args:
            return f"list[{_format_type_to_string(args[0])}]"
        return "list[Any]"  # Or just "list"
    elif origin is dict or origin is dict:
        if args and len(args) == 2:
            return f"dict[{_format_type_to_string(args[0])}, {_format_type_to_string(args[1])}]"
        return "dict[Any, Any]"  # Or just "dict"
    elif origin is Union or origin is types.UnionType:
        # Handle Optional[T] as Union[T, NoneType]
        if len(args) == 2 and type(None) in args:
            inner_type = next(t for t in args if t is not type(None))
            return _format_type_to_string(inner_type)
        # return f"Optional[{_format_type_to_string(inner_type)}]"
        return (
            f"Union[{', '.join(_format_type_to_string(arg) for arg in args)}]"
        )
    elif origin is Literal:
        formatted_args = []
        for arg in args:
            if isinstance(arg, str):
                formatted_args.append(f"'{arg}'")
            else:
                formatted_args.append(str(arg))
        return f"Literal[{', '.join(formatted_args)}]"
    elif hasattr(
        type_hint, "__forward_arg__"
    ):  # Handle ForwardRefs if necessary
        return type_hint.__forward_arg__
    elif hasattr(type_hint, "__name__"):
        # Handle custom types registered in registry (get preferred name)
        registry = get_registry()
        for (
            name,
            reg_type,
        ) in registry._types.items():  # Access internal for lookup
            if reg_type == type_hint:
                return name  # Return registered name
        return type_hint.__name__  # Fallback to class name if not registered
    else:
        # Fallback for complex types or types not handled above
        type_repr = str(type_hint).replace("typing.", "")  # Basic cleanup
        type_repr = str(type_hint).replace("| None", "")
        type_repr = type_repr.strip()
        logger.debug(
            f"Using fallback string representation for type: {type_repr}"
        )
        return type_repr


def extract_identifiers_from_type_str(type_str: str) -> set[str]:
    """Extract all identifiers from a type annotation string using the AST."""
    tree = ast.parse(type_str, mode="eval")
    identifiers = set()

    class IdentifierVisitor(ast.NodeVisitor):
        def visit_Name(self, node):
            identifiers.add(node.id)

        def visit_Attribute(self, node):
            # Optionally support dotted names like mymodule.MyModel
            full_name = []
            while isinstance(node, ast.Attribute):
                full_name.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                full_name.append(node.id)
                identifiers.add(".".join(reversed(full_name)))

    IdentifierVisitor().visit(tree)
    return identifiers


def resolve_name(name: str):
    """Resolve a name to a Python object from loaded modules."""
    # Try dotted names first
    parts = name.split(".")
    obj = None

    if len(parts) == 1:
        # Search globals and builtins
        if parts[0] in globals():
            return globals()[parts[0]]
        if parts[0] in builtins.__dict__:
            return builtins.__dict__[parts[0]]
    else:
        try:
            obj = sys.modules[parts[0]]
            for part in parts[1:]:
                obj = getattr(obj, part)
            return obj
        except Exception:
            return None

    # Try all loaded modules' symbols
    for module in list(sys.modules.values()):
        if module is None or not hasattr(module, "__dict__"):
            continue
        if parts[0] in module.__dict__:
            return module.__dict__[parts[0]]

    return None


def extract_pydantic_models_from_type_string(
    type_str: str,
) -> list[type[BaseModel]]:
    identifiers = extract_identifiers_from_type_str(type_str)
    models = []
    for name in identifiers:
        resolved = resolve_name(name)
        if (
            isinstance(resolved, type)
            and issubclass(resolved, BaseModel)
            and resolved is not BaseModel
        ):
            models.append(resolved)
    return models


def collect_pydantic_models(
    type_hint, seen: set[type[BaseModel]] | None = None
) -> set[type[BaseModel]]:
    if seen is None:
        seen = set()

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Direct BaseModel
    if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
        seen.add(type_hint)
        return seen

    # For Unions, Lists, Dicts, Tuples, etc.
    if origin is not None:
        for arg in args:
            collect_pydantic_models(arg, seen)

    return seen


def serialize_item(item: Any) -> Any:
    """Recursively prepares an item for serialization (e.g., to dict for YAML/JSON).
    Converts known callables to their path strings using FlockRegistry.
    Converts Pydantic models using model_dump.
    """
    # Import the registry lazily when needed
    from flock.core.flock_registry import get_registry

    FlockRegistry = get_registry()

    if callable(item) and not isinstance(item, type):
        path_str = FlockRegistry.get_callable_path_string(
            item
        )  # Use registry helper
        if path_str:
            # Store the simple name (last part of the path) for cleaner YAML/JSON
            simple_name = path_str.split(".")[-1]
            logger.debug(
                f"Serializing callable '{getattr(item, '__name__', 'unknown')}' as reference: '{simple_name}' (from path '{path_str}')"
            )
            return {
                "__callable_ref__": simple_name
            }  # Use simple name convention
        else:
            # Handle unregistered callables (e.g., lambdas defined inline)
            # Option 1: Raise error (stricter)
            # raise ValueError(f"Cannot serialize unregistered callable: {getattr(item, '__name__', item)}")
            # Option 2: Store string representation with warning (more lenient)
            logger.warning(
                f"Cannot serialize unregistered callable {getattr(item, '__name__', item)}, storing as string."
            )
            return str(item)
    elif isinstance(item, BaseModel):
        logger.debug(
            f"Serializing Pydantic model instance: {item.__class__.__name__}"
        )
        serialized_dict = {}
        # Iterate through defined fields in the model
        fields_to_iterate = {}
        if hasattr(item, "model_fields"):  # Pydantic v2
            fields_to_iterate = item.model_fields

        for field_name in fields_to_iterate:
            # Get the value *from the instance*
            try:
                value = getattr(item, field_name)
                if value is not None:  # Exclude None values
                    # Recursively serialize the field's value
                    serialized_dict[field_name] = serialize_item(value)
            except AttributeError:
                # Should not happen if iterating model_fields/__fields__ but handle defensively
                logger.warning(
                    f"Attribute '{field_name}' not found on instance of {item.__class__.__name__} during serialization."
                )
        return serialized_dict
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
    elif isinstance(item, Enum):
        return item.value
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
            ref_name = item["__callable_ref__"]
            try:
                # The registry's get_callable needs to handle lookup by simple name OR full path
                # Or we assume get_callable handles finding the right function from the simple name
                resolved_callable = FlockRegistry.get_callable(ref_name)
                logger.debug(
                    f"Deserialized callable reference '{ref_name}' to {resolved_callable}"
                )
                return resolved_callable
            except KeyError:
                logger.error(
                    f"Callable reference '{ref_name}' not found during deserialization."
                )
                return None  # Or raise?
            except Exception as e:
                logger.error(
                    f"Error resolving callable reference '{ref_name}': {e}",
                    exc_info=True,
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
