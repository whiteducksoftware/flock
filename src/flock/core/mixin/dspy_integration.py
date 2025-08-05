# src/flock/core/mixin/dspy_integration.py
"""Mixin class for integrating with the dspy library."""

import ast
import re  # Import re for parsing
import typing
from typing import Any, Literal

from dspy import Tool

from flock.core.logging.logging import get_logger
from flock.core.util.splitter import split_top_level

# Import split_top_level (assuming it's moved or copied appropriately)
# Option 1: If moved to a shared util
# from flock.core.util.parsing_utils import split_top_level
# Option 2: If kept within this file (as in previous example)
# Define split_top_level here or ensure it's imported

logger = get_logger("mixin.dspy")

# Type definition for agent type override
AgentType = Literal["ReAct", "Completion", "ChainOfThought"] | None


# Helper function to resolve type strings (can be static or module-level)
def _resolve_type_string(type_str: str) -> type:
    """Resolves a type string into a Python type object.
    Handles built-ins, registered types, and common typing generics like
    List, Dict, Optional, Union, Literal.
    """
    # Import registry here to avoid circular imports
    from flock.core.registry import get_registry

    registry = get_registry()

    type_str = type_str.strip()
    logger.debug(f"Attempting to resolve type string: '{type_str}'")

    # 1. Check built-ins and registered types directly
    try:
        # This covers str, int, bool, Any, and types registered by name
        resolved_type = registry.get_type(type_str)
        logger.debug(f"Resolved '{type_str}' via registry to: {resolved_type}")
        return resolved_type
    except KeyError:
        logger.debug(
            f"'{type_str}' not found directly in registry, attempting generic parsing."
        )
        pass  # Not found, continue parsing generics

    # 2. Handle typing generics (List, Dict, Optional, Union, Literal)
    # Use regex to match pattern like Generic[InnerType1, InnerType2, ...]
    generic_match = re.fullmatch(r"(\w+)\s*\[(.*)\]", type_str)
    if generic_match:
        base_name = generic_match.group(1).strip()
        args_str = generic_match.group(2).strip()
        logger.debug(
            f"Detected generic pattern: Base='{base_name}', Args='{args_str}'"
        )

        try:
            # Get the base generic type (e.g., list, dict, Optional) from registry/builtins
            BaseType = registry.get_type(
                base_name
            )  # Expects List, Dict etc. to be registered
            logger.debug(
                f"Resolved base generic type '{base_name}' to: {BaseType}"
            )

            # Special handling for Literal
            if BaseType is typing.Literal:
                # Split literal values, remove quotes, strip whitespace
                def parse_literal_args(args_str: str) -> tuple[str, ...]:
                    try:
                        return tuple(ast.literal_eval(f"[{args_str}]"))
                    except (SyntaxError, ValueError) as exc:
                        raise ValueError(
                            f"Cannot parse {args_str!r} as literals"
                        ) from exc

                literal_args = parse_literal_args(args_str)
                logger.debug(
                    f"Parsing Literal arguments: {args_str} -> {literal_args}"
                )
                resolved_type = typing.Literal[literal_args]  # type: ignore
                logger.debug(f"Constructed Literal type: {resolved_type}")
                return resolved_type

            # Recursively resolve arguments for other generics
            logger.debug(f"Splitting generic arguments: '{args_str}'")
            arg_strs = split_top_level(args_str)
            logger.debug(f"Split arguments: {arg_strs}")
            if not arg_strs:
                raise ValueError("Generic type has no arguments.")

            resolved_arg_types = tuple(
                _resolve_type_string(arg) for arg in arg_strs
            )
            logger.debug(f"Resolved generic arguments: {resolved_arg_types}")

            # Construct the generic type hint
            if BaseType is typing.Optional:
                if len(resolved_arg_types) != 1:
                    raise ValueError("Optional requires exactly one argument.")
                # type: ignore
                resolved_type = typing.Union[resolved_arg_types[0], type(None)]
                logger.debug(
                    f"Constructed Optional type as Union: {resolved_type}"
                )
                return resolved_type
            elif BaseType is typing.Union:
                if not resolved_arg_types:
                    raise ValueError("Union requires at least one argument.")
                # type: ignore
                resolved_type = typing.Union[resolved_arg_types]
                logger.debug(f"Constructed Union type: {resolved_type}")
                return resolved_type
            elif hasattr(
                BaseType, "__getitem__"
            ):  # Check if subscriptable (like list, dict, List, Dict)
                resolved_type = BaseType[resolved_arg_types]  # type: ignore
                logger.debug(
                    f"Constructed subscripted generic type: {resolved_type}"
                )
                return resolved_type
            else:
                # Base type found but cannot be subscripted
                logger.warning(
                    f"Base type '{base_name}' found but is not a standard subscriptable generic. Returning base type."
                )
                return BaseType

        except (KeyError, ValueError, IndexError, TypeError) as e:
            logger.warning(
                f"Failed to parse generic type '{type_str}': {e}. Falling back."
            )
            # Fall through to raise KeyError below if base type itself wasn't found or parsing failed

    # 3. If not resolved by now, raise error
    logger.error(f"Type string '{type_str}' could not be resolved.")
    raise KeyError(f"Type '{type_str}' could not be resolved.")


