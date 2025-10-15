# Concurrency Fix: OutputGroup Parameter for All Engine Methods

**Date**: 2025-10-15
**Status**: In Progress
**Context**: Phase 4 implementation

## The Problem

During Phase 4 implementation, we discovered a **critical concurrency bug** in the engine contract design.

### Original Broken Design

```python
# EngineComponent base class
async def evaluate(self, agent, ctx, inputs) -> EvalResult
async def evaluate_batch(self, agent, ctx, inputs) -> EvalResult
async def evaluate_fanout(self, agent, ctx, inputs, count, group_description=None) -> EvalResult
```

### Why This Breaks

**Scenario**: Agent with multiple output groups
```python
agent = (
    flock.agent("multi")
    .publishes(TaskArtifact, fan_out=3)  # Group 0
    .publishes(ResultArtifact)           # Group 1
)
```

**Execution flow**:
1. Agent calls `engine.evaluate_fanout()` for Group 0
2. Agent calls `engine.evaluate()` for Group 1

**The Issue**: Engine receives `agent` parameter which contains **ALL** `agent.output_groups`

Engine sees:
```python
agent.output_groups = [
    OutputGroup(outputs=[TaskArtifact(count=3)]),  # Group 0
    OutputGroup(outputs=[ResultArtifact(count=1)])  # Group 1
]
```

**But engine doesn't know WHICH group it's processing!**

### Attempted Workarounds (All Broken)

#### ❌ Workaround 1: Track call count in engine
```python
class MockEngine(EngineComponent):
    _call_count = 0

    async def evaluate(self, agent, ctx, inputs):
        current_group = agent.output_groups[self._call_count]
        self._call_count += 1
        # Generate artifacts based on current_group
```

**Problem**: Breaks with concurrency!
- If 2 agents share the same engine instance
- If 1 agent runs multiple times concurrently
- Call count becomes corrupt

#### ❌ Workaround 2: Add group_idx to context
```python
# Agent passes group index via context
ctx.current_group_idx = 0
result = await engine.evaluate(agent, ctx, inputs)
```

**Problem**: Pollutes Context with execution details, violates abstraction boundaries

#### ❌ Workaround 3: Hacky agent property
```python
# Agent sets hidden property before calling engine
agent._current_group_idx = 0
result = await engine.evaluate(agent, ctx, inputs)
```

**Problem**: Hidden state, thread-unsafe, terrible design

### The Real Issue

**Engines need to know exactly what to produce, but the signature doesn't tell them.**

## The Solution

### New Clean Design

**Pass `OutputGroup` explicitly to ALL engine methods:**

```python
# EngineComponent base class
async def evaluate(self, agent, ctx, inputs, output_group: OutputGroup) -> EvalResult
async def evaluate_batch(self, agent, ctx, inputs, output_group: OutputGroup) -> EvalResult
async def evaluate_fanout(self, agent, ctx, inputs, output_group: OutputGroup) -> EvalResult
```

### Why This Works

**Now engines receive complete information:**

```python
class MockEngine(EngineComponent):
    async def evaluate_fanout(self, agent, ctx, inputs, output_group):
        # Extract exactly what we need to produce
        first_output = output_group.outputs[0]
        count = first_output.count
        type_name = first_output.spec.type_name
        description = output_group.group_description

        # Generate artifacts accordingly
        artifacts = [create_artifact(type_name) for _ in range(count)]
        return EvalResult.from_objects(*artifacts, agent=agent)
```

**Benefits**:
- ✅ **Thread-safe**: No shared state
- ✅ **Concurrency-safe**: Each call is independent
- ✅ **Clear contract**: Engine knows exactly what to produce
- ✅ **Single source of truth**: OutputGroup contains all requirements
- ✅ **Testable**: Easy to test in isolation

## Implementation Changes

### 1. EngineComponent Signatures (components.py)

```python
class EngineComponent(AgentComponent):
    async def evaluate(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs,
        output_group: OutputGroup  # NEW
    ) -> EvalResult:
        raise NotImplementedError

    async def evaluate_batch(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs,
        output_group: OutputGroup  # NEW
    ) -> EvalResult:
        raise NotImplementedError(...)

    async def evaluate_fanout(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs,
        output_group: OutputGroup  # CHANGED from count + description
    ) -> EvalResult:
        raise NotImplementedError(...)
```

