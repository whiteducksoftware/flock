# Flock Context System Specification

## Overview
The context system provides a shared state mechanism for agents, modules, and tools to exchange information during workflow execution. It maintains state across agent executions and supports both local and distributed execution environments.

## Core Context Components

### 1. FlockContext

**Purpose:**
Provide a central state repository for workflow execution.

**Requirements:**
- Must be serializable for distributed execution
- Must provide access to agent definitions
- Must support dynamic addition of values
- Must be thread-safe for concurrent access

**Key Components:**
- `agent_definitions`: Registry of agent types and configurations
- `agent_states`: Current state of agents in the workflow
- `shared_state`: Generic key-value store for cross-agent data
- Methods for accessing and modifying context data

### 2. Context Manager

**Purpose:**
Initialize and manage context lifecycle.

**Responsibilities:**
- Set up initial context with required values
- Ensure context is properly propagated between agents
- Handle context serialization when needed
- Manage context cleanup

## Context Interaction Points

### 1. Agent Initialization
- Context is passed to agent during initialization
- Agent registers itself in the context if not already present
- Agent modules access context during initialization

### 2. Agent Evaluation
- Evaluator has access to context during evaluation
- Tools can access and modify context during execution
- Modules can access context in pre/post evaluation hooks

### 3. Agent Termination
- Context is updated with final agent state
- Modules can update context during termination

### 4. Router Execution
- Router uses context to make routing decisions
- Router can modify context for the next agent

## Context Propagation

### Local Execution
- Single context instance shared across all agents
- Direct in-memory references
- Thread safety considerations for concurrent access

### Distributed Execution
- Context must be serialized between activities
- Context changes tracked and propagated
- Consistency guarantees for distributed state

## Design Principles

1. **State Sharing**:
   - Common mechanism for sharing data between components
   - Structured approach to state management
   - Prevention of global variables

2. **Access Control**:
   - Explicit methods for accessing data
   - Namespaced values to prevent collisions
   - Type-safe access patterns

3. **Transparency**:
   - Clear visibility of available context
   - Traceable state changes
   - Debuggable state transitions

4. **Efficiency**:
   - Lightweight implementation
   - Minimal serialization overhead
   - Efficient storage and retrieval

## Implementation Requirements

1. Context must be a Pydantic model for serialization
2. Context must support dictionary-like access patterns
3. Context should handle missing values gracefully
4. Context should provide type hints for accessed values
5. Context should be observable for debugging purposes

## Usage Patterns

### 1. Agent Definition Registry
The context maintains a registry of agent definitions:
```python
context.add_agent_definition(agent_type, agent_name, agent_config)
agent_def = context.get_agent_definition(agent_name)
```

### 2. Shared State Access
Components can access shared state through the context:
```python
context.set_shared_value("key", value)
value = context.get_shared_value("key")
```

### 3. Agent State Tracking
The context tracks the state of agents in the workflow:
```python
context.set_agent_state(agent_name, state)
state = context.get_agent_state(agent_name)
``` 