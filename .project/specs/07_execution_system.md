# Flock Execution System Specification

## Overview
The execution system defines how agent workflows are executed, with support for both local synchronous execution and distributed execution through Temporal. This specification defines the requirements and behavior of the execution subsystem.

## Execution Modes

### 1. Local Execution
- Synchronous execution in the current process
- Suitable for development, debugging, and simple workflows
- Executes the entire workflow in a single process
- Managed through `run()` and `run_async()` methods on `Flock`

### 2. Temporal Execution
- Distributed execution using Temporal workflow engine
- Suitable for production, long-running workflows, and reliability
- Executes workflow steps as separate activities
- Managed through `enable_temporal` flag and specialized methods

## Execution Components

### 1. Local Executor

**Responsibilities:**
- Execute agent workflows synchronously
- Manage agent context and state
- Handle agent initialization and termination
- Process routing between agents
- Collect and return final results

### 2. Temporal Executor

**Responsibilities:**
- Set up Temporal workflow definitions
- Convert agents to Temporal activities
- Manage serialization/deserialization for distributed execution
- Handle workflow state persistence
- Provide reliability features like retries and timeouts

## Execution Flow

### Local Execution Flow
1. User calls `flock.run()` with start agent and input
2. Flock resolves the start agent (by name or reference)
3. Flock initializes the context
4. Flock calls `run_local_workflow()` to execute the workflow
5. Local executor calls `agent.run_async()` on the start agent
6. If agent has a router, determine next agent and continue execution
7. Continue until no next agent is specified
8. Return final result to the user

### Temporal Execution Flow
1. User calls `flock.run()` with start agent and input
2. Flock checks `enable_temporal` flag and identifies Temporal execution
3. Flock serializes the necessary components
4. Flock calls `run_temporal_workflow()` with serialized components
5. Temporal workflow executes agent activities asynchronously
6. Workflow handles routing between agents
7. Workflow returns final result to the user

## Serialization Requirements

For Temporal execution, components must be serializable:
1. Agents must be convertible to/from dictionaries
2. Tools must be properly serialized/deserialized
3. Context must maintain state across activities
4. All inputs and outputs must be JSON-serializable

## Error Handling

**Local Execution:**
- Errors propagate to calling code
- Agent's `on_error()` method is called
- Modules' `on_error()` methods are called

**Temporal Execution:**
- Activity failures trigger retry mechanisms
- Workflow maintains state for retries
- Errors are logged to Temporal history
- Final failures can trigger compensation workflows

## Design Principles

1. **Execution Transparency**:
   - Same API for local and distributed execution
   - Minimal code changes to switch execution modes
   - Consistent behavior across modes

2. **Reliability**:
   - Temporal execution handles failures gracefully
   - Persistence of workflow state
   - Retries and timeouts configurable

3. **Observability**:
   - Tracing through all execution steps
   - Logging at key points
   - Metrics for performance analysis

4. **Flexibility**:
   - Support for synchronous and asynchronous APIs
   - Compatible with different execution environments
   - Extensible to other execution engines

## Implementation Requirements

1. Local execution must work without external dependencies
2. Temporal execution must handle serialization challenges
3. Both modes must support the same core features
4. Must handle context propagation appropriately
5. Must provide clear error information 