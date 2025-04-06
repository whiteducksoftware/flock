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

### CLI Auto-Registration

The CLI includes an auto-registration scanner that can detect components in directories and register them with file paths:

1. Run the Flock CLI: `python -m flock`
2. Select "Registry Management"
3. Choose "Auto-Registration Scanner"
4. Select directories to scan

### Working with File Paths Directly

You can also work with file paths directly using the utility functions:

```python
from flock.core.util.file_path_utils import load_class_from_file

# Load a class directly from a file path
GreetingModule = load_class_from_file("/path/to/greeting_module.py", "GreetingModule")
```

## Benefits

1. **CLI & Direct Execution**: Components can be loaded directly from file paths, enabling CLI usage without package installation
2. **Development Flexibility**: Easier development workflow using local files and paths
3. **Improved Portability**: Flock configurations can be shared with both module paths and file paths
4. **Graceful Fallbacks**: When module imports fail, the system attempts to load from file paths

## Example

See the complete example in `examples/file_path_demo.py` that demonstrates:

1. Creating a custom component
2. Serializing to YAML with file paths
3. Loading back using file path fallback
4. Testing the loaded components

## Technical Details

The file path support is implemented through:

1. **Registry Enhancement**: The `FlockRegistry` maintains a `_component_file_paths` dictionary
2. **Serialization**: Component definitions include both module and file paths
3. **Deserialization**: A fallback mechanism tries file paths when module imports fail
4. **Utilities**: The `file_path_utils.py` module provides helper functions

The implementation is backward-compatible with existing Flock configurations. 