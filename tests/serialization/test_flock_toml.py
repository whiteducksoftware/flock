"""Tests for TOML serialization of Flock systems."""

import os
import tempfile
from pathlib import Path

import pytest
import toml

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator
from flock.core.flock_router import FlockRouter
from flock.routers.default.default_router import DefaultRouter, DefaultRouterConfig

# Sample tool function for testing
def sample_tool(x: int) -> int:
    """Sample tool function."""
    return x * 2


# Sample evaluator for testing
class TestEvaluator(FlockEvaluator):
    """Test evaluator for Flock serialization tests."""

    async def evaluate(self, agent, inputs, tools=None):
        """Evaluate the agent inputs and return outputs."""
        return {"result": "Test result"}


@pytest.fixture
def simple_flock():
    """Fixture for a simple Flock with one agent."""
    flock = Flock(model="openai/gpt-4o")
    
    agent = FlockAgent(
        name="test_agent",
        model="openai/gpt-4o",
        description="A test agent",
        input="query: str | The query to process",
        output="result: str | The processed result",
    )
    
    flock.add_agent(agent)
    
    return flock


@pytest.fixture
def multi_agent_flock():
    """Fixture for a Flock with multiple agents and handoffs."""
    flock = Flock(model="openai/gpt-4o")
    
    # Create first agent
    agent1 = FlockAgent(
        name="first_agent",
        model="openai/gpt-4o",
        description="The first agent in the workflow",
        input="query: str | The initial query",
        output="intermediate_result: str | An intermediate result",
    )
    
    # Create second agent
    agent2 = FlockAgent(
        name="second_agent",
        model="openai/gpt-4o",
        description="The second agent in the workflow",
        input="intermediate_result: str | Result from the first agent",
        output="final_result: str | The final processed result",
    )
    
    # Add router to first agent to handoff to second
    agent1.handoff_router = DefaultRouter(
        config=DefaultRouterConfig(hand_off="second_agent")
    )
    
    # Add both agents to the flock
    flock.add_agent(agent1)
    flock.add_agent(agent2)
    
    return flock


@pytest.fixture
def complex_flock():
    """Fixture for a complex Flock with tools, custom evaluators, and context."""
    flock = Flock(model="openai/gpt-4o", enable_logging=True)
    
    # Create first agent with tool and custom evaluator
    agent1 = FlockAgent(
        name="tool_agent",
        model="openai/gpt-4o",
        description="An agent with tools",
        input="query: str | The initial query",
        output="result: str | The processed result",
        tools=[sample_tool],
    )
    agent1.evaluator = TestEvaluator()
    
    # Create second agent
    agent2 = FlockAgent(
        name="standard_agent",
        model="openai/gpt-4o",
        description="A standard agent",
        input="query: str | The query to process",
        output="result: str | The processed result",
    )
    
    # Add agents to the flock
    flock.add_agent(agent1)
    flock.add_agent(agent2)
    
    # Register global tool
    flock.add_tool("global_sample_tool", sample_tool)
    
    return flock


