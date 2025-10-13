# UX Improvement Proposal: Type-Based Predicates

**Status:** 💡 Proposal
**Created:** 2025-10-13
**Related Spec:** 003 - Logic Operations
**Priority:** Medium (Post Phase 1)

---

## 📋 Problem Statement

### Current Behavior (Phase 1 Implementation)

In the Phase 1 implementation of AND gates, `where` predicates apply **globally** to ALL artifact types in a subscription:

```python
# Current implementation
orchestrator.agent("test").consumes(
    TypeA,
    TypeB,
    where=lambda payload: payload.value.startswith("x")
)
```

**How it works:**
1. Predicate evaluated **per artifact** as it arrives
2. Predicate acts as "bouncer at the door" of the waiting pool
3. Rejected artifacts **never enter** the waiting pool
4. Predicate must handle ALL types in the subscription

### The Ergonomic Problem

When you want to filter **only one type** (not all), you need ugly `isinstance` checks:

```python
# Awkward: Check type in every predicate
def predicate(payload):
    if isinstance(payload, TypeA):
        return payload.value.startswith("x")  # Filter TypeA
    return True  # Allow all TypeB

orchestrator.agent("test").consumes(TypeA, TypeB, where=predicate)
```

**Issues:**
1. **Verbose**: Requires `isinstance` checks for type-specific logic
2. **Coupling**: All types must have compatible interfaces
3. **Error-Prone**: Easy to forget the `else: return True` fallback
4. **Not Intuitive**: Users expect per-type filtering to be easier

---

## ✨ Proposed Solution: Type-Based Predicates

### Option A: Method Chaining (Recommended)

```python
# Elegant: Per-type predicates
orchestrator.agent("test").consumes(
    TypeA.where(lambda a: a.value.startswith("x")),  # Filter only TypeA
    TypeB  # No filter
)
```

**Advantages:**
- ✅ Intuitive: "Filter TypeA, don't filter TypeB"
- ✅ Clean syntax: No `isinstance` needed
- ✅ Type-safe: Each predicate knows its type
- ✅ Composable: Can combine multiple filters per type

**Implementation Sketch:**
```python
class TypePredicate:
    """Wrapper for type + predicate."""
    def __init__(self, type_cls: type[BaseModel], predicate: Callable[[BaseModel], bool] | None = None):
        self.type_cls = type_cls
        self.predicate = predicate

    @classmethod
    def where(cls, type_cls: type[BaseModel], predicate: Callable[[BaseModel], bool]):
        return cls(type_cls, predicate)

# Add to BaseModel or via decorator
@flock_type
class TypeA(BaseModel):
    value: str

    @classmethod
    def where(cls, predicate: Callable[["TypeA"], bool]):
        return TypePredicate(cls, predicate)
```

### Option B: Dictionary-Based (Alternative)

```python
# Alternative: Dict of predicates
orchestrator.agent("test").consumes(
    TypeA,
    TypeB,
    where={
        TypeA: lambda a: a.value.startswith("x"),
        TypeB: None  # No filter
    }
)
```

**Advantages:**
- ✅ Explicit: Clear which types have filters
- ✅ Flexible: Can omit types without filters

**Disadvantages:**
- ❌ More verbose than chaining
- ❌ Dict syntax less fluent

### Option C: Separate Method (Alternative)

```python
# Alternative: Separate filter method
orchestrator.agent("test") \
    .consumes(TypeA, TypeB) \
    .filter(TypeA, lambda a: a.value.startswith("x"))
```

**Advantages:**
- ✅ Backward compatible: Doesn't change `.consumes()` signature

**Disadvantages:**
- ❌ Less intuitive: Filter feels disconnected from consumption
- ❌ Order matters: Must call `.filter()` after `.consumes()`

---

## 🎯 Recommended Approach

**Phase 1 (Current Spec 003):**
✅ Ship with global `where` predicates (current behavior)
✅ Document the behavior clearly
✅ Note the `isinstance` workaround in docs

**Future Spec (Post Phase 1):**
💡 Implement **Option A (Method Chaining)** for type-based predicates
💡 Keep global `where` for backward compatibility
💡 Allow mixing: `TypeA.where(...)` with global `where`

### Migration Path

