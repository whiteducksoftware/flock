"""Utility functions for resolving input keys to their corresponding values."""

from flock.core.context.context import FlockContext


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


def split_top_level(s: str) -> list[str]:
    """Split a string on commas that are not enclosed within brackets, parentheses, or quotes.

    This function iterates over the string while keeping track of the nesting level. It
    only splits on commas when the nesting level is zero. It also properly handles quoted
    substrings.

    Args:
        s (str): The input string.

    Returns:
        List[str]: A list of substrings split at top-level commas.
    """
    parts = []
    current = []
    level = 0
    in_quote = False
    quote_char = ""

    for char in s:
        # If inside a quote, only exit when the matching quote is found.
        if in_quote:
            current.append(char)
            if char == quote_char:
                in_quote = False
            elif char == "\\":
                # Include escape sequences
                continue
            continue

        # Check for the start of a quote.
        if char in ('"', "'"):
            in_quote = True
            quote_char = char
            current.append(char)
            continue

        # Track nesting.
        if char in "([{":
            level += 1
        elif char in ")]}":
            level -= 1

        # Split on commas if not nested.
        if char == "," and level == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


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
                inputs[key] = historic_value
                continue

            # Fallback to the initial input
            inputs[key] = context.get_variable("flock." + key)

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
            inputs[key] = context.get_variable(f"{entity_name}.{property_name}")
            continue

    return inputs
