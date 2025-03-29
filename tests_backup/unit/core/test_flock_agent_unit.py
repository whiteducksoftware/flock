# tests/unit/core/test_flock_agent_unit.py
import pytest
import asyncio
import cloudpickle
from typing import Any, Dict
from unittest.mock import MagicMock, AsyncMock, patch

from flock.core.flock_agent import FlockAgent
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.flock_router import FlockRouter, FlockRouterConfig
from flock.core.context.context import FlockContext

# --- Test Fixtures ---

@pytest.fixture
def mock_module():
    """Provides a MagicMock instance simulating a FlockModule."""
    module = MagicMock(spec=FlockModule)
    module.name = "mock_module"
    module.config = FlockModuleConfig(enabled=True)
    # Mock async methods
    module.initialize = AsyncMock()
    module.terminate = AsyncMock()
    module.pre_evaluate = AsyncMock(side_effect=lambda agent, inputs, context: inputs) # Pass inputs through
    module.post_evaluate = AsyncMock(side_effect=lambda agent, inputs, result, context: result) # Pass result through
    module.on_error = AsyncMock()
    return module

@pytest.fixture
def mock_evaluator():
    """Provides a MagicMock instance simulating a FlockEvaluator."""
    evaluator = MagicMock(spec=FlockEvaluator)
    evaluator.name = "mock_evaluator"
    evaluator.config = FlockEvaluatorConfig(name="mock_eval_config")
    evaluator.evaluate = AsyncMock(return_value={"eval_result": "mocked"})
    return evaluator

@pytest.fixture
def mock_router():
    """Provides a MagicMock instance simulating a FlockRouter."""
    router = MagicMock(spec=FlockRouter)
    router.name = "mock_router"
    router.config = FlockRouterConfig(name="mock_router_config")
    router.route = AsyncMock(return_value=None) # Default: no handoff
    return router

@pytest.fixture
def dummy_context():
    """Provides a simple FlockContext instance."""
    return FlockContext()

def dummy_tool_func(a: int) -> int:
    """A simple tool function for serialization tests."""
    return a * 2

@pytest.fixture
def basic_agent(mock_evaluator):
    """Provides a basic FlockAgent instance for testing."""
    return FlockAgent(
        name="test_basic_agent",
        model="test_model",
        input="query: str",
        output="response: str",
        evaluator=mock_evaluator # Need an evaluator for run_async
    )

@pytest.fixture
def complex_agent(mock_evaluator, mock_router, mock_module):
    """Provides a more complex FlockAgent instance for serialization."""
    agent = FlockAgent(
        name="test_complex_agent",
        model="complex_model",
        description="A complex test agent",
        input="data: dict | Input data",
        output="processed: dict | Processed data",
        tools=[dummy_tool_func],
        use_cache=False,
        evaluator=mock_evaluator,
        handoff_router=mock_router,
    )
    agent.add_module(mock_module)
    return agent

@pytest.fixture
def minimal_serializable_evaluator():
    """A minimal, real, serializable evaluator for testing serialization."""
    class MinimalEvaluator(FlockEvaluator):
        config: FlockEvaluatorConfig = FlockEvaluatorConfig(name="minimal_eval_config")
        async def evaluate(self, agent: Any, inputs: dict[str, Any], tools: list[Any]) -> dict[str, Any]:
            return {"minimal_result": True} # Dummy implementation
    # Return an instance of the concrete class
    return MinimalEvaluator(name="minimal_serializable_evaluator")

@pytest.fixture
def complex_agent_serializable(minimal_serializable_evaluator):
    """Provides a FlockAgent instance suitable for serialization testing.
       Uses a real (but simple) evaluator and None for optional router/modules."""
    agent = FlockAgent(
        name="test_complex_agent_serializable",
        model="complex_model",
        description="A complex test agent for serialization",
        input="data: dict | Input data",
        output="processed: dict | Processed data",
        tools=[dummy_tool_func], # Keep the callable tool
        use_cache=False,
        evaluator=minimal_serializable_evaluator, # Use the real, serializable evaluator
        handoff_router=None, # Use None instead of a mock router
        modules={} # Use an empty dict instead of mock modules
    )
    return agent

# --- Test Cases ---

