# Product Requirements Document (Minimal)

> **Note:** This is a minimal PRD. The complete design is documented in GitHub issue #364.

## References

- **GitHub Issue #364:** [Until conditions and subscription activation](https://github.com/whiteducksoftware/flock/issues/364)
- **Existing Implementation:** `src/flock/core/orchestrator.py` (`run_until_idle`)
- **Subscription System:** `src/flock/core/subscription.py`
- **Store Query API:** `src/flock/core/store.py` (`query_artifacts`, `FilterConfig`)

---

## Problem Statement

Flock supports emergent workflows via type-based subscriptions and `publish()` + `run_until_idle()`. However, there is no first-class way to:

1. **Stop running when "enough" artifacts exist** - e.g., stop when 5 `UserStory` artifacts exist instead of waiting for full idle
2. **Express board-level activation conditions** - e.g., only activate a summarizer after N inputs exist, or once a high-confidence result is available

Today teams implement these rules in ad-hoc ways:
- Calling `run_until_idle()` then ignoring excess artifacts
- Baking early-exit logic into agent implementations
- Building custom components that manually query the store

This scatters workflow intent across agents and makes it harder to reason about or observe.

## Value Proposition

- **Declarative workflow termination:** Express "when to stop" as data, not code
- **Conditional agent activation:** Agents wait for board-level conditions before consuming
- **Observable intent:** Dashboards can show "what we're waiting for"
- **Reusable DSL:** Same condition language for `run_until()` and subscription activation

---

## Feature Requirements

### Must Have (P0)

#### Feature 1: `run_until(condition)` Method
- **Behavior:** Run orchestrator until condition evaluates true (or timeout)
- **Acceptance Criteria:**
  - [ ] `Until.artifact_count(Type, correlation_id).at_least(N)` works
  - [ ] `Until.exists(Type, correlation_id)` works
  - [ ] `Until.idle()` works (current behavior)
  - [ ] `Until.workflow_error(correlation_id).exists()` works
  - [ ] Boolean combinators work: `condition1 | condition2`, `condition1 & condition2`, `~condition`
  - [ ] Timeout parameter respected

#### Feature 2: Condition DSL (`Until` helper)
- **Builders:**
  - [ ] `Until.idle()` / `Until.no_pending_work()`
  - [ ] `Until.artifact_count(Model, correlation_id=..., tags=..., produced_by=...)` with `.at_least(N)`, `.at_most(N)`, `.exactly(N)`
  - [ ] `Until.exists(Model, ...)` and `Until.none(Model, ...)`
  - [ ] `Until.any_field(Model, field=..., predicate=lambda v: ..., correlation_id=...)`
  - [ ] `Until.workflow_state(correlation_id)` with `.is_in({"completed", "failed"})`
  - [ ] `Until.workflow_error(correlation_id).exists()`

#### Feature 3: `RunCondition` Protocol
- **Interface:** Boolean protocol with `__and__`, `__or__`, `__invert__`
- **Acceptance Criteria:**
  - [ ] Conditions are composable
  - [ ] Conditions are evaluable against orchestrator state
  - [ ] Conditions are serializable (for dashboard display)

### Should Have (P1)

#### Feature 4: Subscription Activation Conditions
- **Syntax:** `agent.consumes(Type, activation=When.correlation(Type).count_at_least(N))`
- **Acceptance Criteria:**
  - [ ] `When` helper mirrors `Until` DSL
  - [ ] Scheduler evaluates activation before scheduling agent
  - [ ] False activation → DEFER (try again later)
  - [ ] True activation → proceed as normal

### Could Have (P2)

- [ ] Time-windowed conditions (e.g., count within last N minutes)
- [ ] Semantic conditions (e.g., `Until.semantic_match(query, threshold)`)
- [ ] Dashboard visualization of pending conditions

### Won't Have (This Phase)

- Complex temporal logic (temporal operators like "eventually", "always")
- Cross-correlation conditions
- Condition persistence/serialization to database

---

## Usage Examples (from Issue #364)

### Example 1: Early stop on artifact count
```python
await flock.run_until(
    Until.artifact_count(UserStory, correlation_id=workflow_id).at_least(5)
    | Until.workflow_error(correlation_id=workflow_id).exists()
)
```

### Example 2: Until high-confidence result
```python
await flock.run_until(
    Until.any_field(
        ResearchHypothesis,
        field="score",
        predicate=lambda s: s is not None and s > 9,
        correlation_id=workflow_id,
    )
    | Until.workflow_error(correlation_id=workflow_id).exists()
)
```

### Example 3: Subscription activation guardrail
```python
qa_agent = (
    flock.agent("qa")
    .consumes(
        CodeReview,
        activation=When.correlation(CodeReview).count_at_least(2),
    )
    .publishes(QAReport)
)
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Condition evaluation latency | < 10ms per check |
| DSL expressiveness | Covers 90% of common use cases |
| Adoption | Used in 3+ internal workflows within 1 month |

---

## Constraints

- Must reuse existing `BlackboardStore.query_artifacts`, `FilterConfig`, `get_correlation_status`
- Must not introduce new workflow engine (stay lightweight)
- Conditions evaluated between scheduler steps (not continuously)
- Subscription activation is opt-in (default behavior unchanged)
