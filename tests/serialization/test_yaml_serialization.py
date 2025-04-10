# tests/serialization/test_yaml_serialization.py

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

import pytest
import yaml

# --- Core Flock Imports ---
# Assume these are correctly implemented and importable
from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.flock_router import FlockRouter, FlockRouterConfig, HandOffRequest
from flock.core.context.context import FlockContext
from flock.core.serialization.serializable import Serializable

# --- Registry and Decorators ---
from flock.core.flock_registry import (
    flock_component,
    flock_tool,
    flock_type,
    get_registry,
)

# Get registry instance
FlockRegistry = get_registry()

# --- Mock Components for Testing ---

class MockEvalConfig(FlockEvaluatorConfig):
    mock_eval_param: str = "eval_default"

@flock_component # Register this component class
class MockEvaluator(FlockEvaluator, Serializable): # Inherit Serializable
    name: str = "mock_evaluator"
    config: MockEvalConfig = MockEvalConfig()

    # Needed for serialization if not just using Pydantic dump
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "config": self.config.model_dump(), "type": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockEvaluator":
        config = MockEvalConfig(**data.get("config", {}))
        return cls(name=data.get("name", "mock_evaluator"), config=config)

    async def evaluate(self, agent: Any, inputs: Dict[str, Any], tools: List[Any]) -> Dict[str, Any]:
        return {"mock_result": f"evaluated {inputs.get('test_input', '')} with {self.config.mock_eval_param}"}

class MockModuleConfig(FlockModuleConfig):
    mock_module_param: bool = True

@flock_component # Register this component class
class MockModule(FlockModule, Serializable): # Inherit Serializable
    config: MockModuleConfig = MockModuleConfig()

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "config": self.config.model_dump(), "type": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockModule":
        config = MockModuleConfig(**data.get("config", {}))
        return cls(name=data.get("name", "mock_module"), config=config)

    # Mock lifecycle methods if needed for testing interactions
    async def post_evaluate(self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any], context: FlockContext | None = None) -> dict[str, Any]:
        result["mock_module_added"] = self.config.mock_module_param
        return result

class MockRouterConfig(FlockRouterConfig):
    next_agent_name: str = "default_next"

@flock_component # Register this component class
class MockRouter(FlockRouter, Serializable): # Inherit Serializable
    config: MockRouterConfig = MockRouterConfig()

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "config": self.config.model_dump(), "type": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockRouter":
        config = MockRouterConfig(**data.get("config", {}))
        return cls(name=data.get("name", "mock_router"), config=config)

    async def route(self, current_agent: Any, result: Dict[str, Any], context: FlockContext) -> HandOffRequest:
        return HandOffRequest(next_agent=self.config.next_agent_name)

# --- Sample Tool Function ---
@flock_tool # Register this tool function
def sample_tool(text: str, capitalize: bool = True) -> str:
    """A sample registered tool."""
    return text.upper() if capitalize else text.lower()

# --- Sample Custom Type ---
@flock_type # Register this custom type
@dataclass
class MyCustomData:
    id: int
    value: str
    tags: List[str] | None = None

# --- Test Class ---

