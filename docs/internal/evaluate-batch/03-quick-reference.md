# Quick Reference: evaluate_batch Implementation

**For rapid lookup during implementation** 📖

---

## 🎯 Files to Modify (in order)

1. **src/flock/components.py** (line ~108)
   - Add `evaluate_batch()` method to `EngineComponent`

2. **src/flock/runtime.py** (line ~252)
   - Add `is_batch: bool = False` to `Context`

3. **src/flock/orchestrator.py** (lines ~997, 999, 1015)
   - Add `is_batch` parameter to `_schedule_task()`
   - Add `is_batch` parameter to `_run_agent_task()`
   - Set `is_batch=True` when flushing BatchSpec

4. **src/flock/agent.py** (line ~241-274)
   - Add routing logic in `_run_engines()`

5. **src/flock/engines/examples/simple_batch_engine.py** (new file)
   - Create example batch engine

---

## 💻 Code Snippets (Copy-Paste Ready)

### 1. evaluate_batch() Method (components.py)

```python
async def evaluate_batch(
    self, agent: Agent, ctx: Context, inputs: EvalInputs
) -> EvalResult:
    """Process batch of accumulated artifacts (BatchSpec).

    Override this method if your engine supports batch processing.

    Args:
        agent: Agent instance executing this engine
        ctx: Execution context (ctx.is_batch will be True)
        inputs: EvalInputs with inputs.artifacts containing batch items

    Returns:
        EvalResult with processed artifacts

    Raises:
        NotImplementedError: If engine doesn't support batching

    Example:
        >>> async def evaluate_batch(self, agent, ctx, inputs):
        ...     events = inputs.all_as(Event)  # Get ALL items
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

### 2. Context.is_batch Field (runtime.py)

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

### 3. Orchestrator Changes

**_schedule_task signature (line ~999)**:
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

**_run_agent_task signature (line ~1015)**:
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

**Batch flush call (line ~997)**:
```python
# Schedule agent with ALL artifacts (batched, correlated, or AND gate complete)
# NEW: Mark as batch execution if flushed from BatchSpec
is_batch_execution = subscription.batch is not None
self._schedule_task(agent, artifacts, is_batch=is_batch_execution)
```

### 4. Agent Routing Logic (agent.py, line ~241)

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

    if self.best_of_n <= 1:
        return await run_chain()

    # ... rest unchanged
```

---

## 🧪 Test Commands

### Run specific test files
```bash
# Components tests
uv run pytest tests/test_components.py -v

# Runtime tests
uv run pytest tests/test_runtime.py -v

# Orchestrator tests
uv run pytest tests/test_orchestrator.py -v

# Batch tests
uv run pytest tests/test_orchestrator_batchspec.py -v

# Agent tests
uv run pytest tests/test_agent.py -v
```

### Run all tests with coverage
```bash
cd src/flock
uv run pytest tests/ -v --cov=flock --cov-report=html
```

### Run formatter and linter
```bash
uv run ruff format src/flock/
uv run ruff check src/flock/
```

---

## 📝 Commit Message Templates

### Phase 1: Base Class
```
feat: Add evaluate_batch() method to EngineComponent base class

- Added evaluate_batch() with clear NotImplementedError
- Error message provides actionable guidance
- No breaking changes - purely additive API
- Includes unit test for default behavior

Part of: Phase 1 - evaluate_batch support
```

### Phase 2: Context
```
feat: Add is_batch field to Context for batch execution tracking

- Added Context.is_batch boolean field (default False)
- Enables routing between evaluate() and evaluate_batch()
- No breaking changes - optional field with default
- Includes unit test for field behavior

Part of: Phase 2 - evaluate_batch support
```

### Phase 3: Orchestrator
```
feat: Propagate is_batch flag through task scheduling

- Updated _schedule_task() to accept is_batch parameter
- Updated _run_agent_task() to pass is_batch to Context
- Set is_batch=True when flushing BatchSpec accumulator
- All other scheduling paths use is_batch=False (default)
- Includes integration test for flag propagation

Part of: Phase 3 - evaluate_batch support
```

### Phase 4: Agent Routing
```
feat: Route agent execution to evaluate_batch for BatchSpec

- Agent._run_engines() checks ctx.is_batch flag
- Calls evaluate_batch() when is_batch=True
- Calls evaluate() when is_batch=False (default)
- Logs routing decisions for debugging
- Handles NotImplementedError with clear context
- Includes unit test for routing logic

Part of: Phase 4 - evaluate_batch support
```

