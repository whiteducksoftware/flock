# Enhanced Flock Serialization Implementation

## Overview

We've implemented a comprehensive serialization system for the Flock framework that enables fully self-contained YAML exports. The key innovation is the inclusion of type definitions, component references, and dependencies directly in the serialized output, making Flock configurations portable across different environments.

## Problem Statement

Previously, when serializing a Flock to YAML, the configuration would reference custom types (like `RandomPerson`) without including their definitions. This meant that systems loading the YAML needed to already have these types defined, limiting portability.

Example issue:
```yaml
# Before: References type but doesn't define it
output: 'random_user_list: list[RandomPerson]'
```

## Solution Architecture

Our solution enhances the serialization process to create self-contained configurations by:

1. **Detecting Custom Types**: Analyzing agent input/output signatures to identify custom types
2. **Extracting Type Definitions**: Capturing full schema definitions of custom types
3. **Including Component References**: Documenting the modules that provide components
4. **Specifying Dependencies**: Listing required packages and versions

### Key Components

1. **Enhanced Serialization**:
   - `Flock.to_dict()`: Now extracts and includes types and components
   - Type extraction from signatures via `_extract_types_from_signature()`
   - Schema generation via Pydantic's `model_json_schema()`

2. **Enhanced Deserialization**:
   - `Flock.from_dict()`: First processes types, then components, then agents
   - Dynamic type recreation for missing types
   - Component registration from module paths

3. **Type Handling**:
   - Support for Pydantic models and dataclasses
   - Nested type structures via schema references
   - Generic types like List and Dict

4. **File Path Support**:
   - Storing both module paths and file system paths for components
   - Fallback mechanism that tries module import first, then file path loading
   - Flexibility for CLI and non-package environments

5. **Improved Tool Serialization** (NEW):
   - Tools are now serialized as simple function names in agent's tools list
   - Tools are included in the components section with type "flock_callable"
   - Better integrated with the component-based architecture

## Implementation Details

### Type Detection and Extraction

```python
def _extract_types_from_signature(self, signature: str) -> list[str]:
    """Extract type names from an input/output signature string."""
    # Basic type extraction from strings like "result: TypeName" or "list[TypeName]"
    custom_types = []
    
    # Look for type annotations (everything after ":")
    parts = signature.split(":")
    if len(parts) > 1:
        type_part = parts[1].strip()
        
        # Extract from list[Type]
        if "list[" in type_part:
            inner_type = type_part.split("list[")[1].split("]")[0].strip()
            if inner_type and not inner_type.lower() in ["str", "int", "float", "bool", "dict", "list"]:
                custom_types.append(inner_type)
        
        # Extract direct type references
        elif type_part and not type_part.lower() in ["str", "int", "float", "bool", "dict", "list"]:
            custom_types.append(type_part.split()[0])
            
    return custom_types
```

### Type Definition Extraction

```python
def _extract_type_definition(self, type_name: str, type_obj: type) -> dict[str, Any]:
    """Extract a definition for a custom type."""
    type_def = {
        "module_path": type_obj.__module__,
    }
    
    # Handle Pydantic models
    if hasattr(type_obj, "model_json_schema") and callable(getattr(type_obj, "model_json_schema")):
        type_def["type"] = "pydantic.BaseModel"
        try:
            schema = type_obj.model_json_schema()
            # Clean up schema to remove unnecessary fields
            if "title" in schema and schema["title"] == type_name:
                del schema["title"]
            type_def["schema"] = schema
        except Exception as e:
            logger.warning(f"Could not extract schema for Pydantic model {type_name}: {e}")
    
    # Handle dataclasses
    elif is_dataclass(type_obj):
        type_def["type"] = "dataclass"
        fields = {}
        for field_name, field in type_obj.__dataclass_fields__.items():
            fields[field_name] = {
                "type": str(field.type),
                "default": str(field.default) if field.default is not inspect.Parameter.empty else None
            }
        type_def["fields"] = fields
        
    # Handle other types
    else:
        type_def["type"] = "custom"
        
    # Extract import statement
    type_def["imports"] = [f"from {type_obj.__module__} import {type_name}"]
        
    return type_def
```

