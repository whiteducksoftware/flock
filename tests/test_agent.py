import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import cloudpickle
import msgpack
from temporalio.client import Client

from flock.core.flock_agent import FlockAgent, AgentConfig
from flock.core.context.context import FlockContext

class ConcreteAgent(FlockAgent):
    """Test implementation of abstract Agent class"""
    async def run(self, context: FlockContext) -> dict:
        return {"test": "success"}
    async def run_temporal(self, context: FlockContext) -> dict:
        return {"test": "temporal_success"}

@pytest.fixture
def agent():
    return ConcreteAgent(
        name="test_agent",
        model="test_model",
        description="test description",
        hand_off=["next_agent"],
        termination="stop"
    )

@pytest.fixture
def context():
    return FlockContext(
        state={"init_input": "test input"},
        history=[],
        agent_definitions={},
    )

class TestAgent:
    def test_initialization(self, agent):
        assert agent.name == "test_agent"
        assert agent.model == "test_model"
        assert agent.description == "test description"
        assert agent.hand_off == ["next_agent"]
        assert agent.termination == "stop"

    def test_initialization_with_callable_description(self):
        def get_description():
            return "dynamic description"
            
        agent = ConcreteAgent(
            name="test",
            description=get_description
        )
        assert callable(agent.description)

    def test_initialization_with_callable_handoff(self):
        def next_agent(context):
            return "dynamic_next"
            
        agent = ConcreteAgent(
            name="test",
            hand_off=[next_agent]
        )
        assert callable(agent.hand_off[0])

    @pytest.mark.asyncio
    async def test_run_local(self, agent, context):
        result = await agent.run(context)
        assert result == {"test": "success"}

    @pytest.mark.asyncio
    async def test_run_temporal(self, agent, context):
        # Mock Temporal client and activity
        with patch('temporalio.client.Client.connect') as mock_connect:
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            with patch('flock.workflow.temporal_setup.run_activity') as mock_run:
                mock_run.return_value = {"test": "temporal_success"}
                
                result = await agent.run_temporal(context)
                
                assert result == {"test": "temporal_success"}
                mock_connect.assert_called_once_with("localhost:7233", namespace="default")

    @pytest.mark.asyncio
    async def test_lifecycle_hooks(self, agent, context):
        # Override hooks for testing
        initialize_called = False
        terminate_called = False
        
        async def test_initialize(self, ctx):
            nonlocal initialize_called
            initialize_called = True
            
        async def test_terminate(self, ctx):
            nonlocal terminate_called
            terminate_called = True
            
        agent.initialize = test_initialize.__get__(agent)
        agent.terminate = test_terminate.__get__(agent)
        
        await agent.run_temporal(context)
        
        assert initialize_called
        assert terminate_called

    def test_serialization_to_dict(self, agent):
        data = agent.to_dict()
        
        assert isinstance(data, dict)
        assert data["name"] == "test_agent"
        assert data["model"] == "test_model"
        
        # Test callable serialization
        def test_func():
            return "test"
            
        agent.hand_off = [test_func]
        data = agent.to_dict()
        assert isinstance(data["hand_off"][0], str)  # Should be serialized to hex string

    def test_deserialization_from_dict(self, agent):
        data = agent.to_dict()
        new_agent = ConcreteAgent.from_dict(data)
        
        assert new_agent.name == agent.name
        assert new_agent.model == agent.model
        
        # Test callable deserialization
        def test_func():
            return "test"
            
        agent.hand_off = [test_func]
        data = agent.to_dict()
        new_agent = ConcreteAgent.from_dict(data)
        assert callable(new_agent.hand_off[0])

    @pytest.mark.asyncio
    async def test_error_handling(self, agent, context):
        # Test handling of Temporal connection error
        with patch('temporalio.client.Client.connect', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception) as exc_info:
                await agent.run_temporal(context)
            assert str(exc_info.value) == "Connection failed"

    def test_config_validation(self):
        # Test valid config
        config = AgentConfig(save_to_file=True, data_type="json")
        assert config.save_to_file == True
        assert config.data_type == "json"
        
        # Test invalid data_type
        with pytest.raises(ValueError):
            AgentConfig(data_type="invalid")

    @pytest.mark.asyncio
    async def test_context_interaction(self, agent, context):
        # Test agent interaction with context
        context.set_variable("test_key", "test_value")
        context.record("test_agent", {"input": "test"}, {"output": "success"})
        
        result = await agent.run(context)
        
        assert context.get_variable("test_key") == "test_value"
        assert len(context.history) == 1
        assert context.history[0].agent == "test_agent"

    def test_cloudpickle_serialization(self, agent):
        # Test full cloudpickle serialization
        pickled = cloudpickle.dumps(agent)
        unpickled = cloudpickle.loads(pickled)
        
        assert unpickled.name == agent.name
        assert unpickled.model == agent.model

    def test_msgpack_serialization(self, agent):
        # Test msgpack serialization
        packed = msgpack.packb(agent.to_dict())
        unpacked = ConcreteAgent.from_dict(msgpack.unpackb(packed))
        
        assert unpacked.name == agent.name
        assert unpacked.model == agent.model

    @pytest.mark.asyncio
    async def test_multiple_handoffs(self, agent, context):
        def next_agent1(ctx):
            return "agent1"
            
        def next_agent2(ctx):
            return "agent2"
            
        agent.hand_off = [next_agent1, next_agent2]
        
        # Run agent and verify both handoffs are preserved
        result = await agent.run_temporal(context)
        new_agent = ConcreteAgent.from_dict(agent.to_dict())
        
        assert len(new_agent.hand_off) == 2
        assert all(callable(h) for h in new_agent.hand_off)