# Flock Agent Factory Specification

## Overview
The Factory design pattern is implemented in Flock to simplify agent creation with sensible defaults. This specification defines the requirements and behavior of the agent factory system.

## FlockFactory

**Implementation:** `src/flock/core/flock_factory.py`

### Purpose
Provide a simplified interface for creating pre-configured agents without requiring manual setup of all components.

### Responsibilities
- Create agents with sensible defaults
- Configure common modules automatically
- Set up evaluators with appropriate configuration
- Simplify the agent creation process

## Default Agent Creation

### Method: `create_default_agent`

**Implementation:** `src/flock/core/flock_factory.py:create_default_agent`

**Parameters:**
- `name`: Required unique agent identifier
- `description`: Optional human-readable description
- `model`: Optional LLM model identifier (defaults to configured default)
- `input`: Required input field definitions
- `output`: Required output field definitions
- `tools`: Optional list of callable tools
- `use_cache`: Whether to cache evaluation results (default: True)
- `enable_rich_tables`: Whether to render rich tables in output (default: False)
- `output_theme`: Visual theme for rendered output
- `wait_for_input`: Whether to pause after execution (default: False)
- `temperature`: Model temperature setting (default: 0.0)
- `max_tokens`: Maximum generated tokens (default: 4096)
- `alert_latency_threshold_ms`: Threshold for latency alerts (default: 30000)
- `no_output`: Whether to suppress output (default: False)
- `print_context`: Whether to print context (default: False)

**Return Value:**
- A fully configured `FlockAgent` instance

**Default Configuration:**
1. Creates a `DeclarativeEvaluator` with:
   - Specified model or default
   - Configured cache settings
   - Specified max tokens and temperature

2. Creates an `OutputModule` with:
   - Table rendering settings
   - Theme configuration
   - Wait-for-input behavior

3. Creates a `MetricsModule` with:
   - Latency threshold alerts

## Design Principles

1. **Convention over Configuration**:
   - Reasonable defaults for most parameters
   - Only essential parameters required

2. **Complete Configuration**:
   - Agents created are fully functional
   - All required components initialized

3. **Flexibility**:
   - All defaults can be overridden
   - Additional configuration possible after creation

4. **Extension**:
   - Factory pattern allows future specialized factory methods
   - Custom agent templates possible

## Implementation Notes

1. The factory uses the standard `FlockAgent` class
2. Modules are attached via the agent's `add_module` method
3. The agent is ready to use immediately after creation
4. The agent is not automatically added to a Flock instance 