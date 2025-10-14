# Implementation Plan: evaluate_batch Support

**Status**: Planning
**Created**: 2025-01-14 03:00 AM
**Target**: Phase 4 - Batch Processing Enhancement

---

## 🎯 Problem Statement

**Current Issue**: DSPy engine only processes the LAST artifact in a batch (`artifacts[-1]`), ignoring all other accumulated items. This makes BatchSpec effectively broken for actual batch processing.

**Discovery Location**: `flock/engines/dspy_engine.py:351-352`

```python
def _select_primary_artifact(self, artifacts: Sequence[Artifact]) -> Artifact:
    return artifacts[-1]  # ← ONLY processes last artifact!
```

**Impact**:
- BatchSpec accumulates artifacts correctly ✅
- But DSPy engine discards all but the last one ❌
- Users expect ALL accumulated artifacts to be processed together

---

## 🏗️ Solution Architecture

### Core Design Principle
**"Batch processing is opt-in at the engine level"**

Engines that support batch processing implement `evaluate_batch()`. Engines that don't will raise a clear error if used with BatchSpec subscriptions.

### API Surface

```python
class EngineComponent(AgentComponent):
    """Base class for engine components."""

    async def evaluate(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs
    ) -> EvalResult:
        """Process single artifact or AND gate result.

        This is the default execution path for:
        - Single type subscriptions
        - AND gate complete (multiple types, one of each)
        - JoinSpec complete (correlated group)
        """
        raise NotImplementedError

    async def evaluate_batch(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs
    ) -> EvalResult:
        """Process a batch of accumulated artifacts (BatchSpec).

        Override this method if your engine supports batch processing.

        Args:
            inputs.artifacts: List of artifacts accumulated by BatchSpec.
                             Could be:
                             - N individual artifacts (single type + BatchSpec)
                             - N correlated groups (JoinSpec + BatchSpec)
                             - N AND gate results (multi-type + BatchSpec)

        Returns:
            EvalResult with processed outputs

        Raises:
            NotImplementedError: If engine doesn't support batching.
                                Provides actionable error message.

        Example:
            >>> async def evaluate_batch(self, agent, ctx, inputs):
            ...     events = inputs.all_as(Event)  # Get ALL items
            ...     # Process all together (e.g., bulk API call)
            ...     results = await bulk_process(events)
            ...     return EvalResult.from_objects(*results, agent=agent)
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support batch processing.\n\n"
            f"To fix this:\n"
            f"1. Remove BatchSpec from agent subscription, OR\n"
            f"2. Implement evaluate_batch() in {self.__class__.__name__}, OR\n"
            f"3. Use a batch-aware engine (e.g., CustomBatchEngine)\n\n"
            f"Agent: {agent.name}\n"
            f"Engine: {self.__class__.__name__}"
        )
```

---

## 🔄 Execution Flow Changes

### Current Flow (Single Artifact)

```
Orchestrator.publish(artifact)
  ↓
_schedule_artifact(artifact)
  ↓ (subscription matches)
_schedule_task(agent, [artifact])
  ↓
_run_agent_task(agent, [artifact])
  ↓
agent.execute(ctx, [artifact])
  ↓
agent._run_engines(ctx, EvalInputs(artifacts=[artifact]))
  ↓
engine.evaluate(agent, ctx, inputs)  # ← Single artifact
```

### New Flow (Batch)

```
Orchestrator.publish(artifact1)
  ↓ (batch accumulator)
BatchEngine.add_artifact() → should_flush=False (wait)

Orchestrator.publish(artifact2)
  ↓
BatchEngine.add_artifact() → should_flush=False (wait)

Orchestrator.publish(artifact3)
  ↓
BatchEngine.add_artifact() → should_flush=TRUE! (size=3 reached)
  ↓
_schedule_task(agent, [art1, art2, art3], is_batch=True)  # ← NEW FLAG
  ↓
_run_agent_task(agent, [art1, art2, art3], is_batch=True)
  ↓
agent.execute(ctx, [art1, art2, art3])
  where ctx.is_batch = True  # ← NEW CONTEXT FLAG
  ↓
agent._run_engines(ctx, EvalInputs(artifacts=[art1, art2, art3]))
  ↓
if ctx.is_batch:
    engine.evaluate_batch(agent, ctx, inputs)  # ← BATCH PATH!
else:
    engine.evaluate(agent, ctx, inputs)        # ← SINGLE PATH
```

