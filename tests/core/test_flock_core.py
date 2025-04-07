# tests/core/test_flock_core.py
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from pydantic import BaseModel

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.context.context import FlockContext
from flock.core.flock_registry import get_registry, FlockRegistry

# Simple mock agent for testing addition
class SimpleAgent(FlockAgent):
    async def evaluate(self, inputs: dict) -> dict:
        return {"result": "simple"}

@pytest.fixture(autouse=True)
def clear_registry():
    """Fixture to ensure a clean registry for each test."""
    registry = get_registry()
    registry._initialize() # Reset internal dictionaries
    yield # Run the test
    registry._initialize() # Clean up after test


@pytest.fixture
def basic_flock() -> Flock:
    """Fixture for a basic Flock instance."""
    return Flock(name="test_basic_flock", model="test-model", enable_logging=False, show_flock_banner=False)

@pytest.fixture
def simple_agent() -> SimpleAgent:
    """Fixture for a simple agent instance."""
    return SimpleAgent(name="agent1", input="query", output="result")


# --- Initialization Tests ---

def test_flock_init_defaults():
    """Test Flock initialization with default values."""
    flock = Flock(enable_logging=False, show_flock_banner=False)
    assert flock.name.startswith("flock_")
    assert flock.model == "openai/gpt-4o" # Default from config
    assert flock.description is None
    assert not flock.enable_temporal
    assert not flock.enable_logging
    assert not flock.show_flock_banner
    assert flock._agents == {}

def test_flock_init_custom(mocker):
    """Test Flock initialization with custom values."""
    mock_configure_logging = mocker.patch.object(Flock, '_configure_logging')
    mock_set_temporal = mocker.patch.object(Flock, '_set_temporal_debug_flag')
    mock_ensure_session = mocker.patch.object(Flock, '_ensure_session_id')

    flock = Flock(
        name="custom_flock",
        model="custom_model",
        description="My custom flock",
        enable_temporal=True,
        enable_logging=["flock", "agent"],
        show_flock_banner=False
    )
    assert flock.name == "custom_flock"
    assert flock.model == "custom_model"
    assert flock.description == "My custom flock"
    assert flock.enable_temporal
    assert flock.enable_logging == ["flock", "agent"]
    assert not flock.show_flock_banner

    mock_configure_logging.assert_called_once_with(["flock", "agent"])
    mock_set_temporal.assert_called_once()
    mock_ensure_session.assert_called_once()


def test_flock_init_with_agents(simple_agent):
    """Test Flock initialization with agents passed in the constructor."""
    flock = Flock(agents=[simple_agent], enable_logging=False, show_flock_banner=False)
    assert "agent1" in flock.agents
    assert flock.agents["agent1"] is simple_agent

# --- Agent Management Tests ---

def test_add_agent(basic_flock, simple_agent):
    """Test adding an agent to the Flock."""
    basic_flock.add_agent(simple_agent)
    assert "agent1" in basic_flock._agents
    assert basic_flock._agents["agent1"] is simple_agent
    # Check if agent was registered globally too
    assert get_registry().get_agent("agent1") is simple_agent

def test_add_agent_sets_default_model(basic_flock):
    """Test that adding an agent without a model assigns the Flock's default."""
    agent_no_model = SimpleAgent(name="agent_no_model", model=None, input="in", output="out")
    basic_flock.model = "flock-default-model"
    basic_flock.add_agent(agent_no_model)
    assert agent_no_model.model == "flock-default-model"

def test_add_agent_duplicate(basic_flock, simple_agent, caplog):
    """Test adding an agent with a name that already exists."""
    basic_flock.add_agent(simple_agent)
    new_agent_same_name = SimpleAgent(name="agent1", input="query2", output="result2")
    basic_flock.add_agent(new_agent_same_name)

    assert "already exists. Overwriting" in caplog.text
    assert basic_flock.agents["agent1"] is new_agent_same_name # Should be overwritten

def test_add_agent_invalid_type(basic_flock):
    """Test adding something that is not a FlockAgent."""
    with pytest.raises(TypeError):
        basic_flock.add_agent({"not": "an agent"})

