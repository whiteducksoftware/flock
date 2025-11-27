# Workflow Control with Conditions

Flock provides a powerful DSL for controlling workflow execution. Instead of just waiting for all work to complete, you can specify exactly when to stop based on artifact counts, field values, errors, or custom conditions.

## Quick Start

```python
from flock import Flock
from flock.core.conditions import Until

flock = Flock("openai/gpt-4.1")

# Wait for exactly 5 reports to be generated
success = await flock.run_until(
    Until.artifact_count(Report).at_least(5),
    timeout=60,
)

if success:
    print("Got 5 reports!")
else:
    print("Timed out before getting 5 reports")
```

## run_until() vs run_until_idle()

| Method | Stops When | Use Case |
|--------|-----------|----------|
| `run_until_idle()` | No pending work | Let everything finish |
| `run_until(condition)` | Condition is True | Stop at specific milestone |

```python
# Old way: wait for everything
await flock.run_until_idle()

# New way: stop when you have what you need
await flock.run_until(Until.artifact_count(Result).at_least(10))
```

## The Until Helper

The `Until` class provides a fluent interface for building conditions:

### Artifact Count Conditions

```python
from flock.core.conditions import Until

# At least N artifacts
Until.artifact_count(UserStory).at_least(5)

# At most N artifacts
Until.artifact_count(Error).at_most(3)

# Exactly N artifacts
Until.artifact_count(Approval).exactly(2)

# With filters
Until.artifact_count(
    Report,
    correlation_id="workflow-123",  # Scope to workflow
    tags={"reviewed"},              # Must have tag
    produced_by="analyst",          # From specific agent
).at_least(5)
```

### Existence Conditions

```python
# Stop when any artifact of type exists
Until.exists(FinalReport)

# Stop when NO artifacts of type exist
Until.none(BlockingIssue)

# With correlation scope
Until.exists(Approval, correlation_id="workflow-123")
```

### Field Value Conditions

```python
# Stop when any artifact has a field matching predicate
Until.any_field(
    Hypothesis,
    field="confidence",
    predicate=lambda v: v >= 0.9,  # High confidence found
)

# Multiple field checks
Until.any_field(
    Analysis,
    field="status",
    predicate=lambda v: v == "complete",
)
```

### Idle Condition

```python
# Same as run_until_idle() but composable
Until.idle()

# Alias
Until.no_pending_work()
```

### Error Conditions

```python
# Stop on first workflow error
Until.workflow_error("correlation-id")
```

## Composing Conditions

Conditions can be combined with boolean operators:

### OR (|) - Stop when ANY condition is true

```python
# Stop at 10 results OR on error
stop_condition = (
    Until.artifact_count(Result).at_least(10)
    | Until.workflow_error(correlation_id)
)

await flock.run_until(stop_condition, timeout=120)
```

### AND (&) - Stop when ALL conditions are true

```python
# Stop when we have results AND system is idle
stop_condition = (
    Until.artifact_count(Result).at_least(5)
    & Until.idle()
)

await flock.run_until(stop_condition)
```

### NOT (~) - Invert a condition

```python
# Stop when there are NO blocking issues
stop_condition = ~Until.exists(BlockingIssue)

# Equivalent to:
stop_condition = Until.none(BlockingIssue)
```

### Complex Compositions

```python
# Stop when:
# - (5+ results AND high confidence found) OR
# - Error occurred OR
# - System is idle
stop_condition = (
    (
        Until.artifact_count(Result).at_least(5)
        & Until.any_field(Result, field="confidence", predicate=lambda v: v >= 0.9)
    )
    | Until.workflow_error(cid)
    | Until.idle()
)
```

## Timeout Handling

Always consider using timeouts for production code:

```python
# With timeout (recommended)
success = await flock.run_until(condition, timeout=60.0)

if not success:
    # Handle timeout - check what we got
    results = await flock.store.get_by_type(Result)
    print(f"Timed out with {len(results)} results")

# Without timeout (blocks indefinitely until condition or idle)
await flock.run_until(condition)
```

## Activation Conditions (When Helper)

For more advanced control, you can defer agent activation until conditions are met:

```python
from flock.core.conditions import When

# QA agent only activates after 5 user stories exist
qa_agent = (
    flock.agent("qa_reviewer")
    .consumes(
        UserStory,
        activation=When.correlation(UserStory).count_at_least(5),
    )
    .publishes(QAReport)
)
```

### When Helper Methods

```python
# Count-based activation
When.correlation(Model).count_at_least(5)
When.correlation(Model).count_at_most(10)
When.correlation(Model).count_exactly(3)

# Existence-based activation
When.correlation(Model).exists()

# Field-based activation
When.correlation(Model).any_field(
    field="confidence",
    predicate=lambda v: v >= 0.9,
)
```

### Activation vs run_until

| Feature | `run_until()` | `activation=` |
|---------|--------------|---------------|
| Scope | Orchestrator-level | Per-subscription |
| Controls | When to stop running | When agent activates |
| Use case | "Stop after 10 reports" | "QA runs after 5 stories" |

### Composite Activation Conditions

```python
# Activate when 5 inputs exist OR a trigger signal arrives
activation = (
    When.correlation(Input).count_at_least(5)
    | When.correlation(TriggerSignal).exists()
)

processor.consumes(Input, activation=activation)
```

## Real-World Examples

### Backlog Generation with Early Stop

```python
# Generate user stories, stop when we have enough good ones
@flock_type
class UserStory(BaseModel):
    title: str
    points: int
    quality_score: float

# Generator produces stories
generator = flock.agent("story_generator").consumes(Brief).publishes(UserStory)

# Run until 20 high-quality stories
await flock.publish(Brief(topic="E-commerce checkout"))
success = await flock.run_until(
    Until.any_field(
        UserStory,
        field="quality_score",
        predicate=lambda scores: len([s for s in scores if s >= 8.0]) >= 20,
    ),
    timeout=120,
)
```

### Research with Confidence Threshold

```python
# Stop when a high-confidence hypothesis is found
@flock_type
class Hypothesis(BaseModel):
    content: str
    confidence: float

researcher = flock.agent("researcher").consumes(Question).publishes(Hypothesis)

await flock.publish(Question(text="What causes X?"))
await flock.run_until(
    Until.any_field(
        Hypothesis,
        field="confidence",
        predicate=lambda v: v >= 0.95,
    )
    | Until.artifact_count(Hypothesis).at_least(10),  # Or stop at 10 attempts
    timeout=300,
)
```

### Multi-Stage Pipeline with Guardrails

```python
# Synthesis agent waits for enough validated inputs
synthesis = (
    flock.agent("synthesis")
    .consumes(
        ValidatedData,
        activation=When.correlation(ValidatedData).count_at_least(3),
    )
    .publishes(SynthesisReport)
)

# Error handler activates immediately on any error
error_handler = (
    flock.agent("error_handler")
    .consumes(WorkflowError)  # No activation = immediate
    .publishes(ErrorReport)
)
```

## Best Practices

1. **Always use timeouts in production** - Prevents indefinite hangs
2. **Combine with error conditions** - Stop early on failures
3. **Use activation for rate limiting** - Prevent premature agent execution
4. **Keep conditions simple** - Complex conditions are hard to debug
5. **Log condition evaluations** - Helps understand workflow behavior

## See Also

- [Orchestrator Components](orchestrator-components.md) - ActivationComponent details
- [Agent Subscriptions](agents.md) - Full subscription options
- [Examples: Workflow Conditions](../../examples/01-getting-started/10_workflow_conditions.py) - Working example
