# Implementation Plan

## Validation Checklist
- [x] Context Ingestion section complete with all required specs
- [x] Implementation phases logically organized
- [x] Each phase starts with test definition (TDD approach)
- [x] Dependencies between phases identified
- [x] Parallel execution marked where applicable
- [x] Multi-component coordination identified (if applicable)
- [x] Final validation phase included
- [x] No placeholder content remains

## Metadata Reference

- `[ref: file]` - Links to design documents
- `[ref: file:lines]` - Links to specific lines in design documents
- `[activity: type]` - Activity hint for specialist agent selection (write_tests, implement, validate)

---

## Context Priming

*GATE: You MUST fully read all files mentioned in this section before starting any implementation.*

**Design Documentation** (PRIMARY REFERENCE - Skip PRD/SDD per user request):

- `.flock/schedule/DESIGN.md` - Complete design specification with architecture, API design, and implementation details `[ref: .flock/schedule/DESIGN.md]`
- `.flock/schedule/API_EXAMPLES.md` - API usage examples and patterns `[ref: .flock/schedule/API_EXAMPLES.md]`
- `.flock/schedule/TEST_EXAMPLES.md` - Test patterns and examples `[ref: .flock/schedule/TEST_EXAMPLES.md]`
- `.flock/schedule/IMPLEMENTATION_CHECKLIST.md` - Task checklist `[ref: .flock/schedule/IMPLEMENTATION_CHECKLIST.md]`

**Key Design Decisions**:

1. **Timers Are Artifact Producers**: Timers internally publish `TimerTick` artifacts, maintaining Flock's artifact-driven architecture
2. **Empty Input Pattern**: Timer-triggered agents receive `ctx.artifacts = []`, not input artifacts
3. **Context Filtering**: `.consumes()` with timers acts as context filter, NOT trigger
4. **Component Priority**: TimerComponent priority = 5 (before collection at 100)
5. **Graceful Shutdown**: Timer tasks cancelled via `on_shutdown()` hook

**Implementation Context**:

- **Test Commands**: `pytest tests/ -v`, `pytest --cov=flock --cov-report=term-missing`
- **Linting**: `ruff check src/flock/`
- **Type Checking**: `mypy src/flock/`
- **Patterns to Follow**:
  - BatchSpec/JoinSpec for ScheduleSpec `[ref: src/flock/core/subscription.py]`
  - OrchestratorComponent lifecycle hooks `[ref: src/flock/components/orchestrator/base.py]`
  - AgentBuilder fluent API `[ref: src/flock/core/agent.py]`

**Code Patterns Reference**:
- `src/flock/core/subscription.py` - Existing subscription patterns (BatchSpec, JoinSpec)
- `src/flock/core/agent.py` - AgentBuilder fluent API patterns
- `src/flock/models/system_artifacts.py` - System artifact patterns
- `src/flock/components/orchestrator/base.py` - Component lifecycle hooks

---

## Implementation Phases

### Phase 1: Core Infrastructure `[ref: .flock/schedule/DESIGN.md:207-509]`

**Delivers**: ScheduleSpec dataclass, TimerTick artifact, AgentBuilder.schedule() method, AgentContext timer properties

**Dependencies**: None (foundation phase)

**Estimated Time**: 1-2 days

#### Task 1.1: ScheduleSpec Data Model `[activity: write_tests, implement, validate]`

- [x] **Prime Context**:
    - [x] Read DESIGN.md Section 5.1 (ScheduleSpec) `[ref: .flock/schedule/DESIGN.md:209-247]`
    - [x] Review BatchSpec/JoinSpec patterns `[ref: src/flock/core/subscription.py:68-101]`

- [x] **Write Tests**: Create `tests/test_schedule_spec.py`
    - [x] test_schedule_spec_interval_only - Validate single trigger type `[ref: .flock/schedule/TEST_EXAMPLES.md:12-17]`
    - [x] test_schedule_spec_time_only - Validate time-based scheduling `[ref: .flock/schedule/TEST_EXAMPLES.md:19-24]`
    - [x] test_schedule_spec_datetime_only - Validate datetime-based scheduling `[ref: .flock/schedule/TEST_EXAMPLES.md:26-30]`
    - [x] test_schedule_spec_multiple_triggers_raises - Validation error test `[ref: .flock/schedule/TEST_EXAMPLES.md:32-36]`
    - [x] test_schedule_spec_no_triggers_raises - Validation error test `[ref: .flock/schedule/TEST_EXAMPLES.md:38-42]`
    - [x] test_schedule_spec_with_options - Test after/max_repeats `[ref: .flock/schedule/TEST_EXAMPLES.md:44-55]`

