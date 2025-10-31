# Timer Scheduling — v0.5.30 Addendum

This addendum amends the original design and plan for timer‑based agents with a concrete implementation plan for v0.5.30. It addresses identified gaps, introduces cron support, and documents the selected approach for timer metadata injection.

Status: Planned (implement next)  • Target version: 0.5.30  • Scope: Backend only

---

## Goals

- Preserve the developer‑facing API (AgentBuilder.schedule, Context properties) while fixing behavioral gaps.
- Implement “Option B” for timer metadata injection so timer agents keep `ctx.artifacts == []` but still access `ctx.trigger_type`, `ctx.timer_iteration`, and `ctx.fire_time`.
- Make one‑time datetime schedules implicitly stop after the first execution.
- Enforce validations: scheduled agents must declare `.publishes()`, and scheduling options must be positive.
- Add cron expression support for schedules.

---

## Summary of Changes

1) Timer metadata injection (Option B) via ContextBuilder
- Detect TimerTick during context construction and embed a compact metadata blob into `Context.state["__timer__"]`.
- Keep `ctx.artifacts` empty for timer triggers (DX stays clean and aligned with docs).
- Update Context properties to read metadata from state when present.

2) One‑time datetime semantics (implicit stop)
- When `ScheduleSpec.at` is a `datetime` and `max_repeats` is not provided, treat as `max_repeats = 1`.

3) Validation hardening
- Scheduled agents must declare `.publishes()`; raise a helpful error at orchestrator initialization time.
- Validate `after >= 0` and `max_repeats > 0` when provided.

4) Cron support
- Support standard 5‑field cron expressions (min, hour, dom, mon, dow) in UTC.
- Compute next fire time and integrate with existing `_wait_for_next_fire()`.

5) Docs, tests, and versioning
- Update scheduling docs and examples to reflect actual behavior and cron support.
- Strengthen/adjust tests to assert timer metadata in real executions and one‑time semantics.
- Bump backend version to 0.5.30.

---

## Detailed Implementation Plan

### A) Timer Metadata Injection (Option B)

Rationale: Maintain the clean DX of “no input artifact for timers” while still exposing timer metadata via `Context` properties.

Implementation steps:
- File: `src/flock/orchestrator/context_builder.py`
  - When building a context, inspect the `artifacts` parameter (the triggering inputs, which can include a `TimerTick`).
  - If any input is a `TimerTick`, extract `{ timer_name, iteration, fire_time }` and set on `Context.state["__timer__"] = {"name": ..., "iter": ..., "fire": ...}`.
  - Continue to evaluate blackboard context via the provider as today. The builder already excludes input artifacts from the returned context artifacts, so timer agents still receive `ctx.artifacts == []`.

- File: `src/flock/utils/runtime.py`
  - Update `Context.trigger_type`, `Context.timer_iteration`, and `Context.fire_time` to prefer the `__timer__` state blob when present. Fallback to the legacy artifact sniffing logic for safety/compatibility.

Notes:
- This is internal only; no user‑facing API changes.
- We do not expose `TimerTick` to engines; we only surface its metadata.

### B) One‑Time Datetime Semantics

Goal: If `ScheduleSpec.at` is a `datetime` and no `max_repeats` is provided, make the schedule implicitly one‑time.

Implementation:
- File: `src/flock/components/orchestrator/scheduling/timer.py`
  - In `_timer_loop()`, compute `effective_max = spec.max_repeats` or `1` if `spec.at` is a `datetime` and `spec.max_repeats is None`.
  - Use `effective_max` for the loop’s stop condition.

Alternative (optional): Normalize in `ScheduleSpec.__post_init__` — we prefer runtime normalization in `_timer_loop()` to avoid mutating user config.

### C) Validation Hardening

1. Scheduled agents must have `.publishes()`
- File: `src/flock/core/orchestrator.py`
  - During `_run_initialize()`, before registering/starting `TimerComponent`, assert that each `agent.schedule_spec` agent has `agent.output_groups` non‑empty.
  - If not, raise `ValueError("Scheduled agents must declare .publishes()")` with the agent name.
- Reasoning: Calling `.schedule()` before `.publishes()` is common in the fluent chain; we validate at orchestrator init to avoid blocking the common builder order.

2. Positive values for options
- File: `src/flock/core/subscription.py` (`ScheduleSpec.__post_init__`)
  - If `after is not None and after.total_seconds() < 0: raise ValueError("after must be >= 0")`.
  - If `max_repeats is not None and max_repeats <= 0: raise ValueError("max_repeats must be > 0")`.

### D) Cron Support (UTC)

Scope:
- Support 5‑field cron: `minute hour day_of_month month day_of_week`.
- Fields: `*`, lists (`,`), ranges (`-`), steps (`/`), and names for months/days (JAN..DEC, SUN..SAT) are recommended but optional; at minimum, support numerics with `*`, ranges, steps, and lists.
- All scheduling computed in UTC (consistent with existing timer behavior).

Implementation steps:
- File: `src/flock/components/orchestrator/scheduling/timer.py`
  - Replace `NotImplementedError` path with a cron branch in `_wait_for_next_fire()`.
  - Add helper: `_next_cron_fire(now_utc: datetime, expr: str) -> datetime`.
  - Compute `seconds_until = (next_fire - now_utc).total_seconds()`; `await asyncio.sleep(seconds_until)` when positive; if zero/negative (edge), compute again.