### Component Definition with File Paths

```python
def _get_component_definition(self, component_type: str) -> dict[str, Any]:
    """Get definition for a component type."""
    from flock.core.flock_registry import get_registry
    import inspect
    import os
    import sys
    
    registry = get_registry()
    component_def = {}
    
    try:
        # Try to get the component class from registry
        component_class = registry._components.get(component_type)
        if component_class:
            # Get the standard module path
            module_path = component_class.__module__
            
            # Get the actual file system path if possible
            file_path = None
            try:
                if hasattr(component_class, "__module__") and component_class.__module__:
                    module = sys.modules.get(component_class.__module__)
                    if module and hasattr(module, "__file__"):
                        file_path = os.path.abspath(module.__file__)
            except Exception:
                # If we can't get the file path, we'll just use the module path
                pass
            
            component_def = {
                "type": "flock_component",
                "module_path": module_path,
                "file_path": file_path,  # Include actual file system path
                "description": getattr(component_class, "__doc__", "").strip() or f"{component_type} component"
            }
    except Exception as e:
        logger.warning(f"Could not extract definition for component {component_type}: {e}")
        # Provide minimal information if we can't extract details
        component_def = {
            "type": "flock_component",
            "module_path": "unknown",
            "file_path": None,
            "description": f"{component_type} component (definition incomplete)"
        }
        
    return component_def
```

### Tool Callable Definition (NEW)

```python
def _get_callable_definition(self, callable_ref: str, func_name: str) -> dict[str, Any]:
    """Get definition for a callable reference.
    
    Args:
        callable_ref: The fully qualified path to the callable
        func_name: The simple function name (for display purposes)
    """
    import os
    import sys
    import inspect
    from flock.core.flock_registry import get_registry

    registry = get_registry()
    callable_def = {}

    try:
        # Try to get the callable from registry
        func = registry.get_callable(callable_ref)
        if func:
            # Get the standard module path
            module_path = func.__module__

            # Get the actual file system path if possible
            file_path = None
            try:
                if func.__module__ and func.__module__ != "builtins":
                    module = sys.modules.get(func.__module__)
                    if module and hasattr(module, "__file__"):
                        file_path = os.path.abspath(module.__file__)
            except Exception:
                # If we can't get the file path, just use the module path
                pass

            # Get the docstring for description
            docstring = inspect.getdoc(func) or f"Callable function {func_name}"
            
            callable_def = {
                "type": "flock_callable",
                "module_path": module_path,
                "file_path": file_path,
                "description": docstring.strip(),
            }
    except Exception as e:
        logger.warning(
            f"Could not extract definition for callable {callable_ref}: {e}"
        )
        # Provide minimal information
        callable_def = {
            "type": "flock_callable",
            "module_path": callable_ref.split(".")[0] if "." in callable_ref else "unknown",
            "file_path": None,
            "description": f"Callable {func_name} (definition incomplete)",
        }

    return callable_def
```

### Tool Serialization for Agents (NEW)

```python
# --- Serialize Tools (Callables) ---
if self.tools:
    logger.debug(f"Serializing {len(self.tools)} tools for agent '{self.name}'")
    serialized_tools = []
    for tool in self.tools:
        if callable(tool) and not isinstance(tool, type):
            path_str = FlockRegistry.get_callable_path_string(tool)
            if path_str:
                # Get just the function name from the path string
                # If it's a namespaced path like module.submodule.function_name
                # Just use the function_name part
                func_name = path_str.split(".")[-1]  
                serialized_tools.append(func_name)
                logger.debug(f"Added tool '{func_name}' to agent '{self.name}'")
            else:
                logger.warning(
                    f"Could not get path string for tool {tool} in agent '{self.name}'. Skipping."
                )
        else:
            logger.warning(f"Non-callable item found in tools list for agent '{self.name}': {tool}. Skipping.")
    if serialized_tools:
        data["tools"] = serialized_tools
```

