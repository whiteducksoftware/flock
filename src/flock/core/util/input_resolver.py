"""Utility functions for resolving input keys to their corresponding values."""

from flock.core.context.context import FlockContext
from flock.core.util.splitter import split_top_level


def get_callable_members(obj):
    """Extract all callable (methods/functions) members from a module or class.
    Returns a list of callable objects.
    """
    import inspect

    # Get all members of the object
    members = inspect.getmembers(obj)

    # Filter for callable members that don't start with underscore (to exclude private/special methods)
    callables = [
        member[1]
        for member in members
        if inspect.isroutine(member[1]) and not member[0].startswith("_")
    ]

    return callables


def _parse_keys(keys: list[str]) -> list[str]:
    """Split a comma‐separated string and strip any type annotations.

    For example, "a, b: list[str]" becomes ["a", "b"].
    """
    res_keys = []
    for key in keys:
        if "|" in key:
            key = key.split("|")[0].strip()
        if ":" in key:
            key = key.split(":")[0].strip()
        res_keys.append(key)
    return res_keys


def top_level_to_keys(s: str) -> list[str]:
    """Convert a top-level comma-separated string to a list of keys."""
    top_level_split = split_top_level(s)
    return _parse_keys(top_level_split)


def resolve_inputs(
    input_spec: str, context: FlockContext, previous_agent_name: str
) -> dict:
    """Build a dictionary of inputs based on the input specification string and the provided context.

    The lookup rules are:
      - "context" (case-insensitive): returns the entire context.
      - "context.property": returns an attribute from the context.
      - "def.agent_name": returns the agent definition for the given agent.
      - "agent_name": returns the most up2date record from the given agent's history.
      - "agent_name.property": returns the value of a property from the state variable keyed by "agent_name.property".
      - "property": searches the history for the most recent value of a property.
      - Otherwise, if no matching value is found, fallback to the FLOCK_INITIAL_INPUT.

    -> Recommendations:
        - prefix your agent variables with the agent name or a short handle to avoid conflicts.
        eg. agent name: "idea_agent", variable: "ia_idea" (ia = idea agent)
        - or set hand off mode to strict to avoid conflicts.
        with strict mode, the agent will only accept inputs from the previous agent.

    Args:
        input_spec: Comma-separated input keys (e.g., "query" or "agent_name.property").
        context: A FlockContext instance.

    Returns:
        A dictionary mapping each input key to its resolved value.
    """
    split_input = split_top_level(input_spec)
    keys = _parse_keys(split_input)
    inputs = {}

    def _normalize_empty_string(val):
        """Treat empty string inputs as None to match None semantics.

        This aligns behavior so passing "" behaves like passing None
        for agent input properties.
        """
        if isinstance(val, str) and val == "":
            return None
        return val

    for key in keys:
        split_key = key.split(".")

        # Case 1: A single key
        if len(split_key) == 1:
            # Special keyword: "context"
            if key.lower() == "context":
                inputs[key] = context
                continue

            # Try to get a historic record for an agent (if any)
            historic_records = context.get_agent_history(key)
            if historic_records:
                # You may choose to pass the entire record or just its data.
                inputs[key] = historic_records[0].data
                continue

            # Fallback to the most recent value in the state
            historic_value = context.get_most_recent_value(key)
            if historic_value is not None:
                inputs[key] = _normalize_empty_string(historic_value)
                continue

            # Fallback to the initial input
            var_value = context.get_variable(key)
            if var_value is not None:
                inputs[key] = _normalize_empty_string(var_value)
                continue

            inputs[key] = _normalize_empty_string(
                context.get_variable("flock." + key)
            )

        # Case 2: A compound key (e.g., "agent_name.property" or "context.property")
        elif len(split_key) == 2:
            entity_name, property_name = split_key

            if entity_name.lower() == "context":
                # Try to fetch the attribute from the context
                inputs[key] = getattr(context, property_name, None)
                continue

            if entity_name.lower() == "def":
                # Return the agent definition for the given property name
                inputs[key] = context.get_agent_definition(property_name)
                continue

            # Otherwise, attempt to look up a state variable with the key "agent_name.property"
            inputs[key] = _normalize_empty_string(
                context.get_variable(f"{entity_name}.{property_name}")
            )
            continue

    return inputs
