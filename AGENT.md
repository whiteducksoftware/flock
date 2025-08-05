# AGENT.md - Flock Framework Onboarding Guide

## Project Overview

**Flock** is a declarative AI agent orchestration framework built by white duck GmbH. It solves common LLM development pain points by providing:

- **Declarative Contracts**: Define inputs/outputs with Pydantic models instead of brittle prompts
- **Built-in Resilience**: Automatic retries, state persistence via Temporal.io
- **Production-Ready**: Deploy as REST APIs, scale without rewriting
- **Actually Testable**: Clear contracts make agents unit-testable
- **Dynamic Workflows**: Self-correcting loops, conditional routing
- **Unified Architecture**: Simplified from 4 concepts to 2 (Agent + Components)

**Key Differentiator**: You define what goes in and what should come out - the framework handles the "how" with LLMs.

**Recent Architecture Update**: Flock has been refactored to use a unified component system that simplifies the mental model from "Agent + Evaluator + Router + Modules" to just "Agent + Components". Legacy components have been completely removed.

## Project Structure

```
flock/
├── src/flock/
│   ├── core/                   # Framework foundation
│   │   ├── flock.py           # Main orchestrator class
│   │   ├── flock_agent.py     # Base agent class (~500 lines)
│   │   ├── registry/          # Thread-safe component discovery & registration
│   │   ├── context/           # State management
│   │   ├── execution/         # Local & Temporal executors
│   │   ├── serialization/     # Save/load functionality
│   │   └── mcp/              # Model Context Protocol integration
│   ├── components/            # Unified agent components (evaluation, routing, utility)
│   ├── tools/                 # Utility functions
│   ├── webapp/                # FastAPI web interface
│   └── workflow/              # Temporal.io activities
├── tests/                     # Comprehensive test suite
│   ├── components/            # Tests for unified components
│   ├── core/                  # Core framework tests
│   └── integration/           # Integration tests
├── examples/                  # Usage examples and showcases
└── docs/                      # Documentation
```

## Key Components & Architecture

### Core Classes

1. **`Flock`** (`src/flock/core/flock.py`)
   - Main orchestrator, manages agents and execution
   - Handles both local and Temporal.io execution
   - Entry point for most operations

2. **`FlockAgent`** (`src/flock/core/flock_agent.py`)
   - Base class for all agents (refactored from 1000+ to ~500 lines)
   - Lifecycle hooks: initialize → evaluate → terminate
   - **Unified Architecture**: Uses single `components` list instead of separate evaluator/router/modules
   - **Workflow State**: `next_agent` property for explicit workflow control
   - Composition-based architecture with focused components

3. **`RegistryHub`** (`src/flock/core/registry/`)
   - Thread-safe registry system using composition pattern
   - Manages agents, callables, types, servers with specialized helpers
   - Auto-registration capabilities with component discovery

4. **`FlockContext`** (`src/flock/core/context/context.py`)
   - State management between agent executions
   - History tracking, variable storage

### Unified Component Architecture

**Mental Model**: Agent + Components (2 concepts instead of 4)

**Component Types** (all follow `*ComponentBase` naming convention):
- **EvaluationComponentBase**: Core LLM evaluation logic
- **RoutingComponentBase**: Workflow routing decisions (sets `next_agent`)
- **UtilityComponentBase**: Cross-cutting concerns (metrics, output, memory)

**Key Properties**:
- `agent.components`: List of all components
- `agent.evaluator`: Primary evaluation component (delegates to helper)
- `agent.router`: Primary routing component (delegates to helper)
- `agent.next_agent`: Next agent in workflow (string, callable, or None)
- `agent._components`: Component management helper (lazy-loaded)

### Execution Flow

```
Flock.run() → FlockAgent.run_async() → Components.evaluate() → Router.set_next_agent() → Next Agent
```

**Workflow Steps**:
1. Agent initializes and runs evaluation components
2. Routing components analyze results and set `agent.next_agent`
3. Utility components handle cross-cutting concerns
4. Orchestrator uses `agent.next_agent` to continue workflow

## Development Workflow

### Essential Commands

