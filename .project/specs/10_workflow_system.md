# Flock Workflow System Specification

## Overview
The workflow system implements the execution of agent chains using the Temporal workflow engine. It provides the foundation for both local synchronous execution and distributed, reliable execution across environments. This specification defines the components and behavior of the workflow system.

**Core Implementation:** `src/flock/workflow/`

## Core Components

### 1. FlockWorkflow

**Implementation:** `src/flock/workflow/workflow.py`

**Purpose:**
Defines the Temporal workflow that orchestrates agent execution.

**Key Features:**
- Workflow definition using Temporal's `@workflow.defn` decorator
- Context serialization and management
- Activity execution with timeouts
- Error handling and reporting

**API:**
- `run(context_dict)`: Main workflow entry point that executes the agent chain

### 2. Workflow Activities

**Implementation:** `src/flock/workflow/activities.py`

**Purpose:**
Provides the core activity that runs an agent chain with proper context management.

**Key Features:**
- Activity definition using Temporal's `@activity.defn` decorator
- Span management for tracing agent execution
- Handoff routing between agents
- Context recording
- Error handling with appropriate logging

**API:**
- `run_agent(context)`: Executes a chain of agents, managing handoffs between them

### 3. Temporal Setup

**Implementation:** `src/flock/workflow/temporal_setup.py`

**Purpose:**
Sets up the Temporal client and worker for workflow execution.

**Key Features:**
- Worker registration
- Client configuration
- Task queue management

**API:**
- `setup_worker(workflow, activity)`: Registers workflows and activities with Temporal
- `create_temporal_client()`: Creates a Temporal client for workflow execution

## Workflow Execution Flow

1. **Initialization:**
   - The workflow receives a serialized context dictionary
   - The context is deserialized into a `FlockContext` instance
   - Workflow ID and timestamp are recorded

2. **Agent Chain Execution:**
   - The `run_agent` activity is executed with the context
   - The initial agent is retrieved from the context variables
   - The agent is executed with resolved inputs

3. **Handoff Processing:**
   - After each agent execution, the handoff router is consulted
   - If a next agent is specified, the context is updated
   - The next agent is retrieved and execution continues
   - If no next agent is specified, the chain completes

4. **Result Handling:**
   - Final agent output is returned as the workflow result
   - Result is recorded in the context with success status
   - Exceptions are caught and recorded with failure status

## Tracing and Observability

1. **Span Management:**
   - Top-level span for the entire `run_agent` activity
   - Nested spans for each agent iteration
   - Execution spans for individual agent runs
   - Event recording for key execution points

2. **Logging:**
   - Detailed logging of agent execution
   - Error logging with contextual information
   - Handoff logging between agents
   - Workflow start and completion logging

## Integration Points

### Execution System Integration
- The execution system uses the workflow system to run agent chains
- Local execution calls `run_agent` directly
- Temporal execution runs the `FlockWorkflow` workflow

### Registry Integration
- The workflow system uses the registry to resolve agents by name
- Agents are retrieved at each handoff point

### Router Integration
- The workflow system consults agent handoff routers
- Handoff requests determine the next agent in the chain
- Router errors are properly handled and reported

## Design Principles

1. **Reliability**:
   - Proper error handling at all levels
   - Context state consistency
   - Timeout management

2. **Observability**:
   - Comprehensive tracing
   - Detailed logging
   - Context recording of execution history

3. **Extensibility**:
   - Modular structure
   - Clear interfaces
   - Support for different execution environments

4. **Performance**:
   - Efficient context management
   - Minimal serialization overhead
   - Proper resource cleanup

## Implementation Requirements

1. Workflow components must be serializable
2. Activities must be idempotent when possible
3. Error handling must be comprehensive
4. Tracing must be consistent across execution boundaries
5. Context must be properly managed across activities 