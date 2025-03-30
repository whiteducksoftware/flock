"""Integration tests for YAML serialization across all components."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator


# Sample function for callable reference tests
def sample_tool_function(text: str) -> str:
    """A sample tool function that capitalizes text."""
    return text.upper()


class TestYAMLIntegration:
    """Integration tests for YAML serialization across components."""

    def test_end_to_end_agent_serialization(self):
        """Test end-to-end serialization of an agent to YAML and back."""
        # Create an agent
        agent = FlockAgent(
            name="integration_test_agent",
            description="An agent for integration testing",
            model="openai/gpt-4o",
            input="test_input: str | Input for integration test",
            output="test_output: str | Output from integration test",
            use_cache=True,
            use_tools=True
        )
        
        # This will raise NotImplementedError until YAML serialization is implemented
        with pytest.raises(NotImplementedError):
            # Serialize to YAML
            yaml_str = agent.to_yaml()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                agent.to_yaml_file(tmp_path)
            
            try:
                # Deserialize from file
                loaded_agent = FlockAgent.from_yaml_file(tmp_path)
                
                # Verify properties
                assert loaded_agent.name == "integration_test_agent"
                assert loaded_agent.description == "An agent for integration testing"
                assert loaded_agent.model == "openai/gpt-4o"
                assert loaded_agent.input == "test_input: str | Input for integration test"
                assert loaded_agent.output == "test_output: str | Output from integration test"
                assert loaded_agent.use_cache is True
                assert loaded_agent.use_tools is True
            finally:
                # Clean up
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    def test_end_to_end_flock_serialization(self):
        """Test end-to-end serialization of a Flock to YAML and back."""
        # Create a Flock with multiple agents
        flock = Flock(model="openai/gpt-4o")
        
        # Add agents
        agent1 = FlockAgent(
            name="first_agent",
            description="First agent in chain",
            model="openai/gpt-4o",
            input="initial_input: str | Initial input",
            output="intermediate: str | Intermediate output"
        )
        
        agent2 = FlockAgent(
            name="second_agent",
            description="Second agent in chain",
            model="openai/gpt-4o",
            input="intermediate: str | Intermediate input",
            output="final_output: str | Final output"
        )
        
        flock.add_agent(agent1)
        flock.add_agent(agent2)
        
        # This will raise NotImplementedError until YAML serialization is implemented
        with pytest.raises(NotImplementedError):
            # Serialize to YAML
            yaml_str = flock.to_yaml()
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                flock.to_yaml_file(tmp_path)
            
            try:
                # Deserialize from file
                loaded_flock = Flock.from_yaml_file(tmp_path)
                
                # Verify properties
                assert loaded_flock.model == "openai/gpt-4o"
                assert len(loaded_flock.agents) == 2
                assert "first_agent" in loaded_flock.agents
                assert "second_agent" in loaded_flock.agents
                assert loaded_flock.agents["first_agent"].output == "intermediate: str | Intermediate output"
                assert loaded_flock.agents["second_agent"].input == "intermediate: str | Intermediate input"
            finally:
                # Clean up
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    def test_callable_references_in_yaml(self):
        """Test serialization of callables in YAML."""
        # This test will initially fail until CallableReference is implemented
        with pytest.raises(ImportError):
            # This will fail until the module is implemented
            from flock.core.serialization.callable_reference import function_to_reference
            from flock.core.serialization.callable_reference import reference_to_function
            
            # Create a reference to the sample function
            ref = function_to_reference(sample_tool_function)
            
            # Serialize to YAML
            yaml_str = yaml.dump(ref)
            
            # Deserialize from YAML
            loaded_ref = yaml.safe_load(yaml_str)
            
            # Convert back to function
            func = reference_to_function(loaded_ref)
            
            # Verify function works
            assert func("test") == "TEST"

    def test_json_yaml_conversion(self):
        """Test conversion between JSON and YAML formats."""
        # Create an agent
        agent = FlockAgent(
            name="format_conversion_agent",
            description="Agent for testing format conversion",
            model="openai/gpt-4o"
        )
        
        # This will raise NotImplementedError until the conversion is implemented
        with pytest.raises(NotImplementedError):
            # This will fail until the method is implemented
            # After implementation, this would be replaced with the appropriate method
            
            # First to JSON
            json_str = agent.to_json()
            
            # Then convert JSON to YAML
            # This function would need to be implemented
            from flock.core.serialization import convert_json_to_yaml
            yaml_str = convert_json_to_yaml(json_str)
            
            # Load from YAML
            loaded_agent = FlockAgent.from_yaml(yaml_str)
            
            # Verify properties
            assert loaded_agent.name == "format_conversion_agent"
            assert loaded_agent.description == "Agent for testing format conversion"
            assert loaded_agent.model == "openai/gpt-4o"

    def test_manual_yaml_editing(self):
        """Test manually editing YAML and loading it back."""
        # Create an agent and serialize to YAML
        agent = FlockAgent(
            name="manual_edit_agent",
            description="Agent for testing manual editing",
            model="openai/gpt-4o"
        )
        
        # This will raise NotImplementedError until YAML serialization is implemented
        with pytest.raises(NotImplementedError):
            # Serialize to YAML
            yaml_str = agent.to_yaml()
            
            # Manually edit the YAML (simulate user editing the file)
            # Change the description and add a custom property
            edited_yaml = yaml_str.replace(
                "description: Agent for testing manual editing", 
                "description: Manually edited description\n"
                "custom_property: Custom value added manually"
            )
            
            # Load the edited YAML
            edited_agent = FlockAgent.from_yaml(edited_yaml)
            
            # Verify changes were applied
            assert edited_agent.name == "manual_edit_agent"
            assert edited_agent.description == "Manually edited description"
            # Verify custom property was added (implementation dependent)
            # This might require custom handling in the from_yaml method
            assert hasattr(edited_agent, "custom_property")
            assert edited_agent.custom_property == "Custom value added manually"

    def test_performance_comparison(self):
        """Compare performance between JSON and YAML serialization."""
        import time
        
        # Create a complex Flock with multiple agents
        flock = Flock(model="openai/gpt-4o")
        for i in range(10):
            agent = FlockAgent(
                name=f"perf_agent_{i}",
                description=f"Performance test agent {i}",
                model="openai/gpt-4o",
                input=f"input{i}: str | Input for agent {i}",
                output=f"output{i}: str | Output from agent {i}",
                use_cache=i % 2 == 0,
                use_tools=i % 2 == 1
            )
            flock.add_agent(agent)
        
        # This will raise NotImplementedError until YAML serialization is implemented
        with pytest.raises(NotImplementedError):
            # Measure JSON serialization time
            json_start = time.time()
            json_str = flock.to_json()
            json_time = time.time() - json_start
            
            # Measure YAML serialization time
            yaml_start = time.time()
            yaml_str = flock.to_yaml()
            yaml_time = time.time() - yaml_start
            
            # Print performance comparison (this is informational only, not an assertion)
            print(f"JSON serialization: {json_time:.6f} seconds")
            print(f"YAML serialization: {yaml_time:.6f} seconds")
            print(f"Ratio (YAML/JSON): {yaml_time/json_time:.2f}")
            
            # Verify YAML string is not empty
            assert yaml_str
            assert len(yaml_str) > 0 