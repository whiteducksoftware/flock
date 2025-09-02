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

## Testing Workstream Guide (for Agents)

This section captures practical instructions and conventions for evolving Flock's tests. Use it to quickly onboard and to execute the release Must‑Haves.

- Commands
  - Install dev: `uv sync --dev --all-groups`
  - Quick suite (CI‑equivalent): `uv run poe test`
  - Full/nightly: `uv run poe test-all`
  - Select markers: `uv run pytest -m 'p0 or (integration and not otel)'`
  - Lint: `uv run ruff check src/flock/* tests/*`

- Markers and defaults
  - p0: fast, deterministic, CI‑blocking
  - integration: cross‑module flows (no network); default quick run includes them
  - otel: telemetry span tests (opt‑in)
  - temporal, mcp, web, perf: opt‑in categories for extended coverage
  - tests disable auto telemetry setup by default via `FLOCK_DISABLE_TELEMETRY_AUTOSETUP=1` (see tests/conftest.py)

- Patterns
  - Use `tests/_helpers/fakes.py` for deterministic components.
  - Registry is auto‑cleared per test via `registry_clear` fixture.
  - For discovery tests, write temp packages in `tmp_path`, push to `sys.path` inside test, and remove in `finally`.
  - For server registry tests, a minimal stub with `.config.name` is sufficient to validate registry paths.
  - Lazy imports: core uses lazy `__getattr__` to avoid importing heavy deps (datasets/pyarrow) during collection.

- Coverage gates
  - Quick suite targets core modules with a configurable threshold (currently 70%).
  - Raise incrementally (80–85%) by adding targeted tests in weak areas (orchestration, decorators, serialization_utils).

### Linting Routine (Before Every Commit)

- Run: `uv run ruff check src/flock/* tests/*`.
- Fix reported issues (imports/order, docstrings, unused imports, small style nits).
- If a rule requires a larger refactor, prefer a minimal, safe change with a clear `# noqa:` comment and a follow‑up TODO.
- Never commit with SyntaxError or import errors — keep the tree runnable.

### Commit Discipline (Follow This Cadence)

- Small, atomic commits: one logical change per commit (e.g., a new test file, a specific fix, or a CI tweak).
- Always run the quick suite locally before committing: `uv run poe test`.
- Keep commits green: tests pass and coverage gate holds.
- Prefer multiple small commits over one large “kitchen sink” change.
- Use clear commit messages (prefix with `test:`, `ci:`, `fix:`, `docs:` as appropriate).
- Avoid committing noisy changes (formatting only) unless included in the same logical change.

- Serialization contracts (snapshots)
  - `FlockAgent.to_dict`: simple and router+evaluator variants should be snapshotted to catch drift.
  - `Flock.to_dict`: minimal shape and multi‑agent shape; allow optional components catalog in minimal cases.

### Release Must‑Haves (v0.5.0)

Implement these to finalize the test framework for 0.5.0:

1. Coverage to 80–85% (core)
   - Add error‑path tests for orchestration (`_format_result`; exception path → error dict vs Box)
   - Expand weak modules: `orchestration/*`, `registry/decorators.py` (invalid inputs), `serialization_utils` dynamic import fallbacks.

2. CI
   - GitHub Actions: Linux+macOS; Python 3.10/3.11/3.12.
   - PR: `uv run poe test` with coverage gate; Nightly: `uv run poe test-all` including optional markers.
   - Upload coverage; optional Codecov.

3. Packaging sanity
   - `uv build`; import sanity on built wheel: `python -c "import flock; import flock.core"`.

4. Snapshots
   - Golden snapshots for `FlockAgent.to_dict` (variants) and `Flock.to_dict` (2 agents + router).

5. Discovery
   - Tests for skip private modules and robust behavior on import errors (no crash; log warning).

6. Docs
  - Keep `docs/testing_strategy.md`, `docs/testing_guide.md`, `docs/internal/testing_todo.md` up to date and linked in CONTRIBUTING/README.

### Strongly Recommended

- Temporal test (marker `temporal`) with in‑process worker; skip when unavailable.
- MCP test (marker `mcp`) with a stub server and tool roundtrip.
- `FLOCK_OTEL_TEST=1` shim to emit run spans without external exporters and allow default‑suite span checks.
- Thread‑safety smoke for `RegistryHub` across threads.
- Fuzz/property tests for `splitter.parse_schema` and `serialization_utils.deserialize_item`.

