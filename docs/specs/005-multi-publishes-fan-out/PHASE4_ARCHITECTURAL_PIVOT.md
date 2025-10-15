# Phase 4 Architectural Pivot: Engine-Agnostic Fan-Out

## Summary

**Date**: 2025-10-15
**Context**: After completing Phase 3, we discovered a fundamental design flaw in the planned Phase 4 approach.

**Original Phase 4**: "LLM Prompt Engineering" - Generate prompts for each OutputGroup to guide LLM artifact generation.

**New Phase 4**: "Engine Fan-Out Contract" - Add `evaluate_fanout()` method to EngineComponent, allowing ANY engine to opt-in to fan-out support.

---

## Why the Pivot?

### The Insight

After reviewing `src/flock/components.py` and the existing `evaluate_batch()` pattern (lines 116-146), we realized:

1. ❌ **Original assumption was wrong**: Not all engines are LLMs
   - Rule-based engines don't need prompts
   - ML models don't need prompts
   - Database query engines don't need prompts
   - Custom business logic engines don't need prompts

2. ✅ **Better pattern exists**: `evaluate_batch()` shows how to do optional engine capabilities
   - Base class raises `NotImplementedError` with helpful message
   - Engines opt-in by implementing the method
   - Framework detects capability and calls appropriate method
   - Clear error messages guide users to solutions

