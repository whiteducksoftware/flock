# Flock Enhanced Serialization

Flock provides a powerful serialization system that allows you to save your Flock instances to various formats including YAML, JSON, and MsgPack, and then load them back in another environment.

## Self-Contained Serialization

The enhanced serialization system makes Flock configurations fully portable by including:

1. **Type Definitions** - Custom data models used in agent signatures
2. **Component Definitions** - Evaluators, modules, routers used in the Flock
3. **Dependency Information** - Required packages and versions
4. **Tool Definitions** - Callable functions used by agents as tools

This means you can share a Flock YAML file with someone else, and they can load it without needing to have all the same custom types pre-defined in their code.

## Serializing a Flock to YAML

```python
from flock.core import Flock, FlockFactory
from flock.core.flock_registry import flock_type, flock_tool
from pydantic import BaseModel
from typing import Literal

# Define a custom type
@flock_type
class Person(BaseModel):
    name: str
    age: int
    role: Literal["admin", "user", "guest"]

# Define a custom tool
@flock_tool
def get_person_details(person_id: str) -> Person:
    """Get details about a person."""
    # Implementation...
    return Person(name="John Doe", age=30, role="user")

# Create a Flock with an agent that uses the custom type and tool
flock = Flock(name="my_flock")
agent = FlockFactory.create_default_agent(
    name="person_agent",
    input="query: str",
    output="result: Person",
    tools=[get_person_details]
)
flock.add_agent(agent)

# Save to YAML - includes type and tool definitions
flock.to_yaml_file("my_flock.yaml")
```

The resulting YAML file will include:

```yaml
model: openai/gpt-4o
enable_temporal: false
name: my_flock
types:
  Person:
    module_path: your_module
    type: pydantic.BaseModel
    schema:
      properties:
        name:
          type: string
        age:
          type: integer
        role:
          type: string
          enum: [admin, user, guest]
      required: [name, age, role]
    imports:
      - from your_module import Person
components:
  DeclarativeEvaluator:
    type: flock_component
    module_path: flock.evaluators.declarative.declarative_evaluator
    description: Standard evaluator for declarative agent definitions
  
  # Tool definition
  get_person_details:
    type: flock_callable
    module_path: your_module
    file_path: /path/to/your_module.py
    description: Get details about a person.
agents:
  person_agent:
    name: person_agent
    # ... agent definition ...
    tools:
    - get_person_details  # Simple function name reference
dependencies:
  - pydantic>=2.0.0
  - flock-framework>=1.0.0
```

## Loading a Flock from YAML

Loading a Flock from a YAML file is straightforward:

```python
from flock.core import Flock

# Load from YAML - automatically recreates types and components
loaded_flock = Flock.load_from_file("my_flock.yaml")

# Run the loaded Flock
result = loaded_flock.run(
    start_agent="person_agent",
    input={"query": "Get a person"},
)

# The result.result will be a Person object
print(f"Name: {result.result.name}, Age: {result.result.age}")
```

## How Type Recreation Works

When loading a YAML file:

1. **Type Detection**: The system first processes the `types` section
2. **Import Attempt**: It attempts to import the types from their original modules
3. **Dynamic Creation**: If import fails, it creates the types dynamically:
   - For Pydantic models: Uses `create_model` to recreate the model from schema
   - For dataclasses: Uses `make_dataclass` to recreate the class structure
4. **Registry Integration**: All types are registered in the FlockRegistry
5. **Component Registration**: Component classes are imported and registered
6. **Tool Registration**: Callable functions are imported and registered

## Tool Serialization

Tools are now serialized using a new format that improves readability while maintaining all necessary information:

### How Tool Serialization Works

1. **In Agent Definition**: Tools are referenced by simple function name in the agent's `tools` list
2. **In Components Section**: Full tool definitions are stored in the `components` section with:
   - `type: flock_callable` - Identifies it as a callable function
   - `module_path` - The Python module containing the function
   - `file_path` - The actual file system path for direct loading
   - `description` - The docstring or description of the tool

### Advantages

1. **Readability**: Tool lists in agent definitions are simpler and more readable
2. **Consistency**: Tools follow the same pattern as other components
3. **Self-Documentation**: Tools include their descriptions as well as paths
4. **Direct Loading**: Tools can be loaded directly from file paths when needed

## Supported Formats

Flock supports multiple serialization formats:

- **YAML**: Human-readable configuration (recommended)
- **JSON**: For compatibility with web APIs and other systems
- **MsgPack**: Binary format for efficient storage and transmission
- **Pickle**: For complete object graphs (use with caution)

## File Extension Detection

The `load_from_file` method automatically detects the file format based on extension:

```python
# These all work based on file extension
flock = Flock.load_from_file("my_flock.yaml")  # YAML
flock = Flock.load_from_file("my_flock.json")  # JSON
flock = Flock.load_from_file("my_flock.msgpack")  # MsgPack
flock = Flock.load_from_file("my_flock.pkl")  # Pickle
```

## Best Practices

- **Use YAML** for most use cases - it's human-readable and self-documenting
- **Register types** with `@flock_type` decorator to ensure they're properly tracked
- **Register tools** with `@flock_tool` decorator for better serialization
- **Add docstrings** to tools to improve their serialized descriptions
- **Test serialization** in your CI/CD pipeline to ensure portability
- **Include docstrings** in your custom types to improve generated documentation

## Limitations

- Complex custom methods on types will not be preserved in dynamic recreation
- Custom validation logic may need to be reimplemented separately
- Some advanced type annotations might not serialize perfectly
- External resources (like API credentials) will need separate configuration

## Additional Resources

- See the `examples/01_introduction/05_typed_output2.py` for a complete example
- Check the `examples/01_introduction/08_serialization.py` for tools serialization
- Check the API documentation for detailed method signatures 