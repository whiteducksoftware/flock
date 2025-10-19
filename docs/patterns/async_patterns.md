# Async Patterns in Flock

This guide documents async/await patterns and best practices used throughout the Flock framework. Following these patterns ensures correct concurrent behavior, prevents race conditions, and maintains performance.

---

## Table of Contents

1. [Pattern 1: Sequential Operations](#pattern-1-sequential-operations)
2. [Pattern 2: Parallel Operations](#pattern-2-parallel-operations)
3. [Pattern 3: Fire-and-Forget Tasks](#pattern-3-fire-and-forget-tasks)
4. [Pattern 4: Async Context Managers](#pattern-4-async-context-managers)
5. [Pattern 5: Async Iteration](#pattern-5-async-iteration)
6. [Pattern 6: Task Groups (Python 3.11+)](#pattern-6-task-groups-python-311)
7. [Anti-Patterns](#anti-patterns)
8. [Testing Async Code](#testing-async-code)

---

## Pattern 1: Sequential Operations

### When to Use

Use sequential operations when:
- Operation B depends on result from Operation A
- Order of execution matters
- You need to maintain state consistency

### Examples from Flock

**Sequential agent execution:**
```python
# From core/agent.py (line 244)
async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
    """Execute agent with sequential lifecycle hooks."""
    async with self._semaphore:
        try:
            # Each step depends on the previous
            self._resolve_engines()
            self._resolve_utilities()
            await self._run_initialize(ctx)  # 1. Initialize

            processed_inputs = await self._run_pre_consume(ctx, artifacts)  # 2. Pre-consume

            eval_inputs = EvalInputs(
                artifacts=processed_inputs, state=dict(ctx.state)
            )
            eval_inputs = await self._run_pre_evaluate(ctx, eval_inputs)  # 3. Pre-evaluate

            # ... more sequential steps

            return outputs
        except Exception as exc:
            await self._run_error(ctx, exc)
            raise
        finally:
            await self._run_terminate(ctx)
```

**Why sequential:**
- Each hook depends on previous hook's output
- State must be consistent at each step
- Hooks must run in priority order

**Sequential engine chain:**
```python
# From core/agent.py (line 346)
async def run_chain() -> EvalResult:
    """Chain multiple engines sequentially."""
    current_inputs = inputs
    accumulated_logs: list[str] = []
    accumulated_metrics: dict[str, float] = {}

    for engine in engines:
        # Each engine processes output of previous
        current_inputs = await engine.on_pre_evaluate(self, ctx, current_inputs)
        result = await engine.evaluate(self, ctx, current_inputs, output_group)
        result = await engine.on_post_evaluate(self, ctx, current_inputs, result)

        # Accumulate results
        accumulated_logs.extend(result.logs)
        accumulated_metrics.update(result.metrics)

        # Pass output to next engine
        merged_state = dict(current_inputs.state)
        merged_state.update(result.state)
        current_inputs = EvalInputs(
            artifacts=result.artifacts or current_inputs.artifacts,
            state=merged_state,
        )

    return EvalResult(
        artifacts=current_inputs.artifacts,
        state=current_inputs.state,
        metrics=accumulated_metrics,
        logs=accumulated_logs,
    )
```

### Performance Implications

Sequential operations are **slower** but **safer**:
- ✅ Guaranteed order of execution
- ✅ Consistent state at each step
- ✅ Easy to debug and reason about
- ❌ No parallelism - full latency cost

---

## Pattern 2: Parallel Operations

### When to Use

Use parallel operations when:
- Operations are independent
- No shared mutable state
- You want maximum throughput
- Order doesn't matter

### Examples from Flock

**Parallel agent scheduling:**
```python
# From orchestrator/scheduler.py (line 126)
def schedule_task(
    self, agent: Agent, artifacts: list[Artifact], is_batch: bool = False
) -> Task[Any]:
    """Schedule agent task to run in parallel with others."""
    task = asyncio.create_task(
        self._orchestrator._run_agent_task(agent, artifacts, is_batch=is_batch)
    )
    self._tasks.add(task)
    task.add_done_callback(self._tasks.discard)
    return task
```

**Why parallel:**
- Each agent execution is independent
- No shared state between agents
- Maximum parallelism for throughput

**Parallel best-of-N execution:**
```python
# From core/agent.py (line 388)
async with asyncio.TaskGroup() as tg:  # Python 3.11+
    tasks: list[asyncio.Task[EvalResult]] = []
    for _ in range(self.best_of_n):
        # Run N evaluations in parallel
        tasks.append(tg.create_task(run_chain()))

# All tasks complete before continuing
results = [task.result() for task in tasks]
if self.best_of_score is None:
    return results[0]
return max(results, key=self.best_of_score)
```

**Why parallel:**
- All N runs are independent
- Want fastest possible completion
- Take best result from all runs

### Using asyncio.gather()

```python
# Pattern: Parallel operations with error handling
async def process_multiple_artifacts(artifacts: list[Artifact]) -> list[Result]:
    """Process multiple artifacts in parallel."""
    tasks = [
        process_single_artifact(artifact)
        for artifact in artifacts
    ]

    # Run all tasks in parallel
    # return_exceptions=False: First exception stops all (default)
    # return_exceptions=True: Collect all results and exceptions
    results = await asyncio.gather(*tasks, return_exceptions=False)

    return results

# With error handling
async def process_with_fallback(artifacts: list[Artifact]) -> list[Result]:
    """Process in parallel, handle individual failures."""
    tasks = [
        process_single_artifact(artifact)
        for artifact in artifacts
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out failures
    successful = [
        r for r in results
        if not isinstance(r, Exception)
    ]

    # Log failures
    failures = [
        r for r in results
        if isinstance(r, Exception)
    ]
    for error in failures:
        logger.error("Task failed: %s", error)

    return successful
```

### Performance Implications

Parallel operations are **faster** but **more complex**:
- ✅ Maximum throughput
- ✅ Better resource utilization
- ❌ Race conditions possible
- ❌ Harder to debug
- ❌ Need proper error handling

---

## Pattern 3: Fire-and-Forget Tasks

### When to Use

Use fire-and-forget for:
- Background monitoring tasks
- Non-critical operations
- Cleanup operations
- Periodic tasks

### Examples from Flock

**Background batch timeout checker:**
```python
# From orchestrator/lifecycle_manager.py
async def start_batch_timeout_checker(self) -> None:
    """Start background task to check batch timeouts."""
    if self._batch_timeout_task is not None:
        return  # Already running

    # Create task but don't await it
    self._batch_timeout_task = asyncio.create_task(
        self._batch_timeout_loop()
    )

    # Task runs in background until shutdown

async def _batch_timeout_loop(self) -> None:
    """Background loop that checks timeouts periodically."""
    while True:
        await asyncio.sleep(1.0)  # Check every second

        # Call timeout callback
        if self._batch_timeout_callback:
            await self._batch_timeout_callback()
```

**Background correlation cleanup:**
```python
# From orchestrator/lifecycle_manager.py
async def start_correlation_cleanup(self) -> None:
    """Start background cleanup of expired correlations."""
    if self._correlation_cleanup_task is not None:
        return  # Already running

    self._correlation_cleanup_task = asyncio.create_task(
        self._correlation_cleanup_loop()
    )

async def _correlation_cleanup_loop(self) -> None:
    """Periodically clean up expired correlation groups."""
    while True:
        await asyncio.sleep(5.0)  # Check every 5 seconds

        await self._correlation_engine.cleanup_expired()
```

### Task Lifecycle Management

**IMPORTANT:** Always clean up fire-and-forget tasks on shutdown!

```python
class LifecycleManager:
    def __init__(self):
        self._batch_timeout_task: asyncio.Task | None = None
        self._correlation_cleanup_task: asyncio.Task | None = None

    async def shutdown(self) -> None:
        """Shutdown and clean up background tasks."""
        # Cancel batch timeout task
        if self._batch_timeout_task is not None:
            self._batch_timeout_task.cancel()
            try:
                await self._batch_timeout_task
            except asyncio.CancelledError:
                pass  # Expected
            self._batch_timeout_task = None

        # Cancel correlation cleanup task
        if self._correlation_cleanup_task is not None:
            self._correlation_cleanup_task.cancel()
            try:
                await self._correlation_cleanup_task
            except asyncio.CancelledError:
                pass  # Expected
            self._correlation_cleanup_task = None
```

### When NOT to Use Fire-and-Forget

❌ **Never use for:**
- Operations that must complete
- Operations that produce critical results
- Operations that modify shared state without locks

---

## Pattern 4: Async Context Managers

### When to Use

Use async context managers for:
- Resource acquisition/release (locks, connections)
- Cleanup guarantees
- Tracing boundaries
- Temporary state changes

### Examples from Flock

**Tracing context:**
```python
# From orchestrator/tracing.py
@asynccontextmanager
async def traced_run(
    self, name: str = "workflow", flock_id: str | None = None
) -> AsyncGenerator[Any, None]:
    """Context manager for unified tracing."""
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(
        name,
        attributes={
            "flock.workflow": name,
            "flock.orchestrator_id": flock_id or "unknown",
        },
    ) as span:
        self.current_workflow_span = span
        try:
            yield span
        finally:
            self.current_workflow_span = None

# Usage
async with flock.traced_run("pizza_workflow"):
    await flock.publish(pizza_idea)
    await flock.run_until_idle()
```

**Semaphore for concurrency control:**
```python
# From core/agent.py (line 245)
async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
    """Execute agent with concurrency limit."""
    async with self._semaphore:  # Limit concurrent executions
        try:
            # Do work
            outputs = await self._process(ctx, artifacts)
            return outputs
        finally:
            # Semaphore automatically released
            pass
```

**Custom async context manager:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def agent_execution_context(agent: Agent, ctx: Context):
    """Context manager for agent execution lifecycle."""
    # Setup
    await agent._run_initialize(ctx)
    logger.info("Agent %s initialized", agent.name)

    try:
        yield agent
    except Exception as exc:
        # Error handling
        await agent._run_error(ctx, exc)
        raise
    finally:
        # Cleanup (always runs)
        await agent._run_terminate(ctx)
        logger.info("Agent %s terminated", agent.name)

# Usage
async with agent_execution_context(agent, ctx) as agent:
    result = await agent.evaluate(inputs)
```

### Benefits

✅ Guaranteed cleanup (even on exceptions)
✅ Clear resource boundaries
✅ Readable, self-documenting code
✅ Prevents resource leaks

---

## Pattern 5: Async Iteration

### When to Use

Use async iteration for:
- Streaming results
- Processing queues
- Hook execution
- Database cursors

### Examples from Flock

**Async generator for component hooks:**
```python
# From orchestrator/component_runner.py
async def run_hook(
    self, hook_name: str, *args, **kwargs
) -> AsyncIterator[tuple[OrchestratorComponent, Any]]:
    """Execute hook on all components, yielding results."""
    for component in self._components:
        hook = getattr(component, hook_name, None)
        if hook is None:
            continue

        try:
            result = await hook(*args, **kwargs)
            yield component, result  # Yield each result
        except Exception as exc:
            self._logger.exception(
                "Component hook failed: component=%s, hook=%s",
                component.name or component.__class__.__name__,
                hook_name
            )
            # Continue with next component
```

**Using async iteration:**
```python
# Iterate over hook results
async for component, result in runner.run_hook("on_idle", orchestrator):
    logger.info(
        "Component %s idle result: %s",
        component.name,
        result
    )
```

**Async generator for streaming:**
```python
async def stream_agent_outputs(
    agent: Agent,
    inputs: list[Artifact]
) -> AsyncIterator[Artifact]:
    """Stream outputs as they're generated."""
    async for output in agent.execute_streaming(inputs):
        # Process each output immediately
        logger.info("Got output: %s", output.type)
        yield output
        # Could publish immediately for real-time cascade

# Usage
async for artifact in stream_agent_outputs(agent, inputs):
    await orchestrator.publish(artifact)
```

### Error Handling in Async Iteration

```python
async def process_with_error_handling() -> AsyncIterator[Result]:
    """Stream results, handling errors gracefully."""
    try:
        async for item in source_iterator():
            try:
                result = await process(item)
                yield result
            except ProcessingError as e:
                # Log but continue
                logger.warning("Failed to process item: %s", e)
                continue
    finally:
        # Cleanup even if consumer breaks early
        await cleanup()
```

---

## Pattern 6: Task Groups (Python 3.11+)

### When to Use

Use `asyncio.TaskGroup` instead of `gather()` for:
- Automatic exception propagation
- Automatic task cancellation
- Cleaner error handling

### Examples from Flock

**Best-of-N with TaskGroup:**
```python
# From core/agent.py (line 388)
async with asyncio.TaskGroup() as tg:
    tasks: list[asyncio.Task[EvalResult]] = []
    for _ in range(self.best_of_n):
        tasks.append(tg.create_task(run_chain()))

# All tasks guaranteed to complete (or all cancelled on error)
results = [task.result() for task in tasks]
```

**Benefits over gather():**
- If ANY task fails, ALL tasks are cancelled immediately
- Cleaner exception handling (first exception re-raised)
- No need for `return_exceptions=True` complexity

**Comparison:**
```python
# OLD WAY (gather)
tasks = [run_agent(a) for a in agents]
try:
    results = await asyncio.gather(*tasks)
except Exception:
    # Manual cleanup needed
    for task in tasks:
        if not task.done():
            task.cancel()
    raise

# NEW WAY (TaskGroup - Python 3.11+)
async with asyncio.TaskGroup() as tg:
    tasks = [tg.create_task(run_agent(a)) for a in agents]
# Automatic cancellation on error!
results = [t.result() for t in tasks]
```

---

## Anti-Patterns

### ❌ Anti-Pattern 1: Blocking Operations in Async Functions

**BAD:**
```python
async def process_artifact(artifact: Artifact) -> Result:
    # BLOCKING! Freezes entire event loop
    response = requests.get("https://api.example.com/data")
    return Result(data=response.json())
```

**Why it's bad:**
- Blocks event loop
- No other tasks can run
- Defeats purpose of async

**GOOD:**
```python
import httpx  # Async HTTP library

async def process_artifact(artifact: Artifact) -> Result:
    async with httpx.AsyncClient() as client:
        # Non-blocking HTTP request
        response = await client.get("https://api.example.com/data")
        return Result(data=response.json())
```

### ❌ Anti-Pattern 2: Missing `await`

**BAD:**
```python
async def broken_function():
    # Returns coroutine object, doesn't execute!
    result = some_async_function()  # Missing await

    # result is <coroutine object>, not the actual result
    return result
```

**Python will warn:**
```
RuntimeWarning: coroutine 'some_async_function' was never awaited
```

**GOOD:**
```python
async def correct_function():
    result = await some_async_function()  # Properly awaited
    return result
```

### ❌ Anti-Pattern 3: Not Handling Task Cancellation

**BAD:**
```python
async def background_task():
    while True:
        await asyncio.sleep(1)
        await do_work()  # Never handles cancellation
```

**Why it's bad:**
- Shutdown hangs waiting for task
- Resources not released
- Tests timeout

**GOOD:**
```python
async def background_task():
    try:
        while True:
            await asyncio.sleep(1)
            await do_work()
    except asyncio.CancelledError:
        # Cleanup on cancellation
        await cleanup()
        raise  # Re-raise to signal completion
```

### ❌ Anti-Pattern 4: Creating Tasks Without Tracking

**BAD:**
```python
async def start_agents():
    for agent in agents:
        # Fire-and-forget with no tracking!
        asyncio.create_task(agent.run())

    # No way to wait for completion or handle errors
```

**Why it's bad:**
- Can't wait for completion
- Errors are silently swallowed
- Resource leaks

**GOOD:**
```python
async def start_agents():
    tasks = set()
    for agent in agents:
        task = asyncio.create_task(agent.run())
        tasks.add(task)
        # Remove from set when done
        task.add_done_callback(tasks.discard)

    # Wait for all tasks
    await asyncio.gather(*tasks)
```

### ❌ Anti-Pattern 5: Deadlocks with Locks

**BAD:**
```python
async def deadlock_example():
    async with lock_a:
        await asyncio.sleep(0.1)
        async with lock_b:  # Different order in other function!
            await do_work()

async def other_function():
    async with lock_b:  # Opposite order = potential deadlock!
        await asyncio.sleep(0.1)
        async with lock_a:
            await do_work()
```

**GOOD:**
```python
# Always acquire locks in same order
async def correct_example():
    async with lock_a:  # Always A first
        async with lock_b:  # Always B second
            await do_work()

async def other_function():
    async with lock_a:  # Same order everywhere
        async with lock_b:
            await do_work()
```

---

## Testing Async Code

### Basic Async Test

```python
import pytest

@pytest.mark.asyncio
async def test_agent_execution():
    """Test async agent execution."""
    flock = Flock("test")
    agent = flock.agent("test").consumes(Task).publishes(Result)

    # Await async operations
    await flock.publish(Task(name="test"))
    await flock.run_until_idle()

    # Verify results
    artifacts = await flock.store.list()
    assert len(artifacts) == 2  # Input + output
```

### Testing Concurrent Operations

```python
@pytest.mark.asyncio
async def test_concurrent_agent_execution():
    """Test that agents run in parallel."""
    flock = Flock("test")

    execution_times = []

    async def slow_agent(inputs):
        start = time.time()
        await asyncio.sleep(1.0)
        execution_times.append(time.time() - start)
        return Result()

    # Create 3 agents
    for i in range(3):
        flock.agent(f"agent_{i}").consumes(Task).calls(slow_agent)

    # Publish to all 3
    start = time.time()
    await flock.publish(Task(name="test"))
    await flock.run_until_idle()
    total_time = time.time() - start

    # Should complete in ~1 second (parallel), not 3 seconds (sequential)
    assert total_time < 1.5, "Agents should run in parallel"
    assert len(execution_times) == 3
```

### Mocking Async Functions

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_async_mock():
    """Test using async mocks."""
    flock = Flock("test")

    # Mock async method
    mock_evaluate = AsyncMock(return_value=EvalResult(artifacts=[]))

    with patch.object(DSPyEngine, 'evaluate', mock_evaluate):
        agent = flock.agent("test").consumes(Task).publishes(Result)
        await flock.arun(agent, Task(name="test"))

        # Verify mock was called
        assert mock_evaluate.call_count == 1
```

### Testing Timeouts

```python
@pytest.mark.asyncio
async def test_timeout_handling():
    """Test that operations timeout correctly."""
    flock = Flock("test")

    async def slow_operation():
        await asyncio.sleep(10)  # Very slow

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_operation(), timeout=1.0)
```

---

## Summary

**Key Principles:**

1. **Sequential** - Use when order matters and operations depend on each other
2. **Parallel** - Use for independent operations to maximize throughput
3. **Fire-and-Forget** - Use for background tasks, always clean up on shutdown
4. **Context Managers** - Use for guaranteed cleanup and resource management
5. **Async Iteration** - Use for streaming and progressive processing
6. **Task Groups** - Use for automatic cancellation and error handling (Python 3.11+)

**Golden Rules:**
- Always `await` async functions
- Handle `asyncio.CancelledError` in background tasks
- Track all created tasks
- Use locks in consistent order
- Test concurrent behavior
- Clean up resources in `finally` blocks

**Performance Tips:**
- Parallelize independent operations
- Use semaphores to limit concurrency
- Batch operations when possible
- Profile with `asyncio` debugging tools
