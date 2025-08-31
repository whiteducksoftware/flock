"""Defines granular Temporal activities for executing a single agent
and determining the next agent in a Flock workflow.
"""

from collections.abc import Callable

from opentelemetry import trace
from temporalio import activity

# Third-party imports only within activity functions if needed, or pass context
# For core flock types, import directly
from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_MODEL
from flock.core.flock_agent import FlockAgent  # Import concrete class if needed
from flock.core.registry import get_registry
# HandOffRequest removed - using agent.next_agent directly
from flock.core.logging.logging import get_logger
from flock.core.util.input_resolver import resolve_inputs

logger = get_logger("agent_activity")  # Using a distinct logger category
tracer = trace.get_tracer(__name__)
registry = get_registry()  # Get registry instance once


@activity.defn
async def execute_single_agent(agent_name: str, context_dict: dict) -> dict:
    """Executes a single specified agent and returns its result.

    Args:
        agent_name: The name of the agent to execute.
        context: The current FlockContext (passed from the workflow).

    Returns:
        The raw result dictionary from the agent's execution.

    Raises:
        ValueError: If the agent is not found in the registry.
        Exception: Propagates exceptions from agent execution for Temporal retries.
    """
    with tracer.start_as_current_span("execute_single_agent") as span:
        span.set_attribute("agent.name", agent_name)
        logger.info("Executing single agent", agent=agent_name)

        agent = registry.get_agent(agent_name)
        if not agent:
            logger.error("Agent not found in registry", agent=agent_name)
            # Raise error for Temporal to potentially retry/fail the activity
            raise ValueError(f"Agent '{agent_name}' not found in registry.")

        # Rehydrate context from dict and set on agent (transient for this execution)
        context = FlockContext.from_dict(context_dict)
        agent.context = context

        # Ensure model is set (using context value if needed)
        # Consider if this should be done once when agent is added or workflow starts
        if agent.model is None:
            agent_model = context.get_variable(FLOCK_MODEL)
            if agent_model:
                agent.set_model(agent_model)
                logger.debug(
                    f"Set model for agent '{agent_name}' from context: {agent_model}"
                )

        # Resolve agent-specific callables if necessary
        # This might be better handled in the workflow before the loop starts
        # or when agents are initially loaded. Assuming it's handled elsewhere for now.
        # agent.resolve_callables(context=context)

        # Resolve inputs for this specific agent run
        previous_agent_name = context.get_last_agent_name()  # May be None on first agent
        prev_def = (
            context.get_agent_definition(previous_agent_name)
            if previous_agent_name
            else None
        )
        prev_out_spec = (
            (prev_def.agent_data.get("output_spec") if isinstance(prev_def, type(prev_def)) else None)
            if prev_def and isinstance(prev_def.agent_data, dict)
            else None
        )
        prev_cfg = (
            prev_def.agent_data.get("config")
            if prev_def and isinstance(prev_def.agent_data, dict)
            else {}
        )
        prev_strategy = (
            prev_cfg.get("handoff_strategy") if isinstance(prev_cfg, dict) else None
        ) or "static"
        prev_map = (
            prev_cfg.get("handoff_map") if isinstance(prev_cfg, dict) else None
        ) or {}
        logger.debug(
            f"Resolving inputs for {agent_name} with previous agent {previous_agent_name}"
        )
        agent_inputs = resolve_inputs(
            agent.input,
            context,
            previous_agent_name or "",
            prev_out_spec or "",
            prev_strategy,
            prev_map,
        )
        span.add_event(
            "resolved inputs", attributes={"inputs": str(agent_inputs)}
        )

        try:
            # Execute just this agent
            result = await agent.run_async(agent_inputs)
            # Avoid logging potentially large results directly to span attributes
            result_str = str(result)
            span.set_attribute("result.type", type(result).__name__)
            span.set_attribute(
                "result.preview",
                result_str[:500] + ("..." if len(result_str) > 500 else ""),
            )
            logger.info("Single agent execution completed", agent=agent_name)
            return result
        except Exception as e:
            logger.error(
                "Single agent execution failed",
                agent=agent_name,
                error=str(e),
                exc_info=True,
            )
            # Debug aid: ensure exception prints even if logger is muted in environment
            print(f"[agent_activity] Single agent execution failed for {agent_name}: {e!r}")
            span.record_exception(e)
            # Re-raise the exception for Temporal to handle based on retry policy
            raise


@activity.defn
async def determine_next_agent(
    current_agent_name: str, result: dict, context_dict: dict
) -> str | None:
    """Determine the next agent using the agent's routing component.

    Returns the next agent's name or None if the workflow should terminate.
    """
    with tracer.start_as_current_span("determine_next_agent") as span:
        span.set_attribute("agent.name", current_agent_name)
        logger.info("Determining next agent after", agent=current_agent_name)

        agent = registry.get_agent(current_agent_name)
        if not agent:
            logger.error(
                "Agent not found for routing", agent=current_agent_name
            )
            raise ValueError(
                f"Agent '{current_agent_name}' not found for routing."
            )

        if not agent.router:
            logger.info(
                "No router defined for agent", agent=current_agent_name
            )
            span.add_event("no_router")
            return None  # Indicate no handoff

        logger.debug(
            f"Using router {agent.router.__class__.__name__}",
            agent=agent.name,
        )
        try:
            # Execute routing logic on the router component (unified architecture)
            context = FlockContext.from_dict(context_dict)
            next_val = await agent.router.determine_next_step(agent, result, context)

            # Convert to a simple agent name if needed
            if isinstance(next_val, FlockAgent):
                next_name = next_val.name
            elif isinstance(next_val, str):
                next_name = next_val
            else:
                next_name = None

            if not next_name:
                logger.info("Router determined no next agent", agent=agent.name)
                span.add_event("no_next_agent_from_router")
                return None

            logger.info(
                "Next agent determined",
                next_agent=next_name,
                agent=agent.name,
            )
            span.set_attribute("next_agent", next_name)
            return next_name

        except Exception as e:
            # Catch potential errors during routing execution
            logger.error(
                "Router execution failed",
                agent=agent.name,
                error=str(e),
                exc_info=True,
            )
            print(f"[agent_activity] Router execution failed for {agent.name}: {e!r}")
            span.record_exception(e)
            # Let Temporal handle the activity failure based on retry policy
            raise
