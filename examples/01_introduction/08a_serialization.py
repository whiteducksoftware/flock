"""
Demo of File Path Support in Flock Serialization

This example demonstrates:
1. Creating a custom component class
2. Creating a Flock with that component
3. Serializing it to YAML with file paths
4. Loading it back using file path fallback

Usage:
    python file_path_demo.py
"""

from typing import Dict

from pydantic import BaseModel, Field

from flock.core import (
    Flock,
    FlockFactory,
    FlockModule,
    FlockAgent,
    FlockContext,
    FlockModuleConfig,
    flock_type,
    flock_component,
    flock_tool,
)



# Define a simple module
# The config defines a language
class GreetingModuleConfig(FlockModuleConfig):
    language: str = Field(default="en")

# The module has a greeting dictionary
# and will replace the result["greeting"] with the appropriate greeting
# decoraters add the decorated entity to the registry
@flock_component
class GreetingModule(FlockModule):
    """A simple module that generates greetings."""
    config: GreetingModuleConfig = Field(default_factory=GreetingModuleConfig)
    greetings: dict[str, str] = Field(default_factory=dict)

    # The initialize method is called when the agent is initialized
    async def initialize(self, agent: FlockAgent, inputs: Dict, context: FlockContext) -> None:
        """Initialize the module."""
        self.greetings = {
            "en": "Hello",
            "es": "Hola",
            "fr": "Bonjour",
            "de": "Guten Tag",
        }

    # The post_evaluate method is called after the agent has evaluated
    # we modify the result before it is returned
    async def post_evaluate(self, agent: FlockAgent, inputs: Dict, result: Dict, context: FlockContext) -> Dict:
        """Post-evaluate the module."""
        name = inputs.get("name", "World")
        greeting = self.greetings.get(self.config.language, self.greetings["en"])
        result["greeting"] = f"{greeting}, {name}!"
        return {
            "greeting": f"{greeting}, {name}!"
        }
    
    

# Define a custom type
# The type is added to the registry
@flock_type
class Person(BaseModel):
    """A simple person model."""
    name: str = Field(description="The name of the person IN ALL CAPS")
    age: int
    languages: list[str] = Field(default_factory=list)


# Define a tool
# The tool is added to the registry
@flock_tool
def get_mobile_number(name: str) -> str:
    """A tool that returns a mobile number to a name."""
    return f"1234567890"


def serialization():
    """Run the serialization demo."""
    
    # Create a Flock instance
    flock = Flock(name="file_path_demo", enable_logging=True)

    greeting_module = GreetingModule(name="greeting_module", config=GreetingModuleConfig(language="es"))
    
    # Create an agent using our GreetingModule
    agent = FlockFactory.create_default_agent(
        name="greeter",
        input="name: str", 
        output="greeting: str, mobile_number: str",
        tools=[get_mobile_number]
    )
    
    agent.add_module(greeting_module)
    # Add the agent to the Flock
    flock.add_agent(agent)
    
    # Create another agent with a custom type
    person_agent = FlockFactory.create_default_agent(
        name="person_creator",
        input="name: str, age: int, languages: list[str]",
        output="person: Person"
    )
    flock.add_agent(person_agent)

    print(f"\nSerializing Flock to: file_path_demo.flock.yaml")
    flock.to_yaml_file("examples/01_introduction/data/file_path_demo.flock.yaml", path_type="relative")

    # Display the YAML content
    print("\nYAML Content:")
    with open("examples/01_introduction/data/file_path_demo.flock.yaml", "r") as f:
        yaml_content = f.read()
        print(yaml_content)

    


if __name__ == "__main__":
    serialization() 