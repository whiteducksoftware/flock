"""Defines Temporal activities for running a chain of agents with logging and tracing."""

from datetime import datetime

from opentelemetry import trace
from temporalio import activity

from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_CURRENT_AGENT
from flock.core.flock_agent import FlockAgent, HandOff
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.formatter_factory import FormatterFactory
from flock.core.logging.logging import get_logger
from flock.core.registry.agent_registry import Registry
from flock.core.util.input_resolver import resolve_inputs

logger = get_logger("activities")
tracer = trace.get_tracer(__name__)


@activity.defn
async def run_agent(
    context: FlockContext, output_formatter: FormatterOptions = None
) -> dict:
    """Runs a chain of agents using the provided context.

    The context contains state, history, and agent definitions.
    After each agent run, its output is merged into the context.
    """
    # Start a top-level span for the entire run_agent activity.
    with tracer.start_as_current_span("run_agent") as span:
        registry = Registry()
        previous_agent_name = ""
        if isinstance(context, dict):
            context = FlockContext.from_dict(context)
        current_agent_name = context.get_variable(FLOCK_CURRENT_AGENT)
        span.set_attribute("initial.agent", current_agent_name)
        logger.info("Starting agent chain", initial_agent=current_agent_name)

        agent = registry.get_agent(current_agent_name)
        agent.resolve_callables(context=context)
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

                # Resolve inputs for the agent.
                agent_inputs = resolve_inputs(
                    agent.input, context, previous_agent_name
                )
                iter_span.add_event(
                    "resolved inputs", attributes={"inputs": str(agent_inputs)}
                )

                # Execute the agent with its own span.
                with tracer.start_as_current_span("execute_agent") as exec_span:
                    logger.info("Executing agent", agent=agent.name)
                    try:
                        result = await agent.run(agent_inputs)
                        exec_span.set_attribute("result", str(result))
                        logger.debug(
                            "Agent execution completed", agent=agent.name
                        )
                    except Exception as e:
                        logger.error(
                            "Agent execution failed",
                            agent=agent.name,
                            error=str(e),
                        )
                        exec_span.record_exception(e)
                        raise

                # Optionally display formatted output.
                display_output = True
                if agent.config:
                    display_output = not agent.config.disable_output

                if output_formatter and display_output:
                    formatter = FormatterFactory.create_formatter(
                        output_formatter
                    )
                    formatter.display(
                        result, agent.name, output_formatter.wait_for_input
                    )

                # If there is no handoff, record the result and finish.
                if not agent.hand_off:
                    context.record(
                        agent.name,
                        result,
                        timestamp=datetime.now(),
                        hand_off=None,
                        called_from=previous_agent_name,
                    )
                    logger.info(
                        "No handoff defined, completing chain", agent=agent.name
                    )
                    iter_span.add_event("chain completed")
                    return result

                # Determine the next agent.
                handoff_data = HandOff()
                if callable(agent.hand_off):
                    logger.debug("Executing handoff function", agent=agent.name)
                    try:
                        handoff_data = agent.hand_off(context, result)
                        if isinstance(handoff_data.next_agent, FlockAgent):
                            handoff_data.next_agent = (
                                handoff_data.next_agent.name
                            )
                    except Exception as e:
                        logger.error(
                            "Handoff function error",
                            agent=agent.name,
                            error=str(e),
                        )
                        iter_span.record_exception(e)
                        return {"error": f"Handoff function error: {e}"}
                elif isinstance(agent.hand_off, (str, FlockAgent)):
                    handoff_data.next_agent = (
                        agent.hand_off
                        if isinstance(agent.hand_off, str)
                        else agent.hand_off.name
                    )
                else:
                    logger.error("Unsupported hand_off type", agent=agent.name)
                    iter_span.add_event("unsupported hand_off type")
                    return {"error": "Unsupported hand_off type."}

                # Record the agent run in the context.
                context.record(
                    agent.name,
                    result,
                    timestamp=datetime.now().isoformat(),
                    hand_off=handoff_data,
                    called_from=previous_agent_name,
                )
                previous_agent_name = agent.name

                # Prepare the next agent.
                try:
                    agent = registry.get_agent(handoff_data.next_agent)
                    agent.resolve_callables(context=context)
                    if not agent:
                        logger.error(
                            "Next agent not found",
                            agent=handoff_data.next_agent,
                        )
                        iter_span.record_exception(
                            Exception(
                                f"Next agent '{handoff_data.next_agent}' not found"
                            )
                        )
                        return {
                            "error": f"Next agent '{handoff_data.next_agent}' not found."
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