### Phase 5: Example Engine
```
feat: Add SimpleBatchEngine example and integration tests

- Created SimpleBatchEngine as reference implementation
- Implements both evaluate() and evaluate_batch()
- Demonstrates batch processing pattern
- Added integration test verifying end-to-end batch flow
- Added test for non-batch engine error handling
- All tests pass with new batch routing

Part of: Phase 5 - evaluate_batch support
```

---

## 🔍 grep Commands (Finding Things Fast)

```bash
# Find all _schedule_task calls
grep -rn "_schedule_task" src/flock/orchestrator.py

# Find evaluate() method implementations
grep -rn "async def evaluate" src/flock/

# Find Context usage
grep -rn "Context(" src/flock/

# Find is_batch usage (after implementation)
grep -rn "is_batch" src/flock/
```

---

## 🐛 Common Issues & Solutions

### Issue: "TypeError: _schedule_task() got an unexpected keyword argument 'is_batch'"
**Solution**: Update ALL calls to `_schedule_task()` to pass `is_batch=False`

### Issue: evaluate_batch not being called
**Check**:
1. Is `ctx.is_batch` set correctly? Add: `print(f"is_batch={ctx.is_batch}")`
2. Is routing logic in agent._run_engines correct?
3. Is BatchSpec actually triggering flush?

### Issue: Tests failing with "agent_name" not found
**Solution**: The error f-string needs `{agent.name}`, not `{agent_name}`

### Issue: Coverage too low
**Solution**: Run `pytest --cov-report=html`, open report, find uncovered lines, add tests

---

## 📊 Success Metrics Checklist

Quick checklist for "is this phase done?":

**Phase 1**:
- [ ] evaluate_batch() exists in EngineComponent
- [ ] Raises NotImplementedError
- [ ] Error message clear and helpful
- [ ] Unit test passes

**Phase 2**:
- [ ] Context has is_batch field
- [ ] Default is False
- [ ] Can be set to True
- [ ] Serialization works

**Phase 3**:
- [ ] _schedule_task accepts is_batch
- [ ] _run_agent_task accepts is_batch
- [ ] Context receives is_batch value
- [ ] Batch flush sets is_batch=True

**Phase 4**:
- [ ] Agent routes to evaluate_batch when is_batch=True
- [ ] Agent routes to evaluate when is_batch=False
- [ ] NotImplementedError handled gracefully
- [ ] Logging shows routing decisions

**Phase 5**:
- [x] SimpleBatchEngine exists
- [ ] Integration test: 3 artifacts → all processed
- [ ] Error test: non-batch engine → clear error
- [ ] Manual test works

**Phase 6**:
- [ ] BatchSpec docs updated
- [ ] Engine development guide created
- [ ] API reference complete
- [ ] Examples clear

**Phase 7**:
- [ ] All tests pass
- [ ] Coverage ≥95%
- [ ] Manual tests work
- [ ] No ruff errors

---

## 🚀 Phase Duration Estimates

- Phase 1: 30 min ☕
- Phase 2: 30 min ☕
- Phase 3: 1 hour ☕☕
- Phase 4: 1.5 hours ☕☕☕
- Phase 5: 1 hour ☕☕
- Phase 6: 1.5 hours ☕☕☕
- Phase 7: 1 hour ☕☕
- Phase 8: 30 min ☕

**Total: 4-6 hours**

Suggested schedule:
- Morning: Phases 1-3 (2 hours)
- Lunch break 🍕
- Afternoon: Phases 4-5 (2.5 hours)
- Coffee break ☕
- Evening: Phases 6-8 (2 hours)

---

## 💡 Pro Tips

1. **Start fresh** - Morning coffee, clear mind, focused time
2. **One phase at a time** - Don't jump ahead
3. **Test after every change** - Catch issues early
4. **Commit frequently** - Each phase = one commit
5. **Read the error messages** - They're designed to be helpful
6. **Take breaks** - Stand up, stretch, hydrate
7. **Celebrate progress** - Each phase is a win! 🎉

---

## 📞 Help Resources

If stuck:
1. Check Implementation Plan (01-implementation-plan.md)
2. Check Checklist (02-implementation-checklist.md)
3. Search existing code for similar patterns
4. Check git history for similar changes
5. Read test files for usage examples
6. Ask team member for pair programming

**Don't spin for >30 minutes alone!**

---

## ✅ Final Checklist

Before marking as "DONE":

- [ ] All 8 phases complete
- [ ] All tests pass
- [ ] Coverage ≥95%
- [ ] Documentation complete
- [ ] PR created and merged
- [ ] Celebration achieved! 🎉

---

**Good luck tomorrow-us! You've got this! 💪☕🚀**
