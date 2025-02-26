"""Module for managing the FlockContext."""

from flock.core.context.context import FlockContext
from flock.core.context.context_vars import (
    FLOCK_CURRENT_AGENT,
    FLOCK_INITIAL_INPUT,
    FLOCK_LOCAL_DEBUG,
    FLOCK_MODEL,
    FLOCK_RUN_ID,
)


def initialize_context(
    context: FlockContext,
    agent_name: str,
    input_data: dict,
    run_id: str,
    local_debug: bool,
    model: str,
) -> None:
    """Initialize the FlockContext with standard variables before running an agent.

    Args:
        context: The FlockContext instance.
        agent_name: The name of the current agent.
        input_data: A dictionary of inputs for the agent.
        run_id: A unique identifier for the run.
        local_debug: Flag indicating whether local debugging is enabled.
    """
    context.set_variable(FLOCK_CURRENT_AGENT, agent_name)
    for key, value in input_data.items():
        context.set_variable("flock." + key, value)
    context.set_variable(FLOCK_INITIAL_INPUT, input_data)
    context.set_variable(FLOCK_LOCAL_DEBUG, local_debug)
    context.run_id = run_id
    context.set_variable(FLOCK_RUN_ID, run_id)
    context.set_variable(FLOCK_MODEL, model)
