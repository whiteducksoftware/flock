# Implementation Plan

## Specification Identity

- **Spec ID:** 003
- **Feature:** Until Conditions DSL & Subscription Activation
- **GitHub Issue:** #364

---

## Context Priming

*GATE: Read all files before starting implementation.*

**Specification Documents:**
- `docs/specs/003-until-conditions-dsl/product-requirements.md`
- `docs/specs/003-until-conditions-dsl/solution-design.md`
- **GitHub Issue #364** - Complete design with examples

**Key Implementation Files:**
- `src/flock/core/orchestrator.py` - Add `run_until()` method
- `src/flock/core/store.py` - `query_artifacts`, `FilterConfig`
- `src/flock/core/subscription.py` - Add `activation` parameter
- `src/flock/orchestrator/scheduler.py` - Scheduler loop reference
- `src/flock/components/orchestrator/base.py` - Component hooks
- `src/flock/registry.py` - `type_registry.name_for()`

**Key Design Decisions:**
1. `RunCondition` is a Protocol with async `evaluate()` method
2. Conditions are composable via `__and__`, `__or__`, `__invert__`
3. `Until` helper provides ergonomic builders
4. `run_until()` evaluates condition between scheduler steps
5. Subscription activation uses same condition DSL via `When` helper
6. `ActivationComponent` evaluates conditions before agent scheduling

**Project Commands:**
- Tests: `uv run pytest tests/ -v`
- Type check: `uv run mypy src/flock`
- Lint: `uv run ruff check src/flock`
- Format: `uv run ruff format src/flock`

---

## Implementation Phases

### Phase 1: RunCondition Protocol & Base Classes

**Goal:** Define the core condition protocol and composite conditions.

- [ ] **T1.1 Prime Context**
    - [ ] T1.1.1 Read orchestrator structure `[ref: src/flock/core/orchestrator.py]`
    - [ ] T1.1.2 Read store query API `[ref: src/flock/core/store.py]`
    - [ ] T1.1.3 Read SDD protocol design `[ref: solution-design.md; Section 1]`

- [ ] **T1.2 Write Tests** `[activity: test-engineering]`
    - [ ] T1.2.1 Test `RunCondition` protocol compliance
    - [ ] T1.2.2 Test `AndCondition` evaluates both sides
    - [ ] T1.2.3 Test `OrCondition` short-circuits on first True
    - [ ] T1.2.4 Test `NotCondition` inverts result
    - [ ] T1.2.5 Test chaining: `cond1 & cond2 | cond3`
    - [ ] T1.2.6 Test `~condition` syntax
    - **File:** `tests/core/test_conditions_base.py`

- [ ] **T1.3 Implement** `[activity: domain-modeling]`
    - [ ] T1.3.1 Create `src/flock/core/conditions.py`
    - [ ] T1.3.2 Define `RunCondition` Protocol with `evaluate(orchestrator) -> bool`
    - [ ] T1.3.3 Add `__and__`, `__or__`, `__invert__` to protocol
    - [ ] T1.3.4 Implement `AndCondition` dataclass
    - [ ] T1.3.5 Implement `OrCondition` dataclass
    - [ ] T1.3.6 Implement `NotCondition` dataclass
    - [ ] T1.3.7 Export from module `__all__`
    - **File:** `src/flock/core/conditions.py`

- [ ] **T1.4 Validate**
    - [ ] T1.4.1 Run `uv run pytest tests/core/test_conditions_base.py -v`
    - [ ] T1.4.2 Type check `uv run mypy src/flock/core/conditions.py`

---

### Phase 2: Concrete Condition Implementations

**Goal:** Implement specific condition types (count, exists, field, idle, error).

- [ ] **T2.1 Prime Context**
    - [ ] T2.1.1 Read FilterConfig structure `[ref: src/flock/core/store.py]`
    - [ ] T2.1.2 Read `get_correlation_status` `[ref: src/flock/core/orchestrator.py]`
    - [ ] T2.1.3 Read type_registry API `[ref: src/flock/registry.py]`
    - [ ] T2.1.4 Read SDD condition implementations `[ref: solution-design.md; Section 2]`

