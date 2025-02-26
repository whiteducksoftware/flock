"""Agent-based router implementation for the Flock framework."""

from typing import Any

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_router import (
    FlockRouter,
    FlockRouterConfig,
    HandOffRequest,
)
from flock.core.logging.formatters.themes import OutputTheme
from flock.core.logging.logging import get_logger
from flock.evaluators.declarative.declarative_evaluator import (
    DeclarativeEvaluator,
    DeclarativeEvaluatorConfig,
)
from flock.modules.output.output_module import OutputModule, OutputModuleConfig
from flock.routers.agent.handoff_agent import (
    AgentInfo,
    HandoffAgent,
)

logger = get_logger("agent_router")


class AgentRouterConfig(FlockRouterConfig):
    """Configuration for the agent router.

    This class extends FlockRouterConfig with parameters specific to the agent router.
    """

    with_output: bool = False
    confidence_threshold: float = 0.5  # No additional parameters needed for now


class AgentRouter(FlockRouter):
    """Router that uses a FlockAgent to determine the next agent in a workflow.

    This class is responsible for:
    1. Creating and managing a HandoffAgent
    2. Analyzing available agents in the registry
    3. Using the HandoffAgent to determine the best next agent
    4. Creating a HandOff object with the selected agent
    """

    def __init__(
        self,
        name: str = "agent_router",
        config: AgentRouterConfig | None = None,
    ):
        """Initialize the AgentRouter.

        Args:
            registry: The agent registry containing all available agents
            name: The name of the router
            config: The router configuration
        """
        super().__init__(
            name=name, config=config or AgentRouterConfig(name=name)
        )

    async def route(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        context: FlockContext,
    ) -> HandOffRequest:
        """Determine the next agent to hand off to based on the current agent's output.

        Args:
            current_agent: The agent that just completed execution
            result: The output from the current agent
            context: The global execution context

        Returns:
            A HandOff object containing the next agent and input data
        """
        # Get all available agents from context.agent_definitions
        agent_definitions = context.agent_definitions
        handoff_agent = HandoffAgent(model=current_agent.model)
        handoff_agent.evaluator = DeclarativeEvaluator(
            name="evaluator",
            config=DeclarativeEvaluatorConfig(
                model=current_agent.model,
                use_cache=True,
                max_tokens=1000,
                temperature=0.0,
            ),
        )
        if self.config.with_output:
            handoff_agent.add_module(
                OutputModule(
                    name="output",
                    config=OutputModuleConfig(
                        theme=OutputTheme.abernathy,
                    ),
                )
            )
        available_agents = self._get_available_agents(
            agent_definitions, current_agent.name
        )

        if not available_agents:
            logger.warning("No available agents for agent-based routing")
            return HandOffRequest(
                next_agent="",
                hand_off_mode="add",
                override_next_agent=None,
                override_context=None,
            )

        # Prepare input for the handoff agent
        handoff_input = {
            "current_agent_name": current_agent.name,
            "current_agent_description": current_agent.description,
            "current_agent_input": current_agent.input,
            "current_agent_output": current_agent.output,
            "current_result": result,
            "available_agents": available_agents,
        }

        try:
            # Run the handoff agent to determine the next agent
            handoff_result = await handoff_agent.run_async(handoff_input)

            # Extract the decision
            next_agent_name = handoff_result.get("agent_name")
            confidence = handoff_result.get("confidence")
            reasoning = handoff_result.get("reasoning")
            logger.info(
                f"Agent router selected agent '{next_agent_name}' with confidence {confidence} and reasoning: {reasoning}"
            )

            if confidence < self.config.confidence_threshold:
                logger.info(
                    f"No suitable next agent found (best score: {confidence})"
                )
                return HandOffRequest(
                    next_agent="",
                    hand_off_mode="add",
                    override_next_agent=None,
                    override_context=None,
                )

            next_agent = agent_definitions.get(next_agent_name)
            if not next_agent:
                logger.error(
                    f"Selected agent '{next_agent_name}' not found in agent definitions"
                )
                return HandOffRequest(
                    next_agent="",
                    hand_off_mode="add",
                    override_next_agent=None,
                    override_context=None,
                )

            logger.info(
                f"Agent router selected agent '{next_agent_name}' with confidence {confidence}"
            )
            return HandOffRequest(
                next_agent=next_agent_name,
                hand_off_mode="add",
                override_next_agent=None,
                override_context=None,
            )

        except Exception as e:
            logger.error(f"Error in agent-based routing: {e}")
            return HandOffRequest(
                next_agent="",
                hand_off_mode="add",
                override_next_agent=None,
                override_context=None,
            )

    def _get_available_agents(
        self, agent_definitions: dict[str, Any], current_agent_name: str
    ) -> list[AgentInfo]:
        """Get all available agents except the current one and the handoff agent.

        Args:
            agent_definitions: Dictionary of available agents
            current_agent_name: Name of the current agent to exclude

        Returns:
            List of available agents as AgentInfo objects
        """
        agents = []
        for agent_name in agent_definitions:
            if agent_name != current_agent_name:
                agent = agent_definitions[agent_name]
                agent_info = AgentInfo(
                    name=agent_name,
                    description=agent.agent_data["description"]
                    if agent.agent_data["description"]
                    else "",
                    input_schema=agent.agent_data["input"],
                    output_schema=agent.agent_data["output"],
                )
                agents.append(agent_info)
        return agents

    def _get_schema_from_agent(
        self, agent: Any, schema_type: str
    ) -> dict[str, Any]:
        """Extract input or output schema from an agent.

        Args:
            agent: The agent to extract schema from
            schema_type: Either "input" or "output"

        Returns:
            Dictionary representation of the schema
        """
        schema = {}
        schema_str = agent.agent_data.get(schema_type, "")

        # Parse the schema string to extract field names, types, and descriptions
        if schema_str:
            fields = schema_str.split(",")
            for field in fields:
                field = field.strip()
                if ":" in field:
                    name, rest = field.split(":", 1)
                    name = name.strip()
                    schema[name] = rest.strip()
                else:
                    schema[field] = "Any"

        return schema

    # The _create_next_input method is no longer needed since we're using hand_off_mode="add"
    # instead of manually preparing inputs for the next agent
