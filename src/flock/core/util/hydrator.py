import asyncio
import json
from typing import get_origin, get_type_hints


# -----------------------------------------------------------
# Dummy FlockAgent for demonstration:
# -----------------------------------------------------------
class FlockAgent:
    def __init__(self, name, input, output, model, description):
        self.name = name
        self.input = input
        self.output = output
        self.model = model
        self.description = description

    async def evaluate(self, data: dict) -> dict:
        """Pretend LLM call.
        We'll parse self.output to see which keys we want,
        then generate some placeholders for those keys.
        """
        print(
            f"[FlockAgent] Evaluate called for agent {self.name} with data: {data}"
        )

        # Very naive parse of output string: "title: str | desc, budget: int | desc, ..."
        fields = []
        for out_part in self.output.split(","):
            out_part = out_part.strip()
            # out_part might look like: "title: str | property of MyBlogPost"
            if not out_part:
                continue
            field_name = out_part.split(":")[0].strip()
            fields.append(field_name)

        # We'll pretend the LLM returns either an integer for int fields or a string for others:
        response = {}
        for f in fields:
            if " int" in self.output:  # naive
                response[f] = 42
            else:
                response[f] = f"Generated data for {f}"
        return response


# -----------------------------------------------------------
# Optional: a decorator that marks a class as "flockclass"
# -----------------------------------------------------------
def flockclass(model: str):
    def decorator(cls):
        cls.__is_flockclass__ = True
        cls.__flock_model__ = model
        return cls

    return decorator


# -----------------------------------------------------------
# Utility sets
# -----------------------------------------------------------
BASIC_TYPES = {str, int, float, bool}


# -----------------------------------------------------------
# The main hydrator that can handle:
#   - basic types (do nothing)
#   - user-defined classes (auto-fill missing fields + recurse)
#   - lists (ask LLM how many items to create + fill them)
#   - dicts (ask LLM how many key->value pairs to create + fill them)
# -----------------------------------------------------------
def hydrate_object(obj, model="gpt-4", class_name=None):
    """Recursively hydrates the object in-place,
    calling an LLM for missing fields or structure.
    """
    # 1) If None or basic, do nothing
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return

    # 2) If list, check if it is empty => ask the LLM how many items we need
    if isinstance(obj, list):
        if len(obj) == 0:
            # We'll do a single LLM call to decide how many items to put in:
            # In real usage, you'd put a more robust prompt.
            list_agent = FlockAgent(
                name=f"{class_name or 'list'}Generator",
                input="Generate number of items for this list",
                output="count: int | number of items to create",
                model=model,
                description="Agent that decides how many items to create in a list.",
            )
            result = asyncio.run(list_agent.evaluate({}))
            num_items = result.get("count", 0)
            # We'll assume the list should hold some type T.
            # But in Python, we rarely store that info in the runtime.
            # For demonstration, let's just store dummy strings or we can guess "object".
            for i in range(num_items):
                # For demonstration, create a simple string or dict
                # If you want a typed approach, you'll need additional metadata or pass in generics
                item = f"Generated item {i + 1}"
                obj.append(item)

        # Now recursively fill each item
        for i in range(len(obj)):
            hydrate_object(
                obj[i],
                model=model,
                class_name=f"{class_name or 'list'}[item={i}]",
            )
        return

    # 3) If dict, check if it is empty => ask LLM for which keys to create
    if isinstance(obj, dict):
        if len(obj) == 0:
            # We'll do a single LLM call that returns a list of keys
            dict_agent = FlockAgent(
                name=f"{class_name or 'dict'}Generator",
                input="Generate keys for this dict",
                output="keys: str | comma-separated list of keys to create",
                model=model,
                description="Agent that decides which keys to create in a dict.",
            )
            result = asyncio.run(dict_agent.evaluate({}))
            keys_str = result.get("keys", "")
            keys = [k.strip() for k in keys_str.split(",") if k.strip()]

            # For demonstration, let's assume the dict holds sub-objects that we can fill further
            # We'll create a plain dict or plain string for each key
            for k in keys:
                obj[k] = f"Placeholder for {k}"

        # Now recursively fill each value
        for key, val in obj.items():
            hydrate_object(
                val,
                model=model,
                class_name=f"{class_name or 'dict'}[key={key}]",
            )
        return

    # 4) If it's a user-defined class with annotations, fill missing fields
    cls = type(obj)
    if hasattr(cls, "__annotations__"):
        # If there's a model stored on the class, we can use that. Else fallback to the default
        used_model = getattr(cls, "__flock_model__", model)

        # Figure out which fields are missing or None
        type_hints = get_type_hints(cls)
        missing_basic_fields = []
        complex_fields = []
        for field_name, field_type in type_hints.items():
            value = getattr(obj, field_name, None)
            if value is None:
                # It's missing. See if it's a basic type or complex
                if _is_basic_type(field_type):
                    missing_basic_fields.append(field_name)
                else:
                    complex_fields.append(field_name)
            else:
                # Already has some value, but if it's a complex type, we should recurse
                if not _is_basic_type(field_type):
                    complex_fields.append(field_name)

        # If we have missing basic fields, do a single LLM call to fill them
        if missing_basic_fields:
            input_str = (
                f"Existing data: {json.dumps(obj.__dict__, default=str)}"
            )
            output_fields_str = []
            for bf in missing_basic_fields:
                bf_type = type_hints[bf]
                bf_type_name = (
                    bf_type.__name__
                    if hasattr(bf_type, "__name__")
                    else str(bf_type)
                )
                desc = f"property of a class named {cls.__name__}"
                output_fields_str.append(f"{bf}: {bf_type_name} | {desc}")

            agent = FlockAgent(
                name=cls.__name__,
                input=input_str,
                output=", ".join(output_fields_str),
                model=used_model,
                description=f"Agent for {cls.__name__}",
            )
            result = asyncio.run(agent.evaluate(obj.__dict__))
            for bf in missing_basic_fields:
                if bf in result:
                    setattr(obj, bf, result[bf])

        # For each "complex" field, instantiate if None + recurse
        for cf in complex_fields:
            cf_value = getattr(obj, cf, None)
            cf_type = type_hints[cf]

            if cf_value is None:
                # We need to create something of the appropriate type
                new_val = _instantiate_type(cf_type)
                setattr(obj, cf, new_val)
                hydrate_object(
                    new_val, model=used_model, class_name=cf_type.__name__
                )
            else:
                # Recurse into it
                hydrate_object(
                    cf_value, model=used_model, class_name=cf_type.__name__
                )

    else:
        # It's some Python object with no annotations -> do nothing
        pass