- [ ] **T2.2 Write Tests** `[activity: test-engineering]`
    - [ ] T2.2.1 Test `IdleCondition` returns True when no pending work
    - [ ] T2.2.2 Test `IdleCondition` returns False when work pending
    - [ ] T2.2.3 Test `ArtifactCountCondition.at_least(5)` with 3 artifacts → False
    - [ ] T2.2.4 Test `ArtifactCountCondition.at_least(5)` with 5 artifacts → True
    - [ ] T2.2.5 Test `ArtifactCountCondition.at_most(3)` boundary cases
    - [ ] T2.2.6 Test `ArtifactCountCondition.exactly(5)` exact match
    - [ ] T2.2.7 Test `ArtifactCountCondition` with correlation_id filter
    - [ ] T2.2.8 Test `ArtifactCountCondition` with tags filter
    - [ ] T2.2.9 Test `ArtifactCountCondition` with produced_by filter
    - [ ] T2.2.10 Test `ExistsCondition` returns True when artifact exists
    - [ ] T2.2.11 Test `ExistsCondition` returns False when no artifacts
    - [ ] T2.2.12 Test `FieldPredicateCondition` with matching field value
    - [ ] T2.2.13 Test `FieldPredicateCondition` with no matching field
    - [ ] T2.2.14 Test `FieldPredicateCondition` with None field value
    - [ ] T2.2.15 Test `WorkflowErrorCondition` with errors present
    - [ ] T2.2.16 Test `WorkflowErrorCondition` with no errors
    - **File:** `tests/core/test_conditions_impl.py`

- [ ] **T2.3 Implement** `[activity: domain-modeling]`
    - [ ] T2.3.1 Implement `IdleCondition` (check `orchestrator.has_pending_work()`)
    - [ ] T2.3.2 Implement `ArtifactCountCondition` with filters and count checks
    - [ ] T2.3.3 Add `at_least(n)`, `at_most(n)`, `exactly(n)` builder methods
    - [ ] T2.3.4 Implement `ExistsCondition` (query with limit=1, check total > 0)
    - [ ] T2.3.5 Implement `FieldPredicateCondition` (query artifacts, check field values)
    - [ ] T2.3.6 Implement `WorkflowErrorCondition` (use `get_correlation_status`)
    - [ ] T2.3.7 Add all to `__all__`
    - **File:** `src/flock/core/conditions.py`

- [ ] **T2.4 Validate**
    - [ ] T2.4.1 Run `uv run pytest tests/core/test_conditions_impl.py -v`
    - [ ] T2.4.2 Type check

---

### Phase 3: Until Helper (Builder Pattern)

**Goal:** Create ergonomic `Until` helper for building conditions.

- [ ] **T3.1 Prime Context**
    - [ ] T3.1.1 Read SDD Until helper design `[ref: solution-design.md; Section 3]`
    - [ ] T3.1.2 Review GitHub issue examples `[ref: issue #364]`

- [ ] **T3.2 Write Tests** `[activity: test-engineering]`
    - [ ] T3.2.1 Test `Until.idle()` returns IdleCondition
    - [ ] T3.2.2 Test `Until.no_pending_work()` returns IdleCondition
    - [ ] T3.2.3 Test `Until.artifact_count(Model)` returns ArtifactCountCondition
    - [ ] T3.2.4 Test `Until.artifact_count(Model, correlation_id=...)` passes filter
    - [ ] T3.2.5 Test `Until.artifact_count(...).at_least(5)` chaining
    - [ ] T3.2.6 Test `Until.exists(Model)` returns ExistsCondition
    - [ ] T3.2.7 Test `Until.none(Model)` returns NotCondition wrapping ExistsCondition
    - [ ] T3.2.8 Test `Until.any_field(Model, field=..., predicate=...)` works
    - [ ] T3.2.9 Test `Until.workflow_error(cid)` returns WorkflowErrorCondition
    - [ ] T3.2.10 Test complex composition: `Until.artifact_count(...).at_least(5) | Until.workflow_error(...)`
    - **File:** `tests/core/test_until_helper.py`

