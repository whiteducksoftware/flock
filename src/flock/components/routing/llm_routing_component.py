# src/flock/components/routing/llm_routing_component.py
"""LLM-based routing component implementation for the unified component architecture."""

import json
from typing import TYPE_CHECKING, Any

import litellm
from pydantic import Field

from flock.core.component.agent_component_base import AgentComponentConfig
from flock.core.component.routing_component import RoutingComponent
from flock.core.context.context import FlockContext

# HandOffRequest removed - using agent.next_agent directly
from flock.core.logging.logging import get_logger
from flock.core.registry import flock_component

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent

logger = get_logger("components.routing.llm")


class LLMRoutingConfig(AgentComponentConfig):
    """Configuration for the LLM routing component."""

    temperature: float = Field(
        default=0.2, description="Temperature for LLM routing decisions"
    )
    max_tokens: int = Field(
        default=500, description="Maximum tokens for LLM response"
    )
    confidence_threshold: float = Field(
        default=0.5, description="Minimum confidence threshold for routing"
    )
    model: str = Field(
        default="azure/gpt-4.1", description="Model to use for routing decisions"
    )
    prompt_template: str = Field(
        default="""You are a workflow routing assistant. Given the current agent's output and available next agents, determine which agent should execute next.

Current Agent: {current_agent_name}
Current Output: {current_output}

Available Agents:
{available_agents}

Select the most appropriate next agent based on the current output. Respond with JSON in this exact format:
{{"next_agent": "agent_name", "confidence": 0.8, "reasoning": "explanation"}}

If no agent is suitable, use "next_agent": "" to end the workflow.""",
        description="Template for LLM routing prompt"
    )


@flock_component(config_class=LLMRoutingConfig)
class LLMRoutingComponent(RoutingComponent):
    """Router that uses an LLM to determine the next agent in a workflow.
    
    This component analyzes the current agent's output and uses an LLM to
    intelligently select the most appropriate next agent from available options.
    """

    config: LLMRoutingConfig = Field(
        default_factory=LLMRoutingConfig
    )

    def __init__(
        self,
        name: str = "llm_router",
        config: LLMRoutingConfig | None = None,
        **data,
    ):
        if config is None:
            config = LLMRoutingConfig()
        super().__init__(name=name, config=config, **data)

    def _get_available_agents(
        self, agent_definitions: dict[str, Any], current_agent_name: str
    ) -> list[str]:
        """Get list of available agent names except the current one."""
        available = []
        for agent_name in agent_definitions:
            if agent_name != current_agent_name:
                available.append(agent_name)
        return available

    def _create_selection_prompt(
        self,
        current_agent: "FlockAgent",
        result: dict[str, Any],
        available_agents: list[str],
    ) -> str:
        """Create the prompt for LLM agent selection."""
        # Format available agents
        agents_list = []
        for agent_name in available_agents:
            agents_list.append(f"- {agent_name}")

        available_agents_str = "\n".join(agents_list) if agents_list else "None available"

        # Format current output
        current_output = json.dumps(result, indent=2) if result else "No output"

        return self.config.prompt_template.format(
            current_agent_name=current_agent.name,
            current_output=current_output,
            available_agents=available_agents_str
        )

    async def _select_next_agent(
        self,
        current_agent: "FlockAgent",
        result: dict[str, Any],
        available_agents: list[str],
    ) -> tuple[str, float]:
        """Use an LLM to select the best next agent."""
        if not available_agents:
            logger.warning("No available agents for LLM routing")
            return "", 0.0

        # Create the selection prompt
        prompt = self._create_selection_prompt(current_agent, result, available_agents)

        try:
            # Call the LLM
            response = await litellm.acompletion(
                model=self.config.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            response_content = response.choices[0].message.content.strip()
            logger.debug(f"LLM routing response: {response_content}")

            # Parse the JSON response
            try:
                routing_decision = json.loads(response_content)
                next_agent = routing_decision.get("next_agent", "")
                confidence = routing_decision.get("confidence", 0.0)
                reasoning = routing_decision.get("reasoning", "No reasoning provided")

                logger.info(f"LLM routing decision: {next_agent} (confidence: {confidence}) - {reasoning}")

                # Validate the selected agent is available
                if next_agent and next_agent not in available_agents and next_agent != "":
                    logger.warning(f"LLM selected unavailable agent '{next_agent}', ending workflow")
                    return "", 0.0

                return next_agent, confidence

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                return "", 0.0

        except Exception as e:
            logger.error(f"Error calling LLM for routing: {e}")
            return "", 0.0

    async def determine_next_step(
        self,
        agent: "FlockAgent",
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Use LLM to determine the next agent based on current output."""
        if not context:
            logger.warning("No context provided for LLM routing")
            return

        logger.info(f"LLM routing from agent '{agent.name}'")

        # Get available agents from context
        agent_definitions = getattr(context, 'agent_definitions', {})
        available_agents = self._get_available_agents(agent_definitions, agent.name)

        logger.debug(f"Available agents for LLM routing: {available_agents}")

        if not available_agents:
            logger.warning("No available agents for LLM routing")
            return

        # Use LLM to select the next agent
        next_agent_name, confidence = await self._select_next_agent(
            agent, result, available_agents
        )

        logger.info(f"LLM routing result: {next_agent_name} (confidence: {confidence})")

        # Check confidence threshold
        if not next_agent_name or confidence < self.config.confidence_threshold:
            logger.warning(
                f"LLM routing confidence {confidence} below threshold {self.config.confidence_threshold}"
            )
            return

        # Validate the selected agent exists
        if next_agent_name not in agent_definitions:
            logger.error(f"LLM selected non-existent agent '{next_agent_name}'")
            return

        logger.info(f"Successfully routed to agent '{next_agent_name}' with confidence {confidence}")
        agent.next_agent = next_agent_name
