# Timer-Based Scheduling - Implementation Checklist

**Target Version:** 0.6.0
**Status:** Ready for Implementation

---

## 📋 **Implementation Tasks**

### **Phase 1: Core Infrastructure** 🔧

#### 1.1 Data Models
- [ ] Create `ScheduleSpec` dataclass in `src/flock/core/subscription.py`
  - [ ] Add fields: `interval`, `at`, `cron`, `after`, `max_repeats`
  - [ ] Add validation in `__post_init__()` (exactly one trigger type)
  - [ ] Add docstrings with examples
  - [ ] Write unit tests for validation logic

- [ ] Create `TimerTick` artifact in `src/flock/models/system_artifacts.py`
  - [ ] Add fields: `timer_name`, `fire_time`, `iteration`, `schedule_spec`
  - [ ] Mark as frozen (immutable)
  - [ ] Add `@flock_type` decorator
  - [ ] Write unit tests for serialization

#### 1.2 AgentBuilder API
- [ ] Add `schedule()` method to `AgentBuilder` class
  - [ ] Location: `src/flock/core/agent.py`
  - [ ] Parameters: `every`, `at`, `cron`, `after`, `max_repeats`
  - [ ] Create `ScheduleSpec` and assign to `agent.schedule_spec`
  - [ ] Auto-subscribe to `TimerTick` filtered by `timer_name`
  - [ ] Return `self` for method chaining
  - [ ] Add comprehensive docstring
  - [ ] Write unit tests for builder pattern

- [ ] Add validation in `AgentBuilder.build()`
  - [ ] Check mutual exclusion: `.schedule()` + `.batch()` raises error
  - [ ] Verify scheduled agents have `.publishes()`
  - [ ] Write validation tests

#### 1.3 Agent Context Enhancements
- [ ] Add properties to `AgentContext` class
  - [ ] Location: `src/flock/core/agent.py`
  - [ ] Add `trigger_type` property (returns "timer" or "artifact")
  - [ ] Add `timer_iteration` property (returns int or None)
  - [ ] Add `fire_time` property (returns datetime or None)
  - [ ] Add docstrings
  - [ ] Write unit tests

- [ ] Modify `Agent.execute()` to hide `TimerTick`
  - [ ] Detect timer trigger: `isinstance(artifact, TimerTick)`
  - [ ] Set `ctx.artifacts = []` for user code
  - [ ] Preserve timer metadata in internal fields
  - [ ] Write integration tests

---

### **Phase 2: Timer Component** ⏰

#### 2.1 Component Implementation
- [ ] Create `TimerComponent` class
  - [ ] Location: `src/flock/components/orchestrator/scheduling/timer.py`
  - [ ] Extend `OrchestratorComponent`
  - [ ] Set `priority = 5` (before collection)
  - [ ] Add `_timer_tasks` dict for task management

- [ ] Implement `on_initialize()` hook
  - [ ] Iterate through `orchestrator.agents`
  - [ ] Check for `agent.schedule_spec`
  - [ ] Create background task for each scheduled agent
  - [ ] Store tasks in `_timer_tasks` dict
  - [ ] Write unit tests

- [ ] Implement `_timer_loop()` method
  - [ ] Handle initial delay (`spec.after`)
  - [ ] Infinite loop (or until `max_repeats`)
  - [ ] Wait for next fire time
  - [ ] Publish `TimerTick` artifact
  - [ ] Increment iteration counter
  - [ ] Handle `asyncio.CancelledError` gracefully
  - [ ] Write unit tests with mocked sleep

- [ ] Implement `_wait_for_next_fire()` method
  - [ ] Support `interval` (simple sleep)
  - [ ] Support `at` with `time` (daily calculation)
  - [ ] Support `at` with `datetime` (one-time calculation)
  - [ ] Raise `NotImplementedError` for `cron` (future)
  - [ ] Write unit tests for each mode

- [ ] Implement `on_shutdown()` hook
  - [ ] Cancel all tasks in `_timer_tasks`
  - [ ] Wait for graceful cancellation with `gather()`
  - [ ] Write shutdown tests

#### 2.2 Integration
- [ ] Auto-register `TimerComponent` in `Flock.__init__()`
  - [ ] Check if any agents have `schedule_spec`
  - [ ] Add component to orchestrator if timers present
  - [ ] Write integration tests

