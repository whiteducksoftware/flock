# Component Architecture in Flock

## Overview

Components in Flock provide a powerful plugin mechanism for extending agent behavior without modifying core engine logic. This document describes how components work and how to leverage them for patterns like fan-out.

## Component Lifecycle

Components participate in the agent execution pipeline through well-defined hooks:

```
┌──────────────┐
│ on_initialize │ - One-time setup when agent starts
└──────┬───────┘
       │
┌──────▼──────────┐
│ on_pre_consume  │ - Transform input artifacts before processing
└──────┬──────────┘
       │
┌──────▼──────────┐
│ on_pre_evaluate │ - Prepare evaluation inputs
└──────┬──────────┘
       │
┌──────▼──────────┐
│ ENGINE.evaluate │ - Core business logic (not a hook)
└──────┬──────────┘
       │
┌──────▼───────────┐
│ on_post_evaluate │ - Transform evaluation results ← KEY HOOK FOR FAN-OUT
└──────┬───────────┘
       │
┌──────▼───────────┐
│ PUBLISH ARTIFACTS│ - Orchestrator publishes to blackboard
└──────┬───────────┘
       │
┌──────▼───────────┐
│ on_post_publish  │ - React to successful publication
└──────┬───────────┘
       │
┌──────▼──────┐
│ on_error    │ - Handle any errors (if they occur)
└──────┬──────┘
       │
┌──────▼──────────┐
│ on_terminate    │ - Cleanup when agent stops
└─────────────────┘
```

## Key Insight: post_evaluate Hook

The `on_post_evaluate` hook is particularly powerful because it:

1. **Receives the complete EvalResult** from the engine
2. **Can modify the artifacts list** before publication
3. **Maintains access to context and metrics**
4. **Executes before type checking and publication**

This makes it the ideal insertion point for transformations like fan-out.

## Component Types

### 1. AgentComponent (Base)

General-purpose components for cross-cutting concerns:

```python
class MetricsComponent(AgentComponent):
    """Track metrics across agent execution."""

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        result.metrics["processing_time"] = time.time() - start_time
        return result
```

### 2. EngineComponent

Specialized components that implement core evaluation logic:

```python
class DSPyEngine(EngineComponent):
    """Evaluate using DSPy framework."""

    async def evaluate(self, agent, ctx, inputs):
        # Core business logic here
        return EvalResult(...)
```

### 3. Utility Components

Pre-built components for common patterns:

- `LoggingUtility` - Rich console output
- `MetricsUtility` - Performance tracking
- `BudgetComponent` - Token/cost limits
- `GuardComponent` - Safety checks

## Component Composition

Components execute in order and can build on each other:

```python
agent = (
    flock.agent("processor")
    .with_utilities(
        ValidationComponent(),  # First: validate inputs
        FanOutComponent(),     # Second: expand lists
        MetricsComponent(),    # Third: track metrics
        LoggingComponent()     # Fourth: log everything
    )
)
```

## Creating Custom Components

### Basic Pattern

```python
from flock.components import AgentComponent
from pydantic import Field

class CustomComponent(AgentComponent):
    name: str = "custom"
    config_value: int = Field(default=10)

    async def on_pre_evaluate(self, agent, ctx, inputs):
        # Modify inputs before evaluation
        inputs.state["custom_data"] = self.config_value
        return inputs

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        # Transform results after evaluation
        if "error" in result.state:
            result.logs.append(f"Handled error: {result.state['error']}")
        return result
```

### Advanced: Stateful Components

```python
class CacheComponent(AgentComponent):
    """Cache evaluation results."""

    def __init__(self, **data):
        super().__init__(**data)
        self._cache: dict = {}

    async def on_pre_evaluate(self, agent, ctx, inputs):
        # Check cache before evaluation
        cache_key = self._compute_key(inputs)
        if cache_key in self._cache:
            # Skip evaluation, return cached result
            inputs.state["cached_result"] = self._cache[cache_key]
        return inputs

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        # Store result in cache
        if "cached_result" not in inputs.state:
            cache_key = self._compute_key(inputs)
            self._cache[cache_key] = result
        return result
```

