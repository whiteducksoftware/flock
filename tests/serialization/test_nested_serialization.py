"""Tests for serialization with nested type structures."""
import os
import tempfile
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from flock.core import Flock, FlockFactory
from flock.core.flock_registry import flock_type


# Define nested custom types for testing
@flock_type
class Address(BaseModel):
    """Address model for nested serialization test."""
    street: str
    city: str
    zip_code: str


@flock_type
class Contact(BaseModel):
    """Contact information for nested serialization test."""
    email: str
    phone: str
    address: Address  # Nested model


@flock_type
class Company(BaseModel):
    """Company model with nested types for serialization test."""
    name: str
    industry: str
    headquarters: Address  # Nested model
    contacts: List[Contact]  # List of nested models
    departments: Dict[str, List[str]]  # Dictionary with nested list


def test_nested_type_serialization():
    """Test serialization with nested type structures."""
    # Create a test Flock with an agent using nested types
    flock = Flock(name="nested_types_flock")
    
    # Create an agent that uses Company in its output (which contains nested types)
    agent = FlockFactory.create_default_agent(
        name="company_agent",
        input="query: str",
        output="result: Company",
    )
    flock.add_agent(agent)
    
    # Create a temporary file for the YAML
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as temp_file:
        yaml_path = temp_file.name
    
    try:
        # Serialize the Flock to YAML
        flock.to_yaml_file(yaml_path)
        
        # Read the YAML to verify it includes nested type definitions
        yaml_content = Path(yaml_path).read_text()
        
        # Check that all type definitions are included
        assert "Company:" in yaml_content
        assert "Address:" in yaml_content  
        assert "Contact:" in yaml_content
        
        # Load the Flock back from YAML
        loaded_flock = Flock.load_from_file(yaml_path)
        
        # Verify the loaded Flock can be used
        assert "company_agent" in loaded_flock.agents
        assert loaded_flock.agents["company_agent"].output == "result: Company"
        
        # Try running the loaded Flock (this will validate all nested types are available)
        result = loaded_flock.run(
            start_agent="company_agent",
            input={"query": "Get a test company"},
        )
        
        # Basic validation that the result has the expected structure
        company = result.result
        assert hasattr(company, "name")
        assert hasattr(company, "headquarters")
        assert hasattr(company.headquarters, "street")
        assert isinstance(company.contacts, list)
        if company.contacts:
            assert hasattr(company.contacts[0], "address")
            assert hasattr(company.contacts[0].address, "city")
        
    finally:
        # Clean up the temporary file
        if os.path.exists(yaml_path):
            os.unlink(yaml_path) 