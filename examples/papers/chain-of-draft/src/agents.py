"""Chain of Draft agent implementations."""

from typing import Any, Dict

from flock.core import FlockAgent
from flock.core.context.context import FlockContext
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.logging.logging import get_logger
from pydantic import Field
from flock.evaluators.declarative.declarative_evaluator import (
    DeclarativeEvaluator,
    DeclarativeEvaluatorConfig,
)

from .prompts import (
    COD_SYSTEM_PROMPT, 
    COT_SYSTEM_PROMPT,
    PROBLEM_ANALYZER_PROMPT,
    COD_REASONING_PROMPT,
    FINAL_ANSWER_PROMPT
)

logger = get_logger("chain_of_draft")


class TokenCounterModuleConfig(FlockModuleConfig):
    """Configuration for token counting module."""
    
    track_individual_calls: bool = Field(
        default=True, description="Whether to track tokens for individual calls"
    )


class TokenCounterModule(FlockModule):
    """Module for counting tokens used in Chain of Draft."""

    name: str = "token_counter"
    config: TokenCounterModuleConfig = Field(
        default_factory=TokenCounterModuleConfig, description="Token counter configuration"
    )
    
    def __init__(self, name: str, config: TokenCounterModuleConfig = None):
        config = config or TokenCounterModuleConfig()
        super().__init__(name=name, config=config)
        # Define these as instance variables, not model fields
        self._input_tokens = 0
        self._output_tokens = 0
        self._total_tokens = 0

    @property
    def input_tokens(self) -> int:
        """Get input token count."""
        return self._input_tokens
        
    @property
    def output_tokens(self) -> int:
        """Get output token count."""
        return self._output_tokens
        
    @property
    def total_tokens(self) -> int:
        """Get total token count."""
        return self._total_tokens

    def add_input_tokens(self, count: int):
        """Add input tokens to the counter."""
        self._input_tokens += count
        self._total_tokens += count
        logger.debug(f"Added {count} input tokens. Total: {self._total_tokens}")

    def add_output_tokens(self, count: int):
        """Add output tokens to the counter."""
        self._output_tokens += count
        self._total_tokens += count
        logger.debug(f"Added {count} output tokens. Total: {self._total_tokens}")

    def reset(self):
        """Reset token counters."""
        self._input_tokens = 0
        self._output_tokens = 0
        self._total_tokens = 0
        
    async def initialize(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Called when the agent starts running."""
        logger.debug(f"Initializing token counter for {agent.name}")
        
    async def pre_evaluate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Called before agent evaluation, can track input tokens."""
        if self.config.track_individual_calls:
            # Simple approximation: 1 token ≈ 4 characters for English text
            input_tokens = sum(len(str(v)) // 4 for v in inputs.values())
            self.add_input_tokens(input_tokens)
        return inputs

    async def post_evaluate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Called after agent evaluation, can track output tokens."""
        if self.config.track_individual_calls:
            # Simple approximation: 1 token ≈ 4 characters for English text
            output_tokens = sum(len(str(v)) // 4 for v in result.values())
            self.add_output_tokens(output_tokens)
        return result

    async def terminate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Called when the agent finishes running."""
        logger.debug(f"Token counter final totals for {agent.name}: input={self.input_tokens}, output={self.output_tokens}, total={self.total_tokens}")

    async def on_error(
        self,
        agent: Any,
        error: Exception,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Called when an error occurs during agent execution."""
        logger.debug(f"Error in agent {agent.name}. Current token usage: {self.total_tokens}")


class ChainOfDraftAgent(FlockAgent):
    """Base agent for implementing Chain of Draft reasoning steps."""
    
    system_prompt: str = Field(default=COD_SYSTEM_PROMPT, description="System prompt for the agent")
    
    def __init__(self, name: str, system_prompt: str = COD_SYSTEM_PROMPT, **kwargs):
        """Initialize a Chain of Draft agent.
        
        Args:
            name: Unique identifier for the agent
            system_prompt: System prompt for the agent
            **kwargs: Additional arguments to pass to FlockAgent
        """
        # Create evaluator if not provided
        if 'evaluator' not in kwargs:
            model = kwargs.get('model', None)
            eval_config = DeclarativeEvaluatorConfig(
                model=model,
                use_cache=True,
                max_tokens=4096,
                temperature=0.0,
            )
            evaluator = DeclarativeEvaluator(name=f"{name}_evaluator", config=eval_config)
            kwargs['evaluator'] = evaluator
            
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
        # The token counting is now handled by the TokenCounterModule
        # through its pre_evaluate and post_evaluate methods
        return await super().run_async(inputs)


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
        # Create evaluator if not provided
        if 'evaluator' not in kwargs:
            model = kwargs.get('model', None)
            eval_config = DeclarativeEvaluatorConfig(
                model=model,
                use_cache=True,
                max_tokens=4096,
                temperature=0.0,
            )
            evaluator = DeclarativeEvaluator(name=f"{name}_evaluator", config=eval_config)
            kwargs['evaluator'] = evaluator
            
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
        # The token counting is now handled by the TokenCounterModule
        # through its pre_evaluate and post_evaluate methods
        return await super().run_async(inputs) 