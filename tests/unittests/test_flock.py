# test_flock.py

import os
from unittest.mock import AsyncMock, patch

import pytest
from rich.prompt import Prompt

from flock.core.context.context import FlockContext
from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent

# ------------------------------------------------------------------------------
# Dummy agent implementation for testing.
# ------------------------------------------------------------------------------

class DummyFlockAgent(FlockAgent):
    async def evaluate(self, inputs: dict) -> dict:
        # For testing purposes, simply return a dict that indicates evaluation occurred.
        return {"result": "success", "inputs": inputs}

    def to_dict(self) -> dict:
        return {"name": self.name, "input": self.input, "model": self.model}

    @classmethod
    def from_dict(cls, data: dict) -> "DummyFlockAgent":
        agent = cls(name=data.get("name", "dummy_agent"))
        agent.input = data.get("input", "")
        agent.model = data.get("model", "dummy_model")
        return agent

# ------------------------------------------------------------------------------
# Pytest fixtures
# ------------------------------------------------------------------------------

@pytest.fixture
def dummy_agent():
    agent = DummyFlockAgent(name="test_agent")
    # Let model be None so that Flock.add_agent will set it to Flock.model.
    agent.model = None
    agent.tools = None
    # Use a field descriptor for input so that top_level_to_keys returns ["required_input"].
    agent.input = "query: str"
    return agent

@pytest.fixture
def flock_instance():
    return Flock(model="test_model", local_debug=True, enable_logging=True)


# ------------------------------------------------------------------------------
# Test Class for Flock
# ------------------------------------------------------------------------------