# -----------------------------------------------------------
# Helper: is a type "basic"?
# -----------------------------------------------------------
def _is_basic_type(t):
    if t in BASIC_TYPES:
        return True
    # You may want to check for Optionals or Unions
    # e.g., if get_origin(t) == Union, parse that, etc.
    return False


# -----------------------------------------------------------
# Helper: instantiate a type (list, dict, or user-defined)
# -----------------------------------------------------------
def _instantiate_type(t):
    origin = get_origin(t)
    if origin is list:
        return []
    if origin is dict:
        return {}

    # If it's a built-in basic type, return None (we fill it from LLM).
    if t in BASIC_TYPES:
        return None

    # If it's a user-defined class
    if isinstance(t, type):
        try:
            # Attempt parameterless init
            return t()
        except:
            # Or try __new__
            try:
                return t.__new__(t)
            except:
                return None
    return None


# -----------------------------------------------------------
# Example classes
# -----------------------------------------------------------
@flockclass("gpt-4")
class LongContent:
    title: str
    content: str


@flockclass("gpt-4")
class MyBlogPost:
    title: str
    headers: str
    # We'll have a dict of key->LongContent
    content: dict[str, LongContent]


@flockclass("gpt-4")
class MyProjectPlan:
    project_idea: str
    budget: int
    title: str
    content: MyBlogPost


# -----------------------------------------------------------
# Demo
# -----------------------------------------------------------
if __name__ == "__main__":
    plan = MyProjectPlan()
    plan.project_idea = "a declarative agent framework"
    plan.budget = 100000

    # content is None by default, so the hydrator will create MyBlogPost
    # and fill it in. MyBlogPost.content is a dict[str, LongContent],
    # also None -> becomes an empty dict -> we let the LLM decide the keys.

    hydrate_object(plan, model="gpt-4", class_name="MyProjectPlan")

    print("\n--- MyProjectPlan hydrated ---")
    for k, v in plan.__dict__.items():
        print(f"{k} = {v}")
    if plan.content:
        print("\n--- MyBlogPost hydrated ---")
        for k, v in plan.content.__dict__.items():
            print(f"  {k} = {v}")
            if k == "content" and isinstance(v, dict):
                print("    (keys) =", list(v.keys()))
                for sub_k, sub_val in v.items():
                    print(f"    {sub_k} -> {sub_val}")
                    if isinstance(sub_val, LongContent):
                        print(
                            f"       -> LongContent fields: {sub_val.__dict__}"
                        )
