# Flock Module System Specification

## Overview
The module system provides a way to extend agent functionality through lifecycle hooks. Modules can modify agent behavior, add new capabilities, or provide cross-cutting concerns like logging or metrics without changing the core agent implementation.

**Core Implementation:** `src/flock/core/flock_module.py`

## Core Module Components

### 1. FlockModuleConfig

**Implementation:** `src/flock/core/flock_module.py:FlockModuleConfig`

**Purpose:**
Base configuration class for all module configurations.

**Requirements:**
- Must extend Pydantic's BaseModel
- Must include an `enabled` flag to toggle module functionality
- Must support extension through subclassing or the `with_fields` factory method

**API:**
- `with_fields(**field_definitions)`: Factory method to create derived config classes with additional fields

### 2. FlockModule

**Implementation:** `src/flock/core/flock_module.py:FlockModule`

**Purpose:**
Base abstract class for all modules that can be attached to agents.

**Requirements:**
- Must extend Pydantic's BaseModel and be abstract (ABC)
- Must include a unique name identifier
- Must include a configuration instance
- Must implement all lifecycle hook methods

**Lifecycle Hooks:**
- `initialize(agent, inputs, context)`: Called when agent starts execution
- `pre_evaluate(agent, inputs, context)`: Called before agent evaluation, can modify inputs
- `post_evaluate(agent, inputs, result, context)`: Called after agent evaluation, can modify results
- `terminate(agent, inputs, result, context)`: Called when agent completes execution
- `on_error(agent, error, inputs, context)`: Called when an error occurs during execution

## Module Integration

### Agent Module Management
The FlockAgent must provide methods to:
- Add modules via `add_module(module)` - **Implementation:** `src/flock/core/flock_agent.py:add_module`
- Remove modules via `remove_module(module_name)` - **Implementation:** `src/flock/core/flock_agent.py:remove_module`
- Retrieve modules via `get_module(module_name)` - **Implementation:** `src/flock/core/flock_agent.py:get_module`
- Get all enabled modules via `get_enabled_modules()` - **Implementation:** `src/flock/core/flock_agent.py:get_enabled_modules`

### Module Execution
During agent execution, the agent must:
1. Call `initialize()` on all enabled modules during agent initialization
2. Call `pre_evaluate()` on all enabled modules before evaluation
3. Call `post_evaluate()` on all enabled modules after evaluation
4. Call `terminate()` on all enabled modules during agent termination
5. Call `on_error()` on all enabled modules when errors occur

## Standard Modules

### 1. OutputModule

**Implementation:** `src/flock/modules/output/output_module.py`

**Purpose:**
Handle formatting and displaying agent outputs.

**Configuration:**
- `render_table`: Whether to render outputs as rich tables
- `theme`: Visual theme for rendered outputs
- `wait_for_input`: Whether to pause for user input after output
- `no_output`: Whether to suppress output entirely
- `print_context`: Whether to print context along with output

### 2. MetricsModule

**Implementation:** `src/flock/modules/metrics/metrics_module.py`

**Purpose:**
Track and report agent performance metrics.

**Configuration:**
- `latency_threshold_ms`: Threshold for latency alerts

## Design Principles

1. **Separation of Concerns**:
   - Modules handle cross-cutting concerns
   - Core agent logic remains focused
   - Modules can be added/removed without modifying agent code

2. **Composability**:
   - Multiple modules can be attached to an agent
   - Modules can interact through shared context
   - Order-independent execution where possible

3. **Configurability**:
   - All modules have configuration classes
   - Configuration can be modified at runtime
   - Modules can be enabled/disabled through configuration

4. **Extension Points**:
   - Clear lifecycle hooks for integration
   - Standardized interfaces for all modules
   - Predictable execution ordering

## Implementation Requirements

1. Modules must be serializable along with agents
2. Modules should have minimal dependencies on each other
3. Modules should gracefully handle missing context or configuration
4. Module hooks should be implemented as async methods
5. Module hooks should not raise exceptions (handle internally) 