- [ ] **T3.3 Implement** `[activity: api-development]`
    - [ ] T3.3.1 Create `Until` class with static methods
    - [ ] T3.3.2 Implement `Until.idle()` → `IdleCondition()`
    - [ ] T3.3.3 Implement `Until.no_pending_work()` → `IdleCondition()`
    - [ ] T3.3.4 Implement `Until.artifact_count(model, *, correlation_id, tags, produced_by)`
    - [ ] T3.3.5 Implement `Until.exists(model, *, correlation_id, tags)`
    - [ ] T3.3.6 Implement `Until.none(model, ...)` → `NotCondition(ExistsCondition(...))`
    - [ ] T3.3.7 Implement `Until.any_field(model, *, field, predicate, correlation_id)`
    - [ ] T3.3.8 Implement `Until.workflow_error(correlation_id)`
    - [ ] T3.3.9 Export `Until` in `__all__`
    - **File:** `src/flock/core/conditions.py`

- [ ] **T3.4 Validate**
    - [ ] T3.4.1 Run `uv run pytest tests/core/test_until_helper.py -v`

---

### Phase 4: run_until() Orchestrator Method

**Goal:** Add `run_until(condition, timeout)` to Flock orchestrator.

- [ ] **T4.1 Prime Context**
    - [ ] T4.1.1 Read `run_until_idle()` implementation `[ref: src/flock/core/orchestrator.py; lines: 537-562]`
    - [ ] T4.1.2 Understand scheduler step execution
    - [ ] T4.1.3 Read SDD run_until design `[ref: solution-design.md; Section 4]`

- [ ] **T4.2 Write Tests** `[activity: test-engineering]`
    - [ ] T4.2.1 Test `run_until(Until.idle())` behaves like `run_until_idle()`
    - [ ] T4.2.2 Test `run_until()` returns True when condition satisfied
    - [ ] T4.2.3 Test `run_until()` returns False on timeout
    - [ ] T4.2.4 Test `run_until()` evaluates condition between steps
    - [ ] T4.2.5 Test `run_until()` with composite condition
    - [ ] T4.2.6 Test `run_until()` stops early when condition met mid-workflow
    - [ ] T4.2.7 Test `run_until()` with no timeout runs until condition or idle
    - **File:** `tests/core/test_run_until.py`

- [ ] **T4.3 Implement** `[activity: domain-modeling]`
    - [ ] T4.3.1 Add `run_until()` method signature to Flock class
    - [ ] T4.3.2 Implement main loop:
        - Check condition → if True, return True
        - Check timeout → if exceeded, return False
        - Run one scheduler step
        - If no pending work, final condition check
        - Repeat
    - [ ] T4.3.3 Handle edge case: condition met immediately (before any work)
    - [ ] T4.3.4 Add type hints for `RunCondition`
    - [ ] T4.3.5 Add docstring with examples
    - **File:** `src/flock/core/orchestrator.py`

- [ ] **T4.4 Export Condition Types**
    - [ ] T4.4.1 Add conditions to `src/flock/core/__init__.py` exports
    - [ ] T4.4.2 Add `Until` to top-level `flock` package exports
    - **Files:** `src/flock/core/__init__.py`, `src/flock/__init__.py`

- [ ] **T4.5 Validate**
    - [ ] T4.5.1 Run `uv run pytest tests/core/test_run_until.py -v`
    - [ ] T4.5.2 Run full test suite to check for regressions

---

### Phase 5: When Helper & Subscription Activation (P1)

**Goal:** Add activation conditions to subscriptions.

