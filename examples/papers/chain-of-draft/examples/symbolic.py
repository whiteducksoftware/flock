"""Example of Chain of Draft for symbolic reasoning."""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to be able to import the chain_of_draft package
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from flock.core import Flock
from src.chain_of_draft import create_chain_of_draft_workflow, get_token_usage

# Sample symbolic problems (coin flip sequences) from the paper
SYMBOLIC_PROBLEMS = [
    "I flip a fair coin 5 times. What is the probability of getting exactly 3 heads?",
    "I flip a fair coin 10 times. What is the probability of getting at least 8 heads?",
    "I have a fair coin and an unfair coin. The unfair coin has a 3/4 probability of heads. I randomly pick one of the coins and flip it. If the result is heads, what is the probability that I picked the unfair coin?",
    "I flip a coin 3 times. If I get heads on the first flip, what is the probability I get at least 2 heads total?",
]


async def main():
    """Run Chain of Draft on symbolic reasoning problems."""
    # Initialize Flock with your preferred model
    flock = Flock(model="openai/gpt-4o", enable_logging=["chain_of_draft"])
    
    # Create a Chain of Draft workflow for symbolic reasoning
    flock = create_chain_of_draft_workflow(flock, problem_type="symbolic")
    
    print("\n===== Chain of Draft Symbolic Reasoning Demo =====\n")
    
    for i, problem in enumerate(SYMBOLIC_PROBLEMS):
        print(f"\nProblem {i+1}: {problem}")
        
        # Run the workflow
        result = await flock.run_async(
            start_agent="problem_analyzer",
            input={"problem": problem}
        )
        
        # Print the answer and reasoning steps
        print(f"\nAnswer: {result['answer']}")
        print("\nReasoning Steps:")
        print(result['reasoning_steps'])
        
        # Print token usage
        token_usage = get_token_usage(flock)
        print(f"\nToken Usage: {token_usage['total_tokens']} tokens")
        print("-" * 60)
    
    print("\nDemo completed!")


if __name__ == "__main__":
    asyncio.run(main()) 