3. ✅ **Separation of concerns**: Agent framework shouldn't dictate engine implementation
   - Agent: "I need 3 outputs of type X"
   - Engine: "I know how to produce 3 outputs" (implementation is engine's choice)
   - No coupling between agent orchestration and engine internals

### The Problem with "Prompt Engineering" Phase

The original Phase 4 would have:
- Assumed all engines use prompts (false)
- Coupled agent execution to LLM-specific concepts
- Required framework to know about prompt engineering
- Made it harder to add non-LLM engines
- Violated single responsibility principle

---

## What Changed

### Phase 3: Updated Status

```diff
- **Goal**: Modify agent execution to call the engine once per OutputGroup instead of once total.
+ **Goal**: Modify agent execution to call the engine once per OutputGroup instead of once total.
+ **Status**: ✅ **COMPLETE** (Shipped 2025-10-15)
```

Added completion status and deliverables summary:
- All checkboxes marked complete
- Test results documented (48/48 passing)
- File locations and line numbers added
- Implementation highlights noted

### Phase 4: Complete Rewrite

**Old Phase 4**: LLM Prompt Engineering
- Focus: Generate system prompts for OutputGroups
- Scope: `_build_group_prompt()` method with prompt templates
- Assumption: All engines are LLMs that need prompts

**New Phase 4**: Engine Fan-Out Contract
- Focus: Add `evaluate_fanout()` method to EngineComponent base class
- Scope: Engine abstraction layer (no agent execution changes)
- Pattern: Follows `evaluate_batch()` opt-in pattern
- Benefit: Engine-agnostic, works for ANY engine type

### New Phase 4.5: DSPyEngine Implementation (Optional)

Separated DSPyEngine-specific implementation into optional Phase 4.5:
- Shows HOW one specific engine (DSPyEngine) can use prompts
- But other engines can implement `evaluate_fanout()` differently
- Rule engine: Run logic `count` times with different seeds
- ML engine: Sample `count` times from model distribution
- Mock engine: Return `count` predetermined artifacts

---

## Technical Details

### New EngineComponent Method

```python
# In src/flock/components.py - EngineComponent

async def evaluate_fanout(
    self,
    agent: Agent,
    ctx: Context,
    inputs: EvalInputs,
    count: int,
    group_description: str | None = None
) -> EvalResult:
    """Generate multiple outputs of the same type (fan-out).

    Override this method if your engine supports fan-out generation.
    Engines can use group_description to guide generation (e.g., for LLM prompts).

    Args:
        agent: Agent instance executing this engine
        ctx: Execution context
        inputs: EvalInputs with input artifacts
        count: Number of outputs to generate
        group_description: Optional instructions for this generation

    Returns:
        EvalResult with exactly `count` artifacts

    Raises:
        NotImplementedError: If engine doesn't support fan-out
    """
    raise NotImplementedError(
        f"{self.__class__.__name__} does not support fan-out generation.\n\n"
        f"To fix this:\n"
        f"1. Remove fan_out parameter from .publishes(), OR\n"
        f"2. Implement evaluate_fanout() in {self.__class__.__name__}, OR\n"
        f"3. Use a fan-out-aware engine (e.g., DSPyEngine)\n\n"
        f"Agent: {agent.name}\n"
        f"Requested count: {count}\n"
        f"Engine: {self.__class__.__name__}"
    )
```

### Agent.execute() Detection Logic

```python
# In src/flock/agent.py - Agent.execute()

for group_idx, output_group in enumerate(self.output_groups):
    group_ctx = self._prepare_group_context(ctx, group_idx, output_group)

    # Detect fan-out scenario (any output has count > 1)
    has_fanout = any(output.count > 1 for output in output_group.outputs)
    is_single_type = len(set(o.spec.type_name for o in output_group.outputs)) == 1

    if has_fanout and is_single_type:
        # Fan-out: single type, multiple instances
        fanout_count = output_group.outputs[0].count
        try:
            result = await self._run_engines_fanout(
                group_ctx,
                eval_inputs,
                count=fanout_count,
                group_description=output_group.group_description
            )
        except NotImplementedError:
            # Engine doesn't support fan-out - provide clear error
            raise ValueError(
                f"Engine {self._engines[0].__class__.__name__} does not support fan-out. "
                f"Either implement evaluate_fanout() or remove fan_out parameter."
            )
    else:
        # Standard evaluation
        result = await self._run_engines(group_ctx, eval_inputs)

    group_outputs = await self._make_outputs_for_group(group_ctx, result, output_group)
    all_outputs.extend(group_outputs)
```

---

## Design Benefits

### 1. Engine Agnostic
✅ No assumptions about LLMs, prompts, or implementation
✅ Works with rule engines, ML models, databases, custom logic
✅ Framework doesn't care HOW engines produce outputs

### 2. Opt-In Pattern
✅ Engines declare capabilities explicitly
✅ Base class provides clear error messages
✅ Follows existing `evaluate_batch()` pattern
✅ Consistent developer experience

### 3. Clear Separation of Concerns
✅ Agent framework: Orchestration and artifact collection
✅ Engine implementation: Output generation strategy
✅ Each component has single responsibility

### 4. Extensible
✅ DSPyEngine can use prompts (Phase 4.5)
✅ RuleEngine can use logic
✅ MLEngine can use model sampling
✅ CustomEngine can use any strategy

### 5. Better Error Messages
✅ "Engine X does not support fan-out" with 3 clear solutions
✅ Guides users to fix (remove fan_out, implement method, or switch engine)
✅ Consistent with existing evaluate_batch() errors

---

## Comparison: Old vs New

| Aspect | Old Phase 4 (Prompts) | New Phase 4 (Contract) |
|--------|----------------------|------------------------|
| **Scope** | Agent execution layer | Engine abstraction layer |
| **Assumption** | All engines = LLMs | Engines are diverse |
| **Implementation** | `_build_group_prompt()` | `evaluate_fanout()` |
| **Location** | `src/flock/agent.py` | `src/flock/components.py` |
| **Coupling** | High (agent knows about prompts) | Low (agent calls method) |
| **Flexibility** | LLMs only | Any engine type |
| **Error Handling** | Unclear | Clear NotImplementedError |
| **Pattern** | New pattern | Follows evaluate_batch() |
| **DSPy Implementation** | Required in Phase 4 | Optional in Phase 4.5 |

---

## Updated Success Criteria

Added two new criteria:

✅ **Engine Fan-Out Contract**: `evaluate_fanout()` method allows engines to opt-in to fan-out support
✅ **Engine Agnostic**: No assumptions about LLMs, prompts, or engine implementation details

Also updated notes section:

- **Architectural Pivot**: Phase 4 changed from "LLM Prompt Engineering" to "Engine Fan-Out Contract" to keep framework engine-agnostic
- **Design Pattern**: `evaluate_fanout()` follows the same opt-in pattern as `evaluate_batch()` - engines declare capabilities explicitly

---

## Migration Path

### For Existing Code
✅ No changes required - backward compatible
✅ Phase 3 works without fan-out support
✅ Engines that don't implement `evaluate_fanout()` still work (for non-fan-out scenarios)

### For New Fan-Out Features
1. **Framework developers** (Phase 4): Add `evaluate_fanout()` to EngineComponent
2. **Engine developers** (Phase 4.5+): Optionally implement fan-out in their engines
3. **Application developers**: Use `fan_out` parameter, get clear errors if engine doesn't support it

---

## Next Steps

1. ✅ **Phase 3 complete**: Multiple engine calls architecture shipped
2. 🔄 **Phase 4 ready**: Engine fan-out contract design approved
3. 🔜 **Phase 4 implementation**: Add `evaluate_fanout()` to EngineComponent
4. 🔜 **Phase 4.5 implementation**: (Optional) Add DSPyEngine support
5. 🔜 **Phase 5**: Filtering, validation, visibility (unchanged)
6. 🔜 **Phase 6**: Documentation and examples (minor updates)
7. 🔜 **Phase 7**: Integration & end-to-end validation

---

## Files Modified

- `docs/specs/005-multi-publishes-fan-out/PLAN.md`:
  - Phase 3: Added completion status and deliverables
  - Phase 4: Complete rewrite (LLM prompts → engine contract)
  - Phase 4.5: New optional phase for DSPyEngine implementation
  - Success Criteria: Added 2 new criteria
  - Notes: Added architectural pivot explanation

---

## Approval Needed

This architectural pivot represents a fundamental design improvement that:
- Makes the framework more flexible and extensible
- Removes incorrect assumptions about engine types
- Follows existing patterns in the codebase
- Improves error messages and developer experience

**Recommendation**: Proceed with new Phase 4 architecture. The benefits far outweigh any minor delay in implementation.
