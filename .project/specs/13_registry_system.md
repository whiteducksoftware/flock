# Flock Registry System Specification

## Overview
The registry system provides centralized management and lookup of Flock components, including agents, callables (functions/methods), types, and component classes. It enables dynamic registration, lookup, and serialization support across the framework. This specification defines the components and behavior of the registry system.

**Core Implementation:** `src/flock/core/flock_registry.py`

## Core Components

### 1. FlockRegistry

**Implementation:** `src/flock/core/flock_registry.py:FlockRegistry`

**Purpose:**
Singleton registry for managing various Flock components.

**Key Features:**
- Singleton pattern ensures a single registry instance
- Separate registries for agents, callables, types, and components
- Dynamic import capabilities for callables and types
- Automatic registration of core components
- Path string generation for components

**Managed Objects:**
- **Agents**: FlockAgent instances, accessed by name
- **Callables**: Functions and methods, accessed by path string
- **Types**: Classes and types used in signatures, accessed by name
- **Components**: Component classes (Modules, Evaluators, Routers), accessed by name

**API:**
- **Agent Management**:
  - `register_agent(agent)`: Register a FlockAgent instance
  - `get_agent(name)`: Retrieve an agent by name
  - `get_all_agent_names()`: Get names of all registered agents

- **Callable Management**:
  - `register_callable(func, name=None)`: Register a callable
  - `get_callable(path_str)`: Retrieve a callable by path string
  - `get_callable_path_string(func)`: Get the path string for a callable

- **Type Management**:
  - `register_type(type_obj, name=None)`: Register a type
  - `get_type(type_name)`: Retrieve a type by name

- **Component Management**:
  - `register_component(component_class, name=None)`: Register a component class
  - `get_component(type_name)`: Retrieve a component class by name
  - `get_component_type_name(component_class)`: Get the name for a component class

- **Auto-Registration**:
  - `register_module_components(module_or_path)`: Auto-register components from a module

### 2. Decorator System

**Implementation:** `src/flock/core/flock_registry.py`

**Purpose:**
Provides decorators for easy registration of components, tools, and types.

**Decorators:**
- `@flock_component`: Register a class as a Flock component
- `@flock_tool`: Register a function/method as a callable tool
- `@flock_type`: Register a class as a type used in signatures

**Features:**
- Preserves type hints and signatures
- Supports both direct decoration and parameterized decoration
- Clear error messages for invalid usage

## Registry Integration

### Serialization Integration
- Registry provides path strings for serialization of callables
- Callables are serialized as path references
- Dynamic component resolution during deserialization
- Support for lookup of types, components, and callables

### Agent Integration
- Agents are registered in the registry for lookups
- The workflow system retrieves agents by name from the registry
- Multiple agents can coexist in the registry with unique names

### Tool System Integration
- Functions registered as tools are available in the registry
- Tools are retrievable by their path strings
- Automatic registration of standard tools

## Auto-Registration

### Core Components
- Evaluators (DeclarativeEvaluator, MemoryEvaluator)
- Modules (OutputModule, MetricsModule, MemoryModule)
- Routers (DefaultRouter, LLMRouter, AgentRouter)

### Tool Modules
- Basic tools
- Azure tools
- Development tools
- LLM tools
- Markdown tools

## Design Principles

1. **Centralized Management**:
   - Single source of truth for component registration
   - Consistent access patterns
   - Clear ownership boundaries

2. **Dynamic Resolution**:
   - Support for dynamic imports
   - Fallback strategies for resolution
   - Graceful handling of missing components

3. **Serialization Support**:
   - Path string generation for serialization
   - Type reference management
   - Component reference handling

4. **Extensibility**:
   - Easy registration of custom components
   - Decorator-based registration
   - Module-level scanning

## Implementation Requirements

1. Registry must be thread-safe for concurrent registration
2. Path string resolution must be deterministic
3. Dynamic imports must have proper error handling
4. Component type checking should be robust
5. Registry singleton should be efficiently accessible 