class TestFlockToml:
    """Tests for Flock system TOML serialization."""

    def test_save_simple_flock_to_toml(self, simple_flock):
        """Test saving a simple Flock to TOML."""
        # This test will fail until save_to_toml_file is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            simple_flock.save_to_toml_file(file_path)
            
            # Verify file exists
            assert file_path.exists()
            
            # Read the file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Parse the TOML
            parsed_toml = toml.loads(content)
            
            # Verify Flock configuration is present
            assert "model" in parsed_toml
            assert parsed_toml["model"] == "openai/gpt-4o"
            
            # Verify agents section exists
            assert "agents" in parsed_toml
            assert "test_agent" in str(parsed_toml["agents"])
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_load_simple_flock_from_toml(self, simple_flock):
        """Test loading a simple Flock from TOML."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file first
            simple_flock.save_to_toml_file(file_path)
            
            # Load from TOML file
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Verify Flock properties
            assert loaded_flock.model == simple_flock.model
            
            # Verify agents were loaded
            assert "test_agent" in loaded_flock.agents
            assert loaded_flock.agents["test_agent"].name == "test_agent"
            assert loaded_flock.agents["test_agent"].model == "openai/gpt-4o"
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_save_multi_agent_flock_to_toml(self, multi_agent_flock):
        """Test saving a multi-agent Flock to TOML."""
        # This test will fail until save_to_toml_file is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            multi_agent_flock.save_to_toml_file(file_path)
            
            # Verify file exists
            assert file_path.exists()
            
            # Read the file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Parse the TOML
            parsed_toml = toml.loads(content)
            
            # Verify agents section contains both agents
            assert "agents" in parsed_toml
            assert "first_agent" in str(parsed_toml["agents"])
            assert "second_agent" in str(parsed_toml["agents"])
            
            # Verify router configuration is present
            assert "hand_off" in content
            assert "second_agent" in content
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_load_multi_agent_flock_from_toml(self, multi_agent_flock):
        """Test loading a multi-agent Flock from TOML."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file first
            multi_agent_flock.save_to_toml_file(file_path)
            
            # Load from TOML file
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Verify agents were loaded
            assert "first_agent" in loaded_flock.agents
            assert "second_agent" in loaded_flock.agents
            
            # Verify router was loaded and configured correctly
            first_agent = loaded_flock.agents["first_agent"]
            assert isinstance(first_agent.handoff_router, DefaultRouter)
            assert first_agent.handoff_router.config.hand_off == "second_agent"
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_save_complex_flock_to_toml(self, complex_flock):
        """Test saving a complex Flock to TOML."""
        # This test will fail until save_to_toml_file is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            complex_flock.save_to_toml_file(file_path)
            
            # Verify file exists
            assert file_path.exists()
            
            # Read the file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Parse the TOML
            parsed_toml = toml.loads(content)
            
            # Verify Flock configuration
            assert parsed_toml["model"] == "openai/gpt-4o"
            assert parsed_toml["enable_logging"] is True
            
            # Verify agents section
            assert "agents" in parsed_toml
            assert "tool_agent" in str(parsed_toml["agents"])
            assert "standard_agent" in str(parsed_toml["agents"])
            
            # Verify tools section
            assert "tools" in parsed_toml or "registry" in parsed_toml
            assert "sample_tool" in content or "global_sample_tool" in content
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_load_complex_flock_from_toml(self, complex_flock):
        """Test loading a complex Flock from TOML."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file first
            complex_flock.save_to_toml_file(file_path)
            
            # Load from TOML file
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Verify Flock configuration
            assert loaded_flock.model == complex_flock.model
            assert loaded_flock.enable_logging == complex_flock.enable_logging
            
            # Verify agents were loaded
            assert "tool_agent" in loaded_flock.agents
            assert "standard_agent" in loaded_flock.agents
            
            # Verify custom evaluator was loaded
            tool_agent = loaded_flock.agents["tool_agent"]
            assert isinstance(tool_agent.evaluator, TestEvaluator)
            
            # Verify tools were loaded
            assert tool_agent.tools is not None
            assert len(tool_agent.tools) > 0
            assert tool_agent.tools[0](5) == 10  # sample_tool(5) should return 10
            
            # Verify registry tools were loaded
            assert "global_sample_tool" in loaded_flock.registry.tools
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_manual_flock_creation(self):
        """Test loading a Flock from a manually created TOML file."""
        # This test will fail until load_from_toml_file is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
            
            # Create a manual TOML configuration
            manual_toml = """
            # Flock System Configuration
            # A simple manually created flock system
            
            model = "openai/gpt-4o"
            enable_logging = true
            
            # Agent definitions
            [agents.manual_agent]
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
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Verify Flock properties
            assert loaded_flock.model == "openai/gpt-4o"
            assert loaded_flock.enable_logging is True
            
            # Verify agent was loaded
            assert "manual_agent" in loaded_flock.agents
            manual_agent = loaded_flock.agents["manual_agent"]
            assert manual_agent.name == "manual_agent"
            assert manual_agent.description == "A manually created agent"
            assert manual_agent.input == "query: str | The query to process"
            assert manual_agent.output == "result: str | The processed result"
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_flock_with_context_values(self):
        """Test saving and loading a Flock with context values."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        # Create a flock with context values
        flock = Flock(model="openai/gpt-4o")
        
        # Add an agent
        agent = FlockAgent(
            name="test_agent",
            model="openai/gpt-4o",
            description="A test agent",
            input="query",
            output="result",
        )
        flock.add_agent(agent)
        
        # Set context values
        flock.context.set("test_key", "test_value")
        flock.context.set("number", 42)
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            flock.save_to_toml_file(file_path)
            
            # Load from TOML file
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Verify context values were preserved
            assert loaded_flock.context.get("test_key") == "test_value"
            assert loaded_flock.context.get("number") == 42
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_flock_with_start_agent(self):
        """Test saving and loading a Flock with start agent and input specified."""
        # This test will fail until save_to_toml_file and load_from_toml_file are implemented
        
        # Create a flock
        flock = Flock(model="openai/gpt-4o")
        
        # Add agents
        agent1 = FlockAgent(
            name="first_agent",
            model="openai/gpt-4o",
            input="query",
            output="result",
        )
        agent2 = FlockAgent(
            name="second_agent",
            model="openai/gpt-4o",
            input="result",
            output="final_result",
        )
        flock.add_agent(agent1)
        flock.add_agent(agent2)
        
        # Set start agent and input
        start_input = {"query": "test query"}
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file with start_agent and input specified
            flock.save_to_toml_file(file_path, start_agent="first_agent", input=start_input)
            
            # Load from TOML file
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Verify start_agent and input were preserved
            assert loaded_flock.start_agent == "first_agent"
            assert loaded_flock.input == start_input
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_flock_toml_comments(self, simple_flock):
        """Test that Flock TOML files include helpful comments."""
        # This test will fail until save_to_toml_file is implemented with comments
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            simple_flock.save_to_toml_file(file_path)
            
            # Read the file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Verify comments are included
            assert "# Flock System" in content
            assert "# " in content  # At least some comment lines
            
            # Check for section comments
            sections = ["agents", "tools", "registry", "context"]
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

    def test_error_handling(self):
        """Test error handling for invalid Flock TOML input."""
        # This test will fail until proper error handling is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
            
            # Create an invalid TOML configuration (malformed agent section)
            invalid_toml = """
            # Invalid Flock configuration
            model = "openai/gpt-4o"
            
            # Malformed agent section (missing required fields)
            [agents.invalid_agent]
            # Missing name and other required fields
            """
            
            # Write to file
            with open(file_path, "w") as f:
                f.write(invalid_toml)
        
        try:
            # Should raise an exception on invalid configuration
            with pytest.raises(Exception):
                Flock.load_from_toml_file(file_path)
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path) 