---

## 📦 Component Changes

### 1. `flock/components.py` (EngineComponent)

**Changes**:
- Add `evaluate_batch()` method with default NotImplementedError
- Clear error message with actionable guidance
- Docstring examples showing usage

**Lines to modify**: Around line 108 (after `evaluate()`)

**New code**:
```python
async def evaluate_batch(
    self, agent: Agent, ctx: Context, inputs: EvalInputs
) -> EvalResult:
    """Process batch of accumulated artifacts (BatchSpec).

    Override this method if your engine supports batch processing.
    """
    raise NotImplementedError(
        f"{self.__class__.__name__} does not support batch processing.\n\n"
        f"To fix this:\n"
        f"1. Remove BatchSpec from agent subscription, OR\n"
        f"2. Implement evaluate_batch() in {self.__class__.__name__}, OR\n"
        f"3. Use a batch-aware engine\n\n"
        f"Agent: {agent.name}\n"
        f"Engine: {self.__class__.__name__}"
    )
```

---

### 2. `flock/runtime.py` (Context)

**Changes**:
- Add `is_batch: bool = False` field to Context model

**Lines to modify**: Around line 247-252

**New code**:
```python
class Context(BaseModel):
    board: Any
    orchestrator: Any
    correlation_id: UUID | None = None
    task_id: str
    state: dict[str, Any] = Field(default_factory=dict)
    is_batch: bool = Field(
        default=False,
        description="True if this execution is processing a BatchSpec accumulation"
    )
```

---

### 3. `flock/orchestrator.py` (Task Scheduling)

**Changes**:
- Update `_schedule_task()` to accept `is_batch` flag
- Update `_run_agent_task()` to accept `is_batch` flag
- Pass `is_batch` flag to Context
- Set `is_batch=True` when flushing batch (line ~997)

**Lines to modify**:
- Line 997: Add `is_batch=True` when scheduling batch flush
- Line 999: Update `_schedule_task` signature
- Line 1015: Update `_run_agent_task` signature
- Line 1018-1023: Add `is_batch` to Context creation

**New code (line 997)**:
```python
# Schedule agent with ALL artifacts (batched, correlated, or AND gate complete)
# NEW: Mark as batch execution if flushed from BatchSpec
is_batch_execution = subscription.batch is not None
self._schedule_task(agent, artifacts, is_batch=is_batch_execution)
```

**New code (_schedule_task)**:
```python
def _schedule_task(
    self,
    agent: Agent,
    artifacts: list[Artifact],
    is_batch: bool = False  # NEW!
) -> None:
    task = asyncio.create_task(
        self._run_agent_task(agent, artifacts, is_batch=is_batch)
    )
    self._tasks.add(task)
    task.add_done_callback(self._tasks.discard)
```

**New code (_run_agent_task)**:
```python
async def _run_agent_task(
    self,
    agent: Agent,
    artifacts: list[Artifact],
    is_batch: bool = False  # NEW!
) -> None:
    correlation_id = artifacts[0].correlation_id if artifacts else uuid4()

    ctx = Context(
        board=BoardHandle(self),
        orchestrator=self,
        task_id=str(uuid4()),
        correlation_id=correlation_id,
        is_batch=is_batch,  # NEW!
    )
    self._record_agent_run(agent)
    await agent.execute(ctx, artifacts)
    # ... rest unchanged
```

---

### 4. `flock/agent.py` (Engine Routing)

