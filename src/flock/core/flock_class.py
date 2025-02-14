# src/flock/core/flock_class.py
import asyncio
import json

from flock.core.flock_agent import FlockAgent

# Define basic types we treat as primitive.
BASIC_TYPES = {str, int, float, bool, list, dict}


def flockclass(model: str):
    def decorator(cls):
        cls.__is_flockclass__ = True  # Mark this class as agent-generated.
        orig_init = cls.__init__

        def new_init(self, *args, **kwargs):
            # --- Parent Initialization ---
            # Call the original __init__ (if defined) so that input fields get set.
            if orig_init is not object.__init__:
                orig_init(self, *args, **kwargs)
            # Save provided constructor inputs on the instance.
            inputs = kwargs.copy()
            for key, value in inputs.items():
                setattr(self, key, value)
            # Determine which fields are inputs (provided) and which should be generated.
            input_fields = list(inputs.keys())
            basic_output_fields = []
            subagent_fields = []
            for field, t in cls.__annotations__.items():
                if field in input_fields:
                    continue
                # If the field's type is a user-defined class (has __annotations__) and not in BASIC_TYPES,
                # mark it for recursive evaluation.
                if (
                    hasattr(t, "__annotations__")
                    and isinstance(t, type)
                    and t not in BASIC_TYPES
                ):
                    subagent_fields.append(field)
                else:
                    basic_output_fields.append(field)
            # --- Parent Agent Evaluation for Basic Outputs ---
            # Build parent's input string:
            # "field: fieldtype | property of a class named CLASSNAME"
            input_list = []
            for field, value in inputs.items():
                t = cls.__annotations__.get(field, type(getattr(self, field)))
                type_str = t.__name__ if hasattr(t, "__name__") else str(t)
                desc = f"property of a class named {cls.__name__}"
                input_list.append(f"{field}: {type_str} | {desc}")
            parent_input_str = ", ".join(input_list)
            # Build parent's output string for basic outputs.
            output_list = []
            for field in basic_output_fields:
                t = cls.__annotations__[field]
                type_str = t.__name__ if hasattr(t, "__name__") else str(t)
                desc = f"property of a class named {cls.__name__}"
                output_list.append(f"{field}: {type_str} | {desc}")
            parent_output_str = ", ".join(output_list)
            # Create and evaluate the parent's agent.
            parent_agent = FlockAgent(
                name=cls.__name__,
                input=parent_input_str,
                output=parent_output_str,
                model=model,
                description=f"Agent for {cls.__name__}",
            )
            parent_result = asyncio.run(parent_agent.evaluate(inputs))
            for field in basic_output_fields:
                if field in parent_result:
                    setattr(self, field, parent_result[field])
            # --- Recursive Evaluation for Subagent Fields ---
            for field in subagent_fields:
                sub_cls = cls.__annotations__[field]
                # Build parent's current state excluding the subobject field.
                parent_data = {
                    k: v for k, v in self.__dict__.items() if k != field
                }
                context_json = json.dumps(parent_data, sort_keys=True)
                # For the subagent, we build its input signature using a single field "context"
                # with a description that embeds the parent's data.
                sub_input_str = f"context: str | this is a sub object of {cls.__name__}: {context_json}"
                # Build the subagent's output string from the subobject's annotations.
                sub_output_list = []
                for sub_field, sub_t in sub_cls.__annotations__.items():
                    type_str = (
                        sub_t.__name__
                        if hasattr(sub_t, "__name__")
                        else str(sub_t)
                    )
                    desc = f"property of a class named {sub_cls.__name__}"
                    sub_output_list.append(f"{sub_field}: {type_str} | {desc}")
                sub_output_str = ", ".join(sub_output_list)
                # Create and evaluate the subagent.
                sub_agent = FlockAgent(
                    name=sub_cls.__name__,
                    input=sub_input_str,
                    output=sub_output_str,
                    model=model,
                    description=f"Agent for sub object {sub_cls.__name__} of {cls.__name__}: {context_json}",
                )
                sub_result = asyncio.run(
                    sub_agent.evaluate({"context": context_json})
                )
                # Instantiate the subobject from the agent result.
                sub_obj = sub_cls.__new__(sub_cls)
                for sub_field in sub_cls.__annotations__.keys():
                    if sub_field in sub_result:
                        setattr(sub_obj, sub_field, sub_result[sub_field])
                setattr(self, field, sub_obj)

        cls.__init__ = new_init
        return cls

    return decorator
