# PLAN.md Changes Summary - Phase 4 Architectural Pivot

## TL;DR

**Changed Phase 4 from "LLM Prompt Engineering" → "Engine Fan-Out Contract"**

Why? Not all engines are LLMs. Let engines decide HOW to implement fan-out.

---

## Key Changes

### 1. Phase 3: Marked Complete ✅

- Added completion status: "✅ COMPLETE (Shipped 2025-10-15)"
- Documented deliverables: 48/48 tests passing
- Added line numbers for implemented code
- Noted strict contract validation approach

### 2. Phase 4: Complete Rewrite 🔄

**OLD**: LLM Prompt Engineering
```python
# Old approach: Framework generates prompts for engines
def _build_group_prompt(self, output_group):
    return f"Generate {count} artifacts..."
```

**NEW**: Engine Fan-Out Contract
```python
# New approach: Engines opt-in to fan-out capability
class EngineComponent:
    async def evaluate_fanout(self, agent, ctx, inputs, count, group_description=None):
        raise NotImplementedError("Engine doesn't support fan-out")
```

**Key Points**:
- Follows existing `evaluate_batch()` pattern (lines 116-146 in components.py)
- Engine-agnostic (works for LLMs, rule engines, ML models, etc.)
- Clear error messages (like evaluate_batch)
- Opt-in pattern (engines declare capabilities)

### 3. Phase 4.5: New Optional Phase 🆕

Separated DSPyEngine-specific implementation:
- Shows ONE way to implement fan-out (using prompts)
- Other engines can implement differently
- Makes it clear: prompts are ONE strategy, not THE strategy

### 4. Success Criteria: Added 2 New Items ✅

```diff
+ ✅ Engine Fan-Out Contract: evaluate_fanout() method allows engines to opt-in
+ ✅ Engine Agnostic: No assumptions about LLMs, prompts, or engine implementation
```

### 5. Notes: Added Architectural Explanation 📝

```diff
+ - Architectural Pivot: Phase 4 changed to keep framework engine-agnostic
+ - Design Pattern: evaluate_fanout() follows evaluate_batch() opt-in pattern
```

---

## Why This Matters

### Problem with Old Approach
❌ Assumed all engines use prompts (false)
❌ Coupled agent execution to LLM concepts
❌ Made non-LLM engines harder to add
❌ Framework knew too much about engine internals

### Benefits of New Approach
✅ Works with ANY engine type (LLM, rule-based, ML, custom)
✅ Engines control their own implementation
✅ Clear opt-in pattern (like evaluate_batch)
✅ Better error messages
✅ Consistent with existing codebase patterns

---

## Example: Different Engine Implementations

```python
# DSPyEngine (Phase 4.5) - Uses prompts
async def evaluate_fanout(self, agent, ctx, inputs, count, group_description=None):
    instructions = f"Generate {count} distinct variations..."
    return await self.evaluate_with_prompt(instructions)

# RuleEngine - Runs logic multiple times
async def evaluate_fanout(self, agent, ctx, inputs, count, group_description=None):
    return EvalResult.from_objects(*[
        self.apply_rules(inputs, seed=i) for i in range(count)
    ])

# MLEngine - Samples from model
async def evaluate_fanout(self, agent, ctx, inputs, count, group_description=None):
    return EvalResult.from_objects(*[
        self.model.sample(inputs) for _ in range(count)
    ])

# SimpleEngine - Doesn't implement (raises NotImplementedError)
# Framework provides clear error: "Implement evaluate_fanout() or remove fan_out parameter"
```

---

## Implementation Impact

### Phase 4 Work
- **Location**: `src/flock/components.py` (not `src/flock/agent.py`)
- **Scope**: Add one method to EngineComponent base class
- **Tests**: Mock engine tests (no LLM required)
- **Complexity**: Low (follows existing pattern)

### Phase 4.5 Work (Optional)
- **Location**: `src/flock/engines/dspy_engine.py`
- **Scope**: Show how DSPyEngine can implement fan-out with prompts
- **Tests**: DSPy-specific tests
- **Complexity**: Medium (prompt engineering logic)

### Agent.execute() Changes
- **Detection logic**: Check if fan-out requested AND engine supports it
- **Error handling**: Provide clear message if engine doesn't support fan-out
- **Fallback**: Use standard evaluate() if no fan-out

---

## Review Checklist

- [x] Phase 3 marked complete with accurate status
- [x] Phase 4 rewritten to use engine contract pattern
- [x] Phase 4.5 added for DSPyEngine-specific implementation
- [x] Success criteria updated with 2 new items
- [x] Notes section explains architectural pivot
- [x] All changes align with existing codebase patterns (evaluate_batch)
- [x] Backward compatibility maintained
- [x] Clear error messages follow existing style

---

## Files Modified

1. **`PLAN.md`**: Updated Phases 3, 4, 4.5, Success Criteria, Notes
2. **`PHASE4_ARCHITECTURAL_PIVOT.md`**: Detailed explanation of pivot (NEW)
3. **`CHANGES_SUMMARY.md`**: This file (NEW)

---

## Recommendation

✅ **APPROVE** - This pivot:
- Removes incorrect assumptions (all engines = LLMs)
- Follows existing patterns (evaluate_batch)
- Makes framework more flexible
- Improves error messages
- Maintains backward compatibility

Next step: Proceed with Phase 4 implementation using new engine contract approach.
