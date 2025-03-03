"""Basic tests for Chain of Draft implementation."""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Add the parent directory to sys.path to be able to import the chain_of_draft package
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from flock.core import Flock
from src.chain_of_draft import (
    create_chain_of_draft_workflow,
    get_token_usage,
    reset_token_counters
)
from src.chain_of_draft.agents import (
    ChainOfDraftAgent,
    TokenCounterModule,
    ProblemAnalyzerAgent,
    ReasoningStepAgent,
    FinalAnswerAgent
)
from src.chain_of_draft.router import ChainOfDraftRouter


def test_create_chain_of_draft_workflow():
    """Test the workflow creation function."""
    # Create a mock Flock instance
    mock_flock = MagicMock(spec=Flock)
    mock_flock.model = "openai/gpt-4o"
    mock_flock.registry = MagicMock()
    mock_flock.registry.agents = {}
    
    # Create the workflow
    result = create_chain_of_draft_workflow(mock_flock)
    
    # Check that the correct agents were added
    assert mock_flock.add_agent.call_count == 3
    
    # Check that the returned instance is the same as the input
    assert result == mock_flock


def test_token_counter_module():
    """Test the TokenCounterModule functionality."""
    # Create a token counter
    counter = TokenCounterModule(name="test_counter")
    
    # Initial state
    assert counter.input_tokens == 0
    assert counter.output_tokens == 0
    assert counter.total_tokens == 0
    
    # Add some tokens
    counter.add_input_tokens(100)
    assert counter.input_tokens == 100
    assert counter.total_tokens == 100
    
    counter.add_output_tokens(50)
    assert counter.output_tokens == 50
    assert counter.total_tokens == 150
    
    # Reset
    counter.reset()
    assert counter.input_tokens == 0
    assert counter.output_tokens == 0
    assert counter.total_tokens == 0


def test_chain_of_draft_agent():
    """Test ChainOfDraftAgent initialization."""
    agent = ChainOfDraftAgent(name="test_agent", model="openai/gpt-4o")
    
    # Check properties
    assert agent.name == "test_agent"
    assert agent.model == "openai/gpt-4o"
    
    # Check that token counter module was added
    token_counter = agent.get_module("token_counter")
    assert token_counter is not None


def test_chain_of_draft_router():
    """Test ChainOfDraftRouter initialization and configuration."""
    router = ChainOfDraftRouter(
        name="test_router",
        final_answer_agent="final",
        reasoning_step_agent="reasoning",
        max_steps=5
    )
    
    # Check properties
    assert router.name == "test_router"
    assert router.final_answer_agent == "final"
    assert router.reasoning_step_agent == "reasoning"
    assert router.max_steps == 5
    
    # Check that config includes the agents
    assert "final" in router.config.agents
    assert "reasoning" in router.config.agents


@pytest.mark.asyncio
async def test_router_routing_logic():
    """Test the routing logic of ChainOfDraftRouter."""
    router = ChainOfDraftRouter(
        final_answer_agent="final",
        reasoning_step_agent="reasoning",
    )
    
    # Mock context and agents
    context = MagicMock()
    context.get_variable.return_value = 0  # First step
    
    problem_analyzer = MagicMock()
    problem_analyzer.name = "problem_analyzer"
    
    reasoning_agent = MagicMock()
    reasoning_agent.name = "reasoning"
    
    # Test routing from problem analyzer
    result = {"initial_step": "x = 5"}
    handoff = await router.route(problem_analyzer, result, context)
    
    # Should route to reasoning step
    assert handoff.next_agent == "reasoning"
    assert handoff.hand_off_mode == "add"
    assert "previous_steps" in result
    assert result["previous_steps"] == "x = 5"
    
    # Test routing from reasoning step (not final)
    result = {"next_step": "y = 10", "is_final": False}
    handoff = await router.route(reasoning_agent, result, context)
    
    # Should continue with reasoning
    assert handoff.next_agent == "reasoning"
    
    # Test routing from reasoning step (final)
    result = {"next_step": "z = 15", "is_final": True}
    handoff = await router.route(reasoning_agent, result, context)
    
    # Should go to final answer
    assert handoff.next_agent == "final"


@pytest.mark.asyncio
async def test_max_steps_routing():
    """Test that router respects max_steps."""
    router = ChainOfDraftRouter(
        final_answer_agent="final",
        reasoning_step_agent="reasoning",
        max_steps=3
    )
    
    # Mock context and agent
    context = MagicMock()
    reasoning_agent = MagicMock()
    reasoning_agent.name = "reasoning"
    
    # Step 1
    context.get_variable.return_value = 0
    result = {"next_step": "Step 1", "is_final": False}
    handoff = await router.route(reasoning_agent, result, context)
    assert handoff.next_agent == "reasoning"  # Continue reasoning
    
    # Step 2
    context.get_variable.return_value = 1
    result = {"next_step": "Step 2", "is_final": False}
    handoff = await router.route(reasoning_agent, result, context)
    assert handoff.next_agent == "reasoning"  # Continue reasoning
    
    # Step 3 (max reached)
    context.get_variable.return_value = 2
    result = {"next_step": "Step 3", "is_final": False}
    handoff = await router.route(reasoning_agent, result, context)
    assert handoff.next_agent == "final"  # Go to final because max steps reached 