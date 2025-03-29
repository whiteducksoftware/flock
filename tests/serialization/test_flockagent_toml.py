"""Tests for TOML serialization of FlockAgent."""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
import toml

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator
from flock.core.flock_module import FlockModule
from flock.core.flock_router import FlockRouter

# Assuming this will be implemented or imported from the callable registry
from flock.core.serialization.callable_registry import CallableRegistry


# Sample functions for testing input/output fields and tools
def sample_input_func() -> str:
    """Sample function for input field definition."""
    return "query: str | The search query, options: dict | Additional options"


def sample_output_func() -> str:
    """Sample function for output field definition."""
    return "result: str | The search result, metadata: dict | Result metadata"


def sample_tool(x: int) -> int:
    """Sample tool function."""
    return x * 2


# Sample evaluator for testing
class TestEvaluator(FlockEvaluator):
    """Test evaluator for FlockAgent serialization tests."""

    name: str = "test_evaluator"
    
    async def evaluate(self, agent, inputs, tools=None):
        """Evaluate the agent inputs and return outputs."""
        return {"result": "Test result"}


# Sample module for testing
class TestModule(FlockModule):
    """Test module for FlockAgent serialization tests."""
    
    async def initialize(self, agent, inputs, context):
        """Initialize the module."""
        pass


# Sample router for testing
class TestRouter(FlockRouter):
    """Test router for FlockAgent serialization tests."""
    
    async def route(self, agent, result):
        """Route to the next agent."""
        return None


@pytest.fixture
def simple_agent():
    """Fixture for a simple FlockAgent."""
    return FlockAgent(
        name="test_agent",
        model="openai/gpt-4o",
        description="A test agent",
        input="query: str | The query to process",
        output="result: str | The processed result",
    )


@pytest.fixture
def complex_agent():
    """Fixture for a complex FlockAgent with all features."""
    agent = FlockAgent(
        name="complex_agent",
        model="openai/gpt-4o",
        description=lambda: "A complex test agent",
        input=sample_input_func,
        output=sample_output_func,
        tools=[sample_tool],
        use_cache=True,
    )
    
    # Add evaluator
    agent.evaluator = TestEvaluator()
    
    # Add module
    agent.add_module(TestModule(name="test_module"))
    
    # Add router
    agent.handoff_router = TestRouter()
    
    return agent


