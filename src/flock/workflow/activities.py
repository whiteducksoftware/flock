"""Defines Temporal activities for running a chain of agents."""

from datetime import datetime

from temporalio import activity

from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_CURRENT_AGENT
from flock.core.flock_agent import FlockAgent, HandoffBase
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.formatter_factory import FormatterFactory
from flock.core.logging.logging import get_logger
from flock.core.registry.agent_registry import Registry
from flock.core.util.input_resolver import resolve_inputs

logger = get_logger("activities")


@activity.defn
async def run_agent(
    context: FlockContext, output_formatter: FormatterOptions = None
) -> dict:
    """Runs a chain of agents using the provided context.

    The context contains:
      - A state (e.g., "init_input", "current_agent", etc.),
      - A history of agent runs.

    Each agent uses the current value of the variable specified in its `input` attribute.
    After each run, its output is merged into the context state.
    The default handoff behavior is to fetch the next agent's input automatically from the context.
    """
    registry = Registry()
    previous_agent_name = ""
    current_agent_name = context.get_variable(FLOCK_CURRENT_AGENT)
    handoff_data: HandoffBase = None

    logger.info("Starting agent chain", initial_agent=current_agent_name)

    agent = registry.get_agent(current_agent_name)
    if not agent:
        logger.error("Agent not found", agent=current_agent_name)
        return {"error": f"Agent '{current_agent_name}' not found."}

    while agent:
        # Get the inputs for the agent

        agent_inputs = resolve_inputs(agent.input, context, previous_agent_name)

        # Execute the agent
        logger.info("Executing agent")
        result = await agent.run(agent_inputs)
        logger.debug("Agent execution completed")

        if output_formatter:
            formatter = FormatterFactory.create_formatter(output_formatter)
            formatter.display(
                result, agent.name, output_formatter.wait_for_input
            )

        # If no handoff is defined, return the result
        if not agent.hand_off:
            context.record(
                agent.name,
                result,
                timestamp=datetime.now(),
                hand_off=None,
                called_from=previous_agent_name,
            )
            logger.info("No handoff defined, completing chain")
            return result

        # Determine the next agent
        handoff_data = HandoffBase()
        if callable(agent.hand_off):
            logger.debug("Executing handoff function")
            handoff_data = agent.hand_off(context, result)
            if isinstance(handoff_data.next_agent, FlockAgent):
                handoff_data.next_agent = handoff_data.next_agent.name

        elif isinstance(agent.hand_off, str | FlockAgent):
            handoff_data.next_agent = (
                agent.hand_off
                if isinstance(agent.hand_off, str)
                else agent.hand_off.name
            )
        else:
            logger.error("Unsupported hand_off type")
            return {"error": "Unsupported hand_off type."}

        context.record(
            agent.name,
            result,
            timestamp=datetime.now().isoformat(),
            hand_off=handoff_data,
            called_from=previous_agent_name,
        )
        previous_agent_name = agent.name

        # Update the current agent and prepare the next input automatically
        try:
            agent = registry.get_agent(handoff_data.next_agent)
            if not agent:
                logger.error(
                    "Next agent not found", agent=handoff_data.next_agent
                )
                return {
                    "error": f"Next agent '{handoff_data.next_agent}' not found."
                }

            context.set_variable(FLOCK_CURRENT_AGENT, agent.name)
            logger.info("Handing off to next agent", next=agent.name)
        except Exception as e:
            logger.error("Error during handoff", error=e)
            return {"error": f"Error during handoff: {e}"}

    return context.get_variable("init_input")
