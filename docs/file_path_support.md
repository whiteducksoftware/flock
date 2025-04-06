# File Path Support in Flock

This document explains the file path support feature in Flock, which allows components to be loaded directly from file system paths rather than requiring module imports.

## Overview

The Flock framework now supports dual-path component serialization and loading:

1. **Module Paths**: Traditional Python import paths (`module.submodule.ClassName`)
2. **File Paths**: Direct file system paths (`/path/to/file.py`)

This enhancement improves portability, simplifies CLI usage, and makes development more flexible.

## Usage

### Serializing with File Paths

When serializing a Flock, the framework automatically includes file paths for components when available:

```python
from flock.core.flock import Flock
from my_components import GreetingModule

# Create and configure your Flock
flock = Flock(name="my_flock")
# ... add agents with components ...

# Serialize to YAML with file paths included
flock.to_yaml_file("my_flock.yaml")
```

### Loading with File Path Fallback

When loading a Flock, the framework tries module paths first, then falls back to file paths if available:

```python
from flock.core.flock import Flock

# Load the Flock - will try module paths first, then file paths
flock = Flock.load_from_file("my_flock.yaml")
```

### Callable/Tool Path Support

Callable tools now use the same file path mechanism as components:

```python
from flock.core import Flock, FlockFactory, flock_tool

@flock_tool
def get_data(query: str) -> dict:
    """Get data from an external source."""
    # Implementation...
    return {"result": "data"}

# Create a Flock with an agent that uses the tool
flock = Flock(name="my_flock")
agent = FlockFactory.create_default_agent(
    name="data_agent",
    tools=[get_data]
)
flock.add_agent(agent)

# Serialize to YAML - includes the tool with its file path
flock.to_yaml_file("my_flock.yaml")
```

The YAML output will include:

```yaml
components:
  # ... other components ...
  get_data:
    type: flock_callable
    module_path: __main__
    file_path: /path/to/your_file.py
    description: Get data from an external source.

agents:
  data_agent:
    # ... agent configuration ...
    tools:
    - get_data
```

### CLI Auto-Registration

The CLI includes an auto-registration scanner that can detect components in directories and register them with file paths:

1. Run the Flock CLI: `python -m flock`
2. Select "Registry Management"
3. Choose "Auto-Registration Scanner"
4. Select directories to scan

### Working with File Paths Directly

You can also work with file paths directly using the utility functions:

```python
from flock.core.util.file_path_utils import load_class_from_file, load_callable_from_file

# Load a class directly from a file path
GreetingModule = load_class_from_file("/path/to/greeting_module.py", "GreetingModule")

# Load a callable function directly from a file path
get_data = load_callable_from_file("/path/to/tools.py", "get_data")
```

## Benefits

1. **CLI & Direct Execution**: Components can be loaded directly from file paths, enabling CLI usage without package installation
2. **Development Flexibility**: Easier development workflow using local files and paths
3. **Improved Portability**: Flock configurations can be shared with both module paths and file paths
4. **Graceful Fallbacks**: When module imports fail, the system attempts to load from file paths
5. **Tool Integration**: Callable tools are now serialized with their file paths, allowing for direct loading

## Example

See the complete example in `examples/file_path_demo.py` that demonstrates:

1. Creating a custom component
2. Serializing to YAML with file paths
3. Loading back using file path fallback
4. Testing the loaded components

## Technical Details

The file path support is implemented through:

1. **Registry Enhancement**: The `FlockRegistry` maintains file path information for components and callables
2. **Serialization**: Component and callable definitions include both module and file paths
3. **Deserialization**: A fallback mechanism tries file paths when module imports fail
4. **Utilities**: The `file_path_utils.py` module provides helper functions for loading from files

## Callable Tool Format

In the serialized YAML, callable tools now appear in two places:

1. In the agent's `tools` list, using just the function name:
   ```yaml
   tools:
   - get_mobile_number
   - fetch_data
   ```

2. In the `components` section with full path information:
   ```yaml
   components:
     get_mobile_number:
       type: flock_callable
       module_path: __main__
       file_path: /path/to/file.py
       description: A tool that returns a mobile number to a name.
   ```

This format improves readability while maintaining all necessary path information for loading.

The implementation is backward-compatible with existing Flock configurations. 