class TestFlockAgentToml:
    """Tests for FlockAgent TOML serialization."""

    def test_save_simple_agent_to_toml(self, simple_agent):
        """Test saving a simple agent to TOML."""
        # This test will fail until save_to_toml_file is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            simple_agent.save_to_toml_file(file_path)
            
            # Verify file exists
            assert file_path.exists()
            
            # Read the file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Verify basic agent properties are in the TOML
            assert "name = \"test_agent\"" in content
            assert "model = \"openai/gpt-4o\"" in content
            assert "description = \"A test agent\"" in content
            assert "input = \"query: str | The query to process\"" in content
            assert "output = \"result: str | The processed result\"" in content
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_load_simple_agent_from_toml(self, simple_agent):
        """Test loading a simple agent from TOML."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file first
            simple_agent.save_to_toml_file(file_path)
            
            # Load from TOML file
            loaded_agent = FlockAgent.load_from_toml_file(file_path)
            
            # Verify properties match
            assert loaded_agent.name == simple_agent.name
            assert loaded_agent.model == simple_agent.model
            assert loaded_agent.description == simple_agent.description
            assert loaded_agent.input == simple_agent.input
            assert loaded_agent.output == simple_agent.output
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_save_complex_agent_to_toml(self, complex_agent):
        """Test saving a complex agent to TOML."""
        # This test will fail until save_to_toml_file is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            complex_agent.save_to_toml_file(file_path)
            
            # Verify file exists
            assert file_path.exists()
            
            # Read the file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Parse the TOML
            parsed_toml = toml.loads(content)
            
            # Verify basic agent properties
            assert parsed_toml["name"] == "complex_agent"
            assert parsed_toml["model"] == "openai/gpt-4o"
            assert "description" in parsed_toml
            assert "input" in parsed_toml
            assert "output" in parsed_toml
            assert parsed_toml["use_cache"] is True
            
            # Verify callable references are included
            assert "tools" in parsed_toml
            assert "@registry:" in content or "@import:" in content
            
            # Verify modules section exists
            assert "modules" in parsed_toml
            assert "test_module" in str(parsed_toml["modules"])
            
            # Verify evaluator section exists
            assert "evaluator" in parsed_toml
            
            # Verify router section exists
            assert "handoff_router" in parsed_toml
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_load_complex_agent_from_toml(self, complex_agent):
        """Test loading a complex agent from TOML."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file first
            complex_agent.save_to_toml_file(file_path)
            
            # Load from TOML file
            loaded_agent = FlockAgent.load_from_toml_file(file_path)
            
            # Verify basic properties match
            assert loaded_agent.name == complex_agent.name
            assert loaded_agent.model == complex_agent.model
            
            # Verify callable properties (description, input, output)
            # Since these are callable functions, we need to check the result
            assert loaded_agent.description() == complex_agent.description()
            assert loaded_agent.input() == complex_agent.input()
            assert loaded_agent.output() == complex_agent.output()
            
            # Verify tools are loaded
            assert loaded_agent.tools is not None
            assert len(loaded_agent.tools) == len(complex_agent.tools)
            assert loaded_agent.tools[0](5) == 10  # sample_tool(5) should return 10
            
            # Verify evaluator type
            assert isinstance(loaded_agent.evaluator, TestEvaluator)
            
            # Verify modules are loaded
            assert "test_module" in loaded_agent.modules
            assert isinstance(loaded_agent.modules["test_module"], TestModule)
            
            # Verify router is loaded
            assert isinstance(loaded_agent.handoff_router, TestRouter)
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_toml_comments(self, simple_agent):
        """Test that TOML files include helpful comments."""
        # This test will fail until save_to_toml_file is implemented with comments
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            simple_agent.save_to_toml_file(file_path)
            
            # Read the file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Verify comments are included
            assert "# FlockAgent:" in content
            assert "# " in content  # At least some comment lines
            
            # Check for section comments
            sections = ["input", "output", "tools", "evaluator", "modules"]
            section_comments = 0
            for section in sections:
                if f"# {section}" in content:
                    section_comments += 1
            
            # At least some section comments should be present
            assert section_comments > 0
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_input_output_field_formats(self):
        """Test serializing agents with different input/output formats."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        # Test cases for different input/output formats
        test_cases = [
            # Simple string
            "query",
            # Typed field
            "query: str",
            # Field with description
            "query | The search query",
            # Typed field with description
            "query: str | The search query",
            # Multiple fields
            "query: str | The search query, options: dict | Additional options",
        ]
        
        for test_case in test_cases:
            # Create an agent with the test input/output
            agent = FlockAgent(
                name=f"test_agent_{hash(test_case) % 1000}",
                model="openai/gpt-4o",
                input=test_case,
                output=test_case,
            )
            
            with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
                file_path = Path(temp_file.name)
            
            try:
                # Save to TOML file
                agent.save_to_toml_file(file_path)
                
                # Load from TOML file
                loaded_agent = FlockAgent.load_from_toml_file(file_path)
                
                # Verify input/output match
                assert loaded_agent.input == agent.input
                assert loaded_agent.output == agent.output
                
            finally:
                # Clean up
                if file_path.exists():
                    os.unlink(file_path)

    def test_manual_editing_and_loading(self):
        """Test loading an agent from a manually edited TOML file."""
        # This test will fail until load_from_toml_file is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
            
            # Create a manual TOML configuration
            manual_toml = """
            # FlockAgent: manual_agent
            # This is a manually created agent configuration
            
            name = "manual_agent"
            model = "openai/gpt-4o"
            description = "A manually created agent"
            input = "query: str | The query to process"
            output = "result: str | The processed result"
            use_cache = true
            
            # No tools or modules in this simple example
            """
            
            # Write to file
            with open(file_path, "w") as f:
                f.write(manual_toml)
        
        try:
            # Load from TOML file
            loaded_agent = FlockAgent.load_from_toml_file(file_path)
            
            # Verify properties
            assert loaded_agent.name == "manual_agent"
            assert loaded_agent.model == "openai/gpt-4o"
            assert loaded_agent.description == "A manually created agent"
            assert loaded_agent.input == "query: str | The query to process"
            assert loaded_agent.output == "result: str | The processed result"
            assert loaded_agent.use_cache is True
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_error_handling(self):
        """Test error handling for invalid TOML input."""
        # This test will fail until proper error handling is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
            
            # Create an invalid TOML configuration (missing required fields)
            invalid_toml = """
            # Missing required fields like name
            model = "openai/gpt-4o"
            """
            
            # Write to file
            with open(file_path, "w") as f:
                f.write(invalid_toml)
        
        try:
            # Should raise an exception on missing required fields
            with pytest.raises(Exception):
                FlockAgent.load_from_toml_file(file_path)
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_type_conversion(self):
        """Test type conversions in TOML serialization."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        # Create an agent with boolean and numeric values
        agent = FlockAgent(
            name="type_test_agent",
            model="openai/gpt-4o",
            input="query",
            output="result",
            use_cache=True,  # Boolean
        )
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            agent.save_to_toml_file(file_path)
            
            # Load from TOML file
            loaded_agent = FlockAgent.load_from_toml_file(file_path)
            
            # Verify types are preserved
            assert isinstance(loaded_agent.use_cache, bool)
            assert loaded_agent.use_cache is True
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path) 