---

### **Phase 3: Testing** 🧪

#### 3.1 Unit Tests
- [ ] Create `tests/unit/test_schedule_spec.py`
  - [ ] Test validation (exactly one trigger type)
  - [ ] Test invalid configurations
  - [ ] Test serialization

- [ ] Create `tests/unit/test_timer_component.py`
  - [ ] Test timer loop publishes ticks
  - [ ] Test initial delay
  - [ ] Test max_repeats limit
  - [ ] Test graceful shutdown
  - [ ] Test interval calculation
  - [ ] Test daily time calculation
  - [ ] Test one-time datetime calculation

- [ ] Create `tests/unit/test_agent_context_timer.py`
  - [ ] Test `trigger_type` property
  - [ ] Test `timer_iteration` property
  - [ ] Test `fire_time` property
  - [ ] Test with non-timer triggers

#### 3.2 Integration Tests
- [ ] Create `tests/integration/test_scheduled_agents.py`
  - [ ] Test scheduled agent executes on timer
  - [ ] Test timer + context filter (`.consumes()`)
  - [ ] Test timer + context provider integration
  - [ ] Test multiple scheduled agents
  - [ ] Test timer with `max_repeats`
  - [ ] Test timer with `after` delay
  - [ ] Test daily scheduled execution
  - [ ] Test one-time scheduled execution
  - [ ] Test validation errors (schedule + batch)

- [ ] Create `tests/integration/test_timer_lifecycle.py`
  - [ ] Test timer starts on orchestrator startup
  - [ ] Test timer stops on orchestrator shutdown
  - [ ] Test timer publishes correct correlation IDs
  - [ ] Test timer respects agent visibility

#### 3.3 Performance Tests
- [ ] Create `tests/performance/test_timer_scalability.py`
  - [ ] Test 100+ concurrent timers
  - [ ] Test timer precision under load
  - [ ] Test memory usage (long-running timers)

---

### **Phase 4: Documentation** 📖

#### 4.1 User Guide
- [ ] Create `docs/guides/scheduling.md`
  - [ ] Overview of timer-based agents
  - [ ] Common use cases (health checks, reports, cleanup)
  - [ ] API reference with examples
  - [ ] Best practices
  - [ ] Performance considerations
  - [ ] Edge cases and troubleshooting

#### 4.2 Tutorial
- [ ] Create `docs/tutorials/scheduled-agents.md`
  - [ ] Step 1: Simple periodic agent (health monitor)
  - [ ] Step 2: Timer + context filtering (error analyzer)
  - [ ] Step 3: Daily scheduled execution (report generator)
  - [ ] Step 4: Multi-type context aggregation
  - [ ] Step 5: One-time scheduled tasks (reminders)

#### 4.3 Examples
- [ ] Create `examples/09-scheduling/` directory
- [ ] Create `01_simple_health_monitor.py`
  - [ ] Basic periodic execution every 30 seconds
  - [ ] Publish `HealthStatus` artifacts
- [ ] Create `02_error_analyzer_with_filter.py`
  - [ ] Timer every 5 minutes
  - [ ] Context filter: only ERROR logs
  - [ ] Demonstrate `ctx.get_artifacts()` filtering
- [ ] Create `03_daily_report.py`
  - [ ] Scheduled at specific time (5 PM)
  - [ ] Aggregate transactions from the day
- [ ] Create `04_multi_type_aggregator.py`
  - [ ] Hourly execution
  - [ ] Context with multiple types (Metric + Alert)
  - [ ] Tag filtering
- [ ] Create `05_one_time_reminder.py`
  - [ ] One-time execution at specific datetime
  - [ ] Send notification artifact

#### 4.4 API Reference
- [ ] Add comprehensive docstrings to all new code
  - [ ] `AgentBuilder.schedule()`
  - [ ] `ScheduleSpec`
  - [ ] `TimerComponent`
  - [ ] `AgentContext.trigger_type`, etc.
- [ ] Update `AGENTS.md` with timer patterns
  - [ ] Add to "Quick Reference" section
  - [ ] Add to "Common Patterns" section

---

### **Phase 5: Dashboard Integration** 🎨 (Optional for v0.6.0)