### 2. Agent Execution (agent.py)

```python
# In Agent.execute()
for group_idx, output_group in enumerate(self.output_groups):
    group_ctx = self._prepare_group_context(ctx, group_idx, output_group)

    # Detect which method to call
    if has_fanout and is_single_type:
        result = await self._run_engines_fanout(
            group_ctx, eval_inputs, output_group  # Pass group
        )
    else:
        result = await self._run_engines(
            group_ctx, eval_inputs, output_group  # Pass group
        )
```

```python
# Helper methods updated
async def _run_engines(self, ctx, inputs, output_group):
    for engine in engines:
        result = await engine.evaluate(self, ctx, inputs, output_group)
        # ...

async def _run_engines_fanout(self, ctx, inputs, output_group):
    engine = engines[0]
    result = await engine.evaluate_fanout(self, ctx, inputs, output_group)
    # ...
```

### 3. All Engine Implementations

**Every engine implementation must be updated:**

- `src/flock/engines/dspy_engine.py` - DSPyEngine
- Test engines in `tests/` - MockEngine, BasicEngine, etc.
- Any custom engines in examples

**Example update**:
```python
# Before
async def evaluate(self, agent, ctx, inputs):
    # Had to guess what to produce by looking at agent.output_groups

# After
async def evaluate(self, agent, ctx, inputs, output_group):
    # Knows exactly what to produce from output_group parameter
```

## Breaking Changes

This is a **breaking change** that affects:

1. **All engine implementations** - Signature changed
2. **All tests calling engines directly** - Must pass output_group
3. **Custom engines** - Users must update their engines

### Migration Guide

**Before**:
```python
class MyEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs):
        return EvalResult.from_objects(MyArtifact(), agent=agent)
```

**After**:
```python
class MyEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Use output_group to determine what to produce
        first_output = output_group.outputs[0]
        artifact_type = first_output.spec.type_name
        # ... generate appropriate artifacts
        return EvalResult.from_objects(MyArtifact(), agent=agent)
```

## Testing Strategy

1. **Update EngineComponent base class** ✅
2. **Update Agent._run_engines() and _run_engines_fanout()** - In progress
3. **Find all engine implementations** - Use grep/search
4. **Update each engine one by one** - Systematic approach
5. **Update all tests** - Comprehensive test updates
6. **Run full test suite** - Verify nothing broken
7. **Update documentation** - Document breaking change

## Backwards Compatibility

**None** - This is an intentional breaking change for architectural correctness.

**Justification**: Better to fix this now (during Phase 4 development) than after shipping Phase 4 with the broken concurrency design.

## Decision Rationale

**Why accept a breaking change?**

1. **Concurrency is critical** - Broken concurrency = broken framework
2. **Early in development** - Phase 4 not yet shipped
3. **Clean architecture** - No workarounds, no hacks
4. **Future-proof** - Scales to any number of output groups
5. **Better DX** - Engine developers have clear contracts

**The alternative** (keeping broken design) would require:
- Complex workarounds
- Hidden state management
- Thread locks
- Difficult debugging
- Fragile under load

**Conclusion**: Accept the breaking change, update everything systematically, ship it right.

## Files Requiring Updates

### Core Framework
- [ ] `src/flock/components.py` - EngineComponent signatures
- [ ] `src/flock/agent.py` - Agent._run_engines(), _run_engines_fanout()
- [ ] `src/flock/engines/dspy_engine.py` - DSPyEngine implementation
- [ ] Any other engine implementations in src/

### Tests
- [ ] `tests/test_engine_fanout.py` - Phase 4 tests
- [ ] `tests/test_agent_builder.py` - Phase 3 tests with engine calls
- [ ] Any other test files with engine implementations

### Examples
- [ ] Search for custom engines in `examples/` directory
- [ ] Update any engines found

## Progress Tracking

- [x] Problem identified
- [x] Solution designed
- [x] Documentation written (this file)
- [ ] EngineComponent updated
- [ ] Agent execution updated
- [ ] DSPyEngine updated
- [ ] All test engines updated
- [ ] Full test suite passing
- [ ] PLAN.md updated

---

**Last Updated**: 2025-10-15
**Status**: Ready to implement