def test_agents_property(basic_flock, simple_agent):
    """Test the agents property."""
    assert basic_flock.agents == {}
    basic_flock.add_agent(simple_agent)
    assert basic_flock.agents == {"agent1": simple_agent}


# --- Execution Tests ---

@pytest.mark.asyncio
async def test_run_async_local_delegation(basic_flock, simple_agent, mocker):
    """Test run_async delegates to local executor when enable_temporal is False."""
    basic_flock.enable_temporal = False
    basic_flock.add_agent(simple_agent)
    mock_local_exec = mocker.patch('flock.core.flock.run_local_workflow', new_callable=AsyncMock)
    mock_temporal_exec = mocker.patch('flock.core.flock.run_temporal_workflow', new_callable=AsyncMock)
    mock_init_context = mocker.patch('flock.core.flock.initialize_context')
    mock_result = {"final_output": "local_result"}
    mock_local_exec.return_value = mock_result

    input_data = {"query": "test"}
    result = await basic_flock.run_async(start_agent="agent1", input=input_data, box_result=False)

    assert result == mock_result
    mock_init_context.assert_called_once()
    mock_local_exec.assert_awaited_once()
    mock_temporal_exec.assert_not_awaited()
    # Check context passed to initialize_context
    call_args, _ = mock_init_context.call_args
    context_arg = call_args[0]
    assert isinstance(context_arg, FlockContext)
    assert call_args[1] == "agent1" # start_agent_name
    assert call_args[2] == input_data # run_input
    assert call_args[4] is True # local_debug flag for initialize_context
    assert call_args[5] == basic_flock.model # model


@pytest.mark.asyncio
async def test_run_async_temporal_delegation(basic_flock, simple_agent, mocker):
    """Test run_async delegates to temporal executor when enable_temporal is True."""
    basic_flock.enable_temporal = True
    basic_flock.add_agent(simple_agent)
    mock_local_exec = mocker.patch('flock.core.flock.run_local_workflow', new_callable=AsyncMock)
    mock_temporal_exec = mocker.patch('flock.core.flock.run_temporal_workflow', new_callable=AsyncMock)
    mock_init_context = mocker.patch('flock.core.flock.initialize_context')
    mock_result = {"final_output": "temporal_result"}
    mock_temporal_exec.return_value = mock_result

    input_data = {"query": "test"}
    result = await basic_flock.run_async(start_agent="agent1", input=input_data, box_result=False)

    assert result == mock_result
    mock_init_context.assert_called_once()
    mock_temporal_exec.assert_awaited_once()
    mock_local_exec.assert_not_awaited()
    # Check context passed to initialize_context
    call_args, _ = mock_init_context.call_args
    context_arg = call_args[0]
    assert isinstance(context_arg, FlockContext)
    assert call_args[4] is False # local_debug flag for initialize_context


@pytest.mark.asyncio
async def test_run_async_no_start_agent_single_agent(basic_flock, simple_agent):
    """Test run_async uses the only agent if none is specified."""
    basic_flock.add_agent(simple_agent)
    basic_flock.enable_temporal = False # Use local for simplicity
    with patch('flock.core.flock.run_local_workflow', new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"result": "ok"}
        await basic_flock.run_async(input={"query": "test"})
        # Check context passed to execute call
        call_args, _ = mock_exec.call_args
        context_arg = call_args[0]
        assert context_arg.get_variable("flock.current_agent") == "agent1"

@pytest.mark.asyncio
async def test_run_async_no_start_agent_multiple_agents(basic_flock, simple_agent):
    """Test run_async raises error if no start agent specified with multiple agents."""
    agent2 = SimpleAgent(name="agent2", input="in", output="out")
    basic_flock.add_agent(simple_agent)
    basic_flock.add_agent(agent2)
    with pytest.raises(ValueError, match="No start_agent specified"):
        await basic_flock.run_async(input={"query": "test"})