**Changes**:
- Update `_run_engines()` to check `ctx.is_batch`
- Route to `evaluate_batch()` if batch mode
- Handle NotImplementedError with clear context

**Lines to modify**: Around line 241-274 (inside `_run_engines`)

**New code**:
```python
async def _run_engines(self, ctx: Context, inputs: EvalInputs) -> EvalResult:
    engines = self._resolve_engines()
    if not engines:
        return EvalResult(artifacts=inputs.artifacts, state=inputs.state)

    async def run_chain() -> EvalResult:
        current_inputs = inputs
        accumulated_logs: list[str] = []
        accumulated_metrics: dict[str, float] = {}

        for engine in engines:
            current_inputs = await engine.on_pre_evaluate(self, ctx, current_inputs)

            # NEW: Route to evaluate_batch if in batch mode
            try:
                if getattr(ctx, 'is_batch', False):
                    logger.debug(
                        f"Agent {self.name}: Routing to evaluate_batch "
                        f"({len(current_inputs.artifacts)} artifacts)"
                    )
                    result = await engine.evaluate_batch(self, ctx, current_inputs)
                else:
                    result = await engine.evaluate(self, ctx, current_inputs)
            except NotImplementedError as e:
                # Re-raise with additional context
                logger.error(
                    f"Batch processing error for agent {self.name}: {str(e)}"
                )
                raise

            # AUTO-WRAP: If engine returns BaseModel instead of EvalResult, wrap it
            from flock.runtime import EvalResult as ER

            if isinstance(result, BaseModel) and not isinstance(result, ER):
                result = ER.from_object(result, agent=self)

            result = await engine.on_post_evaluate(self, ctx, current_inputs, result)
            accumulated_logs.extend(result.logs)
            accumulated_metrics.update(result.metrics)

            # Merge state for next engine in chain
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

    # Rest of method unchanged (best_of_n logic)
    if self.best_of_n <= 1:
        return await run_chain()
    # ... rest unchanged
```

---

## 🎓 Example Implementations

### Example 1: Simple Batch Engine

```python
from flock.components import EngineComponent
from flock.runtime import Context, EvalInputs, EvalResult

class SimpleBatchEngine(EngineComponent):
    """Example engine that processes batches by looping."""

    async def evaluate(self, agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        """Single artifact processing."""
        event = inputs.first_as(Event)
        result = process_single_event(event)
        return EvalResult.from_object(result, agent=agent)

    async def evaluate_batch(self, agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        """Batch processing - loop over all artifacts."""
        events = inputs.all_as(Event)  # Get ALL items

        results = []
        for event in events:
            result = process_single_event(event)
            results.append(result)

        return EvalResult.from_objects(*results, agent=agent)
```

### Example 2: Bulk API Batch Engine

```python
class BulkAPIBatchEngine(EngineComponent):
    """Engine that makes bulk API calls for efficiency."""

    async def evaluate(self, agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        """Single artifact - make single API call."""
        order = inputs.first_as(Order)
        result = await api_client.process_payment(order)
        return EvalResult.from_object(result, agent=agent)

    async def evaluate_batch(self, agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        """Batch - make BULK API call (25x cost savings!)."""
        orders = inputs.all_as(Order)

        # Single bulk API call for all orders
        results = await api_client.bulk_process_payments(orders)

        return EvalResult.from_objects(*results, agent=agent)
```

### Example 3: LLM Batch Engine (Advanced)

```python
class LLMBatchEngine(EngineComponent):
    """Engine that sends all batch items to LLM in single prompt."""

    async def evaluate_batch(self, agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        """Send entire batch to LLM for analysis."""
        events = inputs.all_as(Event)

        # Construct prompt with all events
        batch_prompt = f"""
        Analyze these {len(events)} events together:

        {json.dumps([e.model_dump() for e in events], indent=2)}

        Provide insights for the batch.
        """

        # Send to LLM
        result = await llm.generate(batch_prompt)

        return EvalResult.from_object(result, agent=agent)
```

