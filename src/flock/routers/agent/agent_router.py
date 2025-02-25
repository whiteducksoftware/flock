"""Agent-based router implementation for the Flock framework."""

from typing import Any

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent, HandOffRequest
from flock.core.flock_router import FlockRouter, FlockRouterConfig
from flock.core.logging.logging import get_logger
from flock.core.registry.agent_registry import Registry
from flock.routers.agent.handoff_agent import (
    AgentInfo,
    HandoffAgent,
    HandoffDecision,
)

logger = get_logger("agent_router")


class AgentRouterConfig(FlockRouterConfig):
    """Configuration for the agent router.

    This class extends FlockRouterConfig with parameters specific to the agent router.
    """

    pass  # No additional parameters needed for now


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
        registry: Registry,
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
        self.registry = registry
        self.handoff_agent = HandoffAgent(model=self.get_model(None))
        # Register the handoff agent with the registry
        self.registry.register_agent(self.handoff_agent)

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
        # Get all available agents from the registry
        available_agents = self._get_available_agents(current_agent.name)

        if not available_agents:
            logger.warning("No available agents for agent-based routing")
            return HandOffRequest(next_agent="", input={}, context=None)

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
            handoff_result = await self.handoff_agent.run_async(handoff_input)

            # Extract the decision
            decision = handoff_result.get("decision")
            if not decision or not isinstance(decision, HandoffDecision):
                logger.error("Invalid decision from handoff agent")
                return HandOffRequest(next_agent="", input={}, context=None)

            if decision.confidence < self.config.confidence_threshold:
                logger.info(
                    f"No suitable next agent found (best score: {decision.confidence})"
                )
                return HandOffRequest(next_agent="", input={}, context=None)

            # Get the next agent from the registry
            next_agent_name = decision.agent_name
            next_agent = self.registry.get_agent(next_agent_name)
            if not next_agent:
                logger.error(
                    f"Selected agent '{next_agent_name}' not found in registry"
                )
                return HandOffRequest(next_agent="", input={}, context=None)

            # Create input for the next agent
            next_input = self._create_next_input(
                current_agent, result, next_agent, decision.input_mapping
            )

            logger.info(
                f"Agent router selected agent '{next_agent_name}' with confidence {decision.confidence}"
            )
            return HandOffRequest(
                next_agent=next_agent_name, input=next_input, context=None
            )

        except Exception as e:
            logger.error(f"Error in agent-based routing: {e}")
            return HandOffRequest(next_agent="", input={}, context=None)

    def _get_available_agents(self, current_agent_name: str) -> list[AgentInfo]:
        """Get all available agents except the current one and the handoff agent.

        Args:
            current_agent_name: Name of the current agent to exclude

        Returns:
            List of available agents as AgentInfo objects
        """
        agents = []
        for agent in self.registry._agents:
            if (
                agent.name != current_agent_name
                and agent.name != self.handoff_agent.name
            ):
                agent_info = AgentInfo(
                    name=agent.name,
                    description=agent.description,
                    input_schema=self._get_schema_from_agent(agent, "input"),
                    output_schema=self._get_schema_from_agent(agent, "output"),
                )
                agents.append(agent_info)
        return agents

    def _get_schema_from_agent(
        self, agent: FlockAgent, schema_type: str
    ) -> dict[str, Any]:
        """Extract input or output schema from an agent.

        Args:
            agent: The agent to extract schema from
            schema_type: Either "input" or "output"

        Returns:
            Dictionary representation of the schema
        """
        schema = {}
        schema_str = getattr(agent, schema_type, "")

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

    def _create_next_input(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        next_agent: FlockAgent,
        input_mapping: dict[str, str] = None,
    ) -> dict[str, Any]:
        """Create the input for the next agent, including the previous agent's output.

        Args:
            current_agent: The agent that just completed execution
            result: The output from the current agent
            next_agent: The next agent to execute
            input_mapping: Optional mapping from next agent input keys to current agent output keys

        Returns:
            Input dictionary for the next agent
        """
        # Start with an empty input
        next_input = {}

        # Add a special field for the previous agent's output
        next_input["previous_agent_output"] = {
            "agent_name": current_agent.name,
            "result": result,
        }

        # Apply input mapping if provided
        if input_mapping:
            for next_key, current_key in input_mapping.items():
                if current_key in result:
                    next_input[next_key] = result[current_key]

        # Also try direct key matching for keys not in the mapping
        input_keys = self._get_input_keys(next_agent)
        for key in input_keys:
            if key in result and key not in next_input:
                next_input[key] = result[key]

        return next_input

    def _get_input_keys(self, agent: FlockAgent) -> list[str]:
        """Extract input keys from an agent.

        Args:
            agent: The agent to extract input keys from

        Returns:
            List of input key names
        """
        schema = self._get_schema_from_agent(agent, "input")
        return list(schema.keys())