### Quick How‑To for Must‑Haves

- Orchestration error‑paths
  - Add tests under `tests/p0/` that force exceptions inside `run_async` and assert `_format_result` returns Box/dict as configured.

- Snapshots
  - Add tests under `tests/p0/` with stable assertions against `to_dict` structure. Avoid over‑specifying optional keys to prevent flakiness.

- Discovery
  - Create tmp packages with modules `_hidden.py` and assert they are skipped by registration. Insert logging assertions only if stable.

- CI
  - Add `.github/workflows/ci.yml` with jobs as described; ensure uv caching and matrix. Keep quick job fast; nightly may include optional markers.

These patterns have been validated in the current suite and should keep tests deterministic, fast, and contributor‑friendly.

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

### Pydantic I/O Contracts (New)

In addition to string-based contracts, agents can define input/output using Pydantic models. The framework converts Pydantic schemas into the canonical flock signature used for DSPy and validation, and it accepts `BaseModel` instances as inputs at runtime.

```python
from typing import Literal
from pydantic import BaseModel, Field
from flock.core.registry import flock_type
from flock.core import Flock, DefaultAgent

@flock_type  # recommended: registers the model with the TypeRegistry
class MovieIdea(BaseModel):
    topic: str
    genre: Literal["comedy", "drama", "horror", "action", "adventure"]

@flock_type
class Movie(BaseModel):
    fun_title: str
    runtime: int
    synopsis: str
    characters: list[dict[str, str]]

flock = Flock(name="example", model="openai/gpt-5")
agent = DefaultAgent(
    name="movie_agent",
    description="Create a fun movie",
    input=MovieIdea,      # Pydantic class
    output=Movie,         # Pydantic class
)
flock.add_agent(agent)

# You can pass a BaseModel instance directly; it will be normalized to dict
result = flock.run(agent=agent, input=MovieIdea(topic="AI agents", genre="comedy"))
print(result.fun_title)
```

Notes:
- The framework will auto-register encountered Pydantic models (including nested ones) in the `TypeRegistry` during signature building. Using `@flock_type` is still recommended for clarity and early registration.
- Internally, these models are translated to a string contract like `"field: type | description"`, so existing components (e.g., DSPy integration) work seamlessly.
- String-based I/O remains fully supported and unchanged.

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
from flock.core import Flock, DefaultAgent

flock = Flock(model="openai/gpt-4o")
agent = DefaultAgent(
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

### Hydrator (Pydantic)
You can “hydrate” Pydantic models (fill missing/None fields) using the `@flockclass` decorator, which spins up a temporary agent based on the model’s schema.

```python
from pydantic import BaseModel, Field
from flock.core.util.hydrator import flockclass

@flockclass(model="openai/gpt-5")
class RandomPerson(BaseModel):
    name: str | None = None
    age: int | None = None
    bio: str | None = Field(default=None, description="A short biography")

person = RandomPerson()
person = person.hydrate()  # fills in missing fields via a dynamic agent
```
See `07-hydrator.py` for a full example.

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
4. **Use DefaultAgent**: prefer `DefaultAgent(...)` for explicit setup; `FlockFactory` is deprecated
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
- DefaultAgent wires unified components under the hood
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

## Branching & Pre‑Release Policy

- Pre‑release main branch for 0.5.0: `0.5.0b`.
  - All PRs targeting the 0.5.0 pre‑release must be opened against `0.5.0b`, not `main`.
  - We use a `[Phase0]` prefix in GitHub issue titles for the 0.5.0 peak‑condition tasks.
- Once 0.5.0 ships, `main` will receive a fast‑forward or merge from `0.5.0b` according to release policy.

## Contributor Tips (0.5.0 → 1.0)

- Prefer explicit Agent classes over factory helpers. Factory APIs remain during 0.5.0 but will be deprecated in favor of real agent classes (e.g., `DefaultAgent`).
- Contracts first: for complex schemas, pass Pydantic models for `input`/`output` and pass `BaseModel` instances as `flock.run(..., input=...)` — they are normalized under the hood.
- Unified components only: Evaluation/Routing/Utility; legacy “modules” are considered internal/legacy and will be removed in 1.0.
- Reactive path: future 1.0 work will add a `SubscriptionComponent` and `agent.subscribe_to(...)` sugar; no need to author graphs or decorators.
