"""Tests for enhanced serialization with type and component definitions."""
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from flock.core import Flock, FlockFactory
from flock.core.flock_registry import flock_type


# Define a custom type for testing
@flock_type
class TestPerson(BaseModel):
    """Test person model for serialization tests."""
    name: str
    age: int
    role: Literal["admin", "user", "guest"]
    bio: str = ""

@flock_type
class TestCompany(BaseModel):
    """Test company model for serialization tests."""
    name: str
    industry: str
    employees: int


def test_serialization_with_custom_type():
    """Test serialization with custom type definitions."""
    # Create a test Flock with an agent using the custom type
    flock = Flock(name="test_flock")
    
    # Create an agent that uses TestPerson in its output
    agent = FlockFactory.create_default_agent(
        name="person_agent",
        input="query: str",
        output="result: TestPerson",
    )
    flock.add_agent(agent)
    
    # Create a temporary file for the YAML
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as temp_file:
        yaml_path = temp_file.name
    
    try:
        # Serialize the Flock to YAML
        flock.to_yaml_file(yaml_path)
        
        # Read the YAML to verify it includes type definitions
        yaml_content = Path(yaml_path).read_text()
        
        # Check that type definitions are included
        assert "types:" in yaml_content
        assert "TestPerson:" in yaml_content
        
        # Check that component definitions are included
        assert "components:" in yaml_content
        assert "DeclarativeEvaluator:" in yaml_content
        
        # Load the Flock back from YAML
        loaded_flock = Flock.load_from_file(yaml_path)
        
        # Verify the loaded Flock structure
        assert loaded_flock.name == "test_flock"
        assert "person_agent" in loaded_flock.agents
        assert loaded_flock.agents["person_agent"].output == "result: TestPerson"
        
        # Try running the loaded Flock (this will validate the TestPerson type is available)
        # Just a basic smoke test - not testing actual output
        result = loaded_flock.run(
            start_agent="person_agent",
            input={"query": "Get a test person"},
        )
        
        # Verify result contains a TestPerson
        assert hasattr(result, "result")
        
    finally:
        # Clean up the temporary file
        if os.path.exists(yaml_path):
            os.unlink(yaml_path)


def test_serialization_with_multiple_types():
    """Test serialization with multiple custom types."""
    # Define another custom type for testing
    
        
    # Create a test Flock with agents using both custom types
    flock = Flock(name="multi_type_flock")
    
    # Create agents that use both custom types
    person_agent = FlockFactory.create_default_agent(
        name="person_agent",
        input="query: str",
        output="result: TestPerson",
    )
    flock.add_agent(person_agent)
    
    company_agent = FlockFactory.create_default_agent(
        name="company_agent",
        input="industry: str",
        output="result: TestCompany",
    )
    flock.add_agent(company_agent)
    
    # Create a temporary file for the YAML
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as temp_file:
        yaml_path = temp_file.name
    
    try:
        # Serialize the Flock to YAML
        flock.to_yaml_file(yaml_path)
        
        # Read the YAML to verify it includes both type definitions
        yaml_content = Path(yaml_path).read_text()
        print(yaml_content)
        
        # Check that both type definitions are included
        assert "TestPerson:" in yaml_content
        assert "TestCompany:" in yaml_content
        
        # Load the Flock back from YAML
        loaded_flock = Flock.load_from_file(yaml_path)
        
        # Verify both agents are present
        assert "person_agent" in loaded_flock.agents
        assert "company_agent" in loaded_flock.agents
        
    finally:
        # Clean up the temporary file
        if os.path.exists(yaml_path):
            os.unlink(yaml_path) 