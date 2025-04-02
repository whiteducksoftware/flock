# src/flock/core/mixin/dspy_integration.py
"""Mixin class for integrating with the dspy library."""

import re  # Import re for parsing
import typing
from typing import Any, Literal

from flock.core.logging.logging import get_logger

# Import split_top_level (assuming it's moved or copied appropriately)
# Option 1: If moved to a shared util
# from flock.core.util.parsing_utils import split_top_level
# Option 2: If kept within this file (as in previous example)
# Define split_top_level here or ensure it's imported

logger = get_logger("mixin.dspy")

# Type definition for agent type override
AgentType = Literal["ReAct", "Completion", "ChainOfThought"] | None


# Helper function needed by _resolve_type_string (copied from input_resolver.py/previous response)
def split_top_level(s: str) -> list[str]:
    """Split a string on commas that are not enclosed within brackets, parentheses, or quotes."""
    parts = []
    current = []
    level = 0
    in_quote = False
    quote_char = ""
    i = 0
    while i < len(s):
        char = s[i]
        # Handle escapes within quotes
        if in_quote and char == "\\" and i + 1 < len(s):
            current.append(char)
            current.append(s[i + 1])
            i += 1  # Skip next char
        elif in_quote:
            current.append(char)
            if char == quote_char:
                in_quote = False
        elif char in ('"', "'"):
            in_quote = True
            quote_char = char
            current.append(char)
        elif char in "([{":
            level += 1
            current.append(char)
        elif char in ")]}":
            level -= 1
            current.append(char)
        elif char == "," and level == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        i += 1
    if current:
        parts.append("".join(current).strip())
    # Filter out empty strings that might result from trailing commas etc.
    return [part for part in parts if part]


# Helper function to resolve type strings (can be static or module-level)
def _resolve_type_string(type_str: str) -> type:
    """Resolves a type string into a Python type object.
    Handles built-ins, registered types, and common typing generics like
    List, Dict, Optional, Union, Literal.
    """
    # Import registry here to avoid circular imports
    from flock.core.flock_registry import get_registry

    FlockRegistry = get_registry()

    type_str = type_str.strip()
    logger.debug(f"Attempting to resolve type string: '{type_str}'")

    # 1. Check built-ins and registered types directly
    try:
        # This covers str, int, bool, Any, and types registered by name
        resolved_type = FlockRegistry.get_type(type_str)
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
            BaseType = FlockRegistry.get_type(
                base_name
            )  # Expects List, Dict etc. to be registered
            logger.debug(
                f"Resolved base generic type '{base_name}' to: {BaseType}"
            )

            # Special handling for Literal
            if BaseType is typing.Literal:
                # Split literal values, remove quotes, strip whitespace
                literal_args_raw = split_top_level(args_str)
                literal_args = tuple(
                    s.strip().strip("'\"") for s in literal_args_raw
                )
                logger.debug(
                    f"Parsing Literal arguments: {literal_args_raw} -> {literal_args}"
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
                resolved_type = typing.Union[resolved_arg_types[0], type(None)]  # type: ignore
                logger.debug(
                    f"Constructed Optional type as Union: {resolved_type}"
                )
                return resolved_type
            elif BaseType is typing.Union:
                if not resolved_arg_types:
                    raise ValueError("Union requires at least one argument.")
                resolved_type = typing.Union[resolved_arg_types]  # type: ignore
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
        resolving types using the FlockRegistry.
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

            for field in split_top_level(fields_string):
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

    def _select_task(
        self,
        signature: Any,
        agent_type_override: AgentType,
        tools: list[Any] | None = None,
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

        dspy_program = None
        selected_type = agent_type_override

        # Determine type if not overridden
        if not selected_type:
            selected_type = (
                "ReAct" if processed_tools else "Predict"
            )  # Default logic

        logger.debug(
            f"Selecting DSPy program type: {selected_type} (Tools provided: {bool(processed_tools)})"
        )

        try:
            if selected_type == "ChainOfThought":
                dspy_program = dspy.ChainOfThought(signature)
            elif selected_type == "ReAct":
                # ReAct requires tools, even if empty list
                dspy_program = dspy.ReAct(
                    signature, tools=processed_tools or [], max_iters=10
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
    ) -> dict[str, Any]:
        """Convert the DSPy result object to a dictionary."""
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
            return final_result

        except Exception as conv_error:
            logger.error(
                f"Failed to process DSPy result into dictionary: {conv_error}",
                exc_info=True,
            )
            return {
                "error": "Failed to process result",
                "raw_result": str(result),
            }