@pytest.mark.asyncio
async def test_run_async_agent_not_found(basic_flock):
    """Test run_async raises error if start agent doesn't exist."""
    with pytest.raises(ValueError, match="Start agent 'non_existent_agent' not found"):
        await basic_flock.run_async(start_agent="non_existent_agent", input={"query": "test"})

@pytest.mark.asyncio
async def test_run_async_result_boxing(basic_flock, simple_agent, mocker):
    """Test the box_result parameter."""
    basic_flock.enable_temporal = False
    basic_flock.add_agent(simple_agent)
    mock_exec = mocker.patch('flock.core.flock.run_local_workflow', new_callable=AsyncMock)
    raw_result = {"final_output": "local_result"}
    mock_exec.return_value = raw_result

    # Test with boxing (default)
    boxed_result = await basic_flock.run_async(start_agent="agent1", input={}, box_result=True)
    from box import Box # Import locally for test
    assert isinstance(boxed_result, Box)
    assert boxed_result.final_output == "local_result"

    # Test without boxing
    dict_result = await basic_flock.run_async(start_agent="agent1", input={}, box_result=False)
    assert isinstance(dict_result, dict)
    assert not isinstance(dict_result, Box)
    assert dict_result == raw_result

def test_run_sync_wrapper(basic_flock, mocker):
    """Test that the synchronous run method correctly calls run_async."""
    # Mock run_async to avoid actual async execution
    mock_run_async = mocker.patch.object(basic_flock, 'run_async', new_callable=AsyncMock)
    mock_run_async.return_value = {"result": "async_ran"}

    # Mock asyncio loop handling
    mock_loop = MagicMock()
    mock_get_loop = mocker.patch('asyncio.get_running_loop', return_value=mock_loop)
    mock_loop.run_until_complete.return_value = {"result": "async_ran"}

    # Call the synchronous run method
    sync_result = basic_flock.run(start_agent="agent1", input={"query": "sync_test"})

    # Assert run_async was called
    mock_run_async.assert_awaited_once_with(
        start_agent="agent1",
        input={"query": "sync_test"},
        context=None,
        run_id="",
        box_result=True,
        agents=None,
    )
    # Assert the result from run_until_complete is returned
    assert sync_result == {"result": "async_ran"}
    mock_loop.run_until_complete.assert_called_once()


# --- Serialization Delegation Tests ---

def test_to_dict_delegates_to_serializer(basic_flock, mocker):
    """Verify Flock.to_dict calls FlockSerializer.serialize."""
    mock_serializer_serialize = mocker.patch('flock.core.serialization.flock_serializer.FlockSerializer.serialize')
    mock_serializer_serialize.return_value = {"serialized": "data"}

    result = basic_flock.to_dict(path_type="relative")

    mock_serializer_serialize.assert_called_once_with(basic_flock, path_type="relative")
    assert result == {"serialized": "data"}

def test_from_dict_delegates_to_serializer(mocker):
    """Verify Flock.from_dict calls FlockSerializer.deserialize."""
    mock_flock_instance = Flock(name="deserialized", enable_logging=False, show_flock_banner=False)
    mock_serializer_deserialize = mocker.patch('flock.core.serialization.flock_serializer.FlockSerializer.deserialize')
    mock_serializer_deserialize.return_value = mock_flock_instance
    input_data = {"name": "deserialized", "agents": {}}

    result = Flock.from_dict(input_data)

    mock_serializer_deserialize.assert_called_once_with(Flock, input_data)
    assert result is mock_flock_instance

# --- Static Loader Delegation Test ---

def test_load_from_file_delegates_to_loader(mocker):
    """Verify Flock.load_from_file calls the loader function."""
    mock_loader_func = mocker.patch('flock.core.loader.load_flock_from_file')
    mock_flock_instance = Flock(name="loaded_from_file", enable_logging=False, show_flock_banner=False)
    mock_loader_func.return_value = mock_flock_instance
    file_path = "dummy/path/flock.yaml"

    result = Flock.load_from_file(file_path)

    mock_loader_func.assert_called_once_with(file_path)
    assert result is mock_flock_instance