class TestFlockYAMLSerialization:

    def test_agent_serialization_basic(self, tmp_path):
        """Test serializing and deserializing a basic FlockAgent."""
        agent = FlockAgent(
            name="basic_agent",
            model="test_model",
            description="A basic agent",
            input="query: str",
            output="answer: str"
        )
        file_path = tmp_path / "basic_agent.yaml"

        # Act
        agent.to_yaml_file(file_path)
        loaded_agent = FlockAgent.from_yaml_file(file_path)

        # Assert
        assert isinstance(loaded_agent, FlockAgent)
        assert loaded_agent.name == agent.name
        assert loaded_agent.model == agent.model
        assert loaded_agent.description == agent.description
        assert loaded_agent.input == agent.input
        assert loaded_agent.output == agent.output
        assert loaded_agent.evaluator is None # Default should be None before factory
        assert loaded_agent.modules == {}
        assert loaded_agent.handoff_router is None
        assert loaded_agent.tools == []

    def test_agent_serialization_with_components(self, tmp_path):
        """Test agent serialization with evaluator, module, and router."""
        evaluator = MockEvaluator(name="mock_evaluator", config=MockEvalConfig(mock_eval_param="test_eval"))
        router = MockRouter(name="mock_router", config=MockRouterConfig(next_agent_name="agent_two"))
        module = MockModule(name="extra_module", config=MockModuleConfig(mock_module_param=False))

        agent = FlockAgent(
            name="component_agent",
            model="test_model_comp",
            evaluator=evaluator,
            handoff_router=router,
            modules={"extra_module": module}
        )
        file_path = tmp_path / "component_agent.yaml"

        # Act
        agent.to_yaml_file(file_path)
        loaded_agent = FlockAgent.from_yaml_file(file_path)

        # Assert
        assert loaded_agent.name == "component_agent"
        assert isinstance(loaded_agent.evaluator, MockEvaluator)
        assert loaded_agent.evaluator.name == "mock_evaluator" # Default name from mock
        assert loaded_agent.evaluator.config.mock_eval_param == "test_eval"

        assert isinstance(loaded_agent.handoff_router, MockRouter)
        assert loaded_agent.handoff_router.name == "mock_router" # Default name from mock
        assert loaded_agent.handoff_router.config.next_agent_name == "agent_two"

        assert "extra_module" in loaded_agent.modules
        assert isinstance(loaded_agent.modules["extra_module"], MockModule)
        assert loaded_agent.modules["extra_module"].config.mock_module_param is False

    def test_agent_serialization_with_tools(self, tmp_path):
        """Test agent serialization with callable tools."""
        agent = FlockAgent(
            name="tool_agent",
            model="tool_model",
            tools=[sample_tool, print] # Include a built-in for testing path gen
        )
        file_path = tmp_path / "tool_agent.yaml"

        # Act
        agent.to_yaml_file(file_path)
        # Optional: Inspect YAML for callable refs
        yaml_content = file_path.read_text()
        assert "sample_tool" in yaml_content
        assert "print" in yaml_content # Check built-in

        loaded_agent = FlockAgent.from_yaml_file(file_path)

        # Assert
        assert loaded_agent.name == "tool_agent"
        assert loaded_agent.tools is not None
        assert len(loaded_agent.tools) == 2
        assert loaded_agent.tools[0] is sample_tool # Check identity after registry lookup
        assert loaded_agent.tools[1] is print       # Check identity for built-in
        # Test calling the loaded tool
        assert loaded_agent.tools[0]("hello") == "HELLO"

    def test_agent_serialization_with_custom_type(self, tmp_path):
        """Test agent serialization where signature uses a registered custom type."""
        agent = FlockAgent(
            name="custom_type_agent",
            model="custom_model",
            input="data: MyCustomData", # Use the registered custom type
            output="result_tags: list[str]"
        )
        file_path = tmp_path / "custom_type_agent.yaml"

        # Act
        agent.to_yaml_file(file_path)
        loaded_agent = FlockAgent.from_yaml_file(file_path)

        # Assert - Primarily check that loading worked and fields are correct
        assert loaded_agent.name == "custom_type_agent"
        assert loaded_agent.input == "data: MyCustomData"
        assert loaded_agent.output == "result_tags: list[str]"
        # We don't directly test type resolution here, but successful loading implies
        # the type string was stored correctly. Resolution is tested implicitly by DSPy mixin tests.

    def test_flock_serialization_basic(self, tmp_path):
        """Test serializing and deserializing a basic Flock instance."""
        flock = Flock(
            model="global_model",
            description="Test Flock Instance"
        )
        file_path = tmp_path / "basic_flock.yaml"

        # Act
        flock.to_yaml_file(file_path)
        loaded_flock = Flock.from_yaml_file(file_path)

        # Assert
        assert isinstance(loaded_flock, Flock)
        assert loaded_flock.model == flock.model
        assert loaded_flock.description == flock.description
        assert loaded_flock.agents == {} # No agents added

    def test_flock_serialization_with_agents(self, tmp_path):
        """Test Flock serialization with multiple agents."""
        flock = Flock(model="flock_model")
        agent1 = FlockAgent(name="agent_one", input="in1", output="out1")
        agent2 = FlockAgent(
            name="agent_two",
            input="out1", output="out2",
            evaluator=MockEvaluator(config=MockEvalConfig(mock_eval_param="agent2_eval"))
        )
        flock.add_agent(agent1)
        flock.add_agent(agent2)

        file_path = tmp_path / "flock_with_agents.yaml"

        # Act
        flock.to_yaml_file(file_path)
        loaded_flock = Flock.from_yaml_file(file_path)

        # Assert
        assert loaded_flock.model == "flock_model"
        assert len(loaded_flock.agents) == 2
        assert "agent_one" in loaded_flock.agents
        assert "agent_two" in loaded_flock.agents

        loaded_a1 = loaded_flock.agents["agent_one"]
        loaded_a2 = loaded_flock.agents["agent_two"]

        assert isinstance(loaded_a1, FlockAgent)
        assert loaded_a1.name == "agent_one"
        assert loaded_a1.input == "in1"

        assert isinstance(loaded_a2, FlockAgent)
        assert loaded_a2.name == "agent_two"
        assert loaded_a2.input == "out1"
        assert isinstance(loaded_a2.evaluator, MockEvaluator)
        assert loaded_a2.evaluator.config.mock_eval_param == "agent2_eval"


    def test_yaml_dump_options(self, tmp_path):
        """Verify that options can be passed to yaml.dump."""
        agent = FlockAgent(name="dump_options_test")
        file_path = tmp_path / "dump_options.yaml"

        # Act - Use sort_keys=True
        agent.to_yaml_file(file_path, sort_keys=True)
        content = file_path.read_text()

        # Assert - Check if keys are roughly sorted (basic check)
        # Note: Exact order depends on implementation details, this is a basic check
        assert content.startswith("description:") or content.startswith("evaluator:") # description might come first alphabetically