```python
# Phase 1: Global predicate (works, but awkward)
.consumes(TypeA, TypeB, where=lambda p: isinstance(p, TypeA) and p.value.startswith("x") or isinstance(p, TypeB))

# Future: Type-based predicates (elegant)
.consumes(
    TypeA.where(lambda a: a.value.startswith("x")),
    TypeB
)

# Or combine both:
.consumes(
    TypeA.where(lambda a: a.value.startswith("x")),  # Type-specific
    TypeB,
    where=lambda p: p.version >= 2  # Global (applies to all)
)
```

---

## 📊 Impact Analysis

### User Benefits
- ✅ **Reduced Boilerplate**: No more `isinstance` checks
- ✅ **Clearer Intent**: "Filter TypeA but not TypeB" is obvious
- ✅ **Better Errors**: Type-specific predicates can give better error messages
- ✅ **Composability**: Can add multiple filters per type

### Implementation Effort
- **Low**: Wrapper class around type + predicate
- **Medium**: Integration with subscription matching logic
- **Low**: Documentation and examples

### Breaking Changes
- **None**: Fully backward compatible
- Global `where` continues to work as-is
- Type-based predicates are **opt-in enhancement**

---

## 🧪 Test Scenarios

### Test 1: Type-Specific Filtering
```python
orchestrator.agent("test").consumes(
    TypeA.where(lambda a: a.value > 5),
    TypeB  # No filter
)

# TypeA(value=3) → REJECTED
# TypeA(value=7) + TypeB(value=1) → ACCEPTED (both)
```

### Test 2: Multiple Filters on Same Type
```python
orchestrator.agent("test").consumes(
    TypeA.where(lambda a: a.value > 5).where(lambda a: a.flag == True),
    TypeB
)

# Filters are AND-ed
```

### Test 3: Mixed Type and Global Predicates
```python
orchestrator.agent("test").consumes(
    TypeA.where(lambda a: a.value > 5),  # Type-specific
    TypeB,
    where=lambda p: p.version >= 2  # Global (both types)
)

# TypeA must pass BOTH filters
# TypeB must pass only global filter
```

---

## 📝 Documentation Requirements

### User Guide (docs/guides/agents.md)

```markdown
## Filtering Artifacts with Predicates

### Type-Specific Predicates (Recommended)

Filter individual types without affecting others:

\```python
# Filter TypeA but not TypeB
agent.consumes(
    TypeA.where(lambda a: a.value.startswith("x")),
    TypeB
)
\```

### Global Predicates (Legacy)

Apply predicates to ALL types (requires `isinstance` checks):

\```python
# All types must pass this predicate
agent.consumes(
    TypeA,
    TypeB,
    where=lambda p: p.version >= 2
)
\```

### Combining Both

\```python
# TypeA: value > 5 AND version >= 2
# TypeB: version >= 2 only
agent.consumes(
    TypeA.where(lambda a: a.value > 5),
    TypeB,
    where=lambda p: p.version >= 2
)
\```
```

---

## 🔗 Related Work

### Similar Patterns in Other Frameworks

**Apache Spark:**
```python
df.filter(col("age") > 21)  # Column-specific filter
```

**RxJS:**
```python
obs.filter(x => x.value > 5)  # Type-specific
```

**SQL:**
```sql
SELECT * FROM orders WHERE amount > 100  -- Column-specific
```

All established patterns support **per-field/per-type** filtering elegantly.

---

## ✅ Decision Criteria

**Ship Type-Based Predicates If:**
- ✅ User feedback shows `isinstance` checks are painful
- ✅ Phase 1 is stable and well-adopted
- ✅ Implementation can maintain backward compatibility

**Defer Type-Based Predicates If:**
- ⏸ Global predicates prove sufficient for 90% of use cases
- ⏸ Users don't complain about current UX
- ⏸ Higher priority features need attention

---

## 💡 Next Steps

1. **Phase 1 Complete**: Ship AND gates with global predicates
2. **Gather Feedback**: Monitor user pain points with `where`
3. **Spec Phase**: Create formal spec for type-based predicates (if warranted)
4. **Implement**: Add type-based predicates as opt-in enhancement
5. **Migrate**: Update examples to use cleaner syntax

---

**Author:** Claude Code Team
**Review Date:** After Phase 1 adoption (2-3 months post-release)
