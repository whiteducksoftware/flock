"""Chain of Draft agent implementations."""

from typing import Any, Dict

from flock.core import FlockAgent
from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger

from .prompts import (
    COD_SYSTEM_PROMPT, 
    COT_SYSTEM_PROMPT,
    PROBLEM_ANALYZER_PROMPT,
    COD_REASONING_PROMPT,
    FINAL_ANSWER_PROMPT
)

logger = get_logger("chain_of_draft")


class TokenCounterModule:
    """Module for counting tokens used in Chain of Draft."""

    def __init__(self, name: str):
        self.name = name
        self.config = type("Config", (), {"enabled": True})()
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

    def add_input_tokens(self, count: int):
        """Add input tokens to the counter."""
        self.input_tokens += count
        self.total_tokens += count
        logger.debug(f"Added {count} input tokens. Total: {self.total_tokens}")

    def add_output_tokens(self, count: int):
        """Add output tokens to the counter."""
        self.output_tokens += count
        self.total_tokens += count
        logger.debug(f"Added {count} output tokens. Total: {self.total_tokens}")

    def reset(self):
        """Reset token counters."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0


class ChainOfDraftAgent(FlockAgent):
    """Base agent for implementing Chain of Draft reasoning steps."""
    
    def __init__(self, name: str, system_prompt: str = COD_SYSTEM_PROMPT, **kwargs):
        """Initialize a Chain of Draft agent.
        
        Args:
            name: Unique identifier for the agent
            system_prompt: System prompt for the agent
            **kwargs: Additional arguments to pass to FlockAgent
        """
        super().__init__(name=name, **kwargs)
        
        # Add token counter module
        self.add_module(TokenCounterModule(name="token_counter"))
        
        # Store the system prompt
        self.system_prompt = system_prompt
    
    async def initialize(self, inputs: Dict[str, Any]) -> None:
        """Initialize the agent with a system prompt."""
        await super().initialize(inputs)
        
        if self.context:
            self.context.set_variable(f"flock.agents.{self.name}.system_prompt", 
                                     self.system_prompt)
            
    async def run_async(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the agent with token counting."""
        # Estimate input tokens (this is a simple approximation)
        if self.context:
            token_counter = self.get_module("token_counter")
            if token_counter:
                # Simple approximation: 1 token ≈ 4 characters for English text
                input_tokens = sum(len(str(v)) // 4 for v in inputs.values())
                token_counter.add_input_tokens(input_tokens)
        
        # Run the agent
        result = await super().run_async(inputs)
        
        # Estimate output tokens
        if self.context and token_counter:
            output_tokens = sum(len(str(v)) // 4 for v in result.values())
            token_counter.add_output_tokens(output_tokens)
            
        return result


class ProblemAnalyzerAgent(ChainOfDraftAgent):
    """Agent to analyze the problem and produce the first reasoning step."""
    
    def __init__(self, name: str = "problem_analyzer", **kwargs):
        """Initialize a problem analyzer agent."""
        super().__init__(
            name=name,
            description="Analyze the problem and prepare the first concise reasoning step",
            input="problem: str | The problem to solve",
            output=(
                "initial_step: str | First concise step of reasoning, "
                "problem: str | The original problem"
            ),
            **kwargs
        )


class ReasoningStepAgent(ChainOfDraftAgent):
    """Agent to perform intermediate reasoning steps."""
    
    def __init__(self, name: str = "reasoning_step", **kwargs):
        """Initialize a reasoning step agent."""
        super().__init__(
            name=name,
            description="Perform a single concise reasoning step",
            input=(
                "problem: str | The problem to solve, "
                "previous_steps: str | Previous reasoning steps"
            ),
            output=(
                "next_step: str | Next concise reasoning step, "
                "is_final: bool | Whether this is the final step before the answer, "
                "problem: str | The original problem, "
                "previous_steps: str | Updated reasoning steps including the new step"
            ),
            **kwargs
        )
    
    async def run_async(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the reasoning step and determine if we've reached a conclusion."""
        result = await super().run_async(inputs)
        
        # Combine previous steps with new step for the next iteration
        if "previous_steps" in inputs and "next_step" in result:
            if inputs["previous_steps"]:
                result["previous_steps"] = inputs["previous_steps"] + "\n" + result["next_step"]
            else:
                result["previous_steps"] = result["next_step"]
        
        return result


class FinalAnswerAgent(ChainOfDraftAgent):
    """Agent to extract the final answer from reasoning steps."""
    
    def __init__(self, name: str = "final_answer", **kwargs):
        """Initialize a final answer agent."""
        super().__init__(
            name=name,
            description="Extract the final answer from reasoning steps",
            input=(
                "problem: str | The problem to solve, "
                "previous_steps: str | All reasoning steps"
            ),
            output=(
                "answer: str | The final answer to the problem, "
                "reasoning_steps: str | All steps used to arrive at the answer"
            ),
            **kwargs
        )


class ChainOfThoughtAgent(FlockAgent):
    """Base agent for implementing traditional Chain of Thought reasoning."""
    
    def __init__(self, name: str, system_prompt: str = COT_SYSTEM_PROMPT, **kwargs):
        """Initialize a Chain of Thought agent."""
        super().__init__(name=name, **kwargs)
        
        # Add token counter module
        self.add_module(TokenCounterModule(name="token_counter"))
        
        # Store the system prompt
        self.system_prompt = system_prompt
    
    async def initialize(self, inputs: Dict[str, Any]) -> None:
        """Initialize the agent with a system prompt."""
        await super().initialize(inputs)
        
        if self.context:
            self.context.set_variable(f"flock.agents.{self.name}.system_prompt", 
                                     self.system_prompt)
    
    async def run_async(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the agent with token counting."""
        # Estimate input tokens
        if self.context:
            token_counter = self.get_module("token_counter")
            if token_counter:
                input_tokens = sum(len(str(v)) // 4 for v in inputs.values())
                token_counter.add_input_tokens(input_tokens)
        
        # Run the agent
        result = await super().run_async(inputs)
        
        # Estimate output tokens
        if self.context and token_counter:
            output_tokens = sum(len(str(v)) // 4 for v in result.values())
            token_counter.add_output_tokens(output_tokens)
            
        return result 