- [x] **Implement**: Modify `src/flock/core/subscription.py`
    - [x] Add ScheduleSpec dataclass after BatchSpec (line 101)
    - [x] Fields: interval, at, cron, after, max_repeats
    - [x] Implement `__post_init__` validation (exactly one trigger type)
    - [x] Add comprehensive docstring `[ref: .flock/schedule/DESIGN.md:209-247]`

- [x] **Validate**:
    - [x] Run: `pytest tests/test_schedule_spec.py -v`
    - [x] Run: `mypy src/flock/core/subscription.py`
    - [x] Run: `ruff check src/flock/core/subscription.py`
    - [x] Verify coverage >95%

#### Task 1.2: TimerTick System Artifact `[activity: write_tests, implement, validate]`

- [x] **Prime Context**:
    - [x] Read DESIGN.md Section 5.2 (TimerTick) `[ref: .flock/schedule/DESIGN.md:249-272]`
    - [x] Review system artifact patterns `[ref: src/flock/models/system_artifacts.py:13-31]`

- [x] **Write Tests**: Create `tests/test_timer_tick.py`
    - [x] test_timer_tick_creation - Basic instantiation
    - [x] test_timer_tick_immutable - Verify frozen=True
    - [x] test_timer_tick_serialization - JSON round-trip
    - [x] test_timer_tick_registered_as_flock_type - Type registry check

- [x] **Implement**: Modify `src/flock/models/system_artifacts.py`
    - [x] Add TimerTick class with @flock_type decorator
    - [x] Fields: timer_name, fire_time, iteration, schedule_spec
    - [x] Add Config class with frozen=True
    - [x] Comprehensive docstring `[ref: .flock/schedule/DESIGN.md:249-272]`

- [x] **Validate**:
    - [x] Run: `pytest tests/test_timer_tick.py -v`
    - [x] Verify type registration
    - [x] Run: `ruff check src/flock/models/system_artifacts.py`

#### Task 1.3: AgentBuilder.schedule() Method `[activity: write_tests, implement, validate]`

- [x] **Prime Context**:
    - [x] Read DESIGN.md Section 5.3 (AgentBuilder.schedule) `[ref: .flock/schedule/DESIGN.md:274-333]`
    - [x] Review AgentBuilder fluent API `[ref: src/flock/core/agent.py:501-660]`

- [x] **Write Tests**: Create `tests/test_agent_schedule_api.py`
    - [x] test_agent_builder_schedule_with_interval - Basic API `[ref: .flock/schedule/TEST_EXAMPLES.md:189-201]`
    - [x] test_agent_builder_schedule_with_time - Time-based API `[ref: .flock/schedule/TEST_EXAMPLES.md:203-214]`
    - [x] test_agent_builder_schedule_auto_subscribes_to_timer_tick - Verify subscription `[ref: .flock/schedule/TEST_EXAMPLES.md:216-240]`
    - [x] test_schedule_with_batch_raises_error - Validation `[ref: .flock/schedule/TEST_EXAMPLES.md:242-254]`

- [x] **Implement**: Modify `src/flock/core/agent.py`
    - [x] Add schedule() method to AgentBuilder class (after .publishes())
    - [x] Parameters: every, at, cron, after, max_repeats
    - [x] Create ScheduleSpec and assign to agent.schedule_spec
    - [x] Auto-subscribe to TimerTick with filter
    - [x] Return self for chaining `[ref: .flock/schedule/DESIGN.md:274-333]`

- [x] **Validate**:
    - [x] Run: `pytest tests/test_agent_schedule_api.py -v`
    - [x] Run: `mypy src/flock/core/agent.py`
    - [x] Verify fluent API chaining works

#### Task 1.4: AgentContext Timer Properties `[activity: write_tests, implement, validate]`

- [x] **Prime Context**:
    - [x] Read DESIGN.md Section 5.5 (AgentContext) `[ref: .flock/schedule/DESIGN.md:468-509]`
    - [x] Locate AgentContext class in codebase

