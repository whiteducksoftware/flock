# evaluate_batch Implementation Guide

**Implementation of batch-aware engine support for Flock's BatchSpec feature**

---

## 📚 Documentation Structure

This folder contains complete documentation for implementing `evaluate_batch()` support:

1. **[01-implementation-plan.md](./01-implementation-plan.md)** - Technical design document
   - Problem statement and discovery
   - Solution architecture
   - Component-by-component changes
   - Example implementations
   - Error handling strategy
   - Testing approach

2. **[02-implementation-checklist.md](./02-implementation-checklist.md)** - Step-by-step execution plan
   - 8 phases with detailed tasks
   - Each phase is independent and testable
   - Commit message templates
   - Success criteria
   - Troubleshooting guide

3. **[03-quick-reference.md](./03-quick-reference.md)** - Implementation cheat sheet
   - Copy-paste ready code snippets
   - Test commands
   - Common issues and solutions
   - Progress tracking

---

## 🎯 Quick Start

**If you're starting implementation tomorrow, do this**:

1. **Read Phase 1 of the checklist** (02-implementation-checklist.md)
   - It's only 30 minutes
   - Lowest risk
   - Gets you warmed up

2. **Keep Quick Reference open** (03-quick-reference.md)
   - Has all the code snippets
   - Has test commands
   - Has troubleshooting tips

3. **Work through phases sequentially**
   - Each phase builds on the previous
   - Each phase is independently testable
   - Each phase = one commit

---

## 🎓 Overview

### The Problem

DSPy engine only processes the **last artifact** in a batch:

```python
# Current bug (dspy_engine.py:351)
def _select_primary_artifact(self, artifacts: Sequence[Artifact]) -> Artifact:
    return artifacts[-1]  # ← Only processes LAST artifact!
```

**Impact**: BatchSpec accumulates 10 artifacts, but only 1 gets processed!

### The Solution

Add `evaluate_batch()` method to `EngineComponent`:

```python
class EngineComponent(AgentComponent):
    async def evaluate(self, agent, ctx, inputs):
        """Single artifact (existing)"""
        pass

    async def evaluate_batch(self, agent, ctx, inputs):
        """Batch of artifacts (NEW!)"""
        # Process ALL artifacts together
        events = inputs.all_as(Event)  # Get ALL items
        results = await bulk_process(events)
        return EvalResult.from_objects(*results, agent=agent)
```

### Key Features

- ✅ **Opt-in**: Engines choose to support batching
- ✅ **Clear errors**: Helpful message if engine doesn't support batching
- ✅ **Backward compatible**: Zero breaking changes
- ✅ **Type safe**: `ctx.is_batch` flag indicates batch mode
- ✅ **Well tested**: Unit, integration, and manual tests

---

## 🏗️ Implementation Phases

### Phase 1: Base Class (30 min)
Add `evaluate_batch()` to `EngineComponent` with clear error message.

### Phase 2: Context (30 min)
Add `is_batch` field to `Context` model.

### Phase 3: Orchestrator (1 hour)
Propagate `is_batch` flag through task scheduling.

### Phase 4: Agent Routing (1.5 hours)
Route to `evaluate_batch()` when `ctx.is_batch=True`.

### Phase 5: Example Engine (1 hour)
Create `SimpleBatchEngine` as reference implementation.

### Phase 6: Documentation (1.5 hours)
Update docs with examples and guides.

### Phase 7: Validation (1 hour)
Run full test suite, manual testing, coverage checks.

### Phase 8: PR & Merge (30 min)
Create PR, get review, merge.

**Total Time**: 4-6 hours

---

## 📖 How to Use This Documentation

### Before Starting
1. Read the Implementation Plan (01-implementation-plan.md)
   - Understand the problem and solution
   - Review the architecture
   - Check the example implementations

2. Skim the Checklist (02-implementation-checklist.md)
   - Get a feel for the phases
   - Note the time estimates
   - Check the success criteria

### During Implementation
1. **Follow the Checklist** (02-implementation-checklist.md)
   - Work through Phase 1 → Phase 8
   - Check off tasks as you complete them
   - Use provided commit messages

2. **Keep Quick Reference handy** (03-quick-reference.md)
   - Copy code snippets
   - Run test commands
   - Look up solutions to common issues

3. **Refer to Implementation Plan** (01-implementation-plan.md)
   - When you need deeper understanding
   - When designing test cases
   - When writing documentation

### After Completion
1. Update this README with:
   - Actual time taken
   - Any issues encountered
   - Lessons learned
   - Improvements for future

---

## 🧪 Testing Strategy

### Test Coverage Required
- Unit tests for base class behavior
- Integration tests for end-to-end flow
- Error handling tests
- Manual testing with examples

### Target Metrics
- Code coverage: ≥95% for new code
- All existing tests: 100% pass
- No ruff errors
- Clear documentation

---

## 🎯 Success Criteria

Implementation is complete when:

1. ✅ EngineComponent has evaluate_batch() method
2. ✅ Context has is_batch field
3. ✅ Orchestrator propagates is_batch flag
4. ✅ Agent routes to evaluate_batch() correctly
5. ✅ SimpleBatchEngine example works
6. ✅ All tests pass (existing + new)
7. ✅ Documentation complete
8. ✅ PR merged

---

## 🚀 Getting Started

**Ready to implement? Start here:**

```bash
# 1. Read Phase 1 of the checklist
cat docs/internal/evaluate-batch/02-implementation-checklist.md | head -100

# 2. Open Quick Reference in your editor
code docs/internal/evaluate-batch/03-quick-reference.md

# 3. Create feature branch
git checkout -b feat/evaluate-batch-support

# 4. Start with Phase 1!
```

---

## 📝 Notes

### Design Decisions

1. **Why opt-in?** - Not all engines can/should support batching (e.g., streaming LLMs)
2. **Why separate method?** - Clear API, explicit intent, type safety
3. **Why context flag?** - Simple routing logic, clear execution mode
4. **Why clear errors?** - Better DX, faster debugging, actionable guidance

### Future Enhancements (Out of Scope)

These are intentionally **NOT** part of this implementation:

- DSPy engine batch support (separate effort)
- Batch timeout improvements
- Batch metrics/monitoring
- Dashboard UI for batch state

Focus on the foundation first!

---

## 🎉 Final Note

This is a well-planned, low-risk enhancement that fixes a critical bug (DSPy only processing last artifact) while adding proper batch support.

**The work is planned. The path is clear. Tomorrow-we-both just need to execute!**

Good luck! 💪☕🚀

---

**Created**: 2025-01-14 03:00 AM
**Status**: Ready for Implementation
**Estimated Time**: 4-6 hours
**Risk Level**: Low
