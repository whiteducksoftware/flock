# Timer-Based Scheduling - Test Examples

**Sample test cases to guide implementation**

---

## 🧪 **Unit Tests**

### **Test 1: ScheduleSpec Validation**

```python
import pytest
from datetime import timedelta, time, datetime
from flock.core.subscription import ScheduleSpec

def test_schedule_spec_interval_only():
    """Valid: Only interval specified."""
    spec = ScheduleSpec(interval=timedelta(seconds=30))
    assert spec.interval == timedelta(seconds=30)
    assert spec.at is None
    assert spec.cron is None

def test_schedule_spec_time_only():
    """Valid: Only time specified."""
    spec = ScheduleSpec(at=time(hour=17, minute=0))
    assert spec.at == time(hour=17, minute=0)
    assert spec.interval is None

def test_schedule_spec_datetime_only():
    """Valid: Only datetime specified."""
    dt = datetime(2025, 11, 1, 9, 0)
    spec = ScheduleSpec(at=dt)
    assert spec.at == dt

def test_schedule_spec_multiple_triggers_raises():
    """Invalid: Multiple trigger types specified."""
    with pytest.raises(ValueError, match="Exactly one"):
        ScheduleSpec(interval=timedelta(seconds=30), at=time(hour=17))

def test_schedule_spec_no_triggers_raises():
    """Invalid: No trigger type specified."""
    with pytest.raises(ValueError, match="Exactly one"):
        ScheduleSpec()

def test_schedule_spec_with_options():
    """Valid: Interval with after and max_repeats."""
    spec = ScheduleSpec(
        interval=timedelta(seconds=30),
        after=timedelta(seconds=10),
        max_repeats=5
    )
    assert spec.interval == timedelta(seconds=30)
    assert spec.after == timedelta(seconds=10)
    assert spec.max_repeats == 5
```

---

### **Test 2: TimerComponent - Timer Loop**

```python
import pytest
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock
from flock.components.orchestrator.scheduling.timer import TimerComponent
from flock.core.subscription import ScheduleSpec
from flock.models.system_artifacts import TimerTick

@pytest.mark.asyncio
async def test_timer_loop_publishes_ticks():
    """Timer loop publishes TimerTick artifacts at intervals."""
    orchestrator = AsyncMock()
    component = TimerComponent()

    spec = ScheduleSpec(interval=timedelta(seconds=0.1))  # 100ms for fast test

    # Run timer loop for 0.35s (should publish ~3 ticks)
    task = asyncio.create_task(
        component._timer_loop(orchestrator, "test_agent", spec)
    )

    await asyncio.sleep(0.35)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify publish called 3 times
    assert orchestrator.publish.call_count == 3

    # Verify TimerTick structure
    for call in orchestrator.publish.call_args_list:
        tick = call.args[0]
        assert isinstance(tick, TimerTick)
        assert tick.timer_name == "test_agent"
        assert tick.fire_time is not None

@pytest.mark.asyncio
async def test_timer_loop_respects_initial_delay():
    """Timer waits for initial delay before first tick."""
    orchestrator = AsyncMock()
    component = TimerComponent()

    spec = ScheduleSpec(
        interval=timedelta(seconds=0.1),
        after=timedelta(seconds=0.2)
    )

    task = asyncio.create_task(
        component._timer_loop(orchestrator, "test_agent", spec)
    )

    # Wait 0.15s - should NOT have published yet
    await asyncio.sleep(0.15)
    assert orchestrator.publish.call_count == 0

    # Wait another 0.2s - should have published
    await asyncio.sleep(0.2)
    assert orchestrator.publish.call_count >= 1

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

@pytest.mark.asyncio
async def test_timer_loop_respects_max_repeats():
    """Timer stops after max_repeats executions."""
    orchestrator = AsyncMock()
    component = TimerComponent()

    spec = ScheduleSpec(
        interval=timedelta(seconds=0.05),
        max_repeats=3
    )

    # Run timer loop (should stop after 3 iterations)
    await component._timer_loop(orchestrator, "test_agent", spec)

    # Verify exactly 3 publishes
    assert orchestrator.publish.call_count == 3

    # Verify iteration numbers
    iterations = [call.args[0].iteration for call in orchestrator.publish.call_args_list]
    assert iterations == [0, 1, 2]

@pytest.mark.asyncio
async def test_timer_component_graceful_shutdown():
    """Timer component cancels tasks on shutdown."""
    orchestrator = MagicMock()
    orchestrator.agents = []

    component = TimerComponent()
    await component.on_initialize(orchestrator)

    # Manually add a timer task
    spec = ScheduleSpec(interval=timedelta(seconds=1))
    task = asyncio.create_task(
        component._timer_loop(orchestrator, "test_agent", spec)
    )
    component._timer_tasks["test_agent"] = task

    # Verify task is running
    assert not task.done()

    # Trigger shutdown
    await component.on_shutdown(orchestrator)

    # Verify task was cancelled
    assert task.done()
    assert task.cancelled()
```