### Extracting Tools for Component Registration (NEW)

```python
# Extract tool (callable) information from agent data
if "tools" in agent_data and agent_data["tools"]:
    logger.debug(f"Extracting tool information from agent '{name}': {agent_data['tools']}")
    # Get references to the actual tool objects
    tool_objs = agent_instance.tools if agent_instance.tools else []
    for i, tool_name in enumerate(agent_data["tools"]):
        if i < len(tool_objs):
            tool = tool_objs[i]
            if callable(tool) and not isinstance(tool, type):
                # Get the fully qualified name for registry lookup
                path_str = get_registry().get_callable_path_string(tool)
                if path_str:
                    logger.debug(f"Adding tool '{tool_name}' to components")
                    # Add definition using just the function name as the key
                    components[tool_name] = self._get_callable_definition(path_str, tool_name)
```

### Component Loading with File Path Fallback

```python
@classmethod
def _register_component_definitions(cls, component_defs: dict[str, Any]) -> None:
    """Register component definitions from serialized data."""
    from flock.core.flock_registry import get_registry
    import importlib
    import importlib.util
    import sys
    import os
    
    registry = get_registry()
    
    for component_name, component_def in component_defs.items():
        logger.debug(f"Registering component: {component_name}")
        component_type = component_def.get("type", "flock_component")
        
        try:
            # Handle callables differently than components
            if component_type == "flock_callable":
                # For callables, component_name is just the function name
                func_name = component_name
                module_path = component_def.get("module_path")
                file_path = component_def.get("file_path")
                logger.debug(f"Processing callable '{func_name}' from module '{module_path}', file: {file_path}")

                # Try direct import first
                if module_path:
                    try:
                        logger.debug(f"Attempting to import module: {module_path}")
                        module = importlib.import_module(module_path)
                        if hasattr(module, func_name):
                            callable_obj = getattr(module, func_name)
                            # Register with just the name for easier lookup
                            registry.register_callable(callable_obj, func_name)
                            logger.info(f"Registered callable with name: {func_name}")
                            # Also register with fully qualified path for compatibility
                            if module_path != "__main__":
                                full_path = f"{module_path}.{func_name}"
                                registry.register_callable(callable_obj, full_path)
                                logger.info(f"Also registered callable with full path: {full_path}")
                            logger.info(f"Successfully registered callable {func_name} from module {module_path}")
                            continue
                        else:
                            logger.warning(f"Function '{func_name}' not found in module {module_path}")
                    except ImportError:
                        logger.debug(f"Could not import module {module_path}, trying file path")
                
                # Try file path if module import fails
                if file_path and os.path.exists(file_path):
                    try:
                        logger.debug(f"Attempting to load file: {file_path}")
                        # Create a module name from file path
                        mod_name = f"{func_name}_module" 
                        spec = importlib.util.spec_from_file_location(mod_name, file_path)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[spec.name] = module
                            spec.loader.exec_module(module)
                            logger.debug(f"Successfully loaded module from file, searching for function '{func_name}'")
                            
                            # Look for the function in the loaded module
                            if hasattr(module, func_name):
                                callable_obj = getattr(module, func_name)
                                registry.register_callable(callable_obj, func_name)
                                logger.info(f"Successfully registered callable {func_name} from file {file_path}")
                            else:
                                logger.warning(f"Function {func_name} not found in file {file_path}")
                        else:
                            logger.warning(f"Could not create import spec for {file_path}")
                    except Exception as e:
                        logger.error(f"Error loading callable {func_name} from file {file_path}: {e}")
                
            # Handle regular components (existing code)
            else:
                # ... existing component loading code ...
```

### Dynamic Type Recreation

