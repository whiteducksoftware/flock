"""Mixin class for integrating with the dspy library."""

import inspect
import sys
from typing import Any, Literal

from flock.core.logging.logging import get_logger
from flock.core.util.input_resolver import get_callable_members, split_top_level

logger = get_logger("flock")

AgentType = (
    Literal["ReAct"] | Literal["Completion"] | Literal["ChainOfThought"] | None
)


class DSPyIntegrationMixin:
    """Mixin class for integrating with the dspy library."""

    def create_dspy_signature_class(
        self, agent_name, description_spec, fields_spec
    ) -> Any:
        """Trying to create a dynamic class using dspy library."""
        # ---------------------------
        # 1. Parse the class specification.
        # ---------------------------
        import dspy

        base_class = dspy.Signature

        # Start building the class dictionary with a docstring and annotations dict.
        class_dict = {"__doc__": description_spec, "__annotations__": {}}

        # ---------------------------
        # 2. Split the fields specification into inputs and outputs.
        # ---------------------------
        if "->" in fields_spec:
            inputs_spec, outputs_spec = fields_spec.split("->", 1)
        else:
            inputs_spec, outputs_spec = fields_spec, ""

        # ---------------------------
        # 3. Draw the rest of the owl.
        # ---------------------------
        def parse_field(field_str):
            """Parser.

            Parse a field of the form:
                <name> [ : <type> ] [ | <desc> ]
            Returns a tuple: (name, field_type, desc)
            """
            field_str = field_str.strip()
            if not field_str:
                return None

            parts = field_str.split("|", 1)
            main_part = parts[0].strip()  # contains name and (optionally) type
            desc = parts[1].strip() if len(parts) > 1 else None

            if ":" in main_part:
                name, type_str = [s.strip() for s in main_part.split(":", 1)]
            else:
                name = main_part
                type_str = "str"  # default type

            # Evaluate the type. Since type can be any valid expression (including custom types),
            # we use eval. (Be cautious if using eval with untrusted input.)
            try:
                # TODO: We have to find a way to avoid using eval here.
                # This is a security risk, as it allows arbitrary code execution.
                # Figure out why the following code doesn't work as well as the eval.

                # import dspy

                # field_type = dspy.PythonInterpreter(
                #     sys.modules[__name__].__dict__ | sys.modules["__main__"].__dict__
                # ).execute(type_str)

                try:
                    field_type = eval(type_str, sys.modules[__name__].__dict__)
                except Exception as e:
                    logger.warning(
                        "Failed to evaluate type_str in __name__" + str(e)
                    )
                    field_type = eval(
                        type_str, sys.modules["__main__"].__dict__
                    )

            except Exception as ex:
                # AREPL fix - var
                logger.warning(
                    "Failed to evaluate type_str in __main__" + str(ex)
                )
                try:
                    field_type = eval(
                        f"exec_locals.get('{type_str}')",
                        sys.modules["__main__"].__dict__,
                    )
                except Exception as ex_arepl:
                    logger.warning(
                        "Failed to evaluate type_str in exec_locals"
                        + str(ex_arepl)
                    )
                    field_type = str

            return name, field_type, desc

        def process_fields(fields_string, field_kind):
            """Process a comma-separated list of field definitions.

            field_kind: "input" or "output" determines which Field constructor to use.
            """
            if not fields_string.strip():
                return

            # Split on commas.
            for field in split_top_level(fields_string):
                if field.strip():
                    parsed = parse_field(field)
                    if not parsed:
                        continue
                    name, field_type, desc = parsed
                    class_dict["__annotations__"][name] = field_type

                    # Use the proper Field constructor.
                    if field_kind == "input":
                        if desc is not None:
                            class_dict[name] = dspy.InputField(desc=desc)
                        else:
                            class_dict[name] = dspy.InputField()
                    elif field_kind == "output":
                        if desc is not None:
                            class_dict[name] = dspy.OutputField(desc=desc)
                        else:
                            class_dict[name] = dspy.OutputField()
                    else:
                        raise ValueError("Unknown field kind: " + field_kind)

        # Process input fields (to be used with my.InputField)
        process_fields(inputs_spec, "input")
        # Process output fields (to be used with my.OutputField)
        process_fields(outputs_spec, "output")

        return type("dspy_" + agent_name, (base_class,), class_dict)

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
