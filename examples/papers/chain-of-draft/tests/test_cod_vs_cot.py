"""Tests for comparing Chain of Draft vs Chain of Thought."""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Add the parent directory to sys.path to be able to import the chain_of_draft package
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from flock.core import Flock
from src.chain_of_draft.evaluation import compare_cod_vs_cot, run_with_timing


@pytest.mark.asyncio
@patch('src.chain_of_draft.evaluation.run_with_timing')
async def test_compare_cod_vs_cot(mock_run_with_timing):
    """Test the comparison functionality between CoD and CoT."""
    # Mock the timing function to return predictable results
    cod_result = {
        "method": "CoD",
        "problem": "Test problem",
        "answer": "42",
        "reasoning_steps": "x = 42",
        "execution_time": 1.0,
        "total_tokens": 50,
        "input_tokens": 20,
        "output_tokens": 30,
    }
    
    cot_result = {
        "method": "CoT",
        "problem": "Test problem",
        "answer": "42",
        "reasoning_steps": "The answer is 42 because I thought about it carefully...",
        "execution_time": 2.0,
        "total_tokens": 200,
        "input_tokens": 50,
        "output_tokens": 150,
    }
    
    # Make the mock return CoD result first, then CoT result
    mock_run_with_timing.side_effect = [cod_result, cot_result]
    
    # Run the comparison
    results = await compare_cod_vs_cot(["Test problem"])
    
    # Check that the comparison metrics were calculated correctly
    assert len(results) == 1
    comparison = results[0]
    
    assert comparison["problem"] == "Test problem"
    assert comparison["cod_answer"] == "42"
    assert comparison["cot_answer"] == "42"
    assert comparison["cod_tokens"] == 50
    assert comparison["cot_tokens"] == 200
    assert comparison["cod_time"] == 1.0
    assert comparison["cot_time"] == 2.0
    assert comparison["token_reduction"] == 0.75  # (1 - 50/200)
    assert comparison["time_reduction"] == 0.5  # (1 - 1.0/2.0)
    assert comparison["answers_match"] == True


@pytest.mark.asyncio
@patch('src.chain_of_draft.evaluation.run_with_timing')
async def test_compare_cod_vs_cot_different_answers(mock_run_with_timing):
    """Test the comparison when CoD and CoT give different answers."""
    # Mock the timing function to return different answers
    cod_result = {
        "method": "CoD",
        "problem": "Test problem",
        "answer": "42",
        "reasoning_steps": "x = 42",
        "execution_time": 1.0,
        "total_tokens": 50,
    }
    
    cot_result = {
        "method": "CoT",
        "problem": "Test problem",
        "answer": "43",  # Different answer
        "reasoning_steps": "The answer is 43...",
        "execution_time": 2.0,
        "total_tokens": 200,
    }
    
    # Make the mock return CoD result first, then CoT result
    mock_run_with_timing.side_effect = [cod_result, cot_result]
    
    # Run the comparison
    results = await compare_cod_vs_cot(["Test problem"])
    
    # Check that the answers_match flag is False
    assert results[0]["answers_match"] == False


@pytest.mark.asyncio
@patch('time.time')
@patch('src.chain_of_draft.evaluation.get_token_usage')
@patch('src.chain_of_draft.evaluation.reset_token_counters')
async def test_run_with_timing(mock_reset, mock_get_usage, mock_time):
    """Test the run_with_timing function."""
    # Mock time.time() to return predictable values
    mock_time.side_effect = [10.0, 12.5]  # Start time, end time
    
    # Mock token usage
    mock_get_usage.return_value = {
        "input_tokens": 100,
        "output_tokens": 150,
        "total_tokens": 250,
    }
    
    # Mock flock
    mock_flock = MagicMock(spec=Flock)
    mock_flock.run_async.return_value = {
        "answer": "42",
        "reasoning_steps": "x = 42"
    }
    
    # Run the timing function
    result = await run_with_timing(
        flock=mock_flock,
        problem="What is the answer?",
        is_cot=False
    )
    
    # Check that token counters were reset
    mock_reset.assert_called_once_with(mock_flock)
    
    # Check that flock.run_async was called with the right parameters
    mock_flock.run_async.assert_called_once_with(
        start_agent="problem_analyzer",
        input={"problem": "What is the answer?"}
    )
    
    # Check the result contains all expected fields
    assert result["method"] == "CoD"
    assert result["problem"] == "What is the answer?"
    assert result["answer"] == "42"
    assert result["reasoning_steps"] == "x = 42"
    assert result["execution_time"] == 2.5  # 12.5 - 10.0
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 150
    assert result["total_tokens"] == 250 