## Component Configuration

### Static Configuration

```python
component = FanOutComponent(
    list_field="items",
    preserve_correlation=True,
    max_items=100
)
```

### Dynamic Configuration

```python
class AdaptiveComponent(AgentComponent):
    async def on_initialize(self, agent, ctx):
        # Load configuration from context
        self.threshold = ctx.metadata.get("threshold", 0.8)
```

## Testing Components

Components can be tested in isolation:

```python
async def test_component_transform():
    component = MyComponent()

    # Create test data
    inputs = EvalInputs(artifacts=[...])
    result = EvalResult(artifacts=[...])

    # Test transformation
    modified = await component.on_post_evaluate(
        mock_agent, mock_context, inputs, result
    )

    assert len(modified.artifacts) == expected_count
```

## Component Best Practices

### 1. Single Responsibility
Each component should do one thing well:
- ❌ `DoEverythingComponent`
- ✅ `FanOutComponent`, `MetricsComponent`, `CacheComponent`

### 2. Pass-Through by Default
Always return inputs/results unchanged if not applicable:
```python
async def on_post_evaluate(self, agent, ctx, inputs, result):
    if not self._should_process(result):
        return result  # Pass through unchanged
    # Process...
```

### 3. Configuration over Code
Make behavior configurable:
```python
class FlexibleComponent(AgentComponent):
    enabled: bool = True
    threshold: float = 0.8

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        if not self.enabled:
            return result
        # Use self.threshold...
```

### 4. Error Handling
Handle errors gracefully:
```python
async def on_post_evaluate(self, agent, ctx, inputs, result):
    try:
        return self._transform(result)
    except Exception as e:
        result.logs.append(f"Component error: {e}")
        return result  # Return original on error
```

### 5. Preserve Metadata
Maintain correlation IDs and visibility:
```python
new_artifact = Artifact(
    type=derived_type,
    payload=new_payload,
    correlation_id=original.correlation_id,  # Preserve
    visibility=original.visibility,          # Preserve
    metadata={**original.metadata, "transformed": True}
)
```

## Component Registry (Future)

Planned enhancement for component discovery:

```python
from flock.components import registry

# Register custom component
registry.register("fan_out", FanOutComponent)

# Use by name
agent.with_component("fan_out", config={...})
```

## Performance Considerations

1. **Async Operations**: Use async/await for I/O operations
2. **Early Return**: Skip processing when not needed
3. **Batch Processing**: Handle multiple artifacts efficiently
4. **Memory Management**: Clean up resources in `on_terminate`

## Common Patterns

### Transform Pattern
```python
async def on_post_evaluate(self, agent, ctx, inputs, result):
    result.artifacts = [self._transform(a) for a in result.artifacts]
    return result
```

### Filter Pattern
```python
async def on_post_evaluate(self, agent, ctx, inputs, result):
    result.artifacts = [a for a in result.artifacts if self._should_keep(a)]
    return result
```

### Expand Pattern (Fan-Out)
```python
async def on_post_evaluate(self, agent, ctx, inputs, result):
    expanded = []
    for artifact in result.artifacts:
        expanded.extend(self._expand(artifact))
    result.artifacts = expanded
    return result
```

### Aggregate Pattern (Fan-In)
```python
async def on_post_evaluate(self, agent, ctx, inputs, result):
    if self._should_aggregate(result.artifacts):
        aggregated = self._combine(result.artifacts)
        result.artifacts = [aggregated]
    return result
```

## Conclusion

Components provide a clean, testable way to extend agent behavior without modifying core engine logic. The `on_post_evaluate` hook is particularly powerful for implementing patterns like fan-out, making components the recommended approach for orchestration patterns in Flock.