Parser options:
- Option 1 (preferred for speed): Vendor a minimal cron parser tailored to 5 fields with numerics, `*`, `*/n`, `a-b`, `a,b,c`, and map Sunday as 0 or 7 (decide and document). Keep code local to timer component to avoid a new runtime dependency.
- Option 2 (alt): Add `croniter` as a dependency and call `croniter(expr, now_utc).get_next(datetime)`. If we take this route, add it to `pyproject.toml` and vendor small adapter + tests. Given portability concerns, Option 1 is recommended.

Tests to add:
- `tests/test_timer_component.py`:
  - `test_wait_for_next_fire_cron_minute_every_5` → `*/5 * * * *` waits ~5 min from aligned boundary (use shortened intervals with fake clock or reduce scope to correctness of function output where feasible).
  - `test_wait_for_next_fire_cron_specific_time` → `0 17 * * *` next 17:00 UTC.
  - `test_wait_for_next_fire_cron_range_list_step` with expressions like `0 9-17/2 * * 1-5`.
- Use tolerance on wall‑clock sleeps similar to existing interval/time tests.

---

## Developer Experience (DX) — Using Timer Metadata (Option B)

No API changes. As a developer, you can rely on:

- `ctx.trigger_type == "timer"` when a timer fired your agent.
- `ctx.timer_iteration` returns `0, 1, 2, ...`.
- `ctx.fire_time` returns the `datetime` when the timer fired (UTC).
- `ctx.artifacts == []` for timer triggers (no input artifact exposed).
- Use `ctx.get_artifacts(Type)` to access blackboard context filtered by your `.consumes()`.

Example:

```python
from flock.core.agent import AgentContext
from pydantic import BaseModel, Field
from datetime import datetime

class DailyReport(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    iteration: int
    count: int

async def generate_daily_report(ctx: AgentContext) -> DailyReport:
    # Timer detection & metadata (Option B)
    assert ctx.trigger_type == "timer", "Expected timer trigger"

    iter_no = ctx.timer_iteration or 0
    fired_at = ctx.fire_time  # datetime in UTC

    # No input items for timer triggers
    assert ctx.artifacts == []

    # Pull context from blackboard (filtered by your .consumes())
    logs = ctx.get_artifacts(LogEntry)  # e.g., ERROR logs only

    return DailyReport(
        generated_at=fired_at or datetime.utcnow(),
        iteration=iter_no,
        count=len(logs),
    )
```

What changed under the hood:
- The orchestrator notices a `TimerTick` triggered your agent and injects a small metadata blob into `Context.state["__timer__"]`.
- The `Context` properties read from that state, so your code remains as shown in the docs.

---

## Tests

Adjustments & additions:
- Update `tests/integration/test_scheduled_agents.py` to assert real‑run metadata:
  - `ctx.trigger_type == "timer"`, `ctx.timer_iteration >= 0`, `ctx.fire_time is not None` for timer executions.
- Add integration test for one‑time datetime without explicit `max_repeats` → executes once and stops.
- Add unit tests for positive validations in `ScheduleSpec` (`after`, `max_repeats`).
- Add cron tests as outlined above.

---

## Docs

- Update `docs/guides/scheduling.md` and `docs/tutorials/scheduled-agents.md`:
  - Clarify that cron is supported (UTC) with examples.
  - Reiterate that timer agents see empty inputs but have timer metadata.
  - Note implicit one‑time behavior for datetime when `max_repeats` isn’t provided.
- Fix references to design files if any point to stale locations.

---

## Versioning & Changelog

- Bump backend version to `0.5.30` in `pyproject.toml`.
- Changelog highlights:
  - Feature: Cron support for scheduled agents (UTC, 5‑field cron).
  - Fix: Timer metadata now available in `Context` while keeping inputs empty.
  - Fix: Datetime schedules default to one‑time when `max_repeats` is omitted.
  - Validation: Scheduled agents must declare `.publishes()`; positive option checks.

---

## Rollout Plan

1) Implement metadata injection + Context property fallback.
2) Implement one‑time datetime semantics.
3) Add validations.
4) Implement cron support (parser + `_wait_for_next_fire` integration) and tests.
5) Update docs and examples; run full test suite.
6) Bump to 0.5.30 and update changelog.

Estimated effort: 1–2 days engineering, 0.5 day docs/tests polish.

---

## Acceptance Criteria

- Timer‑triggered agents see `ctx.artifacts == []`, `ctx.trigger_type == "timer"`, valid `ctx.timer_iteration`, and valid `ctx.fire_time` in real executions.
- Datetime schedules (without `max_repeats`) run once and stop.
- Cron expressions trigger at the correct next time in UTC.
- Invalid configurations raise clear errors.
- All new/updated tests pass and existing tests remain green.

---

## Risks & Mitigations

- Cron parsing complexity → Keep scope to 5‑field with common operators. Add thorough unit tests around boundaries.
- Timezone confusion → Explicitly document and implement cron in UTC.
- Builder chaining order → Validate `.publishes()` at orchestrator init to preserve fluent API ergonomics.

---

End of addendum.