- [ ] **T5.1 Prime Context**
    - [ ] T5.1.1 Read Subscription class `[ref: src/flock/core/subscription.py]`
    - [ ] T5.1.2 Read agent consumes API `[ref: src/flock/core/agent.py]`
    - [ ] T5.1.3 Read scheduler component hooks `[ref: src/flock/components/orchestrator/base.py]`
    - [ ] T5.1.4 Read SDD activation design `[ref: solution-design.md; Section 5-6]`

- [ ] **T5.2 Write Tests for When Helper** `[activity: test-engineering]`
    - [ ] T5.2.1 Test `When.correlation(Model).count_at_least(N)` returns condition
    - [ ] T5.2.2 Test `When.correlation(Model).any_field(...)` returns condition
    - **File:** `tests/core/test_when_helper.py`

- [ ] **T5.3 Implement When Helper** `[activity: api-development]`
    - [ ] T5.3.1 Create `When` class with static methods
    - [ ] T5.3.2 Create `CorrelationConditionBuilder` class
    - [ ] T5.3.3 Implement `count_at_least(n)` method
    - [ ] T5.3.4 Implement `any_field(field, predicate)` method
    - [ ] T5.3.5 Export `When` in conditions module
    - **File:** `src/flock/core/conditions.py`

- [ ] **T5.4 Update Subscription Model**
    - [ ] T5.4.1 Add `activation: RunCondition | None = None` to Subscription
    - [ ] T5.4.2 Update `agent.consumes()` to accept `activation` parameter
    - [ ] T5.4.3 Pass activation through to Subscription constructor
    - **Files:** `src/flock/core/subscription.py`, `src/flock/core/agent.py`

- [ ] **T5.5 Write Tests for ActivationComponent** `[activity: test-engineering]`
    - [ ] T5.5.1 Test component skips artifacts when activation is False
    - [ ] T5.5.2 Test component includes artifacts when activation is True
    - [ ] T5.5.3 Test component includes all artifacts when no activation set
    - [ ] T5.5.4 Test activation receives correct correlation_id context
    - **File:** `tests/components/test_activation_component.py`

- [ ] **T5.6 Implement ActivationComponent** `[activity: domain-modeling]`
    - [ ] T5.6.1 Create `src/flock/components/orchestrator/activation.py`
    - [ ] T5.6.2 Implement `ActivationComponent(OrchestratorComponent)`
    - [ ] T5.6.3 Set priority 15 (after circuit breaker, before dedup)
    - [ ] T5.6.4 Implement `on_before_agent_schedule` hook
    - [ ] T5.6.5 Find subscription for each artifact
    - [ ] T5.6.6 Evaluate activation condition with correlation context
    - [ ] T5.6.7 Filter out artifacts that don't meet activation
    - **File:** `src/flock/components/orchestrator/activation.py`

- [ ] **T5.7 Register Component**
    - [ ] T5.7.1 Add to `src/flock/components/orchestrator/__init__.py`
    - [ ] T5.7.2 Decide: auto-register or opt-in (recommend: auto if activation present)
    - **File:** `src/flock/components/orchestrator/__init__.py`

- [ ] **T5.8 Validate**
    - [ ] T5.8.1 Run `uv run pytest tests/core/test_when_helper.py -v`
    - [ ] T5.8.2 Run `uv run pytest tests/components/test_activation_component.py -v`
    - [ ] T5.8.3 Run full test suite

---

### Phase 6: Integration & End-to-End Validation

**Goal:** Ensure complete feature works end-to-end.

- [ ] **T6.1 Integration Tests** `[activity: test-engineering]`
    - [ ] T6.1.1 Test: Publish → run_until count condition → stops at correct count
    - [ ] T6.1.2 Test: Publish → run_until error condition → stops on error
    - [ ] T6.1.3 Test: Publish → run_until composite condition
    - [ ] T6.1.4 Test: Agent with activation condition → only activates after threshold
    - [ ] T6.1.5 Test: Multiple agents with different activation conditions
    - [ ] T6.1.6 Test: run_until + activation conditions together
    - **File:** `tests/integration/test_conditions_e2e.py`

