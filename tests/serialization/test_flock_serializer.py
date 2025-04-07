# tests/serialization/test_flock_serializer.py
import os
import random
from unittest.mock import patch
import pytest
from typing import List, Literal
from dataclasses import dataclass

from pydantic import BaseModel, Field

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.flock_router import FlockRouter, FlockRouterConfig, HandOffRequest
from flock.core.serialization.flock_serializer import FlockSerializer
from flock.core.flock_registry import FlockRegistry, get_registry, flock_component, flock_tool, flock_type
from flock.core.serialization.serializable import Serializable # Needed for mocks if they inherit

# --- Mock Components for Testing ---
# Ensure these are registered before tests that need them run

@pytest.fixture(autouse=True)
def setup_registry():
    """Fixture to ensure mocks are registered before each test."""
    registry = get_registry()
    registry._initialize() # Start fresh

    # Register Mocks
    registry.register_component(MockEvaluator)
    registry.register_component(MockModule)
    registry.register_component(MockRouter)
    registry.register_callable(sample_tool) # Register by function object
    registry.register_callable(print)       # Register built-in
    registry.register_type(MyCustomData)

    yield # Run test

    registry._initialize() # Clean up


class MockEvalConfig(FlockEvaluatorConfig):
    mock_eval_param: str = "eval_default"

@flock_component # Auto-register is fine too
class MockEvaluator(FlockEvaluator, Serializable):
    config: MockEvalConfig = MockEvalConfig()
    # Add evaluate if needed by agent.run, but not strictly required for serialization test
    async def evaluate(self, agent, inputs, tools): return {"mock_result": "mock"}
    # Need serialization methods if not relying solely on Pydantic model_dump in agent
    def to_dict(self): return {"name": self.name, "config": self.config.model_dump(), "type": "MockEvaluator"}
    @classmethod
    def from_dict(cls, data): return cls(name=data.get("name", "default_eval_name"), config=MockEvalConfig(**data.get("config",{})))


class MockModuleConfig(FlockModuleConfig):
    mock_module_param: bool = True

@flock_component
class MockModule(FlockModule, Serializable):
    config: MockModuleConfig = MockModuleConfig()
    def to_dict(self): return {"name": self.name, "config": self.config.model_dump(), "type": "MockModule"}
    @classmethod
    def from_dict(cls, data): return cls(name=data.get("name", "default_mod_name"), config=MockModuleConfig(**data.get("config",{})))


class MockRouterConfig(FlockRouterConfig):
    next_agent_name: str = "default_next"

@flock_component
class MockRouter(FlockRouter, Serializable):
    config: MockRouterConfig = MockRouterConfig()
    async def route(self, current_agent, result, context): return HandOffRequest(next_agent=self.config.next_agent_name)
    def to_dict(self): return {"name": self.name, "config": self.config.model_dump(), "type": "MockRouter"}
    @classmethod
    def from_dict(cls, data): return cls(name=data.get("name", "default_router_name"), config=MockRouterConfig(**data.get("config",{})))


@flock_tool
def sample_tool(text: str) -> str:
    """A sample registered tool."""
    return text.upper()

@flock_type
class MyCustomData(BaseModel):
    id: int = Field(default_factory=lambda: random.randint(1, 1000000))
    value: str = Field(default_factory=lambda: "random_value")

# --- Fixtures ---
@pytest.fixture
def basic_flock():
    return Flock(name="serial_flock", model="serial_model", description="Serialization test flock", enable_logging=False, show_flock_banner=False)

@pytest.fixture
def flock_with_agents(basic_flock):
    agent1 = FlockAgent(name="a1", input="in", output="out1")
    agent2 = FlockAgent(
        name="a2",
        input="out1", output="data: MyCustomData", # Use custom type
        evaluator=MockEvaluator(name="a2_eval", config=MockEvalConfig(mock_eval_param="a2_eval")),
        modules={"m1": MockModule(name="m1", config=MockModuleConfig(mock_module_param=False))},
        tools=[sample_tool, print],
        handoff_router=MockRouter(name="a2_router", config=MockRouterConfig(next_agent_name="a1"))
    )
    basic_flock.add_agent(agent1)
    basic_flock.add_agent(agent2)
    return basic_flock


# --- Serialization Tests ---