```python
@classmethod
def _create_pydantic_model(cls, type_name: str, type_def: dict[str, Any]) -> None:
    """Dynamically create a Pydantic model from a schema definition."""
    from pydantic import create_model
    
    schema = type_def.get("schema", {})
    
    try:
        # Extract field definitions from schema
        fields = {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        for field_name, field_schema in properties.items():
            # Determine the field type based on schema
            field_type = cls._get_type_from_schema(field_schema)
            
            # Determine if field is required
            default = ... if field_name in required else None
            
            # Add to fields dict
            fields[field_name] = (field_type, default)
        
        # Create the model
        DynamicModel = create_model(type_name, **fields)
        
        # Register it
        registry.register_type(DynamicModel, type_name)
        logger.info(f"Created and registered Pydantic model: {type_name}")
        
    except Exception as e:
        logger.error(f"Failed to create Pydantic model {type_name}: {e}")
```

## Nested Type Support

One of the advanced features is support for complex nested type structures:

```python
# Define nested custom types
@flock_type
class Address(BaseModel):
    street: str
    city: str
    zip_code: str

@flock_type
class Contact(BaseModel):
    email: str
    phone: str
    address: Address  # Nested model

@flock_type
class Company(BaseModel):
    name: str
    headquarters: Address  # Nested model
    contacts: List[Contact]  # List of nested models
    departments: Dict[str, List[str]]  # Dictionary with nested list
```

The serialization correctly handles these nested structures by leveraging Pydantic's JSON schema generation, which includes:

1. Definitions for all nested types in the `$defs` section
2. References to these definitions using `$ref`
3. Proper representation of complex structures like lists and dictionaries

## Testing

We've implemented comprehensive tests:

1. **Basic Type Tests**: Verify serialization of simple custom types
2. **Multiple Type Tests**: Verify handling of multiple custom types in a Flock
3. **Nested Structure Tests**: Verify correct handling of complex nested type structures

All tests passed, confirming the robustness of our implementation.

## Example Output

The enhanced serialization produces YAMLs with this structure:

```yaml
# Main Flock configuration
name: my_flock
model: openai/gpt-4o
enable_temporal: false

# Types section with full definitions
types:
  RandomPerson:
    module_path: examples.01_introduction.05_typed_output2
    type: pydantic.BaseModel
    schema:
      properties:
        name:
          type: string
        age:
          type: integer
        # ... other properties
      required: [name, age, ...]
    imports:
      - from examples.01_introduction.05_typed_output2 import RandomPerson

# Component definitions with module paths AND file paths
components:
  DeclarativeEvaluator:
    type: flock_component
    module_path: flock.evaluators.declarative.declarative_evaluator
    file_path: /path/to/flock/evaluators/declarative/declarative_evaluator.py
    description: Standard evaluator for declarative agent definitions
  
  # Tool definition with flock_callable type (NEW)
  get_mobile_number:
    type: flock_callable
    module_path: __main__
    file_path: /path/to/file.py
    description: A tool that returns a mobile number to a name.
  
# Dependencies section
dependencies:
  - pydantic>=2.0.0
  - flock-framework>=1.0.0

# Agents section
agents:
  greeter:
    name: greeter
    # ... agent definition ...
    # Simple function names in tools list (NEW)
    tools:
    - get_mobile_number
```

## Advantages of This Approach

1. **Portability**: Flock YAMLs are now self-contained and can be shared across systems
2. **Self-Documentation**: Type definitions serve as documentation
3. **Dynamic Recreation**: Types can be recreated dynamically even if not available in the target system
4. **Complex Type Support**: Works with nested structures, generics, and complex types
5. **Extensibility**: Architecture allows for additional type support in the future
6. **File Path Support**: Enables CLI use and non-package environments
7. **Tool Integration**: Tools are now properly integrated in the component system (NEW)

## Limitations and Future Work

1. **Custom Methods**: Dynamic recreation doesn't preserve custom methods on types
2. **Circular References**: May need additional handling for types that reference each other
3. **Advanced Type Annotations**: Some very complex type annotations might need special handling
4. **Performance**: For very large type hierarchies, serialization/deserialization could be optimized

## File Path Support