---

### **Test 3: AgentBuilder.schedule()**

```python
import pytest
from datetime import timedelta, time
from flock import Flock
from flock.core.subscription import ScheduleSpec
from flock.models.system_artifacts import TimerTick

def test_agent_builder_schedule_interval():
    """AgentBuilder.schedule() creates ScheduleSpec."""
    flock = Flock("openai/gpt-4.1")

    agent = (
        flock.agent("test")
        .schedule(every=timedelta(seconds=30))
        .publishes(MockArtifact)
        .agent  # Access underlying Agent
    )

    assert agent.schedule_spec is not None
    assert agent.schedule_spec.interval == timedelta(seconds=30)

def test_agent_builder_schedule_time():
    """AgentBuilder.schedule() with time creates daily schedule."""
    flock = Flock("openai/gpt-4.1")

    agent = (
        flock.agent("test")
        .schedule(at=time(hour=17, minute=0))
        .publishes(MockArtifact)
        .agent
    )

    assert agent.schedule_spec.at == time(hour=17, minute=0)

def test_agent_builder_schedule_auto_subscribes():
    """AgentBuilder.schedule() auto-subscribes to TimerTick."""
    flock = Flock("openai/gpt-4.1")

    agent = (
        flock.agent("test")
        .schedule(every=timedelta(seconds=30))
        .publishes(MockArtifact)
        .agent
    )

    # Verify agent has subscription to TimerTick
    assert len(agent.subscriptions) == 1
    assert TimerTick in agent.subscriptions[0].types

    # Verify filter by timer_name
    assert len(agent.subscriptions[0].where) == 1
    predicate = agent.subscriptions[0].where[0]

    # Test predicate
    matching_tick = TimerTick(timer_name="test", iteration=0)
    non_matching_tick = TimerTick(timer_name="other", iteration=0)

    assert predicate(matching_tick) is True
    assert predicate(non_matching_tick) is False

def test_agent_builder_schedule_validation_with_batch_raises():
    """AgentBuilder raises error if .schedule() + .batch()."""
    from flock.core.subscription import BatchSpec

    flock = Flock("openai/gpt-4.1")

    with pytest.raises(ValueError, match="mutually exclusive"):
        agent = (
            flock.agent("test")
            .schedule(every=timedelta(seconds=30))
            .consumes(MockArtifact, batch=BatchSpec(size=10))
            .publishes(Result)
        )
```

---

### **Test 4: AgentContext Timer Properties**

```python
import pytest
from datetime import datetime
from flock.core.agent import AgentContext
from flock.models.system_artifacts import TimerTick

def test_agent_context_trigger_type_timer():
    """AgentContext.trigger_type returns 'timer' for TimerTick."""
    tick = TimerTick(timer_name="test", iteration=5)
    ctx = AgentContext(artifacts=[tick])

    assert ctx.trigger_type == "timer"

def test_agent_context_trigger_type_artifact():
    """AgentContext.trigger_type returns 'artifact' for normal artifacts."""
    artifact = MockArtifact()
    ctx = AgentContext(artifacts=[artifact])

    assert ctx.trigger_type == "artifact"

def test_agent_context_timer_iteration():
    """AgentContext.timer_iteration returns iteration count."""
    tick = TimerTick(timer_name="test", iteration=42)
    ctx = AgentContext(artifacts=[tick])

    assert ctx.timer_iteration == 42

def test_agent_context_timer_iteration_none_for_artifact():
    """AgentContext.timer_iteration returns None for non-timer triggers."""
    artifact = MockArtifact()
    ctx = AgentContext(artifacts=[artifact])

    assert ctx.timer_iteration is None

def test_agent_context_fire_time():
    """AgentContext.fire_time returns fire datetime."""
    fire_time = datetime(2025, 10, 30, 12, 0, 0)
    tick = TimerTick(timer_name="test", iteration=5, fire_time=fire_time)
    ctx = AgentContext(artifacts=[tick])

    assert ctx.fire_time == fire_time

def test_agent_context_fire_time_none_for_artifact():
    """AgentContext.fire_time returns None for non-timer triggers."""
    artifact = MockArtifact()
    ctx = AgentContext(artifacts=[artifact])

    assert ctx.fire_time is None
```

