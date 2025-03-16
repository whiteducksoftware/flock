"""Router implementation for Chain of Draft."""

from typing import Any

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_router import FlockRouter, FlockRouterConfig, HandOffRequest
from flock.core.logging.logging import get_logger
from pydantic import Field

logger = get_logger("chain_of_draft.router")


class ChainOfDraftRouter(FlockRouter):
    """Router for Chain of Draft reasoning workflow.
    
    This router manages the transitions between different reasoning steps in a Chain of Draft workflow,
    determining when to continue with another reasoning step or when to finalize the answer.
    """
    
    final_answer_agent: str | None = Field(default=None, description="Name of the final answer agent")
    reasoning_step_agent: str | None = Field(default=None, description="Name of the reasoning step agent")
    max_steps: int | None = Field(default=None, description="Maximum number of reasoning steps allowed")
    
    def __init__(
        self, 
        name: str = "cod_router", 
        config: FlockRouterConfig = None,
        final_answer_agent: str = "final_answer",
        reasoning_step_agent: str = "reasoning_step",
        max_steps: int = 10,
    ):
        """Initialize the Chain of Draft router.
        
        Args:
            name: Name of the router
            config: Router configuration
            final_answer_agent: Name of the agent to use for final answers
            reasoning_step_agent: Name of the agent to use for reasoning steps
            max_steps: Maximum number of reasoning steps allowed
        """
        if not config:
            config = FlockRouterConfig(
                agents=[reasoning_step_agent, final_answer_agent]
            )
        
        super().__init__(name=name, config=config)
        self.final_answer_agent = final_answer_agent
        self.reasoning_step_agent = reasoning_step_agent
        self.max_steps = max_steps
        logger.debug(f"Router initialized with final_answer_agent={final_answer_agent}, reasoning_step_agent={reasoning_step_agent}")
    
    async def route(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        context: FlockContext,
    ) -> HandOffRequest:
        """Determine the next agent based on the current result.
        
        Args:
            current_agent: The current agent
            result: The result from the current agent
            context: The execution context
            
        Returns:
            HandOffRequest specifying the next agent
        """
        # Get the current step count
        step_count = context.get_variable("cod.step_count", 0)
        context.set_variable("cod.step_count", step_count + 1)
        
        logger.debug(f"Chain of Draft step {step_count + 1} completed by agent {current_agent.name}")
        logger.debug(f"Current result keys: {list(result.keys())}")
        
        # If this is the problem analyzer, always go to the reasoning step
        if current_agent.name == "problem_analyzer":
            # Convert the initial_step to previous_steps for consistency
            if "initial_step" in result:
                logger.debug(f"Initial step: {result['initial_step']}")
                result["previous_steps"] = result["initial_step"]
            else:
                logger.warning(f"Expected 'initial_step' in problem_analyzer result, but got keys: {list(result.keys())}")
                result["previous_steps"] = ""
            
            logger.debug(f"Routing from problem_analyzer to {self.reasoning_step_agent}")
            return HandOffRequest(
                next_agent=self.reasoning_step_agent,
                hand_off_mode="add"
            )
        
        # Check if we have reached a conclusion or the maximum steps
        is_final = result.get("is_final", False)
        reached_max_steps = step_count >= self.max_steps
        
        if is_final or reached_max_steps:
            logger.info(
                f"Moving to final answer agent after {step_count} steps "
                f"(is_final={is_final}, reached_max_steps={reached_max_steps})"
            )
            return HandOffRequest(
                next_agent=self.final_answer_agent,
                hand_off_mode="add"
            )
        
        # Continue with another reasoning step
        logger.debug(f"Continuing with another reasoning step ({step_count + 1}/{self.max_steps})")
        return HandOffRequest(
            next_agent=self.reasoning_step_agent,
            hand_off_mode="add"
        ) 