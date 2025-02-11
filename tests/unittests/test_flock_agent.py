# test_flock_agent.py

import pytest
import asyncio
import cloudpickle
from typing import Any
from flock.core.flock_agent import FlockAgent, FlockAgentConfig
from flock.core.context.context import FlockContext

# ------------------------------------------------------------------------------
# Dummy tool function for testing
# ------------------------------------------------------------------------------
def dummy_tool(x: int) -> int:
    """A simple dummy tool that doubles its input."""
    return x * 2

# ------------------------------------------------------------------------------
# Dummy concrete subclass of FlockAgent for testing.
# ------------------------------------------------------------------------------
class DummyAgent(FlockAgent):
    name: str = "dummy_agent"
    model: str = "dummy_model"
    description: str = "A dummy agent for testing."
    # Declare input and output using a descriptive string.
    input: str = "x: int | Input integer"
    output: str = "result: int | Doubled integer"
    tools: list = [dummy_tool]
    use_cache: bool = False
    hand_off: None = None
    termination: None = None
    config: FlockAgentConfig = FlockAgentConfig()

    async def initialize(self, inputs: dict[str, Any]) -> None:
        # No initialization needed for testing.
        pass

    async def terminate(self, inputs: dict[str, Any], result: dict[str, Any]) -> None:
        # No termination logic.
        pass

    async def on_error(self, error: Exception, inputs: dict[str, Any]) -> None:
        # No error handling.
        pass

    async def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        For testing, simply return a dictionary that doubles the value of 'x'.
        """
        x = inputs.get("x", 0)
        return {"result": x * 2, "x": x}

# ------------------------------------------------------------------------------
# Tests for FlockAgent functionality
# ------------------------------------------------------------------------------

def test_to_dict_from_dict_roundtrip():
    """
    Test that a DummyAgent can be serialized to a dict and then reconstructed,
    with callable fields (like tools) converted back to callables.
    """
    agent = DummyAgent()
    agent_dict = agent.to_dict()

    # In the serialized dictionary, callable objects should be serialized as hex strings.
    # Verify that the tools list contains strings.
    assert isinstance(agent_dict["tools"], list)
    for tool in agent_dict["tools"]:
        assert isinstance(tool, str)

    # Reconstruct the agent from the dictionary.
    new_agent = DummyAgent.from_dict(agent_dict)

    # Check that key fields are equal.
    assert new_agent.name == agent.name
    assert new_agent.model == agent.model
    assert new_agent.input == agent.input
    assert new_agent.output == agent.output

    # Check that the tools list has been restored to callable objects.
    for tool in new_agent.tools:
        assert callable(tool)
    # Optionally, test that the tool works.
    assert new_agent.tools[0](3) == dummy_tool(3)  # should equal 6



@pytest.mark.asyncio
async def test_evaluate():
    """
    Test that the DummyAgent's evaluate method returns the expected result.
    For an input x, it should double x.
    """
    agent = DummyAgent()
    inputs = {"x": 5}
    result = await agent.evaluate(inputs)
    assert result == {"result": 10, "x": 5}

def test_build_clean_signature():
    """
    Test the prompt parser mixin functionality inherited by FlockAgent.
    This uses the protected method _build_clean_signature from PromptParserMixin.
    """
    agent = DummyAgent()
    # Overwrite input and output for clarity.
    agent.input = "x: int | Input integer"
    agent.output = "result: int | Doubled integer"

    # Call the helper (note: this is a protected method, so in real usage you wouldn't call it directly)
    clean_input = agent._build_clean_signature(agent.input)
    clean_output = agent._build_clean_signature(agent.output)
    # Expected outputs are the strings before the pipe.
    assert clean_input == "x: int"
    assert clean_output == "result: int"

# Optionally, you could also test the create_dspy_signature_class method.
# However, if the dspy library is not available or if you prefer not to depend on it in tests,
# you may choose to monkey-patch it. For example:

# ------------------------------------------------------------------------------
# Test: create_dspy_signature_class
# ------------------------------------------------------------------------------
def test_create_dspy_signature_class(monkeypatch):
    """
    Test that the create_dspy_signature_class method returns a dynamic class
    with the expected __doc__ and annotations.
    
    We patch the method on the class level.
    """
    agent = DummyAgent()

    # Define a dummy signature class to simulate dspy.Signature.
    class DummySignature:
        pass

    # Define a dummy create function that returns a dynamic class.
    def dummy_create_signature(self, name, description, fields_spec):
        # Return a new type with __doc__ set to the provided description and empty annotations.
        return type("DummySignature_" + name, (DummySignature,), {"__doc__": description, "__annotations__": {}})

    # Patch the class attribute on DummyAgent.
    monkeypatch.setattr(DummyAgent, "create_dspy_signature_class", dummy_create_signature)
    # Call the method.
    signature_class = agent.create_dspy_signature_class(agent.name, agent.description, f"{agent.input} -> {agent.output}")
    # Check that the signature_class has the expected __doc__.
    assert signature_class.__doc__ == agent.description
    # Also check that __annotations__ is an empty dict.
    assert signature_class.__annotations__ == {}