```bash
# Project uses UV as package manager
uv run python -m pytest tests/core/test_flock_core.py -v    # Run core tests
uv run python -m pytest tests/serialization/ -v            # Test serialization
uv run python -m pytest tests/components/ -v -k memory      # Test specific components

# Common development tasks
uv run python examples/01-getting-started/quickstart.py     # Run basic example
uv run python -c "from flock.core import Flock; print('OK')" # Quick import test
```

### Testing Strategy

- **Unit Tests**: `tests/core/` for framework components
- **Component Tests**: `tests/components/` for unified component architecture
- **Integration Tests**: `tests/integration/` for external dependencies  
- **Serialization Tests**: `tests/serialization/` for save/load

**Important**: Many tests currently have issues unrelated to core functionality (logging conflicts, registry state). Focus on functionality tests.

## Known Issues & Gotchas

### Current Problems
1. **Logging conflicts**: `exc_info` parameter duplication causing test failures
2. **Test brittleness**: Some tests depend on external services or configuration

### Code Quality Issues Found
- Bare `except:` handlers in multiple files
- Global state management patterns
- Some circular import dependencies
- Complex function complexity (Ruff warnings)

## Important Patterns & Conventions

### Component Registration
```python
from flock.core.registry import flock_component
from flock.core.component.evaluation_component_base import EvaluationComponentBase

@flock_component(config_class=MyComponentConfig)
class MyComponent(EvaluationComponentBase):
    # Component implementation
```

### Agent Creation
```python
from flock.core import Flock, FlockFactory

flock = Flock(model="openai/gpt-4o")
agent = FlockFactory.create_default_agent(
    name="my_agent",
    input="query: str",
    output="result: str"
)
flock.add_agent(agent)
result = flock.run(start_agent="my_agent", input={"query": "test"})
```

### Manual Component Assembly
```python
from flock.core import FlockAgent
from flock.core.agent.flock_agent_components import FlockAgentComponents
from flock.components.evaluation.declarative_evaluation_component import (
    DeclarativeEvaluationComponent, DeclarativeEvaluationConfig
)
from flock.components.utility.output_utility_component import (
    OutputUtilityComponent, OutputUtilityConfig
)
from flock.components.routing.default_routing_component import (
    DefaultRoutingComponent, DefaultRoutingConfig
)

# Create agent with unified components
agent = FlockAgent(
    name="my_agent",
    input="query: str",
    output="result: str",
    components=[
        DeclarativeEvaluationComponent(name="evaluator", config=DeclarativeEvaluationConfig()),
        OutputUtilityComponent(name="output", config=OutputUtilityConfig()),
        DefaultRoutingComponent(name="router", config=DefaultRoutingConfig(hand_off="next_agent"))
    ]
)

# Use helper for component management
helper = agent._components  # Lazy-loaded property
print(f"Evaluation components: {len(helper.get_evaluation_components())}")
print(f"Primary evaluator: {helper.get_primary_evaluator()}")

# Basic operations delegate to helper
agent.add_component(my_component)  # Delegates to helper
agent.get_component("component_name")  # Delegates to helper

# Alternative: Set next_agent directly
agent.next_agent = "next_agent_name"
```

### Component Management Helper

The `FlockAgentComponents` class provides convenient methods for managing components:

```python
# Access helper through agent property (lazy-loaded)
helper = agent._components

# Component management
helper.add_component(my_component)
helper.remove_component("component_name")
component = helper.get_component("component_name")

# Type-specific getters
evaluation_components = helper.get_evaluation_components()
routing_components = helper.get_routing_components()
utility_components = helper.get_utility_components()

# Convenience methods
primary_evaluator = helper.get_primary_evaluator()
primary_router = helper.get_primary_router()
enabled_components = helper.get_enabled_components()

# Basic operations delegate to helper automatically
agent.add_component(my_component)  # Same as helper.add_component()
agent.evaluator  # Same as helper.get_primary_evaluator()
agent.router     # Same as helper.get_primary_router()
```

### Serialization
- All core classes inherit from `Serializable`
- Support JSON, YAML, and Python dict formats
- Use `to_dict()` / `from_dict()` for persistence

