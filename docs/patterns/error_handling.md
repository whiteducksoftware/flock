# Error Handling Patterns in Flock

This guide documents error handling best practices and patterns used throughout the Flock framework. Following these patterns ensures consistent, debuggable, and maintainable error handling across the codebase.

---

## Table of Contents

1. [Pattern 1: Specific Exception Types](#pattern-1-specific-exception-types)
2. [Pattern 2: Error Context and Causation](#pattern-2-error-context-and-causation)
3. [Pattern 3: Custom Exceptions](#pattern-3-custom-exceptions)
4. [Pattern 4: Component Error Hooks](#pattern-4-component-error-hooks)
5. [Anti-Patterns](#anti-patterns)
6. [Testing Error Handling](#testing-error-handling)

---

## Pattern 1: Specific Exception Types

### When to Use

Catch specific exception types rather than broad `Exception` when you know what can go wrong and need different handling for different error cases.

### Examples from Flock

**Good: Specific exception handling**
```python
# From orchestrator/scheduler.py (line 174)
def _check_visibility(self, artifact: Artifact, identity: AgentIdentity) -> bool:
    """Check if artifact is visible to agent."""
    try:
        return artifact.visibility.allows(identity)
    except AttributeError:  # pragma: no cover - fallback
        return True
```

**Why this works:**
- Catches only `AttributeError` (expected if visibility is None)
- Provides sensible fallback behavior
- Doesn't hide unexpected errors

**Good: Multiple specific handlers**
```python
# From store implementations
async def get(self, artifact_id: str) -> Artifact | None:
    try:
        result = await self._execute_query(query, [artifact_id])
        return self._parse_artifact(result[0]) if result else None
    except IndexError:
        return None  # No results
    except ValueError as e:
        # Artifact data is corrupted
        self._logger.error("Failed to parse artifact %s: %s", artifact_id, e)
        raise
```

### When to Catch Broad Exceptions

Use broad `Exception` only when:
1. You're logging and re-raising
2. You're implementing a plugin/component boundary
3. You must never fail (rare!)

```python
# From core/orchestrator.py (line 820)
try:
    await self.store.record_consumptions(records)
except NotImplementedError:
    pass  # Store doesn't support consumption tracking
except Exception as exc:  # pragma: no cover - defensive logging
    self._logger.exception("Failed to record artifact consumption: %s", exc)
    # Don't re-raise - consumption tracking is optional
```

**Why this works:**
- First catches expected `NotImplementedError`
- Broad `Exception` is last resort for defensive logging
- Only used when failure MUST NOT propagate

---

## Pattern 2: Error Context and Causation

### Adding Context to Errors

Always provide context when catching and re-raising errors. Use `logger.exception()` for automatic traceback capture and `from e` for causation chains.

### Examples from Flock

**Good: Context preservation with causation**
```python
# Pattern used in agent execution
try:
    result = await engine.evaluate(self, ctx, inputs, output_group)
except ValueError as e:
    # Add context about which engine and agent failed
    self._logger.exception(
        "Engine evaluation failed: agent=%s, engine=%s",
        self.name,
        engine.__class__.__name__
    )
    raise RuntimeError(
        f"Engine {engine.__class__.__name__} failed for agent {self.name}"
    ) from e  # Preserve original cause
```

**Good: Rich error logging**
```python
# From scheduler logging
self._logger.error(
    "Circuit breaker tripped: agent=%s, iterations=%s, limit=%s",
    agent.name,
    current_count,
    max_limit
)
```

### Context Keys to Include

When logging errors, include:
- **Agent name** - Which agent failed
- **Artifact ID** - What artifact was being processed
- **Subscription** - Which subscription matched
- **Component** - Which component failed
- **Operation** - What operation was attempted

```python
# Comprehensive error context
logger.exception(
    "Failed to process artifact: "
    "agent=%s, artifact_id=%s, artifact_type=%s, operation=%s",
    agent.name,
    artifact.id,
    artifact.type,
    "evaluation",
    exc_info=True  # Include full traceback
)
```

---

## Pattern 3: Custom Exceptions

### When to Create Custom Exceptions

Create custom exception classes when:
1. You need to distinguish your errors from library errors
2. You want to attach structured data to errors
3. You need a hierarchy of related errors

### Examples from Flock

**Basic custom exception:**
```python
class CircuitBreakerError(Exception):
    """Raised when circuit breaker prevents agent execution."""

    def __init__(self, agent_name: str, iteration_count: int, max_iterations: int):
        self.agent_name = agent_name
        self.iteration_count = iteration_count
        self.max_iterations = max_iterations
        super().__init__(
            f"Circuit breaker tripped for agent {agent_name}: "
            f"{iteration_count}/{max_iterations} iterations"
        )
```

**Exception hierarchy:**
```python
class FlockError(Exception):
    """Base exception for all Flock errors."""
    pass

class SubscriptionError(FlockError):
    """Errors related to subscription matching."""
    pass

class InvalidJoinSpecError(SubscriptionError):
    """JoinSpec validation failed."""

    def __init__(self, spec: dict, reason: str):
        self.spec = spec
        self.reason = reason
        super().__init__(f"Invalid JoinSpec: {reason}")
```

**Usage:**
```python
# Raise with context
if not all(key in spec for key in required_keys):
    raise InvalidJoinSpecError(
        spec=spec,
        reason=f"Missing required keys: {required_keys - spec.keys()}"
    )

# Catch hierarchy
try:
    await process_subscription(subscription)
except SubscriptionError as e:
    # Handle all subscription-related errors
    logger.error("Subscription failed: %s", e)
except FlockError as e:
    # Handle other Flock errors
    logger.error("Flock error: %s", e)
```

---

## Pattern 4: Component Error Hooks

### Agent Component Error Handling

Agent components can implement `on_error` hooks to handle errors gracefully:

```python
from flock.components.agent import AgentComponent
from flock.runtime import Context

class RetryComponent(AgentComponent):
    """Retry failed evaluations with exponential backoff."""

    priority = 5

    async def on_error(
        self,
        agent: Agent,
        ctx: Context,
        error: Exception
    ) -> None:
        """Handle evaluation errors with retry logic."""
        if isinstance(error, TimeoutError) and ctx.retry_count < 3:
            # Exponential backoff
            delay = 2 ** ctx.retry_count
            logger.warning(
                "Retrying after timeout: agent=%s, attempt=%s, delay=%ss",
                agent.name,
                ctx.retry_count + 1,
                delay
            )
            await asyncio.sleep(delay)
            ctx.retry_count += 1
            # Re-raise to trigger retry
            raise
        else:
            # Max retries exceeded or non-retriable error
            logger.error(
                "Giving up after error: agent=%s, error=%s",
                agent.name,
                error.__class__.__name__
            )
            # Don't re-raise - allow graceful failure
```

### Orchestrator Component Error Handling

Orchestrator components can prevent scheduling on errors:

```python
from flock.components.orchestrator import OrchestratorComponent, ScheduleDecision

class ErrorTrackingComponent(OrchestratorComponent):
    """Track and block agents with high error rates."""

    priority = 5

    def __init__(self):
        super().__init__()
        self._error_counts: dict[str, int] = {}
        self._max_errors = 10

    async def on_before_schedule(
        self,
        orchestrator: Flock,
        artifact: Artifact,
        agent: Agent,
        subscription: Subscription
    ) -> ScheduleDecision:
        """Skip agents with too many errors."""
        error_count = self._error_counts.get(agent.name, 0)
        if error_count >= self._max_errors:
            logger.warning(
                "Blocking agent due to errors: agent=%s, errors=%s",
                agent.name,
                error_count
            )
            return ScheduleDecision.SKIP
        return ScheduleDecision.CONTINUE

    async def on_orchestrator_idle(self, orchestrator: Flock) -> None:
        """Reset error counts when idle."""
        self._error_counts.clear()
```

---

## Anti-Patterns

### ❌ Anti-Pattern 1: Silent Failures

**BAD:**
```python
try:
    await risky_operation()
except Exception:
    pass  # Silently swallow all errors
```

**Why it's bad:**
- Hides bugs completely
- Makes debugging impossible
- Violates principle of least surprise

**GOOD:**
```python
try:
    await risky_operation()
except OperationError as e:
    # Log the error with context
    logger.warning(
        "Operation failed but continuing: operation=%s, error=%s",
        "risky_operation",
        e
    )
    # Optionally: metrics.increment("operation_errors")
```

### ❌ Anti-Pattern 2: Catching Without Re-raising

**BAD:**
```python
try:
    await critical_operation()
except Exception as e:
    logger.error("Operation failed: %s", e)
    # Error logged but not propagated - caller has no idea!
```

**Why it's bad:**
- Caller thinks operation succeeded
- Can lead to data corruption
- Breaks error handling chain

**GOOD:**
```python
try:
    await critical_operation()
except Exception as e:
    logger.exception("Critical operation failed")
    # Add context and re-raise
    raise RuntimeError("Critical operation failed") from e
```

### ❌ Anti-Pattern 3: Losing Error Context

**BAD:**
```python
try:
    result = await engine.evaluate(inputs)
except Exception:
    raise ValueError("Evaluation failed")  # Lost original error!
```

**Why it's bad:**
- Original exception type lost
- Traceback lost
- Root cause unclear

**GOOD:**
```python
try:
    result = await engine.evaluate(inputs)
except Exception as e:
    # Preserve causation chain
    raise ValueError(
        f"Evaluation failed for agent {agent.name}"
    ) from e  # ← Preserves original exception
```

### ❌ Anti-Pattern 4: Bare Except

**BAD:**
```python
try:
    await operation()
except:  # Catches EVERYTHING including KeyboardInterrupt!
    logger.error("Failed")
```

**Why it's bad:**
- Catches `KeyboardInterrupt`, `SystemExit`, etc.
- Makes program un-killable
- Hides syntax errors during development

**GOOD:**
```python
try:
    await operation()
except Exception as e:  # Only catches normal exceptions
    logger.error("Operation failed: %s", e)
    raise
```

---

## Testing Error Handling

### Using pytest.raises()

```python
import pytest
from flock import Flock
from flock.components.orchestrator import CircuitBreakerComponent

@pytest.mark.asyncio
async def test_circuit_breaker_prevents_infinite_loops():
    """Test that circuit breaker stops runaway agents."""
    flock = Flock("test")
    flock.add_component(CircuitBreakerComponent(max_iterations=5))

    # Create agent that triggers itself infinitely
    agent = (
        flock.agent("infinite_loop")
        .consumes(Task)
        .publishes(Task)
        .prevent_self_trigger(False)  # Allow feedback loop
    )

    # Should stop after 5 iterations due to circuit breaker
    await flock.publish(Task(name="start"))
    await flock.run_until_idle()

    # Verify circuit breaker worked
    assert flock._agent_iteration_count[agent.name] == 5
```

### Verifying Error Messages

```python
@pytest.mark.asyncio
async def test_invalid_subscription_error_message():
    """Test that invalid subscriptions have clear error messages."""
    flock = Flock("test")

    with pytest.raises(ValueError) as exc_info:
        flock.agent("test").consumes(
            Task,
            join={"by": ["missing_field"]}  # Invalid JoinSpec
        )

    # Verify error message is helpful
    assert "missing_field" in str(exc_info.value)
    assert "JoinSpec" in str(exc_info.value)
```

### Testing Exception Context

```python
@pytest.mark.asyncio
async def test_engine_error_includes_context():
    """Test that engine errors include agent and artifact context."""
    flock = Flock("test")

    # Mock engine that always fails
    class FailingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            raise RuntimeError("Simulated engine failure")

    agent = (
        flock.agent("failing_agent")
        .consumes(Task)
        .publishes(Result)
        .with_engines(FailingEngine())
    )

    # Capture logs
    with pytest.raises(RuntimeError) as exc_info:
        await flock.arun(agent, Task(name="test"))

    # Verify error includes context
    assert "failing_agent" in str(exc_info.value)
    assert "engine" in str(exc_info.value).lower()
```

### Mocking for Error Testing

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_storage_error_handling():
    """Test that storage errors are handled gracefully."""
    flock = Flock("test")

    # Mock storage to raise error
    with patch.object(flock.store, 'persist',
                     side_effect=IOError("Disk full")):
        with pytest.raises(IOError) as exc_info:
            await flock.publish(Task(name="test"))

        # Verify error message
        assert "Disk full" in str(exc_info.value)
```

---

## Summary

**Key Principles:**

1. **Be Specific** - Catch specific exceptions when you know what can fail
2. **Add Context** - Include agent, artifact, and operation details in logs
3. **Preserve Causation** - Use `from e` to maintain error chains
4. **Log with `exception()`** - Get automatic tracebacks
5. **Test Errors** - Verify error messages and context
6. **Never Silence** - Always log or re-raise exceptions
7. **Use Components** - Implement error hooks for reusable error handling

**When in Doubt:**
- Log the error with full context
- Re-raise unless you have a very good reason not to
- Ask: "Will this make debugging harder?"
