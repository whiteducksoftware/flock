# Flock Core Architecture Specification

## Overview
Flock is a framework for building, orchestrating, and running AI agent systems. It provides a declarative approach to agent design, focusing on inputs and outputs rather than prompts. This specification defines the core architecture components of the Flock framework.

## Components

### 1. Flock

The central orchestrator that manages agents, tools, and execution flow.

**Implementation:** `src/flock/core/flock.py`

**Responsibilities:**
- Managing agent registration and retrieval
- Orchestrating workflow execution
- Providing execution context
- Supporting local and distributed execution modes (Temporal)
- Initializing and managing logging

**Key Attributes:**
- `agents`: Collection of registered agents
- `registry`: Central registry for agents and tools
- `context`: Global execution context
- `model`: Default LLM model identifier
- `enable_temporal`: Flag for distributed execution

### 2. FlockAgent

The core agent class that defines a single AI agent's capabilities.

**Implementation:** `src/flock/core/flock_agent.py`

**Responsibilities:**
- Defining agent inputs and outputs
- Managing agent lifecycle
- Providing access to tools
- Supporting serialization and deserialization
- Integrating with modules for extensibility

**Key Attributes:**
- `name`: Unique identifier
- `description`: Human-readable agent description
- `model`: LLM model identifier
- `input`: Input field definitions
- `output`: Output field definitions
- `tools`: Available tools for the agent
- `evaluator`: Strategy for evaluation
- `modules`: Attached modules for extensibility
- `handoff_router`: Optional router for multi-agent workflows

### 3. FlockModule

Extension system for agents to modify behavior through lifecycle hooks.

**Implementation:** `src/flock/core/flock_module.py`

**Responsibilities:**
- Hooking into agent lifecycle events
- Modifying inputs or outputs
- Adding capabilities to agents
- Maintaining module-specific state

**Lifecycle Hooks:**
- `initialize`: Called when agent starts
- `pre_evaluate`: Called before evaluation
- `post_evaluate`: Called after evaluation
- `terminate`: Called when agent finishes
- `on_error`: Called when errors occur

### 4. FlockEvaluator

Strategy for evaluating agent requests and generating outputs.

**Implementation:** `src/flock/core/flock_evaluator.py`

**Responsibilities:**
- Processing agent inputs
- Formulating appropriate prompts
- Managing model interactions
- Processing model outputs
- Handling tool usage

### 5. FlockRouter

Mechanism for directing workflow between agents.

**Implementation:** `src/flock/core/flock_router.py`

**Responsibilities:**
- Determining the next agent in a workflow
- Managing input/output mapping between agents
- Supporting workflow branching logic

**Key Concepts:**
- `HandOffRequest`: Definition of the next agent and input mapping

### 6. FlockContext

Shared execution context for agents and modules.

**Implementation:** `src/flock/core/context/context.py`

**Responsibilities:**
- Storing global state across agents
- Providing access to agent definitions
- Supporting serialization for distributed execution

## Design Principles

1. **Declarative over Imperative**:
   - Focus on what agents do, not how they do it
   - Define inputs and outputs clearly
   - Minimize prompt engineering

2. **Modular Extension**:
   - Module system for adding functionality
   - Clear lifecycle hooks
   - Separation of concerns

3. **Resilient Execution**:
   - Support for local and distributed execution
   - Error handling at each level
   - Observability through logging and tracing

4. **Serialization Support**:
   - All components can be serialized
   - Support for saving and loading agent definitions
   - State preservation across execution environments

5. **Tool Integration**:
   - First-class support for tool usage
   - Flexible tool registration
   - Dynamic tool discovery

## Execution Flow

1. User creates a Flock instance
2. User adds agents to the Flock
3. User registers tools if needed
4. User calls `run()` with a starting agent and input
5. Flock initializes context and resolves the starting agent
6. Agent initializes and resolves modules
7. Agent evaluates input using its evaluator
8. If a router is defined, Flock determines the next agent
9. Process repeats until no next agent is specified
10. Final result is returned 