---

## 🚨 Error Handling

### Error Case 1: BatchSpec + Non-Batch Engine

```python
# User code
agent = (
    flock.agent("batch_processor")
    .consumes(Event, batch=BatchSpec(size=10))
    .with_engines(DSPyEngine())  # Doesn't support batching!
)

# Runtime error (clear and actionable):
NotImplementedError: DSPyEngine does not support batch processing.

To fix this:
1. Remove BatchSpec from agent subscription, OR
2. Implement evaluate_batch() in DSPyEngine, OR
3. Use a batch-aware engine

Agent: batch_processor
Engine: DSPyEngine
```

### Error Case 2: Engine Crashes in evaluate_batch

```python
# Engine raises exception during batch processing
try:
    result = await engine.evaluate_batch(agent, ctx, inputs)
except Exception as e:
    logger.error(
        f"Batch processing failed for agent {agent.name}: {str(e)}",
        exc_info=True
    )
    # Re-raise with context
    raise RuntimeError(
        f"Agent {agent.name} batch processing failed "
        f"({len(inputs.artifacts)} artifacts): {str(e)}"
    ) from e
```

---

## 🧪 Testing Strategy

### Unit Tests

1. **Test EngineComponent.evaluate_batch() default**
   - Verify NotImplementedError is raised
   - Verify error message is clear and actionable
   - Verify agent name is in error message

2. **Test Context.is_batch field**
   - Verify default is False
   - Verify can be set to True
   - Verify serialization works

3. **Test _schedule_task with is_batch flag**
   - Verify flag is passed through correctly
   - Verify Context receives flag

4. **Test agent._run_engines routing**
   - Verify evaluate() called when is_batch=False
   - Verify evaluate_batch() called when is_batch=True
   - Verify NotImplementedError is caught and re-raised with context

### Integration Tests

1. **Test BatchSpec with batch-aware engine**
   - Accumulate 3 artifacts
   - Verify evaluate_batch() called with all 3
   - Verify results are correct

2. **Test BatchSpec with non-batch engine (should fail)**
   - Accumulate artifacts
   - Verify NotImplementedError is raised
   - Verify error message is clear

3. **Test single artifact (non-batch) still works**
   - Verify evaluate() called (not evaluate_batch())
   - Verify backward compatibility

4. **Test JoinSpec + BatchSpec combo**
   - Batch correlated groups
   - Verify evaluate_batch() receives groups as batch items

### Example Test Code

```python
import pytest
from flock import Flock
from flock.components import EngineComponent
from flock.runtime import Context, EvalInputs, EvalResult
from flock.subscription import BatchSpec

class BatchSupportEngine(EngineComponent):
    """Test engine with batch support."""

    async def evaluate(self, agent, ctx, inputs):
        # Single artifact
        return EvalResult.from_object(
            Result(count=1),
            agent=agent
        )

    async def evaluate_batch(self, agent, ctx, inputs):
        # Batch - return count of items
        return EvalResult.from_object(
            Result(count=len(inputs.artifacts)),
            agent=agent
        )

@pytest.mark.asyncio
async def test_batch_engine_called():
    """Verify evaluate_batch() is called for BatchSpec."""
    flock = Flock()

    engine = BatchSupportEngine()
    agent = (
        flock.agent("batcher")
        .consumes(Event, batch=BatchSpec(size=3))
        .with_engines(engine)
    )

    # Publish 3 events
    await flock.publish(Event(id=1))
    await flock.publish(Event(id=2))
    await flock.publish(Event(id=3))
    await flock.run_until_idle()

    # Verify batch was processed
    results = await flock.store.list()
    assert len(results) == 4  # 3 inputs + 1 output

    # Verify output shows batch count
    output = [r for r in results if r.type == "Result"][0]
    assert output.payload["count"] == 3  # All 3 processed together!

@pytest.mark.asyncio
async def test_non_batch_engine_raises_error():
    """Verify clear error when engine doesn't support batching."""
    from flock.engines import DSPyEngine

    flock = Flock()

    agent = (
        flock.agent("batcher")
        .consumes(Event, batch=BatchSpec(size=3))
        .with_engines(DSPyEngine())  # No batch support!
    )

    # Publish 3 events
    await flock.publish(Event(id=1))
    await flock.publish(Event(id=2))
    await flock.publish(Event(id=3))

    # Should raise clear error
    with pytest.raises(NotImplementedError) as exc_info:
        await flock.run_until_idle()

    error_msg = str(exc_info.value)
    assert "DSPyEngine does not support batch processing" in error_msg
    assert "batcher" in error_msg  # Agent name in error
    assert "Remove BatchSpec" in error_msg  # Actionable guidance
```