---

## 🔗 **Integration Tests**

### **Test 5: Scheduled Agent Execution**

```python
import pytest
import asyncio
from datetime import timedelta
from flock import Flock
from flock.core.artifacts import flock_type
from pydantic import BaseModel

@flock_type
class HealthStatus(BaseModel):
    cpu: float
    timestamp: datetime

@pytest.mark.asyncio
async def test_scheduled_agent_executes_on_timer():
    """Scheduled agent executes when timer fires."""
    flock = Flock("openai/gpt-4.1")

    execution_count = 0

    def health_check():
        nonlocal execution_count
        execution_count += 1
        return HealthStatus(cpu=50.0, timestamp=datetime.now())

    agent = (
        flock.agent("health")
        .schedule(every=timedelta(seconds=0.1))  # 100ms
        .publishes(HealthStatus)
        .calls(health_check)
    )

    # Start orchestrator in background
    serve_task = asyncio.create_task(flock.serve())

    # Wait for ~3 executions
    await asyncio.sleep(0.35)

    # Stop orchestrator
    serve_task.cancel()
    try:
        await serve_task
    except asyncio.CancelledError:
        pass

    # Verify agent executed multiple times
    assert execution_count >= 2  # At least 2 executions

@pytest.mark.asyncio
async def test_timer_agent_receives_empty_artifacts():
    """Timer-triggered agent receives empty artifact list."""
    flock = Flock("openai/gpt-4.1")

    received_artifacts = None

    async def check_context(ctx):
        nonlocal received_artifacts
        received_artifacts = ctx.artifacts
        return HealthStatus(cpu=50.0, timestamp=datetime.now())

    agent = (
        flock.agent("health")
        .schedule(every=timedelta(seconds=0.1))
        .publishes(HealthStatus)
        .calls(check_context)
    )

    serve_task = asyncio.create_task(flock.serve())
    await asyncio.sleep(0.2)
    serve_task.cancel()

    try:
        await serve_task
    except asyncio.CancelledError:
        pass

    # Verify agent received empty artifacts
    assert received_artifacts == []

@pytest.mark.asyncio
async def test_timer_agent_has_timer_metadata():
    """Timer-triggered agent context has timer properties."""
    flock = Flock("openai/gpt-4.1")

    received_metadata = {}

    async def check_metadata(ctx):
        nonlocal received_metadata
        received_metadata = {
            "trigger_type": ctx.trigger_type,
            "timer_iteration": ctx.timer_iteration,
            "fire_time": ctx.fire_time
        }
        return HealthStatus(cpu=50.0, timestamp=datetime.now())

    agent = (
        flock.agent("health")
        .schedule(every=timedelta(seconds=0.1))
        .publishes(HealthStatus)
        .calls(check_metadata)
    )

    serve_task = asyncio.create_task(flock.serve())
    await asyncio.sleep(0.2)
    serve_task.cancel()

    try:
        await serve_task
    except asyncio.CancelledError:
        pass

    # Verify timer metadata
    assert received_metadata["trigger_type"] == "timer"
    assert isinstance(received_metadata["timer_iteration"], int)
    assert received_metadata["timer_iteration"] >= 0
    assert isinstance(received_metadata["fire_time"], datetime)
```

---

### **Test 6: Timer + Context Filtering**

