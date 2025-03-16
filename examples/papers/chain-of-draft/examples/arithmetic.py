"""Example of Chain of Draft for arithmetic reasoning."""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to be able to import the chain_of_draft package
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from flock.core import Flock
from flock.core.logging.logging import get_logger
from src.chain_of_draft import create_chain_of_draft_workflow, get_token_usage

# Set up logger
logger = get_logger("chain_of_draft.example")

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
    try:
        flock = Flock(model="openai/gpt-4o", enable_logging=["chain_of_draft"])
        
        # Create a Chain of Draft workflow for arithmetic reasoning
        flock = create_chain_of_draft_workflow(flock, problem_type="arithmetic")
        
        print("\n===== Chain of Draft Arithmetic Reasoning Demo =====\n")
        
        for i, problem in enumerate(ARITHMETIC_PROBLEMS):
            print(f"\nProblem {i+1}: {problem}")
            
            try:
                # Run the workflow
                result = await flock.run_async(
                    start_agent="problem_analyzer",
                    input={"problem": problem}
                )
                
                # Debug the result
                logger.debug(f"Workflow result keys: {list(result.keys())}")
                
                # Print the answer and reasoning steps
                if 'answer' in result:
                    print(f"\nAnswer: {result['answer']}")
                else:
                    print("\nAnswer: [No answer produced]")
                    logger.error(f"Missing 'answer' key in result. Available keys: {list(result.keys())}")
                
                if 'reasoning_steps' in result:
                    print("\nReasoning Steps:")
                    print(result['reasoning_steps'])
                else:
                    print("\nReasoning Steps: [No reasoning steps produced]")
                    logger.error(f"Missing 'reasoning_steps' key in result. Available keys: {list(result.keys())}")
                
                # Print token usage
                token_usage = get_token_usage(flock)
                print(f"\nToken Usage: {token_usage['total_tokens']} tokens")
                
            except Exception as e:
                logger.error(f"Error processing problem {i+1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            print("-" * 60)
        
        print("\nDemo completed!")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main()) 