---

## 📚 Documentation Updates

### User Docs to Update

1. **BatchSpec Guide** (`docs/features/batch-processing.md`)
   - Add section on batch-aware engines
   - Show example custom engine implementations
   - Explain error messages

2. **Engine Development Guide** (new file)
   - How to implement evaluate_batch()
   - When to use batch vs single processing
   - Performance considerations

3. **API Reference**
   - Document EngineComponent.evaluate_batch()
   - Document Context.is_batch field
   - Update examples

### Example Documentation

```markdown
## Batch-Aware Engines

To use BatchSpec, your engine must implement `evaluate_batch()`:

### Example: Simple Batch Engine

\```python
class MyBatchEngine(EngineComponent):
    async def evaluate_batch(self, agent, ctx, inputs: EvalInputs):
        # Get all accumulated artifacts
        events = inputs.all_as(Event)

        # Process them together
        results = process_batch(events)

        return EvalResult.from_objects(*results, agent=agent)
\```

### Error: Engine Doesn't Support Batching

If you see this error:

\```
NotImplementedError: DSPyEngine does not support batch processing.
\```

You have three options:
1. Remove `batch=BatchSpec(...)` from your subscription
2. Implement `evaluate_batch()` in your engine
3. Use a batch-aware engine like `SimpleBatchEngine`
```

---

## 🔄 Backward Compatibility

### Breaking Changes
**NONE** - This is purely additive!

- Existing engines continue to work (they only implement `evaluate()`)
- New `evaluate_batch()` method has default implementation (raises error)
- Error only occurs if user explicitly adds BatchSpec with non-batch engine
- Error message is clear and actionable

### Migration Path
No migration needed! Existing code continues to work as-is.

**Optional**: Add batch support to custom engines by implementing `evaluate_batch()`.

---

## 📊 Success Metrics

### Implementation Complete When:

1. ✅ `EngineComponent.evaluate_batch()` method exists with clear error
2. ✅ `Context.is_batch` field exists and is populated correctly
3. ✅ Orchestrator passes `is_batch` flag through task scheduling
4. ✅ Agent routes to `evaluate_batch()` when `ctx.is_batch=True`
5. ✅ All unit tests pass (see Testing Strategy)
6. ✅ All integration tests pass
7. ✅ Documentation is updated
8. ✅ Example batch-aware engine implementations exist

### Quality Gates

- Zero breaking changes to existing code
- Clear error messages for misconfiguration
- Code coverage ≥ 95% for new code paths
- Documentation complete and reviewed
- Example engines tested and working

---

## 🎯 Future Enhancements (Out of Scope)

These are **NOT** part of this implementation:

1. DSPy engine batch support (separate effort)
2. Batch timeout handling improvements
3. Batch size auto-tuning
4. Batch metrics and monitoring
5. Batch preview in dashboard UI

Focus on the core API foundation first!

---

## 📝 Notes for Tomorrow-We-Both

- Start with Phase 1 (base class changes) - simplest and lowest risk
- Test each phase independently before moving on
- Run existing test suite after each change to catch regressions
- Create example batch engine EARLY to validate API design
- Keep PRs small and focused (one phase = one PR)

Good luck, tomorrow-us! 🚀☕