- [x] **Write Tests**: Create `tests/test_agent_context_timer.py`
    - [x] test_agent_context_trigger_type_timer `[ref: .flock/schedule/TEST_EXAMPLES.md:267-272]`
    - [x] test_agent_context_timer_iteration `[ref: .flock/schedule/TEST_EXAMPLES.md:281-286]`
    - [x] test_agent_context_fire_time `[ref: .flock/schedule/TEST_EXAMPLES.md:295-301]`

- [x] **Implement**: Modify `src/flock/core/agent.py` (AgentContext class)
    - [x] Add @property trigger_type -> str ("timer" or "artifact")
    - [x] Add @property timer_iteration -> int | None
    - [x] Add @property fire_time -> datetime | None
    - [x] Add docstrings `[ref: .flock/schedule/DESIGN.md:468-509]`

- [x] **Validate**:
    - [x] Run: `pytest tests/test_agent_context_timer.py -v`
    - [x] Verify properties return correct types

#### Task 1.5: Schedule + Batch Validation `[activity: write_tests, implement, validate]`

- [x] **Prime Context**:
    - [x] Read DESIGN.md mutual exclusivity section `[ref: .flock/schedule/DESIGN.md:816-838]`

- [x] **Write Tests**: Add to `tests/test_agent_schedule_api.py`
    - [x] test_schedule_and_batch_raises_value_error
    - [x] test_schedule_without_batch_succeeds
    - [x] test_batch_without_schedule_succeeds

- [x] **Implement**: Modify AgentBuilder validation
    - [x] Add check in .schedule() or .consumes() for mutual exclusivity
    - [x] Raise ValueError with clear message

- [x] **Validate**:
    - [x] Run: `pytest tests/test_agent_schedule_api.py -v`
    - [x] Verify error messages helpful

#### Task 1.6: Phase 1 Integration Tests `[activity: write_tests, validate]`

- [x] **Write Tests**: Create `tests/integration/test_schedule_integration.py`
    - [x] test_agent_with_schedule_spec_created
    - [x] test_schedule_auto_subscription_works
    - [x] test_schedule_batch_validation_integrated

- [x] **Validate**:
    - [x] Run: `pytest tests/integration/test_schedule_integration.py -v`
    - [x] Run full test suite: `pytest tests/ -v`
    - [x] Coverage: `pytest tests/ --cov=flock --cov-report=term-missing` (target >90%)

---

### Phase 2: Timer Component `[ref: .flock/schedule/DESIGN.md:335-466]`

**Delivers**: TimerComponent with background tasks, timer loop logic, interval/daily/one-time scheduling, graceful shutdown

**Dependencies**: Phase 1 complete

**Estimated Time**: 2-3 days

#### Task 2.1: TimerComponent Structure `[activity: write_tests, implement, validate]`

- [x] **Prime Context**:
    - [x] Read DESIGN.md Section 5.4 (TimerComponent) `[ref: .flock/schedule/DESIGN.md:335-466]`
    - [x] Review OrchestratorComponent pattern `[ref: src/flock/components/orchestrator/base.py:123-401]`

- [x] **Write Tests**: Create `tests/test_timer_component.py`
    - [x] test_timer_component_creation
    - [x] test_timer_component_priority (should be 5)
    - [x] test_on_initialize_creates_timer_tasks `[ref: .flock/schedule/TEST_EXAMPLES.md:152-175]`
    - [x] test_on_shutdown_cancels_tasks `[ref: .flock/schedule/TEST_EXAMPLES.md:152-175]`

- [x] **Implement**: Create `src/flock/components/orchestrator/scheduling/timer.py`
    - [x] Create scheduling/ subdirectory
    - [x] Create TimerComponent class extending OrchestratorComponent
    - [x] Set name="timer", priority=5
    - [x] Add _timer_tasks dict
    - [x] Implement on_initialize() and on_shutdown() `[ref: .flock/schedule/DESIGN.md:362-369, 457-465]`

- [x] **Validate**:
    - [x] Run: `pytest tests/test_timer_component.py -v`
    - [x] Verify component structure correct

#### Task 2.2: Timer Loop Logic `[activity: write_tests, implement, validate]`

- [x] **Prime Context**:
    - [x] Read DESIGN.md _timer_loop method `[ref: .flock/schedule/DESIGN.md:371-415]`
    - [x] Review TEST_EXAMPLES.md timer loop tests `[ref: .flock/schedule/TEST_EXAMPLES.md:71-149]`

