"""Integration tests for TOML serialization in the Flock framework."""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
import toml

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator
from flock.core.flock_factory import FlockFactory
from flock.routers.default.default_router import DefaultRouter, DefaultRouterConfig


# Simple tool for testing
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


# Test evaluator that returns predictable results
class TestEvaluator(FlockEvaluator):
    """Test evaluator that returns predefined results."""
    
    name: str = "test_evaluator"
    
    async def evaluate(self, agent, inputs, tools=None):
        """Return a predefined result based on the input."""
        if "query" in inputs:
            return {"result": f"Processed: {inputs['query']}"}
        elif "intermediate_result" in inputs:
            return {"final_result": f"Final: {inputs['intermediate_result']}"}
        return {"result": "Default result"}


@pytest.fixture
def workflow_flock():
    """Create a test flock with a simple workflow."""
    flock = Flock(model="openai/gpt-4o")
    
    # First agent processes queries
    processor = FlockAgent(
        name="processor",
        model="openai/gpt-4o",
        description="Processes the initial query",
        input="query: str | The initial query",
        output="result: str | The processed result",
        tools=[add_numbers],
    )
    processor.evaluator = TestEvaluator()
    
    # Second agent finalizes results
    finalizer = FlockAgent(
        name="finalizer",
        model="openai/gpt-4o",
        description="Finalizes the processed result",
        input="intermediate_result: str | The processed result",
        output="final_result: str | The final result",
    )
    finalizer.evaluator = TestEvaluator()
    
    # Set up the workflow
    processor.handoff_router = DefaultRouter(
        config=DefaultRouterConfig(hand_off="finalizer")
    )
    
    # Add agents to the flock
    flock.add_agent(processor)
    flock.add_agent(finalizer)
    
    # Add a global tool
    flock.add_tool("add", add_numbers)
    
    return flock


