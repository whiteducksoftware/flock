# Flock Router System Specification

## Overview
The router system enables multi-agent workflows by determining which agent should execute next based on the current agent's outputs. It provides a mechanism for building complex agent pipelines and workflows.

**Core Implementation:** `src/flock/core/flock_router.py`

## Core Router Components

### 1. HandOffRequest

**Implementation:** `src/flock/core/flock_router.py`

**Purpose:**
Define the next agent to execute and how inputs should be handled.

**Fields:**
- `next_agent`: Name of the next agent to invoke
- `hand_off_mode`: Strategy for mapping outputs to inputs ('match' or 'add')
- `override_next_agent`: Optional direct reference to next agent
- `override_context`: Optional context override

### 2. FlockRouterConfig

**Implementation:** `src/flock/core/flock_router.py`

**Purpose:**
Configuration for router behavior.

**Fields:**
- `enabled`: Whether the router is active
- `agents`: Optional list of potential target agents

### 3. FlockRouter

**Implementation:** `src/flock/core/flock_router.py`

**Purpose:**
Base abstract class for all routers.

**API:**
- `route(current_agent, result, context)`: Async method to determine the next agent

## Router Integration

### Agent Integration
FlockAgent includes an optional `handoff_router` field:
- When present, enables multi-agent workflows
- When absent, execution stops after the agent completes

### Workflow Execution
During Flock execution:
1. After agent evaluation, check if agent has a router
2. If router exists and is enabled, call its `route` method
3. Process the HandOffRequest to determine the next agent
4. Map outputs to inputs according to hand_off_mode
5. Execute the next agent
6. Repeat until no next agent is specified

## Standard Routers

### 1. DefaultRouter

**Implementation:** `src/flock/routers/default/default_router.py`

**Purpose:**
A basic router that directs to a predefined next agent.

**Configuration:**
- `hand_off`: Static agent name, HandOffRequest instance, or callable returning HandOffRequest

**Behavior:**
Provides a simple, non-dynamic routing based on a predetermined path.

### 2. LLMRouter

**Implementation:** `src/flock/routers/llm/llm_router.py`

**Purpose:**
A router that uses an LLM to determine the next agent based on result content.

**Configuration:**
- `with_output`: Whether to include the current agent's output in the routing decision
- `config_model`: Routing model to use

**Behavior:**
Uses an LLM to dynamically select the next agent from a list of available agents based on the current result.

### 3. AgentRouter

**Implementation:** `src/flock/routers/agent/agent_router.py`

**Purpose:**
A router that uses a separate agent to determine the next agent in the workflow.

**Configuration:**
- `router_agent`: The specialized agent that makes routing decisions
- `input_template`: Template for creating input for the router agent

**Behavior:**
Delegates routing decisions to a specialized agent designed specifically for workflow orchestration.

## Design Principles

1. **Flexibility**:
   - Support different routing strategies
   - Allow both static and dynamic routing
   - Enable complex workflow patterns

2. **Clear Handoff Definition**:
   - Explicit next agent specification
   - Well-defined input mapping strategies
   - Support for context modification

3. **Extensibility**:
   - Easy to implement custom routers
   - Support for different routing criteria
   - Integration with external systems

4. **Predictability**:
   - Clear execution paths
   - Debuggable routing decisions
   - Avoidance of circular references

## Implementation Requirements

1. Routers must be serializable
2. Routers must support both string-based and direct agent references
3. Routers must handle missing or invalid next agent gracefully
4. Router implementations should avoid side effects
5. Routers should support tracing of routing decisions 