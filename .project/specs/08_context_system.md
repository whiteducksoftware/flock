# Flock Context System Specification

## Overview
The context system provides shared state management across agent executions within a Flock workflow. It enables agents to access shared data, store intermediate results, and communicate with each other beyond direct input/output mapping. This specification defines the requirements and behavior of the context system.

**Core Implementation:** `src/flock/core/context/`

## Core Components

### 1. FlockContext

**Implementation:** `src/flock/core/context/context.py`

**Purpose:**
Provides a centralized state container for sharing data across agent executions.

**Key Features:**
- State storage for variables
- Agent execution history tracking
- Agent definition registry
- Run/workflow identification
- Variable access via key-value or dictionary-style access
- Serialization support

**API:**
- `get_variable(key, default=None)`: Retrieve a value by key
- `set_variable(key, value)`: Store a value by key
- `__getitem__`/`__setitem__`: Dictionary-style access
- `record(agent_name, data, timestamp, hand_off, called_from)`: Record agent execution
- `get_agent_history(agent_name)`: Get execution history for an agent
- `next_input_for(agent)`: Determine the next input for an agent
- `get_most_recent_value(variable_name)`: Get most recent value from history
- `get_agent_definition(agent_name)`: Get agent definition
- `add_agent_definition(agent_type, agent_name, agent_data)`: Register agent definition

### 2. Context Manager

**Implementation:** `src/flock/core/context/context_manager.py`

**Purpose:**
Initializes and manages context instances for workflows.

**API:**
- `initialize_context(flock_args)`: Create and initialize a new context

## Supporting Models

### 1. AgentRunRecord

**Implementation:** `src/flock/core/context/context.py`

**Purpose:**
Records the details of each agent execution for history tracking.

**Fields:**
- `id`: Unique identifier for the run
- `agent`: Name of the agent
- `data`: Input/output data associated with the run 
- `timestamp`: When the execution occurred
- `hand_off`: Routing information
- `called_from`: Origin of the execution request

### 2. AgentDefinition

**Implementation:** `src/flock/core/context/context.py`

**Purpose:**
Stores information about registered agents.

**Fields:**
- `agent_type`: Type of the agent
- `agent_name`: Name identifier
- `agent_data`: Agent configuration
- `serializer`: Serialization method

## Context Integration

### Flock Integration
- Flock creates and initializes the global context
- Flock passes context to each agent during execution
- Flock ensures context consistency across agents

### Agent Integration
- Agents receive context during initialization and evaluation
- Agents can read from and write to context
- Context determines appropriate inputs for agents based on their input schema

### Module Integration
- Modules receive context in all lifecycle methods
- Modules can use context to store and retrieve state
- Modules can communicate with each other via context

## Design Principles

1. **Shared State Management**:
   - Consistent state across agent executions
   - History tracking for debugging and analysis
   - Dictionary-like access patterns

2. **Flexibility**:
   - Support for various data types
   - Both key-value and path-based access
   - Robust serialization for distribution

3. **Serialization Support**:
   - Full serialization for distributed execution
   - Support for complex object types
   - Proper handling of datetime objects

4. **Observability**:
   - Tracing integration
   - Logging of state changes
   - History recording for execution flow

## Implementation Requirements

1. Context must be serializable for Temporal workflows
2. Context operations must be thread-safe
3. Context should handle large data volumes efficiently
4. Context should support common data operations (get, set, delete)
5. Context should provide clear error messages for invalid operations 