```python
import pytest
import asyncio
from datetime import timedelta
from flock import Flock
from flock.core.artifacts import flock_type
from pydantic import BaseModel

@flock_type
class LogEntry(BaseModel):
    level: str
    message: str

@flock_type
class ErrorReport(BaseModel):
    error_count: int

@pytest.mark.asyncio
async def test_timer_with_context_filter():
    """Timer agent with .consumes() filters blackboard context."""
    flock = Flock("openai/gpt-4.1")

    # Publish mixed logs
    await flock.publish(LogEntry(level="INFO", message="Info 1"))
    await flock.publish(LogEntry(level="ERROR", message="Error 1"))
    await flock.publish(LogEntry(level="ERROR", message="Error 2"))
    await flock.publish(LogEntry(level="INFO", message="Info 2"))

    received_logs = None

    async def analyze_errors(ctx):
        nonlocal received_logs
        received_logs = ctx.get_artifacts(LogEntry)
        return ErrorReport(error_count=len(received_logs))

    # Timer agent that ONLY sees ERROR logs
    analyzer = (
        flock.agent("analyzer")
        .schedule(every=timedelta(seconds=0.1))
        .consumes(LogEntry, where=lambda log: log.level == "ERROR")
        .publishes(ErrorReport)
        .calls(analyze_errors)
    )

    serve_task = asyncio.create_task(flock.serve())
    await asyncio.sleep(0.15)
    serve_task.cancel()

    try:
        await serve_task
    except asyncio.CancelledError:
        pass

    # Verify agent only saw ERROR logs
    assert received_logs is not None
    assert len(received_logs) == 2
    assert all(log.level == "ERROR" for log in received_logs)

@pytest.mark.asyncio
async def test_timer_with_multi_type_context():
    """Timer agent sees multiple artifact types in context."""
    flock = Flock("openai/gpt-4.1")

    @flock_type
    class Metric(BaseModel):
        value: float

    @flock_type
    class Alert(BaseModel):
        message: str

    @flock_type
    class Report(BaseModel):
        metric_count: int
        alert_count: int

    # Publish artifacts
    await flock.publish(Metric(value=1.0))
    await flock.publish(Metric(value=2.0))
    await flock.publish(Alert(message="Alert 1"))

    received_data = {}

    async def aggregate(ctx):
        nonlocal received_data
        received_data = {
            "metrics": ctx.get_artifacts(Metric),
            "alerts": ctx.get_artifacts(Alert)
        }
        return Report(
            metric_count=len(received_data["metrics"]),
            alert_count=len(received_data["alerts"])
        )

    aggregator = (
        flock.agent("aggregator")
        .schedule(every=timedelta(seconds=0.1))
        .consumes(Metric, Alert)
        .publishes(Report)
        .calls(aggregate)
    )

    serve_task = asyncio.create_task(flock.serve())
    await asyncio.sleep(0.15)
    serve_task.cancel()

    try:
        await serve_task
    except asyncio.CancelledError:
        pass

    # Verify both types visible
    assert len(received_data["metrics"]) == 2
    assert len(received_data["alerts"]) == 1
```

---

### **Test 7: Timer Lifecycle**

```python
import pytest
import asyncio
from datetime import timedelta
from flock import Flock

@pytest.mark.asyncio
async def test_timer_starts_on_orchestrator_startup():
    """Timers start when orchestrator starts."""
    flock = Flock("openai/gpt-4.1")

    execution_count = 0

    def counter():
        nonlocal execution_count
        execution_count += 1
        return MockArtifact()

    agent = (
        flock.agent("counter")
        .schedule(every=timedelta(seconds=0.1))
        .publishes(MockArtifact)
        .calls(counter)
    )

    # Before startup - no executions
    assert execution_count == 0

    # Start orchestrator
    serve_task = asyncio.create_task(flock.serve())
    await asyncio.sleep(0.25)

    # After startup - multiple executions
    assert execution_count >= 1

    serve_task.cancel()
    try:
        await serve_task
    except asyncio.CancelledError:
        pass

@pytest.mark.asyncio
async def test_timer_stops_on_orchestrator_shutdown():
    """Timers stop gracefully on shutdown."""
    flock = Flock("openai/gpt-4.1")

    execution_count = 0

    def counter():
        nonlocal execution_count
        execution_count += 1
        return MockArtifact()

    agent = (
        flock.agent("counter")
        .schedule(every=timedelta(seconds=0.1))
        .publishes(MockArtifact)
        .calls(counter)
    )

    # Start and run
    serve_task = asyncio.create_task(flock.serve())
    await asyncio.sleep(0.25)
    count_before_shutdown = execution_count

    # Shutdown
    serve_task.cancel()
    try:
        await serve_task
    except asyncio.CancelledError:
        pass

    # Wait and verify no more executions
    await asyncio.sleep(0.3)
    assert execution_count == count_before_shutdown  # No new executions
```

---

## 🎯 **Example Test: Complete Workflow**

