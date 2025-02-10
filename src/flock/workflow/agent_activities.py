from temporalio import activity

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent


@activity.defn
async def run_declarative_agent_activity(params: dict) -> dict:
    """Temporal activity to run a declarative (or batch) agent.

    Expects a dictionary with:
      - "agent_data": a dict representation of the agent (as produced by .dict()),
      - "context_data": a dict containing the FlockContext state and optionally other fields.

    The activity reconstructs the agent and a FlockContext, then calls the agent’s _evaluate() method.
    """
    agent_data = params.get("agent_data")
    context_data = params.get("context_data", {})
    # Reconstruct the agent from its serialized representation.
    agent = FlockAgent.from_dict(agent_data)
    # Reconstruct the FlockContext from the state.
    context = FlockContext.from_dict(context_data)
    result = await agent.evaluate(context)
    return result