def test_serialize_basic_flock(basic_flock):
    """Test serializing a Flock with no agents or complex components."""
    serialized_data = FlockSerializer.serialize(basic_flock)

    assert serialized_data["name"] == "serial_flock"
    assert serialized_data["model"] == "serial_model"
    assert serialized_data["description"] == "Serialization test flock"
    assert "agents" in serialized_data and serialized_data["agents"] == {}
    assert "types" not in serialized_data # No custom types used
    assert "components" not in serialized_data # No components used
    assert "metadata" in serialized_data
    assert serialized_data["metadata"]["path_type"] == "relative" # Default for serialize

def test_serialize_flock_with_agents(flock_with_agents):
    """Test serializing a Flock with agents and their components."""
    serialized_data = FlockSerializer.serialize(flock_with_agents)

    assert "agents" in serialized_data
    assert "a1" in serialized_data["agents"]
    assert "a2" in serialized_data["agents"]

    # Check agent a2 serialization details
    agent2_data = serialized_data["agents"]["a2"]
    assert agent2_data["name"] == "a2"
    assert agent2_data["input"] == "out1"
    assert agent2_data["output"] == "data: MyCustomData"

    # Check components attached to agent a2
    assert "evaluator" in agent2_data
    assert agent2_data["evaluator"]["type"] == "MockEvaluator"
    assert agent2_data["evaluator"]["config"]["mock_eval_param"] == "a2_eval"

    assert "modules" in agent2_data
    assert "m1" in agent2_data["modules"]
    assert agent2_data["modules"]["m1"]["type"] == "MockModule"
    assert agent2_data["modules"]["m1"]["config"]["mock_module_param"] is False

    assert "tools" in agent2_data
    assert agent2_data["tools"] == ["sample_tool", "print"] # Just names

    assert "handoff_router" in agent2_data
    assert agent2_data["handoff_router"]["type"] == "MockRouter"
    assert agent2_data["handoff_router"]["config"]["next_agent_name"] == "a1"

def test_serialize_includes_types(flock_with_agents):
    """Test that custom types used in agent signatures are included."""
    serialized_data = FlockSerializer.serialize(flock_with_agents)

    assert "types" in serialized_data
    assert "MyCustomData" in serialized_data["types"]
    type_def = serialized_data["types"]["MyCustomData"]
    assert type_def["type"] == "pydantic.BaseModel" # Assuming @flock_type registers it as such
    assert "module_path" in type_def
    assert "schema" in type_def
    assert "id" in type_def["schema"]["properties"]
    assert type_def["schema"]["properties"]["id"]["type"] == "integer"

def test_serialize_includes_components(flock_with_agents):
    """Test that components (evaluators, modules, routers, tools) are included."""
    serialized_data = FlockSerializer.serialize(flock_with_agents)

    assert "components" in serialized_data
    components = serialized_data["components"]

    # Check components from agent a2
    assert "MockEvaluator" in components
    assert components["MockEvaluator"]["type"] == "flock_component"
    assert "file_path" in components["MockEvaluator"] # Path should be present

    assert "MockModule" in components
    assert components["MockModule"]["type"] == "flock_component"

    assert "MockRouter" in components
    assert components["MockRouter"]["type"] == "flock_component"

    # Check tools (callables)
    assert "sample_tool" in components
    assert components["sample_tool"]["type"] == "flock_callable"
    assert "module_path" in components["sample_tool"]
    assert "file_path" in components["sample_tool"]
    assert "description" in components["sample_tool"]

    assert "print" in components # Built-in
    assert components["print"]["type"] == "flock_callable"
    assert components["print"]["module_path"] == "builtins"


def test_serialize_path_type_absolute(flock_with_agents, mocker):
    """Test serialization with absolute path type."""
    # Mock os.path.abspath to ensure we can check its call
    mock_relpath = mocker.patch('os.path.relpath', side_effect=lambda x: f"relative/path/to/{os.path.basename(x)}")
    mocker.patch('inspect.getfile', side_effect=lambda x: f"/abs/path/{x.__name__}.py") # Mock getfile

    serialized_data = FlockSerializer.serialize(flock_with_agents, path_type="absolute")
    components = serialized_data["components"]

    assert "MockEvaluator" in components
    assert components["MockEvaluator"]["file_path"] == "/abs/path/MockEvaluator.py" # Check absolute

    assert "sample_tool" in components
    assert components["sample_tool"]["file_path"] == "/abs/path/sample_tool.py" # Check absolute

    assert mock_relpath.call_count == 0 # Ensure abspath was involved