```python
import pytest
import asyncio
from datetime import timedelta
from flock import Flock
from flock.core.artifacts import flock_type
from pydantic import BaseModel

@flock_type
class HealthMetric(BaseModel):
    cpu: float
    memory: float

@flock_type
class HealthAlert(BaseModel):
    severity: str
    message: str

@flock_type
class HealthReport(BaseModel):
    metric_count: int
    alert_count: int

@pytest.mark.asyncio
async def test_complete_timer_workflow():
    """Complete workflow: collector → monitor → summarizer."""
    flock = Flock("openai/gpt-4.1")

    metrics_collected = []
    alerts_generated = []
    reports_generated = []

    # Agent 1: Collect metrics every 100ms
    def collect_metrics():
        metric = HealthMetric(cpu=75.0, memory=60.0)
        metrics_collected.append(metric)
        return metric

    collector = (
        flock.agent("collector")
        .schedule(every=timedelta(seconds=0.1))
        .publishes(HealthMetric)
        .calls(collect_metrics)
    )

    # Agent 2: Monitor for high CPU (reactive)
    def monitor_health(ctx):
        metric = ctx.artifacts[0]
        if metric.cpu > 70:
            alert = HealthAlert(severity="HIGH", message="High CPU")
            alerts_generated.append(alert)
            return alert
        return None

    monitor = (
        flock.agent("monitor")
        .consumes(HealthMetric, where=lambda m: m.cpu > 70)
        .publishes(HealthAlert)
        .calls(monitor_health)
    )

    # Agent 3: Generate report every 500ms
    def summarize(ctx):
        metrics = ctx.get_artifacts(HealthMetric)
        alerts = ctx.get_artifacts(HealthAlert)
        report = HealthReport(
            metric_count=len(metrics),
            alert_count=len(alerts)
        )
        reports_generated.append(report)
        return report

    summarizer = (
        flock.agent("summarizer")
        .schedule(every=timedelta(seconds=0.5))
        .consumes(HealthMetric, HealthAlert)
        .publishes(HealthReport)
        .calls(summarize)
    )

    # Run workflow
    serve_task = asyncio.create_task(flock.serve())
    await asyncio.sleep(0.6)
    serve_task.cancel()

    try:
        await serve_task
    except asyncio.CancelledError:
        pass

    # Verify workflow
    assert len(metrics_collected) >= 5  # ~6 metrics in 0.6s
    assert len(alerts_generated) >= 5   # All high CPU
    assert len(reports_generated) >= 1  # At least 1 report

    # Verify report accuracy
    final_report = reports_generated[-1]
    assert final_report.metric_count == len(metrics_collected)
    assert final_report.alert_count == len(alerts_generated)
```

---

## 📋 **Test Coverage Goals**

### **Unit Tests** (Target: >95%)

- [ ] `ScheduleSpec` validation
- [ ] `TimerTick` serialization
- [ ] `TimerComponent._timer_loop()` interval logic
- [ ] `TimerComponent._wait_for_next_fire()` calculations
- [ ] `TimerComponent.on_shutdown()` cancellation
- [ ] `AgentBuilder.schedule()` creates spec
- [ ] `AgentBuilder.schedule()` auto-subscribes
- [ ] `AgentBuilder` validation (schedule + batch)
- [ ] `AgentContext.trigger_type` property
- [ ] `AgentContext.timer_iteration` property
- [ ] `AgentContext.fire_time` property

### **Integration Tests** (Target: >90%)

- [ ] Scheduled agent executes on timer
- [ ] Timer agent receives empty artifacts
- [ ] Timer agent has timer metadata
- [ ] Timer + context filter works
- [ ] Timer + multi-type context works
- [ ] Timer + tag filtering works
- [ ] Timer + semantic filtering works
- [ ] Timer + context provider works
- [ ] Timer starts on startup
- [ ] Timer stops on shutdown
- [ ] Multiple scheduled agents coexist
- [ ] Timer with `max_repeats` stops correctly
- [ ] Timer with `after` delays correctly
- [ ] Daily time-based scheduling works
- [ ] One-time datetime scheduling works

### **Performance Tests** (Target: Stable under load)

- [ ] 100+ concurrent timers
- [ ] Timer precision under load
- [ ] Memory usage (long-running timers)
- [ ] No timer drift over time

---

**Next Steps:** Use these tests to drive TDD implementation! 🚀