- [x] **Write Tests**: Add to `tests/test_timer_component.py`
    - [x] test_timer_loop_publishes_ticks `[ref: .flock/schedule/TEST_EXAMPLES.md:71-100]`
    - [x] test_timer_loop_respects_initial_delay `[ref: .flock/schedule/TEST_EXAMPLES.md:102-128]`
    - [x] test_timer_loop_respects_max_repeats `[ref: .flock/schedule/TEST_EXAMPLES.md:130-149]`

- [x] **Implement**: Add `_timer_loop()` method to TimerComponent
    - [x] Async method accepting orchestrator, agent_name, spec
    - [x] Try/except for CancelledError
    - [x] Initial delay handling
    - [x] Loop with iteration counter
    - [x] Publish TimerTick with correlation_id and tags `[ref: .flock/schedule/DESIGN.md:371-415]`

- [x] **Validate**:
    - [x] Run: `pytest tests/test_timer_component.py -k "timer_loop" -v`
    - [x] Verify timing accuracy

#### Task 2.3: Wait For Next Fire Logic `[activity: write_tests, implement, validate]`

- [x] **Prime Context**:
    - [x] Read DESIGN.md _wait_for_next_fire method `[ref: .flock/schedule/DESIGN.md:417-455]`

- [x] **Write Tests**: Add to `tests/test_timer_component.py`
    - [x] test_wait_for_next_fire_interval
    - [x] test_wait_for_next_fire_time_future_today
    - [x] test_wait_for_next_fire_datetime_future
    - [x] test_wait_for_next_fire_cron_raises_not_implemented

- [x] **Implement**: Add `_wait_for_next_fire()` method
    - [x] Handle interval (simple sleep)
    - [x] Handle time (daily calculation)
    - [x] Handle datetime (one-time calculation)
    - [x] Raise NotImplementedError for cron `[ref: .flock/schedule/DESIGN.md:417-455]`

- [x] **Validate**:
    - [x] Run: `pytest tests/test_timer_component.py -k "wait_for_next_fire" -v`

#### Task 2.4: Component Registration `[activity: implement, validate]`

- [x] **Prime Context**:
    - [x] Find where CircuitBreakerComponent is registered in orchestrator

- [x] **Implement**: Modify orchestrator initialization
    - [x] Add import for TimerComponent
    - [x] Instantiate and register TimerComponent
    - [x] Ensure components sorted by priority

- [x] **Validate**:
    - [x] Run: `pytest tests/test_timer_component_registration.py -v`

#### Task 2.5: Phase 2 Integration Tests `[activity: write_tests, validate]`

- [x] **Write Tests**: Create `tests/integration/test_scheduled_agents.py`
    - [x] test_scheduled_agent_executes_on_timer `[ref: .flock/schedule/TEST_EXAMPLES.md:331-363]`
    - [x] test_timer_agent_receives_empty_artifacts `[ref: .flock/schedule/TEST_EXAMPLES.md:365-394]`
    - [x] test_timer_agent_has_timer_metadata `[ref: .flock/schedule/TEST_EXAMPLES.md:396-432]`
    - [x] test_timer_with_context_filter `[ref: .flock/schedule/TEST_EXAMPLES.md:457-495]`
    - [x] test_timer_lifecycle (start/stop) `[ref: .flock/schedule/TEST_EXAMPLES.md:565-633]`

- [x] **Validate**:
    - [x] Run: `pytest tests/integration/test_scheduled_agents.py -v`
    - [x] Run full suite: `pytest tests/ -v`
    - [x] Coverage >90% for timer components

---

### Phase 3: Integration & Examples `[ref: .flock/schedule/API_EXAMPLES.md]`

**Delivers**: Integration tests, 5 production-ready examples, documentation updates

**Dependencies**: Phase 2 complete

**Estimated Time**: 2-3 days

#### Task 3.1: Complete Integration Tests `[activity: write_tests, validate]`

- [x] **Prime Context**:
    - [x] Read TEST_EXAMPLES.md Complete Workflow `[ref: .flock/schedule/TEST_EXAMPLES.md:638-738]`

- [x] **Write Tests**: Create `tests/integration/test_timer_lifecycle.py`
    - [x] test_complete_timer_workflow - Multi-agent cascade `[ref: .flock/schedule/TEST_EXAMPLES.md:663-738]`
    - [x] test_timer_with_tag_filtering
    - [x] test_timer_with_semantic_filtering
    - [x] test_timer_continues_after_agent_error
    - [x] test_timer_with_one_time_datetime