def test_serialize_path_type_relative(flock_with_agents, mocker):
    """Test serialization with relative path type."""
    # Mock os.path.relpath
    mock_relpath = mocker.patch('os.path.relpath', side_effect=lambda x: f"relative/path/to/{os.path.basename(x)}")
    mocker.patch('inspect.getfile', side_effect=lambda x: f"/abs/path/{x.__name__}.py") # Mock getfile

    serialized_data = FlockSerializer.serialize(flock_with_agents, path_type="relative")
    components = serialized_data["components"]

    assert "MockEvaluator" in components
    assert components["MockEvaluator"]["file_path"] == "relative/path/to/MockEvaluator.py"

    assert "sample_tool" in components
    assert components["sample_tool"]["file_path"] == "relative/path/to/sample_tool.py"

    assert mock_relpath.call_count > 0 # Ensure relpath was involved


# --- Deserialization Tests ---

def test_deserialize_basic_flock(basic_flock):
    """Test deserializing a basic Flock from its dictionary representation."""
    serialized_data = FlockSerializer.serialize(basic_flock)
    loaded_flock = FlockSerializer.deserialize(Flock, serialized_data)

    assert isinstance(loaded_flock, Flock)
    assert loaded_flock.name == basic_flock.name
    assert loaded_flock.model == basic_flock.model
    assert loaded_flock.agents == {}

def test_deserialize_flock_with_agents_and_components(flock_with_agents):
    """Test deserializing a complex Flock with agents and components."""
    serialized_data = FlockSerializer.serialize(flock_with_agents)
    loaded_flock = FlockSerializer.deserialize(Flock, serialized_data)

    assert isinstance(loaded_flock, Flock)
    assert len(loaded_flock.agents) == 2
    assert "a1" in loaded_flock.agents
    assert "a2" in loaded_flock.agents

    # Check agent a2 structure after loading
    agent2 = loaded_flock.agents["a2"]
    assert isinstance(agent2, FlockAgent)
    assert isinstance(agent2.evaluator, MockEvaluator)
    assert agent2.evaluator.config.mock_eval_param == "a2_eval"
    assert isinstance(agent2.modules["m1"], MockModule)
    assert agent2.modules["m1"].config.mock_module_param is False
    assert isinstance(agent2.handoff_router, MockRouter)
    assert agent2.handoff_router.config.next_agent_name == "a1"
    assert len(agent2.tools) == 2
    assert agent2.tools[0] is sample_tool
    assert agent2.tools[1] is print

def test_deserialize_registers_components_and_types(flock_with_agents):
    """Verify that deserialization registers the necessary components and types."""
    serialized_data = FlockSerializer.serialize(flock_with_agents)

    # Create a new clean registry to simulate loading in a fresh environment
    new_registry = FlockRegistry()
    new_registry._initialize()

    with patch('flock.core.flock_registry.get_registry', return_value=new_registry):
        # Ensure mocks are NOT initially registered in the new registry
        with pytest.raises(KeyError):
            new_registry.get_type("MockEvaluator")
        with pytest.raises(KeyError):
            new_registry.get_callable("sample_tool")

        # Deserialize using the new registry
        loaded_flock = FlockSerializer.deserialize(Flock, serialized_data)

        # Assert that components and types ARE NOW registered
        assert new_registry.get_component("MockEvaluator") is MockEvaluator
        assert new_registry.get_callable("sample_tool") is sample_tool
        assert new_registry.get_type("MyCustomData") is MyCustomData
        assert new_registry.get_callable("print") is print # Built-in should be handled

def test_deserialize_missing_component_definition(basic_flock, caplog):
    """Test deserialization when a component's definition is missing."""
    # Create agent data referencing a non-existent component type
    agent_data = {
        "name": "missing_comp_agent",
        "input": "in",
        "output": "out",
        "evaluator": {
            "type": "NonExistentEvaluator", # This type is not registered
            "name": "bad_eval",
            "config": {}
        }
    }
    flock_data = FlockSerializer.serialize(basic_flock)
    flock_data["agents"] = {"missing_comp_agent": agent_data}
    # Manually remove component definition if it snuck in somehow (it shouldn't)
    flock_data.pop("components", None)

    # Act
    loaded_flock = FlockSerializer.deserialize(Flock, flock_data)

    # Assert
    assert "missing_comp_agent" in loaded_flock.agents
    agent = loaded_flock.agents["missing_comp_agent"]
    # The agent should be created, but the component should be None or raise during use
    assert agent.evaluator is None
