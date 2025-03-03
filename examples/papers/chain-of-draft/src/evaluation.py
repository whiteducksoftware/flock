"""Evaluation utilities for Chain of Draft."""

import asyncio
import time
from typing import List, Dict, Any, Optional

from flock.core import Flock
from flock.core.logging.logging import get_logger

from .chain_of_draft import (
    create_chain_of_draft_workflow, 
    get_token_usage, 
    reset_token_counters
)

logger = get_logger("chain_of_draft.evaluation")


async def run_with_timing(
    flock: Flock, 
    problem: str, 
    is_cot: bool = False
) -> Dict[str, Any]:
    """Run a problem through a workflow with timing metrics.
    
    Args:
        flock: The configured Flock instance
        problem: The problem to solve
        is_cot: Whether this is Chain of Thought (for logging)
        
    Returns:
        Dictionary with results and metrics
    """
    method = "CoT" if is_cot else "CoD"
    logger.info(f"Running {method} on problem: {problem}")
    
    # Reset token counters
    reset_token_counters(flock)
    
    # Run the workflow with timing
    start_time = time.time()
    result = await flock.run_async(
        start_agent="problem_analyzer",
        input={"problem": problem}
    )
    end_time = time.time()
    
    # Get token usage
    token_usage = get_token_usage(flock)
    
    return {
        "method": method,
        "problem": problem,
        "answer": result.get("answer", "No answer found"),
        "reasoning_steps": result.get("reasoning_steps", ""),
        "execution_time": end_time - start_time,
        "input_tokens": token_usage["input_tokens"],
        "output_tokens": token_usage["output_tokens"],
        "total_tokens": token_usage["total_tokens"],
    }


async def compare_cod_vs_cot(
    problems: List[str], 
    model: Optional[str] = None,
    max_steps: int = 10
) -> List[Dict[str, Any]]:
    """Compare Chain of Draft vs Chain of Thought on a set of problems.
    
    Args:
        problems: List of problem statements to compare
        model: Model to use for both approaches (defaults to "openai/gpt-4o")
        max_steps: Maximum number of reasoning steps
        
    Returns:
        List of comparison results
    """
    model = model or "openai/gpt-4o"
    
    # Create Flock instance for Chain of Draft
    cod_flock = Flock(model=model, enable_logging=["chain_of_draft"])
    cod_flock = create_chain_of_draft_workflow(
        cod_flock, 
        max_steps=max_steps,
        use_cot=False
    )
    
    # Create Flock instance for Chain of Thought
    cot_flock = Flock(model=model, enable_logging=["chain_of_draft"])
    cot_flock = create_chain_of_draft_workflow(
        cot_flock, 
        max_steps=max_steps,
        use_cot=True
    )
    
    results = []
    
    for problem in problems:
        # Run Chain of Draft
        cod_result = await run_with_timing(cod_flock, problem, is_cot=False)
        
        # Run Chain of Thought
        cot_result = await run_with_timing(cot_flock, problem, is_cot=True)
        
        # Calculate improvement metrics
        token_reduction = 1 - (cod_result["total_tokens"] / cot_result["total_tokens"]) if cot_result["total_tokens"] > 0 else 0
        time_reduction = 1 - (cod_result["execution_time"] / cot_result["execution_time"]) if cot_result["execution_time"] > 0 else 0
        
        comparison = {
            "problem": problem,
            "cod_answer": cod_result["answer"],
            "cot_answer": cot_result["answer"],
            "cod_tokens": cod_result["total_tokens"],
            "cot_tokens": cot_result["total_tokens"],
            "cod_time": cod_result["execution_time"],
            "cot_time": cot_result["execution_time"],
            "token_reduction": token_reduction,
            "token_reduction_percent": f"{token_reduction * 100:.1f}%",
            "time_reduction": time_reduction,
            "time_reduction_percent": f"{time_reduction * 100:.1f}%",
            "answers_match": cod_result["answer"] == cot_result["answer"],
            "cod_reasoning": cod_result["reasoning_steps"],
            "cot_reasoning": cot_result["reasoning_steps"],
        }
        
        logger.info(
            f"Comparison results: "
            f"Token reduction: {comparison['token_reduction_percent']}, "
            f"Time reduction: {comparison['time_reduction_percent']}, "
            f"Answers match: {comparison['answers_match']}"
        )
        
        results.append(comparison)
    
    return results


def print_comparison_summary(results: List[Dict[str, Any]]) -> None:
    """Print a summary of comparison results.
    
    Args:
        results: List of comparison results from compare_cod_vs_cot
    """
    if not results:
        print("No results to summarize")
        return
    
    total_problems = len(results)
    matching_answers = sum(1 for result in results if result["answers_match"])
    avg_token_reduction = sum(result["token_reduction"] for result in results) / total_problems
    avg_time_reduction = sum(result["time_reduction"] for result in results) / total_problems
    
    print("\n=== Chain of Draft vs Chain of Thought Summary ===")
    print(f"Total problems evaluated: {total_problems}")
    print(f"Matching answers: {matching_answers} ({matching_answers/total_problems*100:.1f}%)")
    print(f"Average token reduction: {avg_token_reduction*100:.1f}%")
    print(f"Average execution time reduction: {avg_time_reduction*100:.1f}%")
    print("\n=== Sample Problem Comparison ===")
    
    for i, result in enumerate(results):
        if i >= 3:  # Show at most 3 examples
            break
            
        print(f"\nProblem {i+1}: {result['problem']}")
        print(f"CoD Answer: {result['cod_answer']}")
        print(f"CoT Answer: {result['cot_answer']}")
        print(f"CoD Tokens: {result['cod_tokens']}")
        print(f"CoT Tokens: {result['cot_tokens']}")
        print(f"Token Reduction: {result['token_reduction_percent']}")
        print(f"Time Reduction: {result['time_reduction_percent']}")
        print(f"Answers Match: {result['answers_match']}")
        print("\nCoD Reasoning Steps:")
        print(result['cod_reasoning'])
        print("\nCoT Reasoning Steps:")
        print(result['cot_reasoning'][:200] + "..." if len(result['cot_reasoning']) > 200 else result['cot_reasoning']) 