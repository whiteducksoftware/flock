"""Unit tests for YAML serialization of Flock systems."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent


class TestFlockYAML:
    """Tests for YAML serialization of Flock systems."""

    def test_flock_to_yaml_method(self):
        """Test that to_yaml method raises NotImplementedError."""
        flock = Flock(model="openai/gpt-4o")
        with pytest.raises(NotImplementedError):
            flock.to_yaml()

    def test_flock_from_yaml_method(self):
        """Test that from_yaml method raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            Flock.from_yaml("test")

    def test_basic_flock_serialization(self):
        """Test serializing a basic Flock system."""
        flock = Flock(
            model="openai/gpt-4o",
            description="A test Flock system"
        )
        
        # Expected YAML after implementation
        expected_yaml = """model: openai/gpt-4o
description: A test Flock system
agents: {}
"""
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = flock.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # assert yaml_dict["model"] == "openai/gpt-4o"
            # assert yaml_dict["description"] == "A test Flock system"
            # assert "agents" in yaml_dict
            # assert isinstance(yaml_dict["agents"], dict)

    def test_flock_with_agents(self):
        """Test serializing a Flock with multiple agents."""
        flock = Flock(model="openai/gpt-4o")
        
        # Add a few agents
        agent1 = FlockAgent(
            name="agent1",
            description="First test agent",
            model="openai/gpt-4o",
            input="input1: str | Input for agent 1",
            output="output1: str | Output from agent 1"
        )
        
        agent2 = FlockAgent(
            name="agent2",
            description="Second test agent",
            model="openai/gpt-4o",
            input="input2: str | Input for agent 2",
            output="output2: str | Output from agent 2"
        )
        
        flock.add_agent(agent1)
        flock.add_agent(agent2)
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = flock.to_yaml()
            # After implementation, this should work:
            # yaml_dict = yaml.safe_load(yaml_str)
            # assert len(yaml_dict["agents"]) == 2
            # assert "agent1" in yaml_dict["agents"]
            # assert "agent2" in yaml_dict["agents"]
            
            # loaded_flock = Flock.from_yaml(yaml_str)
            # assert len(loaded_flock.agents) == 2
            # assert "agent1" in loaded_flock.agents
            # assert "agent2" in loaded_flock.agents

    def test_flock_deserialization(self):
        """Test deserializing a Flock system."""
        yaml_str = """model: openai/gpt-4o
description: A deserialized Flock system
agents:
  test_agent:
    name: test_agent
    description: A test agent
    model: openai/gpt-4o
    input: 'test_input: str | Input for test'
    output: 'test_output: str | Output from test'
    use_cache: false
    use_tools: false
"""
        
        # This will raise NotImplementedError until from_yaml is implemented
        with pytest.raises(NotImplementedError):
            flock = Flock.from_yaml(yaml_str)
            # After implementation, this should work:
            # assert flock.model == "openai/gpt-4o"
            # assert flock.description == "A deserialized Flock system"
            # assert len(flock.agents) == 1
            # assert "test_agent" in flock.agents
            # assert flock.agents["test_agent"].name == "test_agent"
            # assert flock.agents["test_agent"].input == "test_input: str | Input for test"
            # assert flock.agents["test_agent"].output == "test_output: str | Output from test"

    def test_flock_with_agent_relationships(self):
        """Test serializing a Flock with agent relationships."""
        flock = Flock(model="openai/gpt-4o")
        
        # Create agents with a relationship (hand-off flow)
        agent1 = FlockAgent(
            name="first_agent",
            description="First agent in the chain",
            model="openai/gpt-4o",
            input="initial_input: str | Initial input",
            output="intermediate: str | Intermediate output"
        )
        
        agent2 = FlockAgent(
            name="second_agent",
            description="Second agent in the chain",
            model="openai/gpt-4o",
            input="intermediate: str | Intermediate input",
            output="final_output: str | Final output"
        )
        
        flock.add_agent(agent1)
        flock.add_agent(agent2)
        
        # Set up a simple routing from agent1 to agent2
        # (Implementation will depend on how routing is handled in Flock)
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = flock.to_yaml()
            # After implementation, this should work:
            # loaded_flock = Flock.from_yaml(yaml_str)
            # assert "first_agent" in loaded_flock.agents
            # assert "second_agent" in loaded_flock.agents
            # Verify routing relationships are preserved (depends on implementation)

    def test_flock_yaml_file_operations(self):
        """Test file operations with Flock YAML serialization."""
        flock = Flock(model="openai/gpt-4o", description="File test Flock")
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            # This will raise NotImplementedError until to_yaml_file is implemented
            with pytest.raises(NotImplementedError):
                flock.to_yaml_file(tmp_path)
                # After implementation, this should work:
                # loaded_flock = Flock.from_yaml_file(tmp_path)
                # assert loaded_flock.model == "openai/gpt-4o"
                # assert loaded_flock.description == "File test Flock"
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_complex_flock_serialization(self):
        """Test serializing a complex Flock system with multiple components."""
        flock = Flock(
            model="openai/gpt-4o",
            description="A complex Flock system"
        )
        
        # Add multiple agents with various configurations
        for i in range(3):
            agent = FlockAgent(
                name=f"agent{i}",
                description=f"Test agent {i}",
                model="openai/gpt-4o",
                input=f"input{i}: str | Input for agent {i}",
                output=f"output{i}: str | Output from agent {i}",
                use_cache=i % 2 == 0,  # Alternate cache settings
                use_tools=i % 2 == 1,  # Alternate tool settings
            )
            flock.add_agent(agent)
        
        # This will raise NotImplementedError until to_yaml is implemented
        with pytest.raises(NotImplementedError):
            yaml_str = flock.to_yaml()
            # After implementation, this should work:
            # loaded_flock = Flock.from_yaml(yaml_str)
            # assert len(loaded_flock.agents) == 3
            # for i in range(3):
            #     assert f"agent{i}" in loaded_flock.agents
            #     assert loaded_flock.agents[f"agent{i}"].use_cache == (i % 2 == 0)
            #     assert loaded_flock.agents[f"agent{i}"].use_tools == (i % 2 == 1) 