@pytest.mark.unit
class TestFlockAgentUnit:

    def test_agent_initialization(self, basic_agent):
        """Test basic agent initialization."""
        assert basic_agent.name == "test_basic_agent"
        assert basic_agent.model == "test_model"
        assert basic_agent.input == "query: str"
        assert basic_agent.output == "response: str"
        assert basic_agent.evaluator is not None
        assert basic_agent.modules == {}
        assert basic_agent.tools is None # Default is None if not specified

    def test_module_management(self, basic_agent, mock_module):
        """Test adding, getting, and removing modules."""
        assert not basic_agent.get_enabled_modules()
        basic_agent.add_module(mock_module)
        assert basic_agent.modules == {"mock_module": mock_module}
        assert basic_agent.get_module("mock_module") == mock_module
        assert basic_agent.get_enabled_modules() == [mock_module]

        # Test disabling a module
        mock_module.config.enabled = False
        assert not basic_agent.get_enabled_modules()
        mock_module.config.enabled = True # Reset for other tests

        basic_agent.remove_module("mock_module")
        assert basic_agent.modules == {}
        assert basic_agent.get_module("mock_module") is None
        assert not basic_agent.get_enabled_modules()

    @pytest.mark.asyncio
    async def test_lifecycle_hooks_invocation(self, basic_agent, mock_module, dummy_context):
        """Test that core lifecycle hooks call module hooks."""
        basic_agent.add_module(mock_module)
        basic_agent.context = dummy_context # Assign context for modules
        test_inputs = {"query": "test"}
        test_result = {"response": "test response"}

        # Mock evaluator to return a specific result
        basic_agent.evaluator.evaluate = AsyncMock(return_value=test_result)
        # Run the agent
        await basic_agent.run_async(test_inputs)

        # Verify module hooks were called
        mock_module.initialize.assert_called_once_with(basic_agent, test_inputs, dummy_context)
        mock_module.pre_evaluate.assert_called_once_with(basic_agent, test_inputs, dummy_context)
        mock_module.post_evaluate.assert_called_once_with(basic_agent, test_inputs, test_result, dummy_context)
        mock_module.terminate.assert_called_once_with(basic_agent, test_inputs, test_result, dummy_context)
        mock_module.on_error.assert_not_called()

    @pytest.mark.asyncio
    async def test_lifecycle_on_error(self, basic_agent, mock_module, dummy_context):
        """Test that on_error hook is called when evaluate raises exception."""
        basic_agent.add_module(mock_module)
        basic_agent.context = dummy_context
        test_inputs = {"query": "test"}
        error = ValueError("Evaluation failed")

        # Mock evaluator to raise an error
        basic_agent.evaluator.evaluate = AsyncMock(side_effect=error)

        # Run the agent and expect an exception
        with pytest.raises(ValueError, match="Evaluation failed"):
            await basic_agent.run_async(test_inputs)

        # Verify module hooks
        mock_module.initialize.assert_called_once_with(basic_agent, test_inputs, dummy_context)
        mock_module.pre_evaluate.assert_called_once_with(basic_agent, test_inputs, dummy_context)
        mock_module.post_evaluate.assert_not_called()
        # Verify on_error IS called
        mock_module.on_error.assert_called_once_with(basic_agent, error, test_inputs, dummy_context)
        # Terminate might or might not be called depending on exact error handling flow,
        # let's assume it's NOT called on exception for now. Adjust if needed.
        mock_module.terminate.assert_not_called()

    def test_serialization_deserialization(self, complex_agent_serializable):
        """Test the to_dict and from_dict methods, including callable handling."""
        agent = complex_agent_serializable # Use the modified fixture
        agent_dict = agent.to_dict()

        # Check structure
        assert agent_dict["name"] == "test_complex_agent_serializable"
        assert agent_dict["model"] == "complex_model"
        assert isinstance(agent_dict["tools"], list)
        assert isinstance(agent_dict["tools"][0], str) # Serialized callable
        assert agent_dict["modules"] == {} # Should be empty
        assert isinstance(agent_dict["evaluator"], dict) # Should be a dict rep of MinimalEvaluator
        assert agent_dict["handoff_router"] is None # Should be None

        # Try deserializing
        # Use FlockAgent.from_dict as it handles finding the class
        deserialized_agent = FlockAgent.from_dict(agent_dict)

        # Check basic attributes
        assert deserialized_agent.name == agent.name
        assert deserialized_agent.model == agent.model
        assert deserialized_agent.description == agent.description

        # Check complex attributes were reconstructed
        # The evaluator should be reconstructed as an instance of its class
        assert isinstance(deserialized_agent.evaluator, FlockEvaluator)
        assert deserialized_agent.evaluator.name == "minimal_serializable_evaluator"
        assert deserialized_agent.handoff_router is None

        # Check modules
        assert deserialized_agent.modules == {}

        # Check tools
        assert isinstance(deserialized_agent.tools, list)
        assert len(deserialized_agent.tools) == 1
        assert callable(deserialized_agent.tools[0])

        # Verify the deserialized tool works
        try:
            assert deserialized_agent.tools[0](5) == 10 # dummy_tool_func(5)
        except Exception as e:
            pytest.fail(f"Deserialized tool failed execution: {e}")


    def test_set_model(self, basic_agent, mock_evaluator):
        """Test that set_model updates the agent and its evaluator's config."""
        new_model_name = "new-model-v2"
        basic_agent.set_model(new_model_name)
        assert basic_agent.model == new_model_name
        assert basic_agent.evaluator.config.model == new_model_name

    # TODO: Add tests for resolve_callables if used
    # def test_resolve_callables(self, dummy_context):
    #     def input_func(context): return "dynamic_input: str"
    #     agent = FlockAgent(name="callable_agent", input=input_func, evaluator=MagicMock())
    #     agent.resolve_callables(dummy_context)
    #     assert agent.input == "dynamic_input: str"

    # TODO: Add tests for saving/loading from file using tmp_path fixture
    # def test_save_load_file(self, complex_agent, tmp_path):
    #     file_path = tmp_path / "complex_agent.json"
    #     complex_agent.save_to_file(str(file_path))
    #     assert file_path.exists()
    #
    #     loaded_agent = FlockAgent.load_from_file(str(file_path))
    #     assert loaded_agent.name == complex_agent.name
    #     assert callable(loaded_agent.tools[0])