class TestTOMLIntegration:
    """Integration tests for TOML serialization functionality."""

    def test_end_to_end_workflow(self, workflow_flock):
        """Test a complete workflow with serialization and deserialization."""
        # This test will fail until TOML serialization is fully implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save the flock to TOML
            test_input = {"query": "test query"}
            workflow_flock.save_to_toml_file(
                file_path, 
                start_agent="processor",
                input=test_input
            )
            
            # Load the flock from TOML
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Run the loaded workflow
            result = loaded_flock.run()
            
            # Verify the workflow executed correctly
            assert "final_result" in result
            assert result["final_result"] == "Final: Processed: test query"
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_factory_with_toml(self):
        """Test creating an agent with the factory and serializing to TOML."""
        # This test will fail until TOML serialization is fully implemented
        
        # Create an agent with the factory
        agent = FlockFactory.create_default_agent(
            name="factory_agent",
            model="openai/gpt-4o",
            description="An agent created with the factory",
            input="query: str | The query to process",
            output="result: str | The processed result",
        )
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save to TOML file
            agent.save_to_toml_file(file_path)
            
            # Load from TOML file
            loaded_agent = FlockAgent.load_from_toml_file(file_path)
            
            # Verify properties match
            assert loaded_agent.name == agent.name
            assert loaded_agent.description == agent.description
            assert loaded_agent.input == agent.input
            assert loaded_agent.output == agent.output
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_manual_editing_workflow(self, workflow_flock):
        """Test manually editing a TOML file and loading it back."""
        # This test will fail until TOML serialization is fully implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save the flock to TOML
            workflow_flock.save_to_toml_file(file_path)
            
            # Read the file content
            with open(file_path, "r") as f:
                content = f.read()
            
            # Modify the TOML content
            modified_content = content.replace(
                "description = \"Processes the initial query\"",
                "description = \"MODIFIED: Processes the initial query\""
            )
            
            # Write back the modified content
            with open(file_path, "w") as f:
                f.write(modified_content)
            
            # Load the modified flock
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Verify the modification was applied
            assert loaded_flock.agents["processor"].description == "MODIFIED: Processes the initial query"
            
            # Run the workflow to ensure it still works
            result = loaded_flock.run(
                start_agent="processor",
                input={"query": "test query after modification"}
            )
            
            # Verify the workflow executed correctly
            assert "final_result" in result
            assert "Final: Processed: test query after modification" in result["final_result"]
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_json_toml_conversion(self, workflow_flock):
        """Test converting between JSON and TOML formats."""
        # This test will fail until format conversion is implemented
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as json_file:
            json_path = Path(json_file.name)
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as toml_file:
            toml_path = Path(toml_file.name)
        
        try:
            # Save to JSON
            workflow_flock.save_to_file(json_path)
            
            # Load from JSON and save to TOML
            json_flock = Flock.load_from_file(json_path)
            json_flock.save_to_toml_file(toml_path)
            
            # Load from TOML
            toml_flock = Flock.load_from_toml_file(toml_path)
            
            # Verify agents are preserved in both directions
            assert "processor" in toml_flock.agents
            assert "finalizer" in toml_flock.agents
            
            # Verify the workflow still works
            result = toml_flock.run(
                start_agent="processor",
                input={"query": "testing format conversion"}
            )
            
            # Verify the workflow executed correctly
            assert "final_result" in result
            assert "Final: Processed: testing format conversion" in result["final_result"]
            
        finally:
            # Clean up
            if json_path.exists():
                os.unlink(json_path)
            if toml_path.exists():
                os.unlink(toml_path)

    def test_create_agent_from_scratch_toml(self):
        """Test creating an agent from scratch in TOML and loading it."""
        # This test will fail until TOML serialization is fully implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
            
            # Create a manual TOML configuration
            manual_toml = """
            # FlockAgent: scratch_agent
            # This is a agent created entirely from scratch in TOML

            name = "scratch_agent"
            model = "openai/gpt-4o"
            description = "An agent created from scratch in TOML"
            input = "query: str | The query to process"
            output = "result: str | The processed result"
            use_cache = true

            # Define a custom evaluator
            [evaluator]
            type = "NaturalLanguageEvaluator"
            system_prompt = "You are a helpful assistant that processes queries."
            
            # No modules or tools in this simple example
            """
            
            # Write to file
            with open(file_path, "w") as f:
                f.write(manual_toml)
        
        try:
            # Load from TOML file
            agent = FlockAgent.load_from_toml_file(file_path)
            
            # Verify properties
            assert agent.name == "scratch_agent"
            assert agent.model == "openai/gpt-4o"
            assert agent.description == "An agent created from scratch in TOML"
            assert agent.input == "query: str | The query to process"
            assert agent.output == "result: str | The processed result"
            assert agent.use_cache is True
            
            # Create a simple flock
            flock = Flock(model="openai/gpt-4o")
            flock.add_agent(agent)
            
            # Verify the agent works in the flock
            agent.evaluator = TestEvaluator()  # Use test evaluator for predictable results
            result = flock.run(
                start_agent=agent,
                input={"query": "testing scratch-created agent"}
            )
            
            # Verify execution
            assert "result" in result
            assert result["result"] == "Processed: testing scratch-created agent"
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    @pytest.mark.asyncio
    async def test_async_execution_with_toml_agents(self, workflow_flock):
        """Test async execution of agents loaded from TOML."""
        # This test will fail until TOML serialization is fully implemented
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as temp_file:
            file_path = Path(temp_file.name)
        
        try:
            # Save the flock to TOML
            workflow_flock.save_to_toml_file(file_path)
            
            # Load the flock from TOML
            loaded_flock = Flock.load_from_toml_file(file_path)
            
            # Run the loaded workflow asynchronously
            result = await loaded_flock.run_async(
                start_agent="processor",
                input={"query": "async test"}
            )
            
            # Verify the workflow executed correctly
            assert "final_result" in result
            assert result["final_result"] == "Final: Processed: async test"
            
        finally:
            # Clean up
            if file_path.exists():
                os.unlink(file_path)

    def test_performance_comparison(self, workflow_flock):
        """Compare performance between JSON and TOML serialization."""
        # This test will fail until both serialization methods are implemented
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as json_file:
            json_path = Path(json_file.name)
        
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as toml_file:
            toml_path = Path(toml_file.name)
        
        try:
            # Measure JSON serialization time
            import time
            
            # JSON serialization
            json_start = time.time()
            workflow_flock.save_to_file(json_path)
            json_save_time = time.time() - json_start
            
            json_load_start = time.time()
            Flock.load_from_file(json_path)
            json_load_time = time.time() - json_load_start
            
            # TOML serialization
            toml_start = time.time()
            workflow_flock.save_to_toml_file(toml_path)
            toml_save_time = time.time() - toml_start
            
            toml_load_start = time.time()
            Flock.load_from_toml_file(toml_path)
            toml_load_time = time.time() - toml_load_start
            
            # No specific assertions, just print for analysis
            # We're not testing for which is faster, just that both work
            print(f"JSON save: {json_save_time:.6f}s, load: {json_load_time:.6f}s")
            print(f"TOML save: {toml_save_time:.6f}s, load: {toml_load_time:.6f}s")
            
            # Verify both files exist and have content
            assert os.path.getsize(json_path) > 0
            assert os.path.getsize(toml_path) > 0
            
        finally:
            # Clean up
            if json_path.exists():
                os.unlink(json_path)
            if toml_path.exists():
                os.unlink(toml_path) 