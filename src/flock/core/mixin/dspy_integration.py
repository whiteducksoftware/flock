"""Mixin class for integrating with the dspy library."""

import inspect
import typing
from typing import Any, Literal, Optional

from flock.core.flock_registry import get_registry
from flock.core.logging.logging import get_logger
from flock.core.util.input_resolver import get_callable_members, split_top_level

logger = get_logger("mixin.dspy")
FlockRegistry = get_registry()  # Get singleton instance

AgentType = (
    Literal["ReAct"] | Literal["Completion"] | Literal["ChainOfThought"] | None
)


class DSPyIntegrationMixin:
    """Mixin class for integrating with the dspy library."""

    def create_dspy_signature_class(
        self, agent_name, description_spec, fields_spec
    ) -> Any:
        """Creates a dynamic DSPy Signature class from string specifications."""
        # ... (import dspy) ...
        import dspy  # Import DSPy locally within the method

        base_class = dspy.Signature
        class_dict = {"__doc__": description_spec, "__annotations__": {}}

        if "->" in fields_spec:
            inputs_spec, outputs_spec = fields_spec.split("->", 1)
        else:
            inputs_spec, outputs_spec = fields_spec, ""

        def parse_field(field_str):
            """Parses 'name: type_str | description'"""
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

            # --- Type Resolution using FlockRegistry ---
            field_type = None
            # 1. Check built-ins
            builtins_map = {
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "Any": Any,
            }
            if type_str in builtins_map:
                field_type = builtins_map[type_str]
            else:
                # 2. Check typing module for simple generics (List, Dict, Optional etc.) - Basic parsing
                # More robust parsing needed for nested types like list[dict[str, int]]
                typing_origin = None
                typing_args = ()
                origin_map = {
                    "List": list,
                    "Dict": dict,
                    "Optional": Optional,
                    "Literal": Literal,
                }  # etc.
                generic_match = (
                    typing._GenericAlias
                    if hasattr(typing, "_GenericAlias")
                    else None
                )  # Handle Python version differences

                # Basic check for common patterns like List[str] or Optional[int]
                if "[" in type_str and type_str.endswith("]"):
                    try:
                        base_type_str = type_str[: type_str.find("[")]
                        inner_type_str = type_str[type_str.find("[") + 1 : -1]

                        if base_type_str in origin_map:
                            typing_origin = origin_map[base_type_str]
                            # Try to resolve inner type (recursive call would be better)
                            inner_type = parse_field(
                                f"_{inner_type_str}"
                            )  # Parse inner type string
                            if inner_type:
                                typing_args = (
                                    inner_type[1],
                                )  # Use the resolved type (index 1)
                                field_type = typing_origin[typing_args]  # type: ignore

                        # Basic Literal parsing
                        elif base_type_str == "Literal":
                            literal_vals = [
                                s.strip().strip("'\"")
                                for s in inner_type_str.split(",")
                            ]
                            field_type = Literal[tuple(literal_vals)]  # type: ignore

                    except Exception as e:
                        logger.warning(
                            f"Could not parse complex type '{type_str}': {e}. Falling back."
                        )

                # 3. If not resolved yet, look up in FlockRegistry
                if field_type is None:
                    try:
                        field_type = FlockRegistry.get_type(type_str)
                        logger.debug(
                            f"Resolved type '{type_str}' using FlockRegistry."
                        )
                    except KeyError:
                        logger.warning(
                            f"Type '{type_str}' not found in built-ins, basic typing, or FlockRegistry. Defaulting to 'str'."
                        )
                        field_type = str  # Fallback to string

            return name, field_type, desc

        def process_fields(fields_string, field_kind):
            # ... (rest of process_fields remains the same, using the parsed field_type) ...
            if not fields_string.strip():
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
                    class_dict[name] = (
                        FieldClass(desc=desc)
                        if desc is not None
                        else FieldClass()
                    )

        process_fields(inputs_spec, "input")
        process_fields(outputs_spec, "output")

        # Create and return the dynamic class
        DynamicSignature = type("dspy_" + agent_name, (base_class,), class_dict)
        logger.debug(
            f"Created DSPy Signature: {DynamicSignature.__name__} with fields: {DynamicSignature.__annotations__}"
        )
        return DynamicSignature

    def _configure_language_model(
        self, model, use_cache, temperature, max_tokens
    ) -> None:
        import dspy

        """Initialize and configure the language model using dspy."""
        lm = dspy.LM(
            model,
            cache=use_cache,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        dspy.configure(lm=lm)

    def _select_task(
        self,
        signature: Any,
        agent_type_override: AgentType,
        tools: list[Any] | None = None,
    ) -> Any:
        """Select and instantiate the appropriate task based on tool availability.

        Args:
            prompt: The detailed prompt string.
            input_desc: Dictionary of input key descriptions.
            output_desc: Dictionary of output key descriptions.

        Returns:
            An instance of a dspy task (either ReAct or Predict).
        """
        import dspy

        processed_tools = []
        if tools:
            for tool in tools:
                if inspect.ismodule(tool) or inspect.isclass(tool):
                    processed_tools.extend(get_callable_members(tool))
                else:
                    processed_tools.append(tool)

        dspy_solver = None

        if agent_type_override:
            if agent_type_override == "ChainOfThought":
                dspy_solver = dspy.ChainOfThought(
                    signature,
                )
            if agent_type_override == "ReAct":
                dspy.ReAct(
                    signature,
                    tools=processed_tools,
                    max_iters=10,
                )
            if agent_type_override == "Completion":
                dspy_solver = dspy.Predict(
                    signature,
                )
        else:
            if tools:
                dspy_solver = dspy.ReAct(
                    signature,
                    tools=processed_tools,
                    max_iters=10,
                )
            else:
                dspy_solver = dspy.Predict(
                    signature,
                )

        return dspy_solver

    def _process_result(
        self, result: Any, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert the result to a dictionary and add the inputs for an unified result object.

        Args:
            result: The raw result from the dspy task.
            inputs: The original inputs provided to the agent.

        Returns:
            A dictionary containing the processed output.
        """
        try:
            result = result.toDict()
            for key in inputs:
                result.setdefault(key, inputs.get(key))
        except Exception as conv_error:
            logger.warning(
                f"Warning: Failed to convert result to dict in agent '{self.name}': {conv_error}"
            )
        return result
