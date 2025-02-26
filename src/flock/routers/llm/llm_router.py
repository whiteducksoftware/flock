"""LLM-based router implementation for the Flock framework."""

import json
from typing import Any

import litellm

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_router import (
    FlockRouter,
    FlockRouterConfig,
    HandOffRequest,
)
from flock.core.logging.logging import get_logger

logger = get_logger("llm_router")


class LLMRouterConfig(FlockRouterConfig):
    """Configuration for the LLM router.

    This class extends FlockRouterConfig with parameters specific to the LLM router.
    """

    temperature: float = 0.2
    max_tokens: int = 500
    confidence_threshold: float = 0.5
    prompt: str = ""


class LLMRouter(FlockRouter):
    """Router that uses an LLM to determine the next agent in a workflow.

    This class is responsible for:
    1. Analyzing available agents in the registry
    2. Using an LLM to score each agent's suitability as the next step
    3. Selecting the highest-scoring agent
    4. Creating a HandOff object with the selected agent
    """

    def __init__(
        self,
        name: str = "llm_router",
        config: LLMRouterConfig | None = None,
    ):
        """Initialize the LLMRouter.

        Args:
            registry: The agent registry containing all available agents
            name: The name of the router
            config: The router configuration
        """
        logger.info(f"Initializing LLM Router '{name}'")
        super().__init__(name=name, config=config or LLMRouterConfig(name=name))
        logger.debug(
            "LLM Router configuration",
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
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
        logger.info(
            f"Routing from agent '{current_agent.name}'",
            current_agent=current_agent.name,
        )
        logger.debug("Current agent result", result=result)

        agent_definitions = context.agent_definitions
        # Get all available agents from the registry
        available_agents = self._get_available_agents(
            agent_definitions, current_agent.name
        )
        logger.debug(
            "Available agents for routing",
            count=len(available_agents),
            agents=[a.agent_data["name"] for a in available_agents],
        )

        if not available_agents:
            logger.warning(
                "No available agents for routing",
                current_agent=current_agent.name,
            )
            return HandOffRequest(
                next_agent="", override_next_agent={}, override_context=None
            )

        # Use LLM to determine the best next agent
        next_agent_name, score = await self._select_next_agent(
            current_agent, result, available_agents
        )
        logger.info(
            "Agent selection result",
            next_agent=next_agent_name,
            score=score,
        )

        if not next_agent_name or score < self.config.confidence_threshold:
            logger.warning(
                "No suitable next agent found",
                best_score=score,
            )
            return HandOffRequest(
                next_agent="", override_next_agent={}, override_context=None
            )

        # Get the next agent from the registry
        next_agent = agent_definitions.get(next_agent_name)
        if not next_agent:
            logger.error(
                "Selected agent not found in registry",
                agent_name=next_agent_name,
            )
            return HandOffRequest(
                next_agent="", override_next_agent={}, override_context=None
            )

        # Create input for the next agent

        logger.success(
            f"Successfully routed to agent '{next_agent_name}'",
            score=score,
            from_agent=current_agent.name,
        )
        return HandOffRequest(
            next_agent=next_agent_name,
            hand_off_mode="add",
            override_next_agent=None,
            override_context=None,
        )

    def _get_available_agents(
        self, agent_definitions: dict[str, Any], current_agent_name: str
    ) -> list[FlockAgent]:
        """Get all available agents except the current one.

        Args:
            current_agent_name: Name of the current agent to exclude

        Returns:
            List of available agents
        """
        logger.debug(
            "Getting available agents",
            total_agents=len(agent_definitions),
            current_agent=current_agent_name,
        )
        agents = []
        for agent in agent_definitions:
            if agent != current_agent_name:
                agents.append(agent_definitions.get(agent))
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
        logger.debug(
            "Selecting next agent",
            current_agent=current_agent.name,
            available_count=len(available_agents),
        )

        # Prepare the prompt for the LLM
        prompt = self._create_selection_prompt(
            current_agent, result, available_agents
        )
        logger.debug("Generated selection prompt", prompt_length=len(prompt))

        try:
            logger.info(
                "Calling LLM for agent selection",
                model=current_agent.model,
                temperature=self.config.temperature,
            )
            # Call the LLM to get the next agent
            response = await litellm.acompletion(
                model=current_agent.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature
                if isinstance(self.config, LLMRouterConfig)
                else 0.2,
                max_tokens=self.config.max_tokens
                if isinstance(self.config, LLMRouterConfig)
                else 500,
            )

            content = response.choices[0].message.content
            # Parse the response to get the agent name and score
            try:
                # extract the json object from the response
                content = content.split("```json")[1].split("```")[0]
                data = json.loads(content)
                next_agent = data.get("next_agent", "")
                score = float(data.get("score", 0))
                reasoning = data.get("reasoning", "")
                logger.info(
                    "Successfully parsed LLM response",
                    next_agent=next_agent,
                    score=score,
                    reasoning=reasoning,
                )
                return next_agent, score
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(
                    "Failed to parse LLM response",
                    error=str(e),
                    raw_response=content,
                )
                logger.debug("Attempting fallback parsing")

                # Fallback: try to extract the agent name from the text
                for agent in available_agents:
                    if agent.agent_data["name"] in content:
                        logger.info(
                            "Found agent name in response using fallback",
                            agent=agent.agent_data["name"],
                        )
                        return agent.agent_data[
                            "name"
                        ], 0.6  # Default score for fallback

                return "", 0.0

        except Exception as e:
            logger.error(
                "Error calling LLM for agent selection",
                error=str(e),
                current_agent=current_agent.name,
            )
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
                "name": agent.agent_data["name"],
                "description": agent.agent_data["description"]
                if agent.agent_data["description"]
                else "",
                "input": agent.agent_data["input"],
                "output": agent.agent_data["output"],
            }
            agents_info.append(agent_info)

        agents_str = json.dumps(agents_info, indent=2)

        # Create the prompt
        if self.config.prompt:
            prompt = self.config.prompt
        else:
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