- [ ] **T6.2 Example from Issue #364** `[activity: test-engineering]`
    - [ ] T6.2.1 Implement "backlog generation with early stop" example as test
    - [ ] T6.2.2 Implement "high-confidence hypothesis" example as test
    - [ ] T6.2.3 Implement "QA activation guardrail" example as test
    - **File:** `tests/integration/test_conditions_examples.py`

- [ ] **T6.3 Acceptance Criteria Verification** `[ref: product-requirements.md]`
    - [ ] T6.3.1 `Until.artifact_count().at_least()` works
    - [ ] T6.3.2 `Until.exists()` works
    - [ ] T6.3.3 `Until.idle()` works
    - [ ] T6.3.4 `Until.workflow_error().exists()` works
    - [ ] T6.3.5 Boolean combinators work (`|`, `&`, `~`)
    - [ ] T6.3.6 Timeout parameter respected
    - [ ] T6.3.7 `When` helper creates activation conditions
    - [ ] T6.3.8 Scheduler evaluates activation before scheduling

- [ ] **T6.4 Quality Gates**
    - [ ] T6.4.1 All tests passing: `uv run pytest tests/ -v`
    - [ ] T6.4.2 Type check passing: `uv run mypy src/flock`
    - [ ] T6.4.3 Lint passing: `uv run ruff check src/flock`
    - [ ] T6.4.4 Format check: `uv run ruff format --check src/flock`
    - [ ] T6.4.5 Test coverage maintained

- [ ] **T6.5 Documentation**
    - [ ] T6.5.1 Add docstrings to all public APIs
    - [ ] T6.5.2 Add usage examples to docstrings
    - [ ] T6.5.3 Update CHANGELOG.md
    - [ ] T6.5.4 Consider adding to docs/examples/

- [ ] **T6.6 Final Verification**
    - [ ] T6.6.1 Manual test with real workflow
    - [ ] T6.6.2 Verify backward compatibility (`run_until_idle` unchanged)
    - [ ] T6.6.3 Review PR-ready state

---

## Parallel Execution Notes

- **Phase 1 (Protocol)** must complete first
- **Phase 2 (Implementations)** depends on Phase 1
- **Phase 3 (Until helper)** depends on Phase 2
- **Phase 4 (run_until)** depends on Phase 1-3
- **Phase 5 (When + Activation)** depends on Phase 1-2, can partially parallel with 3-4
- **Phase 6 (E2E)** requires all previous phases

Suggested parallelization:
- After Phase 2: Split into two tracks
  - Track A: Phase 3 → Phase 4 (run_until flow)
  - Track B: Phase 5.1-5.3 (When helper)
- Merge for Phase 5.4+ and Phase 6

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| `has_pending_work()` not exposed | Check if method exists, add if needed |
| Scheduler step not granular enough | May need to refactor scheduler loop |
| Activation condition evaluation overhead | Lazy evaluation, cache correlation status |
| Breaking existing behavior | Extensive backward compatibility tests |
| Complex condition serialization | Start with runtime-only, add serialization later |

---

## Open Questions

1. **`has_pending_work()` availability:** Does this method exist on orchestrator?
2. **Scheduler granularity:** Can we run "one step" or is it all-or-nothing?
3. **Component auto-registration:** Should ActivationComponent auto-register?
4. **Correlation binding:** How to bind correlation_id in activation conditions?

---

## Success Criteria

1. `run_until(condition)` terminates workflow at correct point
2. Boolean combinators compose correctly
3. All `Until` builders work as specified
4. Subscription activation gates agent scheduling
5. All examples from issue #364 work
6. No regression in existing tests
7. Performance acceptable (< 10ms per condition evaluation)