## Development Guidelines

### When Making Changes
1. **Always run diagnostics**: Use `get_diagnostics` tool on modified files
2. **Test serialization**: Many components need to serialize/deserialize correctly
3. **Check imports**: Circular imports are a known issue
4. **Memory management**: Be careful with global state (registry, context)

### Code Style
- Use Pydantic for all data models
- Prefer `async`/`await` for I/O operations
- Type hints are mandatory
- Error handling should be specific (avoid bare `except`)

### Testing
- Mock external dependencies (LLM calls, file systems)
- Use fixtures for complex setup
- Test both success and failure paths
- Verify serialization roundtrips

## Quick Start for Development

1. **Understand the flow**: `Flock` → `FlockAgent` → `Utility/Evaluator/Router` → Result
2. **Start with examples**: Check `examples/01-getting-started/`
3. **Read tests**: `tests/core/test_flock_core.py` shows usage patterns
4. **Use the factory**: `FlockFactory.create_default_agent()` for quick setup
5. **Focus on contracts**: Input/output signatures are key

## Workflow Management

### Setting Next Agent

You can control workflow flow in three ways:

1. **Direct assignment**: `agent.next_agent = "agent_name"`
2. **Callable**: `agent.next_agent = lambda context, result: "dynamic_agent"`
3. **Routing component**: Add a routing component that sets `next_agent` based on evaluation results

### Routing Components

Routing components implement workflow logic:

```python
from flock.components.routing.default_routing_component import DefaultRoutingComponent, DefaultRoutingConfig
from flock.components.routing.conditional_routing_component import ConditionalRoutingComponent, ConditionalRoutingConfig
from flock.components.routing.llm_routing_component import LLMRoutingComponent, LLMRoutingConfig

# Simple static routing
router = DefaultRoutingComponent(
    name="router",
    config=DefaultRoutingConfig(hand_off="next_agent")
)

# Conditional routing based on results
router = ConditionalRoutingComponent(
    name="conditional_router", 
    config=ConditionalRoutingConfig(
        condition=lambda result: result.get("confidence", 0) > 0.8,
        true_agent="high_confidence_agent",
        false_agent="low_confidence_agent"
    )
)

# AI-powered routing decisions
router = LLMRoutingComponent(
    name="llm_router",
    config=LLMRoutingConfig(
        available_agents=["agent_a", "agent_b", "agent_c"],
        routing_prompt="Choose the best next agent based on the result"
    )
)
```

## Web Interface

The framework includes a FastAPI web application at `src/flock/webapp/` with:
- Agent execution interface
- Configuration management
- File upload/download
- Real-time execution monitoring

Start with: `flock.serve()` method on any Flock instance.

## External Dependencies

- **DSPy**: LLM interaction and prompt management
- **Temporal.io**: Workflow orchestration and resilience
- **FastAPI**: Web interface
- **Pydantic**: Data validation and serialization
- **OpenTelemetry**: Observability and tracing

## Next Priority Areas

Based on the review, focus on:
1. **Fixing logging conflicts** in test suite
2. **Improving error handling** patterns  
3. **Adding security guidelines** for component development
4. **Performance optimization** for component operations

## Migration Notes

The unified architecture completely replaces the legacy system:
- Legacy evaluators, modules, and routers have been removed
- All legacy dependencies cleaned up from codebase  
- FlockFactory creates agents with new unified components
- Workflow execution uses `agent.next_agent` for routing
- HandOffRequest system replaced with direct property assignment

**Key Benefits of New Architecture**:
- Simpler mental model (2 concepts vs 4)
- Explicit workflow state management via `agent.next_agent`
- Clean composition over complex inheritance
- Easier testing and debugging
- Unified component registration and discovery
- Consistent `*ComponentBase` naming convention
- Full composition pattern with `_components`, `_execution`, `_integration`, `_serialization`, `_lifecycle`
- Lazy-loaded component helper with rich functionality
- Thread-safe registry system with specialized helpers
- Zero code duplication in registry operations

This should give you a solid foundation to understand and contribute to the Flock framework efficiently!
