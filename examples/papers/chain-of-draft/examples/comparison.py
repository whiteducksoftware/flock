"""Example comparing Chain of Draft vs Chain of Thought."""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to be able to import the chain_of_draft package
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from src.chain_of_draft.evaluation import compare_cod_vs_cot, print_comparison_summary

# Sample arithmetic problems for comparison
COMPARISON_PROBLEMS = [
    "If there are 5 apples and 3 oranges in a basket, and 2 apples are removed, how many fruits remain in the basket?",
    "A train travels at 60 miles per hour for 2.5 hours, how far does it go?",
    "If a recipe requires 3/4 cup of flour for 2 servings, how much flour is needed for 5 servings?",
]


async def main():
    """Run comparison between Chain of Draft and Chain of Thought."""
    print("\n===== Chain of Draft vs Chain of Thought Comparison =====\n")
    print("Running comparison on sample problems...")
    print("This may take a few minutes as we need to run each problem twice (CoD and CoT)")
    
    # Run comparison on sample problems
    results = await compare_cod_vs_cot(
        problems=COMPARISON_PROBLEMS,
        model="openai/gpt-4o",
        max_steps=10
    )
    
    # Print summary of results
    print_comparison_summary(results)
    
    print("\nComparison completed!")


if __name__ == "__main__":
    asyncio.run(main()) 