- [x] **Validate**:
    - [x] Run: `pytest tests/integration/test_timer_lifecycle.py -v`
    - [x] Verify all 14 integration tests pass
    - [x] Coverage >90%

#### Task 3.2: Example Scripts `[activity: implement, validate]` `[parallel: true]`

- [x] **Prime Context**:
    - [x] Read API_EXAMPLES.md Examples 1-7 `[ref: .flock/schedule/API_EXAMPLES.md:223-420]`
    - [x] Review existing example patterns `[ref: examples/01-getting-started/]`

- [x] **Implement**: Create `examples/09-scheduling/`
    - [x] Create directory structure
    - [x] `01_simple_health_monitor.py` - Interval scheduling `[ref: .flock/schedule/API_EXAMPLES.md:223-244]`
    - [x] `02_error_log_analyzer.py` - Timer + filter `[ref: .flock/schedule/API_EXAMPLES.md:246-269]`
    - [x] `03_daily_report_generator.py` - Time-based `[ref: .flock/schedule/API_EXAMPLES.md:273-296]`
    - [x] `04_batch_data_processor.py` - Batch aggregation `[ref: .flock/schedule/API_EXAMPLES.md:298-347]`
    - [x] `05_one_time_reminder.py` - Datetime-based `[ref: .flock/schedule/API_EXAMPLES.md:394-417]`
    - [x] `README.md` - Overview and patterns

- [x] **Validate**:
    - [x] Run each example in CLI mode
    - [x] Run each example in dashboard mode
    - [x] Verify timing behavior correct
    - [x] No errors or warnings

#### Task 3.3: Documentation Updates `[activity: implement, validate]` `[parallel: true]`

- [x] **Implement**: Create/update documentation
    - [x] Create `docs/guides/scheduling.md` - Complete guide
    - [x] Create `docs/tutorials/scheduled-agents.md` - Step-by-step tutorial
    - [x] Update `AGENTS.md` - Add scheduling section
    - [x] Update `docs/guides/index.md` - Add scheduling link
    - [x] Update `docs/tutorials/index.md` - Add tutorial link
    - [x] Update `docs/examples/index.md` - Add examples section

- [x] **Validate**:
    - [x] All links work
    - [x] Code snippets tested
    - [x] Documentation builds successfully
    - [x] `mkdocs serve` renders correctly

---

## Integration & End-to-End Validation

- [ ] **Unit Tests** (>95% coverage)
    - [ ] ScheduleSpec tests pass
    - [ ] TimerTick tests pass
    - [ ] TimerComponent tests pass
    - [ ] AgentBuilder.schedule() tests pass
    - [ ] AgentContext timer property tests pass

- [ ] **Integration Tests** (>90% coverage)
    - [ ] All scheduled agent execution tests pass
    - [ ] Timer lifecycle tests pass (start/stop)
    - [ ] Context filtering tests pass
    - [ ] Multi-agent workflow tests pass
    - [ ] Error handling tests pass

- [ ] **Examples Validation**
    - [ ] All 5 examples run without errors (CLI mode)
    - [ ] All 5 examples run without errors (dashboard mode)
    - [ ] Timing behavior correct for each example
    - [ ] Examples demonstrate key patterns

- [ ] **Documentation Validation**
    - [ ] All documentation links valid
    - [ ] Code snippets syntax-correct
    - [ ] mkdocs builds successfully
    - [ ] Search finds scheduling content

- [ ] **Quality Gates**
    - [ ] Type checking passes: `mypy src/flock/`
    - [ ] Linting passes: `ruff check src/flock/`
    - [ ] Format check passes: `ruff format --check src/flock/`
    - [ ] No regressions in existing tests
    - [ ] Test coverage >90% for new code

- [ ] **Performance Validation**
    - [ ] 100+ concurrent timers work
    - [ ] No memory leaks in long-running timers
    - [ ] Timer precision acceptable (~1 second resolution)

- [ ] **Design Compliance**
    - [ ] Implementation matches DESIGN.md specification
    - [ ] All API patterns from API_EXAMPLES.md work
    - [ ] Test patterns from TEST_EXAMPLES.md validated
    - [ ] No deviations without documentation