class TestFlock:
    def test_init_default_values(self):
        """Test initialization with default values."""
        f = Flock()
        assert f.model == "openai/gpt-4o"
        assert not f.local_debug
        assert isinstance(f.context, FlockContext)
        assert isinstance(f.agents, dict)
        # When local_debug is False, LOCAL_DEBUG should not be set.
        assert "LOCAL_DEBUG" not in os.environ

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        f = Flock(model="custom_model", local_debug=True, enable_logging=True)
        assert f.model == "custom_model"
        assert f.local_debug
        # When local_debug is True, LOCAL_DEBUG is set.
        assert os.environ.get("LOCAL_DEBUG") == "1"

    def test_add_agent_new(self, flock_instance, dummy_agent):
        """Test adding a new agent."""
        result = flock_instance.add_agent(dummy_agent)
        assert result == dummy_agent
        assert dummy_agent.name in flock_instance.agents
        # Since agent.model was None, it should be updated to Flock.model.
        assert dummy_agent.model == flock_instance.model

    def test_add_agent_existing(self, flock_instance, dummy_agent):
        """Test adding an agent that already exists."""
        flock_instance.agents[dummy_agent.name] = dummy_agent
        result = flock_instance.add_agent(dummy_agent)
        assert result == dummy_agent
        assert len(flock_instance.agents) == 1

    def test_add_agent_with_tools(self, flock_instance):
        """Test that an agent with tools registers its tools."""
        def dummy_tool():
            pass

        agent = DummyFlockAgent(name="tool_agent")
        agent.model = None
        agent.tools = [dummy_tool]
        agent.input = ""
        flock_instance.add_agent(agent)
        assert agent.name in flock_instance.agents
        # Check that dummy_tool was registered in the registry.
        registered_tools = [tool_name for tool_name, _ in flock_instance.registry._tools]
        assert dummy_tool.__name__ in registered_tools

    def test_add_tool(self, flock_instance):
        """Test the add_tool function."""
        def sample_tool():
            pass
        flock_instance.add_tool("sample_tool", sample_tool)
        registered_tools = [tool_name for tool_name, _ in flock_instance.registry._tools]
        assert "sample_tool" in registered_tools


    @pytest.mark.asyncio
    async def test_run_async_with_string_agent(self, flock_instance, dummy_agent):
        """Test running an agent when passed by name."""
   
        flock_instance.registry.register_agent(dummy_agent)

        dummy_agent.input = "query: str"
        
        # Patch the run_local_workflow as it is referenced in flock.core.flock.
        with patch("flock.core.flock.run_local_workflow", new_callable=AsyncMock) as mock_run, \
             patch("flock.core.flock.tracer") as mock_tracer:
            mock_run.return_value = {"result": "success"}

            mock_span = AsyncMock()
            mock_tracer.start_as_current_span.return_value.__aenter__.return_value = mock_span


            with patch.object(Prompt, "ask", return_value="dummy_value"):
                result = await flock_instance.run_async(dummy_agent.name)
            

            assert dict(result) == {"result": "success"}

    @pytest.mark.asyncio
    async def test_run_async_with_agent_instance(self, flock_instance, dummy_agent):
        """Test running an agent when passed as an instance."""

        flock_instance.registry.register_agent(dummy_agent)

        dummy_agent.input = ""

        with patch("flock.core.flock.run_local_workflow", new_callable=AsyncMock) as mock_run, \
             patch("flock.core.flock.tracer") as mock_tracer:
            mock_run.return_value = {"result": "success"}
            mock_span = AsyncMock()
            mock_tracer.start_as_current_span.return_value.__aenter__.return_value = mock_span

            result = await flock_instance.run_async(dummy_agent)

        assert dict(result) == {"result": "success"}

    @pytest.mark.asyncio
    async def test_run_async_with_context(self, flock_instance, dummy_agent):
        """Test running an agent with a provided custom context."""
        custom_context = FlockContext()

        dummy_agent.input = ""

        flock_instance.registry.register_agent(dummy_agent)
        
        with patch("flock.core.execution.local_executor.run_local_workflow", new_callable=AsyncMock) as mock_run, \
             patch("flock.core.flock.tracer") as mock_tracer:
            mock_run.return_value = {"result": "success"}
            mock_span = AsyncMock()
            mock_tracer.start_as_current_span.return_value.__aenter__.return_value = mock_span
    
            result = await flock_instance.run_async(dummy_agent, context=custom_context)

        assert dict(result) == {'inputs': {}, 'result': 'success'}

    @pytest.mark.asyncio
    async def test_run_async_with_input_prompt(self, flock_instance, dummy_agent):
        """Test that run_async prompts for missing input keys."""

        with patch("flock.core.flock.run_local_workflow", new_callable=AsyncMock) as mock_run, \
             patch("flock.core.flock.tracer") as mock_tracer:

            mock_run.return_value = {"result": "success"}

            mock_span = AsyncMock()
            mock_tracer.start_as_current_span.return_value.__aenter__.return_value = mock_span

            with patch.object(Prompt, "ask", return_value="provided_value"):
                result = await flock_instance.run_async(dummy_agent)
            
            assert dict(result) == {"result": "success"}


    @pytest.mark.asyncio
    async def test_run_async_temporal(self, flock_instance, dummy_agent):
        """Test run_async when local_debug is False (i.e. Temporal mode)."""
        flock_instance.local_debug = False
        dummy_agent.input = ""
        with patch("flock.core.execution.temporal_executor.run_temporal_workflow", new_callable=AsyncMock) as mock_run, \
             patch("flock.core.flock.tracer") as mock_tracer:
            mock_run.return_value = {"result": "success"}
            mock_span = AsyncMock()
            mock_tracer.start_as_current_span.return_value.__aenter__.return_value = mock_span

            result = await flock_instance.run_async(dummy_agent)
            assert dict(result) == {'inputs': {'query': 'dummy_value'}, 'result': 'success'}

    @pytest.mark.asyncio
    async def test_run_async_invalid_agent(self, flock_instance):
        """Test that run_async raises a ValueError for an invalid agent name."""
        with patch("flock.core.flock.tracer") as mock_tracer:
            mock_span = AsyncMock()
            mock_tracer.start_as_current_span.return_value.__aenter__.return_value = mock_span
            with pytest.raises(ValueError):
                await flock_instance.run_async("nonexistent_agent")

    @pytest.mark.asyncio
    async def test_run_async_execution_error(self, flock_instance, dummy_agent):
        """Test that run_async propagates execution errors from the workflow executor."""
        dummy_agent.input = ""
        with patch("flock.core.flock.run_local_workflow", new_callable=AsyncMock) as mock_run, \
             patch("flock.core.flock.tracer") as mock_tracer:
            # Set side_effect directly to an Exception.
            mock_run.side_effect = Exception("Test error")
            mock_span = AsyncMock()
            mock_tracer.start_as_current_span.return_value.__aenter__.return_value = mock_span

            with pytest.raises(Exception) as exc_info:
                await flock_instance.run_async(dummy_agent)
            assert "Test error" in str(exc_info.value)


