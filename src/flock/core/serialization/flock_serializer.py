# src/flock/core/serialization/flock_serializer.py
"""Handles serialization and deserialization logic for Flock instances."""

import builtins
import importlib
import importlib.util
import inspect
import os
import re
import sys
from dataclasses import is_dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, create_model

# Need registry access
from flock.core.flock_registry import get_registry
from flock.core.logging.logging import get_logger
from flock.core.serialization.serialization_utils import (
    extract_pydantic_models_from_type_string,  # Assuming this handles basic serialization needs
)

if TYPE_CHECKING:
    from flock.core.flock import Flock


logger = get_logger("serialization.flock")
FlockRegistry = get_registry()


class FlockSerializer:
    """Provides static methods for serializing and deserializing Flock instances."""

    @staticmethod
    def serialize(
        flock_instance: "Flock",
        path_type: Literal["absolute", "relative"] = "relative",
    ) -> dict[str, Any]:
        """Convert Flock instance to dictionary representation.

        Args:
            flock_instance: The Flock instance to serialize.
            path_type: How file paths should be formatted ('absolute' or 'relative').
        """
        logger.debug(
            f"Serializing Flock instance '{flock_instance.name}' to dict."
        )
        # Use Pydantic's dump for base fields defined in Flock's model
        data = flock_instance.model_dump(mode="json", exclude_none=True)
        logger.info(
            f"Serializing Flock '{flock_instance.name}' with {len(flock_instance._agents)} agents"
        )

        data["agents"] = {}
        custom_types = {}
        components = {}

        for name, agent_instance in flock_instance._agents.items():
            try:
                logger.debug(f"Serializing agent '{name}'")
                # Agents handle their own serialization via their to_dict
                agent_data = (
                    agent_instance.to_dict()
                )  # This now uses the agent's refined to_dict
                data["agents"][name] = agent_data

                # --- Extract Types from Agent Signatures ---
                input_types = []
                if agent_instance.input:
                    input_types = FlockSerializer._extract_types_from_signature(
                        agent_instance.input
                    )
                    if input_types:
                        logger.debug(
                            f"Found input types in agent '{name}': {input_types}"
                        )

                output_types = []
                if agent_instance.output:
                    output_types = (
                        FlockSerializer._extract_types_from_signature(
                            agent_instance.output
                        )
                    )
                    if output_types:
                        logger.debug(
                            f"Found output types in agent '{name}': {output_types}"
                        )

                all_types = set(input_types + output_types)
                if all_types:
                    custom_types.update(
                        FlockSerializer._get_type_definitions(list(all_types))
                    )

                # --- Extract Component Information ---
                # Evaluator
                if (
                    "evaluator" in agent_data
                    and agent_data["evaluator"]
                    and "type" in agent_data["evaluator"]
                ):
                    component_type = agent_data["evaluator"]["type"]
                    if component_type not in components:
                        logger.debug(
                            f"Adding evaluator component '{component_type}' from agent '{name}'"
                        )
                        components[component_type] = (
                            FlockSerializer._get_component_definition(
                                component_type, path_type
                            )
                        )

                # Modules
                if "modules" in agent_data:
                    for module_name, module_data in agent_data[
                        "modules"
                    ].items():
                        if module_data and "type" in module_data:
                            component_type = module_data["type"]
                            if component_type not in components:
                                logger.debug(
                                    f"Adding module component '{component_type}' from module '{module_name}' in agent '{name}'"
                                )
                                components[component_type] = (
                                    FlockSerializer._get_component_definition(
                                        component_type, path_type
                                    )
                                )

                # Router
                if (
                    "handoff_router" in agent_data
                    and agent_data["handoff_router"]
                    and "type" in agent_data["handoff_router"]
                ):
                    component_type = agent_data["handoff_router"]["type"]
                    if component_type not in components:
                        logger.debug(
                            f"Adding router component '{component_type}' from agent '{name}'"
                        )
                        components[component_type] = (
                            FlockSerializer._get_component_definition(
                                component_type, path_type
                            )
                        )

                # Description (Callables)
                if agent_data.get("description_callable"):
                    logger.debug(
                        f"Adding description callable '{agent_data['description_callable']}' from agent '{name}'"
                    )
                    description_callable_name = agent_data[
                        "description_callable"
                    ]
                    description_callable = agent_instance.description
                    path_str = FlockRegistry.get_callable_path_string(
                        description_callable
                    )
                    if path_str:
                        logger.debug(
                            f"Adding description callable '{description_callable_name}' (from path '{path_str}') to components"
                        )
                        components[description_callable_name] = (
                            FlockSerializer._get_callable_definition(
                                path_str, description_callable_name, path_type
                            )
                        )

                if agent_data.get("input_callable"):
                    logger.debug(
                        f"Adding input callable '{agent_data['input_callable']}' from agent '{name}'"
                    )
                    input_callable_name = agent_data["input_callable"]
                    input_callable = agent_instance.input
                    path_str = FlockRegistry.get_callable_path_string(
                        input_callable
                    )
                    if path_str:
                        logger.debug(
                            f"Adding input callable '{input_callable_name}' (from path '{path_str}') to components"
                        )
                        components[input_callable_name] = (
                            FlockSerializer._get_callable_definition(
                                path_str, input_callable_name, path_type
                            )
                        )

                if agent_data.get("output_callable"):
                    logger.debug(
                        f"Adding output callable '{agent_data['output_callable']}' from agent '{name}'"
                    )
                    output_callable_name = agent_data["output_callable"]
                    output_callable = agent_instance.output
                    path_str = FlockRegistry.get_callable_path_string(
                        output_callable
                    )
                    if path_str:
                        logger.debug(
                            f"Adding output callable '{output_callable_name}' (from path '{path_str}') to components"
                        )
                        components[output_callable_name] = (
                            FlockSerializer._get_callable_definition(
                                path_str, output_callable_name, path_type
                            )
                        )

                # Tools (Callables)
                if agent_data.get("tools"):
                    logger.debug(
                        f"Extracting tool information from agent '{name}': {agent_data['tools']}"
                    )
                    tool_objs = (
                        agent_instance.tools if agent_instance.tools else []
                    )
                    for i, tool_name in enumerate(agent_data["tools"]):
                        if tool_name not in components and i < len(tool_objs):
                            tool = tool_objs[i]
                            if callable(tool) and not isinstance(tool, type):
                                path_str = (
                                    FlockRegistry.get_callable_path_string(tool)
                                )
                                if path_str:
                                    logger.debug(
                                        f"Adding tool '{tool_name}' (from path '{path_str}') to components"
                                    )
                                    components[tool_name] = (
                                        FlockSerializer._get_callable_definition(
                                            path_str, tool_name, path_type
                                        )
                                    )

            except Exception as e:
                logger.error(
                    f"Failed to serialize agent '{name}' within Flock: {e}",
                    exc_info=True,
                )

        if custom_types:
            logger.info(f"Adding {len(custom_types)} custom type definitions")
            data["types"] = custom_types
        if components:
            logger.info(
                f"Adding {len(components)} component/callable definitions"
            )
            data["components"] = components

        data["dependencies"] = FlockSerializer._get_dependencies()
        data["metadata"] = {
            "path_type": path_type,
            "flock_version": "0.4.0",
        }  # Example version

        logger.debug(f"Flock '{flock_instance.name}' serialization complete.")
        return data

    @staticmethod
    def deserialize(cls: type["Flock"], data: dict[str, Any]) -> "Flock":
        """Create Flock instance from dictionary representation."""
        # Import concrete types needed for instantiation
        from flock.core.flock import Flock  # Import the actual class
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

        logger.debug(
            f"Deserializing Flock from dict. Provided keys: {list(data.keys())}"
        )

        metadata = data.pop("metadata", {})
        path_type = metadata.get(
            "path_type", "relative"
        )  # Default to relative for loading flexibility
        logger.debug(
            f"Using path_type '{path_type}' from metadata for component loading"
        )

        if "types" in data:
            logger.info(f"Processing {len(data['types'])} type definitions")
            FlockSerializer._register_type_definitions(data.pop("types"))

        if "components" in data:
            logger.info(
                f"Processing {len(data['components'])} component/callable definitions"
            )
            FlockSerializer._register_component_definitions(
                data.pop("components"), path_type
            )

        if "dependencies" in data:
            logger.debug(f"Checking {len(data['dependencies'])} dependencies")
            FlockSerializer._check_dependencies(data.pop("dependencies"))

        agents_data = data.pop("agents", {})
        logger.info(f"Found {len(agents_data)} agents to deserialize")

        try:
            # Pass only fields defined in Flock's Pydantic model to constructor
            init_data = {
                k: v for k, v in data.items() if k in Flock.model_fields
            }
            logger.debug(
                f"Creating Flock instance with fields: {list(init_data.keys())}"
            )
            flock_instance = cls(**init_data)  # Use cls which is Flock
        except Exception as e:
            logger.error(
                f"Pydantic validation/init failed for Flock: {e}", exc_info=True
            )
            raise ValueError(
                f"Failed to initialize Flock from dict: {e}"
            ) from e

        # Deserialize and add agents AFTER Flock instance exists
        for name, agent_data in agents_data.items():
            try:
                logger.debug(f"Deserializing agent '{name}'")
                agent_data.setdefault("name", name)
                agent_instance = ConcreteFlockAgent.from_dict(agent_data)
                flock_instance.add_agent(agent_instance)
                logger.debug(f"Successfully added agent '{name}' to Flock")
            except Exception as e:
                logger.error(
                    f"Failed to deserialize/add agent '{name}': {e}",
                    exc_info=True,
                )

        logger.info(
            f"Successfully deserialized Flock '{flock_instance.name}' with {len(flock_instance._agents)} agents"
        )
        return flock_instance

    # --- Helper methods moved from Flock ---
    # (Keep all the _extract..., _get..., _register..., _create... methods here)
    # Ensure they use FlockSerializer._... or are standalone functions called directly.
    # Make static if they don't need instance state (which they shouldn't here).

    @staticmethod
    def _extract_types_from_signature(signature: str) -> list[str]:
        """Extract type names from an input/output signature string."""
        if not signature:
            return []
        from flock.core.util.input_resolver import (
            split_top_level,  # Import locally if needed
        )

        type_names = set()
        try:
            parts = split_top_level(signature)
            for part in parts:
                if ":" in part:
                    type_str = part.split(":", 1)[1].split("|", 1)[0].strip()
                    # Use the more robust extractor
                    models = extract_pydantic_models_from_type_string(type_str)
                    for model in models:
                        type_names.add(model.__name__)
        except Exception as e:
            logger.warning(
                f"Could not fully parse types from signature '{signature}': {e}"
            )
        return list(type_names)

    @staticmethod
    def _get_type_definitions(type_names: list[str]) -> dict[str, Any]:
        """Get definitions for the specified custom types from the registry."""
        type_definitions = {}
        for type_name in type_names:
            try:
                type_obj = FlockRegistry.get_type(
                    type_name
                )  # Throws KeyError if not found
                type_def = FlockSerializer._extract_type_definition(
                    type_name, type_obj
                )
                if type_def:
                    type_definitions[type_name] = type_def
            except KeyError:
                logger.warning(
                    f"Type '{type_name}' requested but not found in registry."
                )
            except Exception as e:
                logger.warning(
                    f"Could not extract definition for type {type_name}: {e}"
                )
        return type_definitions

    @staticmethod
    def _extract_type_definition(
        type_name: str, type_obj: type
    ) -> dict[str, Any] | None:
        """Extract a definition for a custom type (Pydantic or Dataclass)."""
        # Definition includes module path and schema/fields
        module_path = getattr(type_obj, "__module__", "unknown")
        type_def = {"module_path": module_path}
        try:
            if issubclass(type_obj, BaseModel):
                type_def["type"] = "pydantic.BaseModel"
                schema = type_obj.model_json_schema()
                if "title" in schema and schema["title"] == type_name:
                    del schema["title"]
                type_def["schema"] = schema
                return type_def
            elif is_dataclass(type_obj):
                type_def["type"] = "dataclass"
                fields = {}
                for field_name, field in getattr(
                    type_obj, "__dataclass_fields__", {}
                ).items():
                    # Attempt to get a string representation of the type
                    try:
                        type_repr = str(field.type)
                    except Exception:
                        type_repr = "unknown"
                    fields[field_name] = {
                        "type": type_repr,
                        "default": str(field.default)
                        if field.default is not inspect.Parameter.empty
                        else None,
                    }
                type_def["fields"] = fields
                return type_def
            else:
                logger.debug(
                    f"Type '{type_name}' is not Pydantic or Dataclass, skipping detailed definition."
                )
                return (
                    None  # Don't include non-data types in the 'types' section
                )
        except Exception as e:
            logger.warning(f"Error extracting definition for {type_name}: {e}")
            return None

    @staticmethod
    def _get_component_definition(
        component_type_name: str, path_type: Literal["absolute", "relative"]
    ) -> dict[str, Any]:
        """Get definition for a component type from the registry."""
        component_def = {
            "type": "flock_component",
            "module_path": "unknown",
            "file_path": None,
        }
        try:
            component_class = FlockRegistry.get_component(
                component_type_name
            )  # Raises KeyError if not found
            component_def["module_path"] = getattr(
                component_class, "__module__", "unknown"
            )
            component_def["description"] = (
                inspect.getdoc(component_class)
                or f"{component_type_name} component"
            )

            # Get file path
            try:
                file_path_abs = inspect.getfile(component_class)
                component_def["file_path"] = (
                    os.path.relpath(file_path_abs)
                    if path_type == "relative"
                    else file_path_abs
                )
            except (TypeError, ValueError) as e:
                logger.debug(
                    f"Could not determine file path for component {component_type_name}: {e}"
                )

        except KeyError:
            logger.warning(
                f"Component class '{component_type_name}' not found in registry."
            )
            component_def["description"] = (
                f"{component_type_name} component (class not found in registry)"
            )
        except Exception as e:
            logger.warning(
                f"Could not extract full definition for component {component_type_name}: {e}"
            )
        return component_def

    @staticmethod
    def _get_callable_definition(
        callable_path: str,
        func_name: str,
        path_type: Literal["absolute", "relative"],
    ) -> dict[str, Any]:
        """Get definition for a callable using its registry path."""
        callable_def = {
            "type": "flock_callable",
            "module_path": "unknown",
            "file_path": None,
        }
        try:
            func = FlockRegistry.get_callable(
                callable_path
            )  # Raises KeyError if not found
            callable_def["module_path"] = getattr(func, "__module__", "unknown")
            callable_def["description"] = (
                inspect.getdoc(func) or f"Callable function {func_name}"
            )
            # Get file path
            try:
                file_path_abs = inspect.getfile(func)
                callable_def["file_path"] = (
                    os.path.relpath(file_path_abs)
                    if path_type == "relative"
                    else file_path_abs
                )
            except (TypeError, ValueError) as e:
                logger.debug(
                    f"Could not determine file path for callable {callable_path}: {e}"
                )

        except KeyError:
            logger.warning(
                f"Callable '{callable_path}' (for tool '{func_name}') not found in registry."
            )
            callable_def["description"] = (
                f"Callable {func_name} (function not found in registry)"
            )
        except Exception as e:
            logger.warning(
                f"Could not extract full definition for callable {callable_path}: {e}"
            )
        return callable_def

    @staticmethod
    def _get_dependencies() -> list[str]:
        """Get list of core dependencies required by Flock."""
        # Basic static list for now
        return [
            "pydantic>=2.0.0",
            "flock-core>=0.4.0",
        ]  # Update version as needed

    @staticmethod
    def _register_type_definitions(type_defs: dict[str, Any]) -> None:
        """Register type definitions from serialized data."""
        # (Logic remains largely the same as original, ensure it uses FlockRegistry)
        for type_name, type_def in type_defs.items():
            logger.debug(f"Registering type definition for: {type_name}")
            # Prioritize direct import
            module_path = type_def.get("module_path")
            registered = False
            if module_path and module_path != "unknown":
                try:
                    module = importlib.import_module(module_path)
                    if hasattr(module, type_name):
                        type_obj = getattr(module, type_name)
                        FlockRegistry.register_type(type_obj, type_name)
                        logger.info(
                            f"Registered type '{type_name}' from module '{module_path}'"
                        )
                        registered = True
                except ImportError:
                    logger.debug(
                        f"Could not import module {module_path} for type {type_name}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Error registering type {type_name} from module: {e}"
                    )

            if registered:
                continue

            # Attempt dynamic creation if direct import failed or wasn't possible
            type_kind = type_def.get("type")
            if type_kind == "pydantic.BaseModel" and "schema" in type_def:
                FlockSerializer._create_pydantic_model(type_name, type_def)
            elif type_kind == "dataclass" and "fields" in type_def:
                FlockSerializer._create_dataclass(type_name, type_def)
            else:
                logger.warning(
                    f"Cannot dynamically register type '{type_name}' with kind '{type_kind}'"
                )

    @staticmethod
    def _create_pydantic_model(
        type_name: str, type_def: dict[str, Any]
    ) -> None:
        """Dynamically create and register a Pydantic model from schema."""
        # (Logic remains the same, ensure it uses FlockRegistry.register_type)
        schema = type_def.get("schema", {})
        try:
            fields = {}
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            for field_name, field_schema in properties.items():
                field_type = FlockSerializer._get_type_from_schema(field_schema)
                default = ... if field_name in required else None
                fields[field_name] = (field_type, default)

            DynamicModel = create_model(type_name, **fields)
            FlockRegistry.register_type(DynamicModel, type_name)
            logger.info(
                f"Dynamically created and registered Pydantic model: {type_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create Pydantic model {type_name}: {e}")

    @staticmethod
    def _get_type_from_schema(field_schema: dict[str, Any]) -> Any:
        """Convert JSON schema type to Python type."""
        # (Logic remains the same)
        schema_type = field_schema.get("type")
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        if schema_type in type_mapping:
            return type_mapping[schema_type]
        if "enum" in field_schema:
            from typing import Literal

            return Literal[tuple(field_schema["enum"])]  # type: ignore
        return Any

    @staticmethod
    def _create_dataclass(type_name: str, type_def: dict[str, Any]) -> None:
        """Dynamically create and register a dataclass."""
        # (Logic remains the same, ensure it uses FlockRegistry.register_type)
        from dataclasses import make_dataclass

        fields_def = type_def.get("fields", {})
        try:
            fields = []
            for field_name, field_props in fields_def.items():
                # Safely evaluate type string - requires care!
                field_type_str = field_props.get("type", "str")
                try:
                    field_type = eval(
                        field_type_str,
                        {"__builtins__": builtins.__dict__},
                        {"List": list, "Dict": dict},
                    )  # Allow basic types
                except Exception:
                    field_type = Any
                fields.append((field_name, field_type))

            DynamicDataclass = make_dataclass(type_name, fields)
            FlockRegistry.register_type(DynamicDataclass, type_name)
            logger.info(
                f"Dynamically created and registered dataclass: {type_name}"
            )
        except Exception as e:
            logger.error(f"Failed to create dataclass {type_name}: {e}")

    @staticmethod
    def _register_component_definitions(
        component_defs: dict[str, Any],
        path_type: Literal["absolute", "relative"],
    ) -> None:
        """Register component/callable definitions from serialized data."""
        # (Logic remains the same, ensure it uses FlockRegistry.register_component/register_callable)
        # Key change: Ensure file_path is handled correctly based on path_type from metadata
        for name, comp_def in component_defs.items():
            logger.debug(
                f"Registering component/callable definition for: {name}"
            )
            kind = comp_def.get("type")
            module_path = comp_def.get("module_path")
            file_path = comp_def.get("file_path")
            registered = False

            # Resolve file path if relative
            if (
                path_type == "relative"
                and file_path
                and not os.path.isabs(file_path)
            ):
                abs_file_path = os.path.abspath(file_path)
                logger.debug(
                    f"Resolved relative path '{file_path}' to absolute '{abs_file_path}'"
                )
                file_path = abs_file_path  # Use absolute path for loading

            # 1. Try importing from module_path
            if module_path and module_path != "unknown":
                try:
                    module = importlib.import_module(module_path)
                    if hasattr(module, name):
                        obj = getattr(module, name)
                        if kind == "flock_callable" and callable(obj):
                            FlockRegistry.register_callable(
                                obj, name
                            )  # Register by simple name
                            # Also register by full path if possible
                            full_path = f"{module_path}.{name}"
                            if full_path != name:
                                FlockRegistry.register_callable(obj, full_path)
                            logger.info(
                                f"Registered callable '{name}' from module '{module_path}'"
                            )
                            registered = True
                        elif kind == "flock_component" and isinstance(
                            obj, type
                        ):
                            FlockRegistry.register_component(obj, name)
                            logger.info(
                                f"Registered component '{name}' from module '{module_path}'"
                            )
                            registered = True
                except (ImportError, AttributeError):
                    logger.debug(
                        f"Could not import '{name}' from module '{module_path}', trying file path."
                    )
                except Exception as e:
                    logger.warning(
                        f"Error registering '{name}' from module '{module_path}': {e}"
                    )

            if registered:
                continue

            # 2. Try importing from file_path if module import failed or wasn't possible
            if file_path and os.path.exists(file_path):
                logger.debug(
                    f"Attempting to load '{name}' from file: {file_path}"
                )
                try:
                    mod_name = f"flock_dynamic_{name}"  # Unique module name
                    spec = importlib.util.spec_from_file_location(
                        mod_name, file_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[spec.name] = (
                            module  # Important for pickle/cloudpickle
                        )
                        spec.loader.exec_module(module)
                        if hasattr(module, name):
                            obj = getattr(module, name)
                            if kind == "flock_callable" and callable(obj):
                                FlockRegistry.register_callable(obj, name)
                                logger.info(
                                    f"Registered callable '{name}' from file '{file_path}'"
                                )
                            elif kind == "flock_component" and isinstance(
                                obj, type
                            ):
                                FlockRegistry.register_component(obj, name)
                                logger.info(
                                    f"Registered component '{name}' from file '{file_path}'"
                                )
                        else:
                            logger.warning(
                                f"'{name}' not found in loaded file '{file_path}'"
                            )
                    else:
                        logger.warning(
                            f"Could not create import spec for file '{file_path}'"
                        )
                except Exception as e:
                    logger.error(
                        f"Error loading '{name}' from file '{file_path}': {e}",
                        exc_info=True,
                    )
            elif not registered:
                logger.warning(
                    f"Could not register '{name}'. No valid module or file path found."
                )

    @staticmethod
    def _check_dependencies(dependencies: list[str]) -> None:
        """Check if required dependencies are available (basic check)."""
        # (Logic remains the same)
        for dep in dependencies:
            match = re.match(r"([^>=<]+)", dep)
            if match:
                pkg_name = match.group(1).replace("-", "_")
                try:
                    importlib.import_module(pkg_name)
                except ImportError:
                    logger.warning(f"Dependency '{dep}' might be missing.")
