"""Implements the auto-handoff router for dynamic agent chaining."""

import json
from typing import Any

import litellm

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent, HandOff
from flock.core.logging.logging import get_logger
from flock.core.registry.agent_registry import Registry

logger = get_logger("handoff_router")


class HandoffRouter:
    """Router that uses an LLM to determine the next agent in a workflow.

    This class is responsible for:
    1. Analyzing available agents in the registry
    2. Using an LLM to score each agent's suitability as the next step
    3. Selecting the highest-scoring agent
    4. Creating a HandOff object with the selected agent
    """

    def __init__(self, registry: Registry):
        """Initialize the HandoffRouter.

        Args:
            registry: The agent registry containing all available agents
        """
        self.registry = registry

    async def route(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        context: FlockContext,
    ) -> HandOff:
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
            logger.warning("No available agents for auto-handoff")
            return HandOff(next_agent="", input={}, context=None)

        # Use LLM to determine the best next agent
        next_agent_name, score = await self._select_next_agent(
            current_agent, result, available_agents
        )

        if not next_agent_name or score < 0.5:  # Threshold for confidence
            logger.info(f"No suitable next agent found (best score: {score})")
            return HandOff(next_agent="", input={}, context=None)

        # Get the next agent from the registry
        next_agent = self.registry.get_agent(next_agent_name)
        if not next_agent:
            logger.error(
                f"Selected agent '{next_agent_name}' not found in registry"
            )
            return HandOff(next_agent="", input={}, context=None)

        # Create input for the next agent
        next_input = self._create_next_input(current_agent, result, next_agent)

        logger.info(
            f"Auto-handoff selected agent '{next_agent_name}' with score {score}"
        )
        return HandOff(
            next_agent=next_agent_name, input=next_input, context=None
        )

    def _get_available_agents(
        self, current_agent_name: str
    ) -> list[FlockAgent]:
        """Get all available agents except the current one.

        Args:
            current_agent_name: Name of the current agent to exclude

        Returns:
            List of available agents
        """
        agents = []
        for agent in self.registry._agents:
            if agent.name != current_agent_name:
                agents.append(agent)
        return agents

    async def _select_next_agent(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        available_agents: list[FlockAgent],
    ) -> tuple[str, float]:
        """Use an LLM to select the best next agent.

        Args:
            current_agent: The agent that just completed execution
            result: The output from the current agent
            available_agents: List of available agents to choose from

        Returns:
            Tuple of (selected_agent_name, confidence_score)
        """
        # Prepare the prompt for the LLM
        prompt = self._create_selection_prompt(
            current_agent, result, available_agents
        )

        try:
            # Call the LLM to get the next agent
            response = await litellm.acompletion(
                model=current_agent.model or "openai/gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500,
            )

            content = response.choices[0].message.content

            # Parse the response to get the agent name and score
            try:
                data = json.loads(content)
                next_agent = data.get("next_agent", "")
                score = float(data.get("score", 0))
                return next_agent, score
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Error parsing LLM response: {e}")
                logger.debug(f"Raw LLM response: {content}")

                # Fallback: try to extract the agent name from the text
                for agent in available_agents:
                    if agent.name in content:
                        return agent.name, 0.6  # Default score for fallback

                return "", 0.0

        except Exception as e:
            logger.error(f"Error calling LLM for agent selection: {e}")
            return "", 0.0

    def _create_selection_prompt(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        available_agents: list[FlockAgent],
    ) -> str:
        """Create a prompt for the LLM to select the next agent.

        Args:
            current_agent: The agent that just completed execution
            result: The output from the current agent
            available_agents: List of available agents to choose from

        Returns:
            Prompt string for the LLM
        """
        # Format the current agent's output
        result_str = json.dumps(result, indent=2)

        # Format the available agents' information
        agents_info = []
        for agent in available_agents:
            agent_info = {
                "name": agent.name,
                "description": agent.description,
                "input": agent.input,
                "output": agent.output,
            }
            agents_info.append(agent_info)

        agents_str = json.dumps(agents_info, indent=2)

        # Create the prompt
        prompt = f"""
You are a workflow router that determines the next agent to execute in a multi-agent system.

CURRENT AGENT:
Name: {current_agent.name}
Description: {current_agent.description}
Input: {current_agent.input}
Output: {current_agent.output}

CURRENT AGENT'S OUTPUT:
{result_str}

AVAILABLE AGENTS:
{agents_str}

Based on the current agent's output and the available agents, determine which agent should be executed next.
Consider the following:
1. Which agent's input requirements best match the current agent's output?
2. Which agent's purpose and description make it the most logical next step?
3. Which agent would provide the most value in continuing the workflow?

Respond with a JSON object containing:
1. "next_agent": The name of the selected agent
2. "score": A confidence score between 0 and 1 indicating how suitable this agent is
3. "reasoning": A brief explanation of why this agent was selected

If no agent is suitable, set "next_agent" to an empty string and "score" to 0.

JSON Response:
"""
        return prompt

    def _create_next_input(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        next_agent: FlockAgent,
    ) -> dict[str, Any]:
        """Create the input for the next agent, including the previous agent's output.

        Args:
            current_agent: The agent that just completed execution
            result: The output from the current agent
            next_agent: The next agent to execute

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

        # Try to map the current agent's output to the next agent's input
        # This is a simple implementation that could be enhanced with more sophisticated mapping
        for key in result:
            # If the next agent expects this key, add it directly
            if key in next_agent.input:
                next_input[key] = result[key]

        return next_input
