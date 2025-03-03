"""Example of Chain of Draft for arithmetic reasoning."""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to be able to import the chain_of_draft package
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from flock.core import Flock
from src.chain_of_draft import create_chain_of_draft_workflow, get_token_usage

# Sample arithmetic problems from the paper
ARITHMETIC_PROBLEMS = [
    "If a recipe requires 3/4 cup of flour for 2 servings, how much flour is needed for 5 servings?",
    "A train travels at 60 miles per hour for 3 hours, then at 80 miles per hour for 2 hours. What is the average speed for the entire journey?",
    "Jason had 20 lollipops. He gave Denny some lollipops. Now Jason has 12 lollipops. How many lollipops did Jason give to Denny?",
    "If there are 5 apples and 3 oranges in a basket, and 2 apples are removed, how many fruits remain in the basket?",
]


async def main():
    """Run Chain of Draft on arithmetic problems."""
    # Initialize Flock with your preferred model
    flock = Flock(model="openai/gpt-4o", enable_logging=["chain_of_draft"])
    
    # Create a Chain of Draft workflow for arithmetic reasoning
    flock = create_chain_of_draft_workflow(flock, problem_type="arithmetic")
    
    print("\n===== Chain of Draft Arithmetic Reasoning Demo =====\n")
    
    for i, problem in enumerate(ARITHMETIC_PROBLEMS):
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