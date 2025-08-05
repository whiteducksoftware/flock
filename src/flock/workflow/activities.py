"""Defines Temporal activities for running a chain of agents with logging and tracing."""

from datetime import datetime

from opentelemetry import trace
from temporalio import activity

from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_CURRENT_AGENT, FLOCK_MODEL

# HandOffRequest removed - using agent.next_agent directly
from flock.core.logging.logging import get_logger
from flock.core.registry import get_registry
from flock.core.util.input_resolver import resolve_inputs

logger = get_logger("activities")
tracer = trace.get_tracer(__name__)

def apply_handoff_strategy(previous_agent_output:str, next_agent_input:str, previous_agent_handoff_strategy:str, previous_agent_handoff_map:dict[str, str]) -> str:
    if previous_agent_handoff_strategy == "append":
        return next_agent_input + previous_agent_output
    elif previous_agent_handoff_strategy == "override":
        return previous_agent_output
    elif previous_agent_handoff_strategy == "static":
        return next_agent_input
    elif previous_agent_handoff_strategy == "map":
        for key, value in previous_agent_handoff_map.items():
            next_agent_input = next_agent_input.replace(key, value)
        return next_agent_input
    raise NotImplementedError


@activity.defn
async def run_agent(context: FlockContext) -> dict:
    """Runs a chain of agents using the provided context.

    The context contains state, history, and agent definitions.
    After each agent run, its output is merged into the context.
    """
    # Start a top-level span for the entire run_agent activity.
    with tracer.start_as_current_span("run_agent") as span:
        registry = get_registry()

        previous_agent_name = ""
        previous_agent_output = ""
        previous_agent_handoff_strategy = ""
        previous_agent_handoff_map = {}
        if isinstance(context, dict):
            context = FlockContext.from_dict(context)
        current_agent_name = context.get_variable(FLOCK_CURRENT_AGENT)
        span.set_attribute("initial.agent", current_agent_name)
        logger.info("Starting agent chain", initial_agent=current_agent_name)

        agent = registry.get_agent(current_agent_name)
        if agent.model is None or agent.evaluator.config.model is None:
            agent.set_model(context.get_variable(FLOCK_MODEL))

        if not agent:
            logger.error("Agent not found", agent=current_agent_name)
            span.record_exception(
                Exception(f"Agent '{current_agent_name}' not found")
            )
            return {"error": f"Agent '{current_agent_name}' not found."}

        # Loop over agents in the chain.
        while agent:
            # Create a nested span for this iteration.
            with tracer.start_as_current_span("agent_iteration") as iter_span:
                iter_span.set_attribute("agent.name", agent.name)
                agent.context = context
                # Resolve inputs for the agent.
                # Gets values from context, previous agent output, and handoff strategy.
                agent_inputs = resolve_inputs(
                    agent.input,
                    context,
                    previous_agent_name,
                    previous_agent_output,
                    previous_agent_handoff_strategy,
                    previous_agent_handoff_map
                )
                iter_span.add_event(
                    "resolved inputs", attributes={"inputs": str(agent_inputs)}
                )

                # Execute the agent with its own span.
                with tracer.start_as_current_span("execute_agent") as exec_span:
                    logger.info("Executing agent", agent=agent.name)
                    try:
                        result = await agent.run_async(agent_inputs)
                        exec_span.set_attribute("result", str(result))
                        logger.debug(
                            "Agent execution completed", agent=agent.name
                        )
                        context.record(
                            agent.name,
                            result,
                            timestamp=datetime.now().isoformat(),
                            hand_off=None,
                            called_from=previous_agent_name,
                        )
                    except Exception as e:
                        logger.error(
                            "Agent execution failed",
                            agent=agent.name,
                            error=str(e),
                        )
                        exec_span.record_exception(e)
                        raise

                # Determine the next agent using routing component if available
                next_agent_name = None

                if agent.router:
                    logger.info(
                        f"Using router: {agent.router.__class__.__name__}",
                        agent=agent.name,
                    )
                    try:
                        # Route to the next agent using new routing component
                        next_agent_name = await agent.router.determine_next_step(
                            agent, result, context
                        )

                        # Set next_agent on the agent instance
                        agent.next_agent = next_agent_name

                    except Exception as e:
                        logger.error(
                            f"Router error: {e}",
                            agent=agent.name,
                            error=str(e),
                        )
                        iter_span.record_exception(e)
                        return {"error": f"Router error: {e}"}
                else:
                    # Check if next_agent was set directly by user
                    next_agent_name = agent.next_agent
                    if callable(next_agent_name):
                        try:
                            next_agent_name = next_agent_name(context, result)
                        except Exception as e:
                            logger.error(f"next_agent callable error: {e}")
                            return {"error": f"next_agent callable error: {e}"}

                if not next_agent_name:
                    logger.info(
                        "No next agent found, completing chain",
                        agent=agent.name,
                    )
                    iter_span.add_event("chain completed")
                    return result

                # Record the agent run in the context.
                context.record(
                    agent.name,
                    result,
                    timestamp=datetime.now().isoformat(),
                    hand_off={"next_agent": next_agent_name} if next_agent_name else None,
                    called_from=previous_agent_name,
                )
                # Remember the current agent's details for the next iteration.
                previous_agent_name = agent.name
                previous_agent_output = agent.output
                previous_agent_handoff_strategy = agent.config.handoff_strategy
                previous_agent_handoff_map = agent.config.handoff_map

                # Activate the next agent.
                try:
                    agent = registry.get_agent(next_agent_name)
                    if not agent:
                        logger.error(
                            "Next agent not found",
                            agent=next_agent_name,
                        )
                        iter_span.record_exception(
                            Exception(
                                f"Next agent '{next_agent_name}' not found"
                            )
                        )
                        return {
                            "error": f"Next agent '{next_agent_name}' not found."
                        }



                    context.set_variable(FLOCK_CURRENT_AGENT, agent.name)

                    logger.info("Handing off to next agent", next=agent.name)
                    iter_span.set_attribute("next.agent", agent.name)
                except Exception as e:
                    logger.error("Error during handoff", error=str(e))
                    iter_span.record_exception(e)
                    return {"error": f"Error during handoff: {e}"}

        # If the loop exits unexpectedly, return the initial input.
        return context.get_variable("init_input")
