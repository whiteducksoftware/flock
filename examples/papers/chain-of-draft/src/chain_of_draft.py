"""Chain of Draft implementation using Flock."""

from typing import Literal, Optional

from flock.core import Flock

from .agents import (
    ChainOfDraftAgent,
    ChainOfThoughtAgent,
    FinalAnswerAgent,
    ProblemAnalyzerAgent,
    ReasoningStepAgent,
)
from .prompts import COD_SYSTEM_PROMPT, COT_SYSTEM_PROMPT
from .router import ChainOfDraftRouter


def create_chain_of_draft_workflow(
    flock: Flock,
    problem_type: Literal["arithmetic", "commonsense", "symbolic"] = "arithmetic",
    model: Optional[str] = None,
    max_steps: int = 10,
    use_cot: bool = False,
) -> Flock:
    """Create a Chain of Draft workflow for the specified problem type.
    
    Args:
        flock: The Flock instance to configure
        problem_type: Type of problem to solve (arithmetic, commonsense, or symbolic)
        model: Optional model override (defaults to the Flock instance's model)
        max_steps: Maximum number of reasoning steps
        use_cot: If True, use Chain of Thought instead of Chain of Draft
        
    Returns:
        Configured Flock instance with Chain of Draft agents
    """
    # Use the Flock model if none specified
    if not model:
        model = flock.model
    
    # Determine system prompt based on reasoning type
    system_prompt = COT_SYSTEM_PROMPT if use_cot else COD_SYSTEM_PROMPT

    # Create a router for the chain
    cod_router = ChainOfDraftRouter(
        name="cod_router",
        final_answer_agent="final_answer",
        reasoning_step_agent="reasoning_step",
        max_steps=max_steps,
    )
    
    # Create agents based on reasoning style
    agent_base_class = ChainOfThoughtAgent if use_cot else ChainOfDraftAgent
    
    # Create problem analyzer agent
    problem_analyzer = ProblemAnalyzerAgent(
        name="problem_analyzer",
        system_prompt=system_prompt,
        model=model,
        handoff_router=cod_router
    )
    
    # Create reasoning step agent
    reasoning_step = ReasoningStepAgent(
        name="reasoning_step",
        system_prompt=system_prompt,
        model=model,
        handoff_router=cod_router
    )
    
    # Create final answer agent
    final_answer = FinalAnswerAgent(
        name="final_answer",
        system_prompt=system_prompt,
        model=model,
    )
    
    # Add agents to the flock
    flock.add_agent(problem_analyzer)
    flock.add_agent(reasoning_step)
    flock.add_agent(final_answer)
    
    return flock


def reset_token_counters(flock: Flock) -> None:
    """Reset all token counters in the Flock instance."""
    for agent_name in flock.registry.agents:
        agent = flock.registry.get_agent(agent_name)
        token_counter = agent.get_module("token_counter")
        if token_counter:
            token_counter.reset()


def get_token_usage(flock: Flock) -> dict:
    """Get token usage statistics from all agents."""
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    
    for agent_name in flock.registry.agents:
        agent = flock.registry.get_agent(agent_name)
        token_counter = agent.get_module("token_counter")
        if token_counter:
            input_tokens += token_counter.input_tokens
            output_tokens += token_counter.output_tokens
            total_tokens += token_counter.total_tokens
    
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens
    } 