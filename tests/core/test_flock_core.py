# tests/core/test_flock_core.py
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import timedelta  # Import timedelta

from pydantic import BaseModel

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.context.context import FlockContext
from flock.core.flock_registry import get_registry, FlockRegistry
from flock.workflow.temporal_config import TemporalRetryPolicyConfig, TemporalWorkflowConfig

# Import Temporal Config models


# Simple mock agent for testing addition
class SimpleAgent(FlockAgent):
    async def evaluate(self, inputs: dict) -> dict:
        return {"result": "simple"}


@pytest.fixture(autouse=True)
def clear_registry():
    """Fixture to ensure a clean registry for each test."""
    registry = get_registry()
    registry._initialize()  # Reset internal dictionaries
    yield  # Run the test
    registry._initialize()  # Clean up after test


@pytest.fixture
def basic_flock() -> Flock:
    """Fixture for a basic Flock instance."""
    return Flock(name="test_basic_flock", model="test-model", show_flock_banner=False)


@pytest.fixture
def simple_agent() -> SimpleAgent:
    """Fixture for a simple agent instance."""
    return SimpleAgent(name="agent1", input="query", output="result")


# --- Initialization Tests ---

def test_flock_init_defaults():
    """Test Flock initialization with default values."""
    flock = Flock(show_flock_banner=False)
    assert flock.name.startswith("flock_")
    assert flock.model == "openai/gpt-4o"  # Default from config
    assert flock.description is None
    assert not flock.enable_temporal
    assert not flock.show_flock_banner
    assert flock._agents == {}


def test_flock_init_custom(mocker):
    """Test Flock initialization with custom values."""
    mock_set_temporal = mocker.patch.object(Flock, '_set_temporal_debug_flag')
    mock_ensure_session = mocker.patch.object(Flock, '_ensure_session_id')

    flock = Flock(
        name="custom_flock",
        model="custom_model",
        description="My custom flock",
        enable_temporal=True,
        show_flock_banner=False
    )
    assert flock.name == "custom_flock"
    assert flock.model == "custom_model"
    assert flock.description == "My custom flock"
    assert flock.enable_temporal
    assert not flock.show_flock_banner

    mock_set_temporal.assert_called_once()
    mock_ensure_session.assert_called_once()


def test_flock_init_with_agents(simple_agent):
    """Test Flock initialization with agents passed in the constructor."""
    flock = Flock(agents=[simple_agent], show_flock_banner=False)
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
    agent_no_model = SimpleAgent(
        name="agent_no_model", model=None, input="in", output="out")
    basic_flock.model = "flock-default-model"
    basic_flock.add_agent(agent_no_model)
    assert agent_no_model.model == "flock-default-model"


def test_add_agent_duplicate(basic_flock, simple_agent):
    """Test adding an agent with a name that already exists raises ValueError."""
    basic_flock.add_agent(simple_agent)
    new_agent_same_name = SimpleAgent(
        name="agent1", input="query2", output="result2")

    with pytest.raises(ValueError, match="Agent with this name already exists"):
        basic_flock.add_agent(new_agent_same_name)


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
    mock_local_exec = mocker.patch(
        'flock.core.flock.run_local_workflow', new_callable=AsyncMock)
    mock_temporal_exec = mocker.patch(
        'flock.core.flock.run_temporal_workflow', new_callable=AsyncMock)
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
    assert call_args[1] == "agent1"  # start_agent_name
    assert call_args[2] == input_data  # run_input
    assert call_args[4] is True  # local_debug flag for initialize_context
    assert call_args[5] == basic_flock.model  # model


@pytest.mark.asyncio
async def test_run_async_temporal_delegation(basic_flock, simple_agent, mocker):
    """Test run_async delegates to temporal executor when enable_temporal is True."""
    basic_flock.enable_temporal = True
    basic_flock.add_agent(simple_agent)
    mock_local_exec = mocker.patch(
        'flock.core.flock.run_local_workflow', new_callable=AsyncMock)
    mock_temporal_exec = mocker.patch(
        'flock.core.flock.run_temporal_workflow', new_callable=AsyncMock)
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
    assert call_args[4] is False  # local_debug flag for initialize_context


@pytest.mark.asyncio
async def test_run_async_no_start_agent_single_agent(basic_flock, simple_agent):
    """Test run_async uses the only agent if none is specified."""
    basic_flock.add_agent(simple_agent)
    basic_flock.enable_temporal = False  # Use local for simplicity
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
async def test_run_async_agent_not_found_in_registry(basic_flock, mocker):
    """Test run_async raises error if start agent not found locally or in registry."""
    mocker.patch.object(FlockRegistry, 'get_agent', return_value=None)
    with pytest.raises(ValueError, match="Start agent 'non_existent_agent' not found locally or in registry"):
        await basic_flock.run_async(start_agent="non_existent_agent", input={"query": "test"})