To improve portability and usability in CLI and non-package environments, the implementation now supports loading components from file system paths, in addition to module paths:

### Core Functionality

1. **Dual Path Storage**:
   - Components are registered with both module paths and file system paths
   - The serialization system records both paths when available
   - During deserialization, a fallback mechanism tries file paths when module imports fail

2. **Registry Enhancement**:
   - The `FlockRegistry` now maintains a `_component_file_paths` dictionary mapping component names to file paths
   - This mapping is preserved during serialization and deserialization operations

3. **CLI Integration**:
   - Registry management displays file paths for components
   - Auto-registration scanner captures file paths during component discovery
   - YAML editor preserves file paths during editing
   - Load mechanism includes fallback for loading from file paths

4. **Callable/Tool Improvements** (NEW):
   - Tools are now registered as components with type "flock_callable"
   - Tools are listed by their simple function name in agent tool lists
   - The same file path support applies to callables as to other components

### Implementation Details

```python
# Component definition now includes file path
def _get_component_definition(self, component_class: Type) -> Dict[str, Any]:
    """Get the definition of a component class."""
    module_path = f"{component_class.__module__}.{component_class.__name__}"
    
    # Try to get the file path
    file_path = None
    try:
        file_path = inspect.getfile(component_class)
    except (TypeError, ValueError):
        pass
        
    return {
        "module_path": module_path,
        "file_path": file_path
    }
```

```python
# Loading with file path fallback
def _register_component_definitions(self, component_defs: List[Dict[str, Any]]) -> None:
    """Register component definitions from a serialized Flock."""
    for component_def in component_defs:
        module_path = component_def.get("module_path")
        file_path = component_def.get("file_path")
        
        # Try loading from module path first
        try:
            module_name, class_name = module_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            component_class = getattr(module, class_name)
            self._registry.register_component(component_class)
            logger.info(f"Registered component {module_path} from module path")
            
        except (ImportError, AttributeError) as e:
            # If module path fails, try file path
            if file_path and os.path.exists(file_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"flock_dynamic_{hash(file_path)}", file_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if hasattr(module, class_name):
                            component_class = getattr(module, class_name)
                            self._registry.register_component(component_class)
                            logger.info(f"Registered component {module_path} from file path {file_path}")
                            continue
                except Exception as file_err:
                    logger.warning(f"Failed to load component from file: {file_err}")
            
            # If we got here, we couldn't load the component
            logger.warning(f"Could not register component {module_path}: {e}")
```

### Utility Functions

A new module `file_path_utils.py` provides utilities for working with file paths:

```python
def load_class_from_file(file_path: str, class_name: str) -> Optional[Type]:
    """Load a class from a file path."""
    try:
        module_name = f"flock_dynamic_import_{hash(file_path)}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        if not hasattr(module, class_name):
            return None
        return getattr(module, class_name)
    except Exception:
        return None
```

### Benefits

1. **CLI & Direct Execution**: Components can be loaded directly from file paths, enabling CLI usage without package installation
2. **Development Flexibility**: Easier development workflow using local files and paths
3. **Improved Portability**: Flock configurations can be shared with both module paths and file paths, improving compatibility across environments
4. **Graceful Fallbacks**: When module imports fail, the system attempts to load from file paths
5. **Consistent Treatment of Tools**: Tools/callables now follow the same component-based pattern (NEW)

### Example Use Case

A user develops a Flock application on their local machine:

1. Components are defined in local Python files
2. The Flock is serialized to YAML including file paths
3. The YAML is shared with another user
4. The second user can load the Flock directly from file paths without needing to install packages

This enhancement significantly improves the portability and usability of Flock configurations in various environments, particularly for CLI usage and non-package deployments.

## Conclusion

The enhanced serialization system significantly improves the portability and usability of Flock configurations by making them self-contained. The addition of file path support further enhances flexibility, allowing for CLI usage and operation in non-package environments. The improved tool serialization integrates callable functions more seamlessly into the component architecture. These changes enable easier sharing of agent systems across environments and simplify deployment. 