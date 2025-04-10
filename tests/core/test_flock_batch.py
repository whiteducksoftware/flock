

import os
import pytest
import pandas as pd
from flock.core import Flock, FlockAgent, FlockFactory
from flock.core.flock_registry import get_registry
from flock.evaluators.test.test_case_evaluator import TestCaseEvaluator, TestCaseEvaluatorConfig



@pytest.fixture
def basic_flock() -> Flock:
    """Fixture for a basic Flock instance."""
    return Flock(name="test_basic_flock", model="test-model", enable_logging=False, show_flock_banner=False)

@pytest.fixture
def simple_agent() -> FlockAgent:
    """Fixture for a simple agent instance."""
    agent = FlockFactory.create_default_agent(name="agent1", input="query", output="col1,col2,col3,col4")
    agent.evaluator = TestCaseEvaluator(name="test_case_evaluator", config=TestCaseEvaluatorConfig())
    return agent


@pytest.fixture(autouse=True)
def clear_registry():
    """Fixture to ensure a clean registry for each test."""
    registry = get_registry()
    registry._initialize() # Reset internal dictionaries
    yield # Run the test
    registry._initialize() # Clean up after test  


@pytest.mark.asyncio
async def test_batch_execution_with_dataframe_input(basic_flock: Flock, simple_agent: FlockAgent):
    """Test batch execution with CSV input."""
    batch_inputs = pd.DataFrame({
        "query": ["test1", "test2", "test3"],
    })
    results = await basic_flock.run_batch_async(
        start_agent=simple_agent,
        batch_inputs=batch_inputs,
        input_mapping={"query": "query"},
        parallel=True,
    )
    assert len(results) == 3
    assert results[0]["col1"] == "Test Result"
    assert results[1]["col2"] == "Test Result"
    assert results[2]["col3"] == "Test Result"
    assert results[2]["col4"] == "Test Result"
    
    
@pytest.mark.asyncio
async def test_batch_execution_with_dataframe_input_and_csv_output(basic_flock: Flock, simple_agent: FlockAgent):
    """Test batch execution with CSV input."""
    batch_inputs = pd.DataFrame({
        "query": ["test1", "test2", "test3"],
    })
    results = await basic_flock.run_batch_async(
        start_agent=simple_agent,
        batch_inputs=batch_inputs,
        input_mapping={"query": "query"},
        parallel=True,
        write_to_csv="test_output.csv",
        hide_columns=["col1", "col2"],
        delimiter="-",
    )
    assert os.path.exists("test_output.csv")
    df = pd.read_csv("test_output.csv", delimiter="-")
    assert len(df) == 3
    assert df.columns.tolist() == ["col3", "col4"]
    assert df["col3"][0] == "Test Result"
    assert df["col4"][1] == "Test Result"
    os.remove("test_output.csv")