#### 5.1 Backend API
- [ ] Add timer metadata to agent serialization
  - [ ] Include `schedule_spec` in agent JSON
  - [ ] Include current iteration count
  - [ ] Include next fire time (calculated)

#### 5.2 Frontend UI
- [ ] Add timer indicator to agent nodes
  - [ ] Clock icon ⏰ for scheduled agents
  - [ ] Tooltip showing schedule details
- [ ] Add timer panel in Agent Details
  - [ ] Show schedule configuration
  - [ ] Show iteration count
  - [ ] Show next fire countdown
  - [ ] Show fire history (last 10 fires)

---

### **Phase 6: Polish & Release** 🚀

#### 6.1 Version Bump
- [ ] Update `pyproject.toml` version to `0.6.0`
- [ ] Update `AGENTS.md` version header
- [ ] Create migration guide (if breaking changes)

#### 6.2 Changelog
- [ ] Add entry to `CHANGELOG.md`
  - [ ] Feature: Timer-based agent scheduling
  - [ ] New API: `AgentBuilder.schedule()`
  - [ ] New component: `TimerComponent`
  - [ ] Examples in `examples/09-scheduling/`

#### 6.3 Release Notes
- [ ] Write release notes for v0.6.0
  - [ ] Highlight timer scheduling feature
  - [ ] Show usage examples
  - [ ] Link to documentation
  - [ ] Migration notes (if any)

#### 6.4 Pre-commit Checks
- [ ] Run full test suite: `poe test`
- [ ] Run linter: `poe lint`
- [ ] Run formatter: `poe format`
- [ ] Check test coverage: `poe test-cov` (>90%)
- [ ] Verify all examples run successfully
- [ ] Manual dashboard testing (if UI added)

---

## 🎯 **Acceptance Criteria**

### **Functional Requirements**
- [x] Design document complete (`.flock/schedule/DESIGN.md`)
- [ ] Users can schedule agents with `.schedule(every=timedelta(...))`
- [ ] Users can schedule agents with `.schedule(at=time(...))`
- [ ] Users can schedule agents with `.schedule(at=datetime(...))`
- [ ] Initial delay works: `.schedule(every=..., after=timedelta(...))`
- [ ] Repeat limit works: `.schedule(every=..., max_repeats=N)`
- [ ] Timer + context filter works: `.schedule().consumes(Type, where=...)`
- [ ] Agent receives empty input: `ctx.artifacts = []`
- [ ] Timer metadata accessible: `ctx.timer_iteration`, `ctx.fire_time`
- [ ] Validation prevents: `.schedule()` + `.batch()`
- [ ] Timers start on orchestrator startup
- [ ] Timers stop gracefully on shutdown

### **Quality Requirements**
- [ ] Unit test coverage > 90%
- [ ] Integration test coverage > 85%
- [ ] All examples run without errors
- [ ] Documentation complete and accurate
- [ ] No performance regression (benchmark tests pass)
- [ ] No memory leaks (long-running timer test)

### **Documentation Requirements**
- [ ] User guide published
- [ ] Tutorial published
- [ ] 5 examples created and tested
- [ ] API docstrings complete
- [ ] `AGENTS.md` updated

---

## 📅 **Timeline Estimate**

**Total:** ~3-4 weeks (1 developer, full-time)

- **Week 1:** Core infrastructure (data models, builder API, context)
- **Week 2:** Timer component implementation
- **Week 3:** Testing and bug fixes
- **Week 4:** Documentation, examples, polish

---

## 🚧 **Known Limitations (v0.6.0)**

These will be addressed in future releases:

1. **No cron expression support** - Only `interval` and `at` (time/datetime)
2. **No persistent timer state** - Iteration resets on restart
3. **No distributed coordination** - Multi-instance orchestrators duplicate timers
4. **No dynamic timer control** - Can't start/stop timers at runtime
5. **Timer precision ~1 second** - Limited by `asyncio.sleep()`

---

## 📞 **Questions / Blockers**

Track questions and blockers here during implementation:

### **Blockers**
- None currently

### **Questions**
- None currently

---

## ✅ **Sign-off**

- [ ] Design reviewed and approved
- [ ] Implementation plan approved
- [ ] Timeline approved
- [ ] Ready to start implementation

---

**Last Updated:** 2025-10-30
**Status:** ✅ Ready for Implementation
