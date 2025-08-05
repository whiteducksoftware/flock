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
async def execute_single_agent(agent_name: str, context: FlockContext) -> dict:
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

        # Set agent's context reference (transient, for this execution)
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
        previous_agent_name = (
            context.get_last_agent_name()
        )  # Relies on context method
        logger.debug(
            f"Resolving inputs for {agent_name} with previous agent {previous_agent_name}"
        )
        agent_inputs = resolve_inputs(agent.input, context, previous_agent_name)
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
            span.record_exception(e)
            # Re-raise the exception for Temporal to handle based on retry policy
            raise


@activity.defn
async def determine_next_agent(
    current_agent_name: str, result: dict, context: FlockContext
) -> dict | None:
    """Determines the next agent using the current agent's handoff router.

    Args:
        current_agent_name: The name of the agent that just ran.
        result: The result produced by the current agent.
        context: The current FlockContext.

    Returns:
        A dictionary representing the HandOffRequest (serialized via model_dump),
        or None if no handoff occurs or router doesn't specify a next agent.

    Raises:
        ValueError: If the current agent cannot be found.
        Exception: Propagates exceptions from router execution for Temporal retries.
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
            # Execute the routing logic
            handoff_data: (
                HandOffRequest | Callable
            ) = await agent.router.route(agent, result, context)

            # Handle callable handoff functions - This is complex in distributed systems.
            # Consider if this pattern should be supported or if routing should always
            # return serializable data directly. Executing arbitrary code from context
            # within an activity can have side effects and security implications.
            # Assuming for now it MUST return HandOffRequest or structure convertible to it.
            if callable(handoff_data):
                logger.warning(
                    "Callable handoff detected - executing function.",
                    agent=agent.name,
                )
                # Ensure context is available if the callable needs it
                try:
                    handoff_data = handoff_data(
                        context, result
                    )  # Potential side effects
                    if not isinstance(handoff_data, HandOffRequest):
                        logger.error(
                            "Handoff function did not return a HandOffRequest object.",
                            agent=agent.name,
                        )
                        raise TypeError(
                            "Handoff function must return a HandOffRequest object."
                        )
                except Exception as e:
                    logger.error(
                        "Handoff function execution failed",
                        agent=agent.name,
                        error=str(e),
                        exc_info=True,
                    )
                    span.record_exception(e)
                    raise  # Propagate error

            # Ensure we have a HandOffRequest object after potentially calling function
            if not isinstance(handoff_data, HandOffRequest):
                logger.error(
                    "Router returned unexpected type",
                    type=type(handoff_data).__name__,
                    agent=agent.name,
                )
                raise TypeError(
                    f"Router for agent '{agent.name}' did not return a HandOffRequest object."
                )

            # Ensure agent instance is converted to name for serialization across boundaries
            if isinstance(handoff_data.next_agent, FlockAgent):
                handoff_data.next_agent = handoff_data.next_agent.name

            # If router logic determines no further agent, return None
            if not handoff_data.next_agent:
                logger.info("Router determined no next agent", agent=agent.name)
                span.add_event("no_next_agent_from_router")
                return None

            logger.info(
                "Handoff determined",
                next_agent=handoff_data.next_agent,
                agent=agent.name,
            )
            span.set_attribute("next_agent", handoff_data.next_agent)
            # Return the serializable HandOffRequest data using Pydantic's export method
            return handoff_data.model_dump(
                mode="json"
            )  # Ensure JSON-serializable

        except Exception as e:
            # Catch potential errors during routing execution
            logger.error(
                "Router execution failed",
                agent=agent.name,
                error=str(e),
                exc_info=True,
            )
            span.record_exception(e)
            # Let Temporal handle the activity failure based on retry policy
            raise
