"""Unit tests for YAML serialization of FlockAgent."""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.flock_router import FlockRouter, FlockRouterConfig, HandOffRequest
from flock.core.context.context import FlockContext


# =========== Mock implementations for testing ===========

# Create a concrete implementation of FlockEvaluator for testing
class MockEvaluator(FlockEvaluator):
    """Mock implementation of FlockEvaluator for testing purposes."""
    
    def __init__(self, name: str = "mock_evaluator", model: str = "test-model"):
        """Initialize the mock evaluator."""
        config = FlockEvaluatorConfig(model=model)
        super().__init__(name=name, config=config)
    
    async def evaluate(self, agent: Any, inputs: Dict[str, Any], tools: List[Any]) -> Dict[str, Any]:
        """Mock implementation of the abstract evaluate method."""
        return {"result": "mock evaluation"}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary representation."""
        return {
            "name": self.name,
            "config": self.config.model_dump(),
            "type": "MockEvaluator"
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockEvaluator":
        """Create instance from dictionary representation."""
        config = FlockEvaluatorConfig(**data.get("config", {}))
        return cls(name=data.get("name", "mock_evaluator"), model=config.model)


# Create a mock module for testing
class MockModuleConfig(FlockModuleConfig):
    """Mock module configuration for testing."""
    
    setting1: str = "default_value"
    setting2: bool = True
    setting3: int = 42


class MockModule(FlockModule):
    """Mock implementation of FlockModule for testing purposes."""
    
    def __init__(self, name: str = "mock_module", config: Optional[MockModuleConfig] = None):
        """Initialize the mock module."""
        if config is None:
            config = MockModuleConfig()
        super().__init__(name=name, config=config)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary representation."""
        return {
            "name": self.name,
            "config": self.config.model_dump(),
            "type": "MockModule"
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockModule":
        """Create instance from dictionary representation."""
        config = MockModuleConfig(**data.get("config", {}))
        return cls(name=data.get("name", "mock_module"), config=config)


# Create a mock router for testing
class MockRouter(FlockRouter):
    """Mock implementation of FlockRouter for testing purposes."""
    
    def __init__(self, name: str = "mock_router", agents: Optional[List[str]] = None):
        """Initialize the mock router."""
        if agents is None:
            agents = ["agent1", "agent2"]
        config = FlockRouterConfig(agents=agents)
        super().__init__(name=name, config=config)
    
    async def route(self, current_agent: Any, result: Dict[str, Any], context: FlockContext) -> HandOffRequest:
        """Mock implementation of the abstract route method."""
        # Simple routing logic - always route to the first agent in the list
        if self.config.agents and len(self.config.agents) > 0:
            return HandOffRequest(next_agent=self.config.agents[0])
        return HandOffRequest(next_agent="")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary representation."""
        return {
            "name": self.name,
            "config": self.config.model_dump(),
            "type": "MockRouter"
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockRouter":
        """Create instance from dictionary representation."""
        config = FlockRouterConfig(**data.get("config", {}))
        return cls(name=data.get("name", "mock_router"), agents=config.agents)


# Sample tool function for testing
def sample_tool_function(text: str) -> str:
    """Sample tool function that converts text to uppercase."""
    return text.upper()


class TestFlockAgentYAML:
    """Tests for YAML serialization of FlockAgent."""

    def test_agent_to_yaml_method(self):
        """Test that to_yaml method raises NotImplementedError."""
        agent = FlockAgent(name="test_agent")
        with pytest.raises(NotImplementedError):
            agent.to_yaml()

    def test_agent_from_yaml_method(self):
        """Test that from_yaml method raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            FlockAgent.from_yaml("test")

    def test_basic_agent_serialization(self):
        """Test serializing a basic agent."""
        agent = FlockAgent(
            name="test_agent",
            description="A test agent",
            model="openai/gpt-4o",
            input="test_input: str | Input for test",
            output="test_output: str | Output from test",
        )
        
        # Expected YAML after implementation
        expected_yaml = """name: test_agent
description: A test agent
model: openai/gpt-4o
input: 'test_input: str | Input for test'
output: 'test_output: str | Output from test'
use_cache: true
"""
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = agent.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # assert yaml_dict["name"] == "test_agent"
            # assert yaml_dict["description"] == "A test agent"
            # assert yaml_dict["model"] == "openai/gpt-4o"
            # assert yaml_dict["input"] == "test_input: str | Input for test"
            # assert yaml_dict["output"] == "test_output: str | Output from test"

    def test_agent_deserialization(self):
        """Test deserializing a basic agent."""
        yaml_str = """name: test_agent_from_yaml
description: A deserialized test agent
model: openai/gpt-4o
input: 'input_field: str | The input field'
output: 'output_field: str | The output field'
use_cache: false
"""
        
        # This will raise NotImplementedError until from_yaml is implemented
        with pytest.raises(NotImplementedError):
            agent = FlockAgent.from_yaml(yaml_str)
            # After implementation, this should work:
            # assert agent.name == "test_agent_from_yaml"
            # assert agent.description == "A deserialized test agent"
            # assert agent.model == "openai/gpt-4o"
            # assert agent.input == "input_field: str | The input field"
            # assert agent.output == "output_field: str | The output field"
            # assert agent.use_cache is False

    def test_agent_with_evaluator(self):
        """Test serializing an agent with a custom evaluator."""
        # Create a simple agent with a concrete evaluator implementation
        mock_evaluator = MockEvaluator(name="test_evaluator", model="openai/gpt-4o")
        agent = FlockAgent(
            name="agent_with_evaluator",
            description="An agent with custom evaluator",
            model="openai/gpt-4o",
            evaluator=mock_evaluator
        )
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = agent.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # assert yaml_dict["name"] == "agent_with_evaluator"
            # assert "evaluator" in yaml_dict
            # assert isinstance(yaml_dict["evaluator"], dict)
            # assert yaml_dict["evaluator"]["name"] == "test_evaluator"
            # assert yaml_dict["evaluator"]["type"] == "MockEvaluator"
            
            # loaded_agent = FlockAgent.from_yaml(yaml_str)
            # assert loaded_agent.name == "agent_with_evaluator"
            # assert loaded_agent.evaluator is not None
            # assert loaded_agent.evaluator.name == "test_evaluator"

    def test_agent_with_module(self):
        """Test serializing an agent with attached modules."""
        # Create a mock module
        mock_module = MockModule(
            name="test_module",
            config=MockModuleConfig(setting1="custom_value", setting2=False, setting3=100)
        )
        
        # Create agent with module
        agent = FlockAgent(
            name="agent_with_module",
            description="An agent with a module",
            model="openai/gpt-4o"
        )
        agent.add_module(mock_module)
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = agent.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # assert yaml_dict["name"] == "agent_with_module"
            # assert "modules" in yaml_dict
            # assert "test_module" in yaml_dict["modules"]
            # assert yaml_dict["modules"]["test_module"]["type"] == "MockModule"
            # assert yaml_dict["modules"]["test_module"]["config"]["setting1"] == "custom_value"
            # assert yaml_dict["modules"]["test_module"]["config"]["setting2"] is False
            # assert yaml_dict["modules"]["test_module"]["config"]["setting3"] == 100
            
            # loaded_agent = FlockAgent.from_yaml(yaml_str)
            # assert loaded_agent.name == "agent_with_module"
            # assert "test_module" in loaded_agent.modules
            # assert loaded_agent.modules["test_module"].config.setting1 == "custom_value"
            # assert loaded_agent.modules["test_module"].config.setting2 is False
            # assert loaded_agent.modules["test_module"].config.setting3 == 100

    def test_agent_with_router(self):
        """Test serializing an agent with a router."""
        # Create a mock router
        mock_router = MockRouter(
            name="test_router",
            agents=["next_agent_1", "next_agent_2", "next_agent_3"]
        )
        
        # Create agent with router
        agent = FlockAgent(
            name="agent_with_router",
            description="An agent with a router",
            model="openai/gpt-4o",
            handoff_router=mock_router
        )
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = agent.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # assert yaml_dict["name"] == "agent_with_router"
            # assert "handoff_router" in yaml_dict
            # assert yaml_dict["handoff_router"]["name"] == "test_router"
            # assert yaml_dict["handoff_router"]["type"] == "MockRouter"
            # assert "next_agent_1" in yaml_dict["handoff_router"]["config"]["agents"]
            # assert "next_agent_2" in yaml_dict["handoff_router"]["config"]["agents"]
            # assert "next_agent_3" in yaml_dict["handoff_router"]["config"]["agents"]
            
            # loaded_agent = FlockAgent.from_yaml(yaml_str)
            # assert loaded_agent.name == "agent_with_router"
            # assert loaded_agent.handoff_router is not None
            # assert loaded_agent.handoff_router.name == "test_router"
            # assert "next_agent_1" in loaded_agent.handoff_router.config.agents
            # assert "next_agent_2" in loaded_agent.handoff_router.config.agents
            # assert "next_agent_3" in loaded_agent.handoff_router.config.agents

    def test_agent_with_tools(self):
        """Test serializing an agent with tools."""
        # Create an agent with tools
        agent = FlockAgent(
            name="agent_with_tools",
            description="An agent that uses tools",
            model="openai/gpt-4o",
            tools=[sample_tool_function]
        )
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = agent.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # assert yaml_dict["name"] == "agent_with_tools"
            # assert "tools" in yaml_dict
            # assert len(yaml_dict["tools"]) == 1
            # # The tools should be serialized in a way that represents the function
            # assert "sample_tool_function" in yaml_str
            
            # loaded_agent = FlockAgent.from_yaml(yaml_str)
            # assert loaded_agent.name == "agent_with_tools"
            # assert loaded_agent.tools is not None
            # assert len(loaded_agent.tools) == 1
            # # Tool should be callable after deserialization
            # assert callable(loaded_agent.tools[0])
            # assert loaded_agent.tools[0]("test") == "TEST"

    def test_complex_agent_configuration(self):
        """Test serializing an agent with evaluator, module, router, and tools."""
        # Create all components
        mock_evaluator = MockEvaluator(name="complex_evaluator", model="openai/gpt-4o")
        mock_module = MockModule(name="complex_module")
        mock_router = MockRouter(name="complex_router")
        
        # Create a complex agent with all components
        agent = FlockAgent(
            name="complex_agent",
            description="An agent with all components",
            model="openai/gpt-4o",
            input="complex_input: dict | Complex input structure",
            output="complex_output: list | Complex output structure",
            use_cache=False,
            tools=[sample_tool_function],
            evaluator=mock_evaluator,
            handoff_router=mock_router
        )
        agent.add_module(mock_module)
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = agent.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # # Verify all components are present
            # assert yaml_dict["name"] == "complex_agent"
            # assert "evaluator" in yaml_dict
            # assert "modules" in yaml_dict
            # assert "complex_module" in yaml_dict["modules"]
            # assert "handoff_router" in yaml_dict
            # assert "tools" in yaml_dict
            
            # loaded_agent = FlockAgent.from_yaml(yaml_str)
            # assert loaded_agent.name == "complex_agent"
            # assert loaded_agent.evaluator is not None
            # assert loaded_agent.evaluator.name == "complex_evaluator"
            # assert "complex_module" in loaded_agent.modules
            # assert loaded_agent.handoff_router is not None
            # assert loaded_agent.handoff_router.name == "complex_router"
            # assert loaded_agent.tools is not None
            # assert len(loaded_agent.tools) == 1
            # assert callable(loaded_agent.tools[0])

    def test_callable_description_input_output(self):
        """Test serializing an agent with callable description, input, and output fields."""
        # Define callable functions for description, input, and output
        def get_description(context=None):
            return "Dynamic description from function"
            
        def get_input(context=None):
            return "dynamic_input: str | Input from function"
            
        def get_output(context=None):
            return "dynamic_output: str | Output from function"
        
        # Create agent with callable fields
        agent = FlockAgent(
            name="callable_fields_agent",
            description=get_description,
            input=get_input,
            output=get_output,
            model="openai/gpt-4o"
        )
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = agent.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # # Verify callable fields are serialized
            # assert yaml_dict["name"] == "callable_fields_agent"
            # # The representation of callables depends on implementation
            # # but should contain information to recreate the function
            
            # loaded_agent = FlockAgent.from_yaml(yaml_str)
            # assert loaded_agent.name == "callable_fields_agent"
            # assert callable(loaded_agent.description)
            # assert callable(loaded_agent.input)
            # assert callable(loaded_agent.output)
            # assert loaded_agent.description() == "Dynamic description from function"
            # assert loaded_agent.input() == "dynamic_input: str | Input from function"
            # assert loaded_agent.output() == "dynamic_output: str | Output from function"

    def test_agent_yaml_file_operations(self):
        """Test file operations with agent YAML serialization."""
        agent = FlockAgent(name="file_test_agent")
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            # This will raise NotImplementedError until to_yaml_file is implemented
            with pytest.raises(NotImplementedError):
                agent.to_yaml_file(tmp_path)
                # After implementation, this should work:
                # loaded_agent = FlockAgent.from_yaml_file(tmp_path)
                # assert loaded_agent.name == "file_test_agent"
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path) 