@pytest.mark.asyncio
async def test_run_async_result_boxing(basic_flock, simple_agent, mocker):
    """Test the box_result parameter."""
    basic_flock.enable_temporal = False
    basic_flock.add_agent(simple_agent)
    mock_exec = mocker.patch(
        'flock.core.flock.run_local_workflow', new_callable=AsyncMock)
    raw_result = {"final_output": "local_result"}
    mock_exec.return_value = raw_result

    # Test with boxing (default)
    boxed_result = await basic_flock.run_async(start_agent="agent1", input={}, box_result=True)
    from box import Box  # Import locally for test
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
    mock_run_async = mocker.patch(
        'flock.core.flock.Flock.run_async', new_callable=AsyncMock)
    mock_run_async.return_value = {"result": "async_ran"}

    # Mock the asyncio module functions
    mock_loop = MagicMock()
    mock_get_loop = mocker.patch(
        'asyncio.get_running_loop', side_effect=RuntimeError)
    mock_new_loop = mocker.patch(
        'asyncio.new_event_loop', return_value=mock_loop)
    mock_set_loop = mocker.patch('asyncio.set_event_loop')
    mock_get_event_loop = mocker.patch(
        'asyncio.get_event_loop', return_value=mock_loop)

    # Configure the loop for the "not running" branch
    mock_loop.is_running.return_value = False
    mock_loop.run_until_complete.return_value = {"result": "async_ran"}

    # Call the synchronous run method
    sync_result = basic_flock.run(
        start_agent="agent1", input={"query": "sync_test"})

    # Assert everything was called correctly
    mock_get_loop.assert_called_once()
    mock_new_loop.assert_called_once()
    mock_set_loop.assert_called_once_with(mock_loop)
    mock_get_event_loop.assert_called_once()
    mock_loop.is_running.assert_called_once()
    mock_loop.run_until_complete.assert_called_once()

    # Assert the result is correct
    assert sync_result == {"result": "async_ran"}


# --- Serialization Delegation Tests ---

def test_to_dict_delegates_to_serializer(basic_flock, mocker):
    """Verify Flock.to_dict calls FlockSerializer.serialize."""
    mock_serializer_serialize = mocker.patch(
        'flock.core.serialization.flock_serializer.FlockSerializer.serialize')
    mock_serializer_serialize.return_value = {"serialized": "data"}

    result = basic_flock.to_dict(path_type="relative")

    mock_serializer_serialize.assert_called_once_with(
        basic_flock, path_type="relative")
    assert result == {"serialized": "data"}


def test_from_dict_delegates_to_serializer(mocker):
    """Verify Flock.from_dict calls FlockSerializer.deserialize."""
    mock_flock_instance = Flock(
        name="deserialized", show_flock_banner=False)
    mock_serializer_deserialize = mocker.patch(
        'flock.core.serialization.flock_serializer.FlockSerializer.deserialize')
    mock_serializer_deserialize.return_value = mock_flock_instance
    input_data = {"name": "deserialized", "agents": {}}

    result = Flock.from_dict(input_data)

    mock_serializer_deserialize.assert_called_once_with(Flock, input_data)
    assert result is mock_flock_instance

# --- Static Loader Delegation Test ---


def test_load_from_file_delegates_to_loader(mocker):
    """Verify Flock.load_from_file calls the loader function."""
    mock_loader_func = mocker.patch(
        'flock.core.util.loader.load_flock_from_file')
    mock_flock_instance = Flock(
        name="loaded_from_file", show_flock_banner=False)
    mock_loader_func.return_value = mock_flock_instance
    file_path = "dummy/path/flock.yaml"

    result = Flock.load_from_file(file_path)

    mock_loader_func.assert_called_once_with(file_path)
    assert result is mock_flock_instance

# --- Temporal Config Tests (Mocking run_temporal_workflow) ---


@pytest.mark.asyncio
async def test_run_async_temporal_uses_workflow_config(simple_agent, mocker):
    """Verify run_async passes correct workflow config options to the temporal executor."""
    mock_temporal_exec = mocker.patch(
        'flock.core.flock.run_temporal_workflow', new_callable=AsyncMock)
    mock_init_context = mocker.patch('flock.core.flock.initialize_context')
    mock_temporal_exec.return_value = {"result": "temporal_config_test"}

    # 1. Define specific Temporal Workflow Config
    retry_config = TemporalRetryPolicyConfig(maximum_attempts=5)
    workflow_config = TemporalWorkflowConfig(
        task_queue="config-test-queue",
        workflow_execution_timeout=timedelta(minutes=15),
        workflow_run_timeout=timedelta(minutes=5),
        default_activity_retry_policy=retry_config
    )

    # 2. Create Flock with this config
    flock_with_config = Flock(
        name="flock_with_temporal_cfg",
        enable_temporal=True,
        temporal_config=workflow_config,
        agents=[simple_agent],  # Add agent directly
        show_flock_banner=False
    )

    input_data = {"query": "test"}
    # 3. Run the flock
    await flock_with_config.run_async(start_agent="agent1", input=input_data, box_result=False)

    # 4. Assert run_temporal_workflow was called correctly
    mock_temporal_exec.assert_awaited_once()
    call_args, call_kwargs = mock_temporal_exec.call_args

    # Check positional arguments passed to run_temporal_workflow
    assert len(call_args) == 2  # Should be (flock_instance, context)
    assert call_args[0] is flock_with_config  # First arg is the Flock instance
    assert isinstance(call_args[1], FlockContext)  # Second arg is the context

    # Check keyword arguments passed to run_temporal_workflow
    # Assert that box_result is False and memo is its default (None)
    assert call_kwargs == {'box_result': False, 'memo': None}

    # We need to mock deeper (start_workflow) to check queue/timeouts,
    # but we *can* check that the config is correctly stored on the Flock instance passed.
    passed_flock_instance = call_args[0]
    assert passed_flock_instance.temporal_config is workflow_config