class DSPyIntegrationMixin:
    """Mixin class for integrating with the dspy library."""

    def create_dspy_signature_class(
        self, agent_name, description_spec, fields_spec
    ) -> Any:
        """Creates a dynamic DSPy Signature class from string specifications,
        resolving types using the registry.
        """
        try:
            import dspy
        except ImportError:
            logger.error(
                "DSPy library is not installed. Cannot create DSPy signature. "
                "Install with: pip install dspy-ai"
            )
            raise ImportError("DSPy is required for this functionality.")

        base_class = dspy.Signature
        class_dict = {"__doc__": description_spec, "__annotations__": {}}

        if "->" in fields_spec:
            inputs_spec, outputs_spec = fields_spec.split("->", 1)
        else:
            inputs_spec, outputs_spec = (
                fields_spec,
                "",
            )  # Assume only inputs if no '->'

        def parse_field(field_str):
            """Parses 'name: type_str | description' using _resolve_type_string."""
            field_str = field_str.strip()
            if not field_str:
                return None

            parts = field_str.split("|", 1)
            main_part = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else None

            if ":" in main_part:
                name, type_str = [s.strip() for s in main_part.split(":", 1)]
            else:
                name = main_part
                type_str = "str"  # Default type

            try:
                field_type = _resolve_type_string(type_str)
            except Exception as e:  # Catch resolution errors
                logger.error(
                    f"Failed to resolve type '{type_str}' for field '{name}': {e}. Defaulting to str."
                )
                field_type = str

            return name, field_type, desc

        def process_fields(fields_string, field_kind):
            """Process fields and add to class_dict."""
            if not fields_string or not fields_string.strip():
                return

            split_fields = split_top_level(fields_string)
            for field in split_fields:
                if field.strip():
                    parsed = parse_field(field)
                    if not parsed:
                        continue
                    name, field_type, desc = parsed
                    class_dict["__annotations__"][name] = (
                        field_type  # Use resolved type
                    )

                    FieldClass = (
                        dspy.InputField
                        if field_kind == "input"
                        else dspy.OutputField
                    )
                    # DSPy Fields use 'desc' for description
                    class_dict[name] = (
                        FieldClass(desc=desc)
                        if desc is not None
                        else FieldClass()
                    )

        try:
            process_fields(inputs_spec, "input")
            process_fields(outputs_spec, "output")
        except Exception as e:
            logger.error(
                f"Error processing fields for DSPy signature '{agent_name}': {e}",
                exc_info=True,
            )
            raise ValueError(
                f"Could not process fields for signature: {e}"
            ) from e

        # Create and return the dynamic class
        try:
            DynamicSignature = type(
                "dspy_" + agent_name, (base_class,), class_dict
            )
            logger.info(
                f"Successfully created DSPy Signature: {DynamicSignature.__name__} "
                f"with fields: {DynamicSignature.__annotations__}"
            )
            return DynamicSignature
        except Exception as e:
            logger.error(
                f"Failed to create dynamic type 'dspy_{agent_name}': {e}",
                exc_info=True,
            )
            raise TypeError(f"Could not create DSPy signature type: {e}") from e

    def _configure_language_model(
        self,
        model: str | None,
        use_cache: bool,
        temperature: float,
        max_tokens: int,
    ) -> None:
        """Initialize and configure the language model using dspy."""
        if model is None:
            logger.warning(
                "No model specified for DSPy configuration. Using DSPy default."
            )
            # Rely on DSPy's global default or raise error if none configured
            # import dspy
            # if dspy.settings.lm is None:
            #      raise ValueError("No model specified for agent and no global DSPy LM configured.")
            return

        try:
            import dspy
        except ImportError:
            logger.error(
                "DSPy library is not installed. Cannot configure language model."
            )
            return  # Or raise

        try:
            # Ensure 'cache' parameter is handled correctly (might not exist on dspy.LM directly)
            # DSPy handles caching globally or via specific optimizers typically.
            # We'll configure the LM without explicit cache control here.
            lm_instance = dspy.LM(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                cache=use_cache,
                # Add other relevant parameters if needed, e.g., API keys via dspy.settings
            )
            dspy.settings.configure(lm=lm_instance)
            logger.info(
                f"DSPy LM configured with model: {model}, temp: {temperature}, max_tokens: {max_tokens}"
            )
            # Note: DSPy caching is usually configured globally, e.g., dspy.settings.configure(cache=...)
            # or handled by optimizers. Setting `cache=use_cache` on dspy.LM might not be standard.
        except Exception as e:
            logger.error(
                f"Failed to configure DSPy language model '{model}': {e}",
                exc_info=True,
            )
            # We need to raise this exception, otherwise Flock will trundle on until it needs dspy.settings.lm and can't find it.
            raise

    def _select_task(
        self,
        signature: Any,
        override_evaluator_type: AgentType,
        max_tool_calls: int = 10,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
        kwargs: dict[str, Any] = {},
    ) -> Any:
        """Select and instantiate the appropriate DSPy Program/Module."""
        try:
            import dspy
        except ImportError:
            logger.error(
                "DSPy library is not installed. Cannot select DSPy task."
            )
            raise ImportError("DSPy is required for this functionality.")

        processed_tools = []
        if tools:
            for tool in tools:
                if callable(tool):  # Basic check
                    processed_tools.append(tool)
                # Could add more sophisticated tool wrapping/validation here if needed
                else:
                    logger.warning(
                        f"Item '{tool}' in tools list is not callable, skipping."
                    )

        processed_mcp_tools = []
        if mcp_tools:
            for mcp_tool in mcp_tools:
                if isinstance(mcp_tool, Tool):  # Basic check
                    processed_mcp_tools.append(mcp_tool)
                else:
                    logger.warning(
                        f"Item '{mcp_tool}' is not a dspy.primitives.Tool, skipping."
                    )

        dspy_program = None
        selected_type = override_evaluator_type

        # Determine type if not overridden
        if not selected_type:
            selected_type = (
                "ReAct" if processed_tools or processed_mcp_tools else "Predict"
            )  # Default logic

        logger.debug(
            f"Selecting DSPy program type: {selected_type} (Tools provided: {bool(processed_tools)}) (MCP Tools: {bool(processed_mcp_tools)}"
        )

        # Merge list of native tools and processed tools.
        # This makes mcp tools appear as native code functions to the llm of the agent.
        merged_tools = []

        if processed_tools:
            merged_tools = merged_tools + processed_tools

        if processed_mcp_tools:
            merged_tools = merged_tools + processed_mcp_tools

        try:
            if selected_type == "ChainOfThought":
                dspy_program = dspy.ChainOfThought(signature, **kwargs)
            elif selected_type == "ReAct":
                if not kwargs:
                    kwargs = {"max_iters": max_tool_calls}
                dspy_program = dspy.ReAct(
                    signature, tools=merged_tools or [], **kwargs
                )
            elif selected_type == "Predict":  # Default or explicitly Completion
                dspy_program = dspy.Predict(signature)
            else:  # Fallback or handle unknown type
                logger.warning(
                    f"Unknown or unsupported agent_type_override '{selected_type}'. Defaulting to dspy.Predict."
                )
                dspy_program = dspy.Predict(signature)

            logger.info(
                f"Instantiated DSPy program: {type(dspy_program).__name__}"
            )
            return dspy_program
        except Exception as e:
            logger.error(
                f"Failed to instantiate DSPy program of type '{selected_type}': {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Could not create DSPy program: {e}") from e

    def _process_result(
        self, result: Any, inputs: dict[str, Any]
    ) -> tuple[dict[str, Any], float, list]:
        """Convert the DSPy result object to a dictionary."""
        import dspy

        if result is None:
            logger.warning("DSPy program returned None result.")
            return {}
        try:
            # DSPy Prediction objects often behave like dicts or have .keys() / items()
            if hasattr(result, "items") and callable(result.items):
                output_dict = dict(result.items())
            elif hasattr(result, "__dict__"):  # Fallback for other object types
                output_dict = {
                    k: v
                    for k, v in result.__dict__.items()
                    if not k.startswith("_")
                }
            else:
                # If it's already a dict (less common for DSPy results directly)
                if isinstance(result, dict):
                    output_dict = result
                else:  # Final fallback
                    logger.warning(
                        f"Could not reliably convert DSPy result of type {type(result)} to dict. Returning as is."
                    )
                    output_dict = {"raw_result": result}

            logger.debug(f"Processed DSPy result to dict: {output_dict}")
            # Optionally merge inputs back if desired (can make result dict large)
            final_result = {**inputs, **output_dict}

            lm = dspy.settings.get("lm")
            cost = sum([x["cost"] for x in lm.history if x["cost"] is not None])
            lm_history = lm.history

            return final_result, cost, lm_history

        except Exception as conv_error:
            logger.error(
                f"Failed to process DSPy result into dictionary: {conv_error}",
                exc_info=True,
            )
            return {
                "error": "Failed to process result",
                "raw_result": str(result),
            }
