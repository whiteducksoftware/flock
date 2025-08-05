"""Handoff agent for the agent-based router."""

from pydantic import BaseModel

from flock.core.flock_agent import FlockAgent


class AgentInfo(BaseModel):
    """Information about an agent for handoff decisions."""

    name: str
    description: str = ""
    input_schema: str = ""
    output_schema: str = ""


class HandoffDecision(BaseModel):
    """Decision about which agent to hand off to."""

    agent_name: str
    confidence: float
    reasoning: str


class HandoffAgent(FlockAgent):
    """Agent that decides which agent to hand off to next.

    This agent analyzes the current agent's output and available agents
    to determine the best next agent in the workflow.
    """

    def __init__(
        self,
        name: str = "handoff_agent",
        model: str | None = None,
        description: str = "Decides which agent to hand off to next",
    ):
        """Initialize the HandoffAgent.

        Args:
            name: The name of the agent
            model: The model to use (e.g., 'openai/gpt-4o')
            description: A human-readable description of the agent
        """
        super().__init__(
            name=name,
            model=model,
            description=description,
            input=(
                "current_agent_name: str | Name of the current agent, "
                "current_agent_description: str | Description of the current agent, "
                "current_agent_input: str | Input schema of the current agent, "
                "current_agent_output: str | Output schema of the current agent, "
                "current_result: dict | Output from the current agent, "
                "available_agents: list[AgentInfo] | List of available agents"
            ),
            output="agent_name: str | Name of the agent to hand off to, confidence: float | Confidence in the decision, reasoning: str | Reasoning for the decision",
        )