@pytest.mark.asyncio
async def test_run_async_temporal_passes_memo(basic_flock, simple_agent, mocker):
    """Verify run_async passes the memo argument to the temporal executor."""
    basic_flock.enable_temporal = True
    basic_flock.add_agent(simple_agent)
    # Patch where it's called from (in the flock module)
    mock_temporal_exec = mocker.patch(
        'flock.core.flock.run_temporal_workflow', new_callable=AsyncMock)
    mock_init_context = mocker.patch(
        'flock.core.flock.initialize_context')  # Keep this mock
    mock_temporal_exec.return_value = {"result": "memo_test"}

    memo_data = {"user": "test_user", "run": 123}
    input_data = {"query": "test"}

    # Call run_async only ONCE
    await basic_flock.run_async(
        start_agent="agent1",
        input=input_data,
        memo=memo_data,  # Pass memo here
        box_result=False
    )

    # Assert the single mock was called correctly
    mock_temporal_exec.assert_awaited_once_with(
        basic_flock,
        mocker.ANY,  # Context object (check type separately if needed)
        box_result=False,
        memo=memo_data  # Assert memo is passed as kwarg
    )
    # Verify context was initialized
    mock_init_context.assert_called_once()


@pytest.mark.asyncio
async def test_run_async_temporal_no_in_process_worker(basic_flock, simple_agent, mocker):
    """Test that the in-process worker is NOT started if flag is False."""
    # Mock the executor and the setup_worker function it calls
    mock_temporal_exec = mocker.patch(
        'flock.core.flock.run_temporal_workflow', new_callable=AsyncMock)
    # Patch setup_worker in executor
    mock_setup_worker = mocker.patch(
        'flock.core.execution.temporal_executor.setup_worker')
    # To check if worker.run() task is created
    mock_create_task = mocker.patch('asyncio.create_task')

    # Configure Flock to disable in-process worker
    basic_flock.enable_temporal = True
    basic_flock.temporal_start_in_process_worker = False
    basic_flock.add_agent(simple_agent)

    # Mock the return value of the executor itself (since setup_worker won't be called to run it)
    # Need to actually call the real executor but mock deeper dependencies

    # --- Let's adjust the mocking strategy ---
    # We need to call the *real* run_temporal_workflow, but mock its internal call to setup_worker
    # So, don't mock run_temporal_workflow itself. Patch setup_worker and start_workflow.

    # Use wraps if needed, but let's patch deeper
    mocker.patch('flock.core.flock.run_temporal_workflow',
                 wraps=run_temporal_workflow)

    mock_setup_worker = mocker.patch(
        'flock.core.execution.temporal_executor.setup_worker', new_callable=AsyncMock)
    # Mock the client and start_workflow to prevent actual Temporal calls
    mock_client = MagicMock()
    mock_handle = MagicMock()
    mock_handle.result = AsyncMock(return_value={"result": "no_worker_test"})
    mock_client.start_workflow = AsyncMock(return_value=mock_handle)
    mocker.patch('flock.core.execution.temporal_executor.create_temporal_client',
                 new_callable=AsyncMock, return_value=mock_client)

    # Reconfigure Flock
    flock_no_worker = Flock(
        name="flock_no_worker",
        enable_temporal=True,
        temporal_start_in_process_worker=False,  # Key setting
        agents=[simple_agent],
        show_flock_banner=False
    )

    # Run
    await flock_no_worker.run_async(start_agent="agent1", input={"query": "test"}, box_result=False)

    # Assert: setup_worker should NOT have been called
    mock_setup_worker.assert_not_awaited()
    # Assert: start_workflow WAS called (the workflow execution should still be attempted)
    mock_client.start_workflow.assert_awaited_once()

# --- Serialization/Dict Tests (Placeholders - Add to serialization tests) ---

# TODO: Add tests in tests/serialization/ to verify TemporalWorkflowConfig
#       and TemporalActivityConfig are correctly handled by Flock.to_dict() / from_dict()
#       and FlockAgent.to_dict() / from_dict().
# Tests added to tests/serialization/test_flock_serializer.py


# --- Other Tests (Keep existing tests like boxing, sync wrapper etc.) ---
