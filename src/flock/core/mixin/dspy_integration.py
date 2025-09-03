# src/flock/core/mixin/dspy_integration.py
"""Mixin class for integrating with the dspy library.

This mixin centralizes Flock ↔ DSPy interop. It intentionally
delegates more to DSPy’s native builders (Signature, settings.context,
modules) to reduce custom glue and stay aligned with DSPy updates.
"""

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

    def create_dspy_signature_class(self, agent_name: str, description_spec: str, fields_spec: str) -> Any:
        """Create a DSPy Signature using DSPy's native builder.

        We support the Flock spec format: "field: type | description, ... -> ...".
        This converts to the dict-based make_signature format with
        InputField/OutputField and resolved Python types.
        """
        try:
            import dspy
        except ImportError as exc:
            logger.error("DSPy is not installed. Install with: pip install dspy-ai")
            raise

        # Split input/output part
        if "->" in fields_spec:
            inputs_spec, outputs_spec = fields_spec.split("->", 1)
        else:
            inputs_spec, outputs_spec = fields_spec, ""

        def parse_field(field_str: str) -> tuple[str, type, str | None] | None:
            field_str = field_str.strip()
            if not field_str:
                return None
            parts = field_str.split("|", 1)
            main_part = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else None
            if ":" in main_part:
                name, type_str = [s.strip() for s in main_part.split(":", 1)]
            else:
                name, type_str = main_part, "str"
            try:
                py_type = _resolve_type_string(type_str)
            except Exception as e:
                logger.warning(
                    f"Type resolution failed for '{type_str}' in field '{name}': {e}. Falling back to str."
                )
                py_type = str
            return name, py_type, desc

        def to_field_tuples(spec: str, kind: str) -> dict[str, tuple[type, Any]]:
            mapping: dict[str, tuple[type, Any]] = {}
            if not spec.strip():
                return mapping
            for raw in split_top_level(spec):
                parsed = parse_field(raw)
                if not parsed:
                    continue
                fname, ftype, fdesc = parsed
                FieldClass = dspy.InputField if kind == "input" else dspy.OutputField
                finfo = FieldClass(desc=fdesc) if fdesc is not None else FieldClass()
                mapping[fname] = (ftype, finfo)
            return mapping

        try:
            fields: dict[str, tuple[type, Any]] = {
                **to_field_tuples(inputs_spec, "input"),
                **to_field_tuples(outputs_spec, "output"),
            }
            sig = dspy.Signature(fields, description_spec or None, signature_name=f"dspy_{agent_name}")
            logger.info("Created DSPy Signature %s", sig.__name__)
            return sig
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Failed to create DSPy Signature for %s: %s", agent_name, e, exc_info=True)
            raise

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
            logger.error("DSPy is not installed; cannot configure LM.")
            return

        # Build an LM instance for per-call usage; prefer settings.context over global configure.
        try:
            lm_instance = dspy.LM(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                cache=use_cache,
            )
            # Do not call settings.configure() here to avoid cross-task/thread conflicts.
            # Callers should pass this LM via dspy.settings.context(lm=...) or program.acall(lm=...)
            dspy.settings  # touch to ensure settings is importable
            logger.info(
                "Prepared DSPy LM (defer install to settings.context): model=%s temp=%s max_tokens=%s",
                model,
                temperature,
                max_tokens,
            )
        except Exception as e:
            logger.error("Failed to prepare DSPy LM '%s': %s", model, e, exc_info=True)
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
            selected_type = "ReAct" if processed_tools or processed_mcp_tools else "Predict"

        # Normalize common aliases/casing
        sel = selected_type.lower() if isinstance(selected_type, str) else selected_type
        if isinstance(sel, str):
            if sel in {"completion", "predict"}:
                sel = "predict"
            elif sel in {"react"}:
                sel = "react"
            elif sel in {"chainofthought", "cot", "chain_of_thought"}:
                sel = "chain_of_thought"

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
            if sel == "chain_of_thought":
                dspy_program = dspy.ChainOfThought(signature, **kwargs)
            elif sel == "react":
                if not kwargs:
                    kwargs = {"max_iters": max_tool_calls}
                dspy_program = dspy.ReAct(
                    signature, tools=merged_tools or [], **kwargs
                )
            elif sel == "predict":
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

    def _process_result(self, result: Any, inputs: dict[str, Any]) -> tuple[dict[str, Any], float, list]:
        """Convert a DSPy Prediction or mapping to a plain dict and attach LM history.

        Returns (result_dict, cost_placeholder, lm_history). The cost is set to 0.0;
        use token usage trackers elsewhere for accurate accounting.
        """
        try:
            import dspy
        except ImportError:
            dspy = None

        if result is None:
            logger.warning("DSPy program returned None result.")
            return {}, 0.0, []

        try:
            # Best-effort extraction from DSPy Prediction
            if dspy and isinstance(result, dspy.Prediction):
                output_dict = dict(result.items(include_dspy=False))
            elif isinstance(result, dict):
                output_dict = result
            elif hasattr(result, "items") and callable(result.items):
                try:
                    output_dict = dict(result.items())
                except Exception:
                    output_dict = {"raw_result": str(result)}
            else:
                output_dict = {"raw_result": str(result)}

            final_result = {**inputs, **output_dict}

            lm_history = []
            try:
                if dspy and dspy.settings.lm is not None and hasattr(dspy.settings.lm, "history"):
                    lm_history = dspy.settings.lm.history
            except Exception:
                lm_history = []

            return final_result, 0.0, lm_history

        except Exception as conv_error:  # pragma: no cover - defensive
            logger.error("Failed to process DSPy result into dictionary: %s", conv_error, exc_info=True)
            return {"error": "Failed to process result", "raw_result": str(result)}, 0.0, []
