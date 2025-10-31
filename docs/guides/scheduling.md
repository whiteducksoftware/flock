---
title: Timer-Based Agent Scheduling
description: Schedule agents to execute periodically or at specific times without requiring artifact triggers
tags:
  - scheduling
  - timers
  - guide
  - advanced
search:
  boost: 1.5
---

# Timer-Based Agent Scheduling

Timer-based scheduling enables agents to execute periodically or at specific times **without requiring artifact triggers**. This is perfect for health checks, periodic reports, batch processing, and scheduled maintenance tasks.

**Think of scheduled agents like cron jobs:** They run automatically on a timer while maintaining full access to the blackboard for context.

---

## When to Use Timer Scheduling

### Use Timers For:

- **Periodic monitoring** - Health checks, system status, resource monitoring
- **Scheduled reports** - Daily summaries, weekly analytics, monthly aggregations
- **Batch processing** - Process accumulated data at regular intervals
- **Cleanup tasks** - Delete old records, archive data, vacuum databases
- **Time-based alerts** - Check for stale data, missed deadlines, expired items

### Use Artifact Triggers For:

- **Event-driven workflows** - Process orders, handle user requests, respond to events
- **Real-time processing** - Immediate reaction to data changes
- **Dependent workflows** - Agent B waits for Agent A's output

### Hybrid Pattern (Powerful!):

Combine timers with context filtering to create **periodic processors that analyze accumulated data**:

```python
# Runs every 5 minutes, but ONLY sees ERROR-level logs
error_analyzer = (
    flock.agent("error_analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)
```

---

## Quick Start

### Simple Periodic Execution

```python
from datetime import timedelta
from flock import Flock

flock = Flock("openai/gpt-4.1")

# Execute every 30 seconds
health_monitor = (
    flock.agent("health_monitor")
    .description("Monitors system health")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)

# Agent implementation receives empty input
async def check_health(ctx: AgentContext) -> HealthStatus:
    # ctx.artifacts = []  (no input artifact)
    # ctx.trigger_type = "timer"
    # ctx.timer_iteration = 0, 1, 2, ...

    import psutil
    return HealthStatus(
        cpu_percent=psutil.cpu_percent(),
        memory_percent=psutil.virtual_memory().percent,
        timestamp=datetime.now()
    )
```

**Key Points:**
- Timer-triggered agents receive **empty input** (`ctx.artifacts = []`)
- Access blackboard context via `ctx.get_artifacts(Type)`
- Timer metadata available via `ctx.timer_iteration`, `ctx.fire_time`
- Timers start automatically when orchestrator starts

---

## Scheduling Modes

### 1. Interval-Based (Periodic)

Execute at regular intervals:

```python
# Every 10 seconds
agent.schedule(every=timedelta(seconds=10))

# Every 5 minutes
agent.schedule(every=timedelta(minutes=5))

# Every hour
agent.schedule(every=timedelta(hours=1))

# Every day
agent.schedule(every=timedelta(days=1))
```

**Use Cases:**
- System health monitoring (every 30s)
- Log aggregation (every 5 min)
- Batch processing (every hour)
- Daily backups (every day)

### 2. Time-Based (Daily Execution)

Execute daily at a specific time:

```python
from datetime import time

# Every day at 5 PM
daily_report = (
    flock.agent("daily_report")
    .schedule(at=time(hour=17, minute=0))
    .publishes(DailyReport)
)

# Every day at midnight
cleanup = (
    flock.agent("cleanup")
    .schedule(at=time(hour=0, minute=0))
    .publishes(CleanupResult)
)
```

**Use Cases:**
- End-of-day reports (5 PM)
- Nightly cleanup (2 AM)
- Morning data refresh (6 AM)

### 3. DateTime-Based (One-Time Execution)

Execute once at a specific datetime:

```python
from datetime import datetime

# Execute once on November 1, 2025 at 9 AM
reminder = (
    flock.agent("meeting_reminder")
    .schedule(at=datetime(2025, 11, 1, 9, 0))
    .publishes(Reminder)
)

# Execute once in 1 hour
delayed_task = (
    flock.agent("delayed")
    .schedule(at=datetime.now() + timedelta(hours=1))
    .publishes(Result)
)
```

**Use Cases:**
- Future reminders
- Delayed notifications
- Scheduled one-time tasks

### 4. Cron (UTC, 5-field)

Run on a cron schedule in UTC. Supported syntax: `*`, lists (`,`), ranges (`-`), and steps (`/`). Sunday may be `0` or `7`.

```python
# Every 5 minutes (UTC)
agent.schedule(cron="*/5 * * * *")

# Every day at 17:00 UTC
agent.schedule(cron="0 17 * * *")

# Weekdays at 9,11,13,15,17 UTC
agent.schedule(cron="0 9-17/2 * * 1-5")
```

Notes:
- Cron expressions are evaluated in UTC.
- Day-of-month and day-of-week follow standard cron OR logic (if both are set, matches when either matches).

### 5. With Initial Delay

Add a delay before the first execution:

```python
# Wait 60 seconds before starting, then every 5 minutes
warmup_agent = (
    flock.agent("warmup")
    .schedule(
        every=timedelta(minutes=5),
        after=timedelta(seconds=60)
    )
    .publishes(WarmupResult)
)
```

**Use Cases:**
- Wait for system warmup
- Stagger multiple timers
- Delayed start after initialization

### 6. With Repeat Limit

Limit the number of executions:

```python
# Execute exactly 10 times, then stop
limited_agent = (
    flock.agent("reminder")
    .schedule(
        every=timedelta(hours=1),
        max_repeats=10
    )
    .publishes(Reminder)
)
```

**Use Cases:**
- Limited reminder series
- Trial period monitoring
- Temporary scheduled tasks

---

## Context Filtering with Timers

This is where timer scheduling becomes **incredibly powerful**. Use `.consumes()` to filter what the timer agent sees on the blackboard.

### Key Insight: Dual Purpose of `.consumes()`

With artifact-triggered agents:
- `.consumes()` defines **what triggers** the agent

With timer-triggered agents:
- `.consumes()` defines **what context** the agent sees (filtering, not triggering)

### Filter by Artifact Type

```python
# Runs every 5 minutes, ONLY sees LogEntry artifacts
log_analyzer = (
    flock.agent("log_analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry)  # Context filter
    .publishes(LogReport)
)

# In agent:
async def analyze(ctx: AgentContext) -> LogReport:
    logs = ctx.get_artifacts(LogEntry)  # Only LogEntry, no other types
    return LogReport(log_count=len(logs))
```

### Filter by Predicate

```python
# Runs every 5 minutes, ONLY sees ERROR-level logs
error_analyzer = (
    flock.agent("error_analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)

# In agent:
async def analyze(ctx: AgentContext) -> ErrorReport:
    errors = ctx.get_artifacts(LogEntry)  # ONLY ERROR logs
    return ErrorReport(
        error_count=len(errors),
        errors=errors
    )
```

### Filter by Tags

```python
# Runs hourly, ONLY sees artifacts tagged "critical"
critical_monitor = (
    flock.agent("critical_monitor")
    .schedule(every=timedelta(hours=1))
    .consumes(Metric, Alert, tags={"critical"})
    .publishes(CriticalReport)
)

# In agent:
async def monitor(ctx: AgentContext) -> CriticalReport:
    metrics = ctx.get_artifacts(Metric)  # Only critical metrics
    alerts = ctx.get_artifacts(Alert)    # Only critical alerts
    return CriticalReport(metrics=metrics, alerts=alerts)
```

### Filter by Source Agent

```python
# Runs every 10 minutes, ONLY sees data from specific agents
processor = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=10))
    .consumes(DataPoint, from_agents=["collector_a", "collector_b"])
    .publishes(ProcessedData)
)
```

### Filter by Semantic Match

```python
# Runs every 5 minutes, ONLY sees billing-related tickets
billing_handler = (
    flock.agent("billing_handler")
    .schedule(every=timedelta(minutes=5))
    .consumes(Ticket, semantic_match="billing payment refund")
    .publishes(BillingResponse)
)
```

### Multiple Type Filters

```python
# See both Metrics AND Alerts (filtered by same tag)
aggregator = (
    flock.agent("aggregator")
    .schedule(every=timedelta(hours=1))
    .consumes(Metric, Alert, tags={"critical"})
    .publishes(AggregatedReport)
)

# In agent:
async def aggregate(ctx: AgentContext) -> AggregatedReport:
    metrics = ctx.get_artifacts(Metric)  # Critical metrics
    alerts = ctx.get_artifacts(Alert)    # Critical alerts
    # Both filtered by "critical" tag
```

---

## Timer Metadata Access

Timer-triggered agents have access to special metadata in their context:

### Context Properties

```python
async def my_agent(ctx: AgentContext) -> Result:
    # Check if timer-triggered
    if ctx.trigger_type == "timer":
        print("Timer-triggered!")

    # Get iteration count (0-indexed)
    iteration = ctx.timer_iteration  # 0, 1, 2, 3, ...

    # Get fire time
    fire_time = ctx.fire_time  # datetime when timer fired

    # Input is always empty for timer triggers (internal TimerTick is hidden)
    assert ctx.artifacts == []

    # Access blackboard context (filtered by .consumes())
    logs = ctx.get_artifacts(LogEntry)

    return Result(
        iteration=iteration,
        processed_at=fire_time,
        log_count=len(logs)
    )
```

### Available Properties

| Property | Type | Description |
|----------|------|-------------|
| `ctx.trigger_type` | `str` | `"timer"` for timer-triggered, `"artifact"` for normal |
| `ctx.timer_iteration` | `int \| None` | Iteration count (0-indexed), `None` if not timer |
| `ctx.fire_time` | `datetime \| None` | When timer fired, `None` if not timer |
| `ctx.artifacts` | `list` | Always `[]` for timer triggers |

---

## Best Practices

### 1. Use Descriptive Agent Names

```python
# Good: Clear purpose
health_monitor = flock.agent("health_monitor").schedule(...)
daily_report = flock.agent("daily_report").schedule(...)

# Bad: Generic names
agent1 = flock.agent("agent1").schedule(...)
timer = flock.agent("timer").schedule(...)
```

### 2. Add Clear Descriptions

```python
agent = (
    flock.agent("error_analyzer")
    .description("Analyzes ERROR-level logs every 5 minutes")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)
```

### 3. Choose Appropriate Intervals

```python
# Too frequent: Wastes resources
agent.schedule(every=timedelta(seconds=1))  # Usually overkill

# Good: Balances freshness and cost
agent.schedule(every=timedelta(seconds=30))  # Health checks
agent.schedule(every=timedelta(minutes=5))   # Log analysis
agent.schedule(every=timedelta(hours=1))     # Aggregation
```

### 4. Use Context Filtering

```python
# Good: Filter to reduce context size and cost
agent = (
    flock.agent("analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(Report)
)

# Bad: Process all artifacts (expensive, slow)
agent = (
    flock.agent("analyzer")
    .schedule(every=timedelta(minutes=5))
    .publishes(Report)
)
# Agent sees ALL artifacts on blackboard!
```

### 5. Stagger Multiple Timers

```python
# Good: Stagger to avoid resource spikes
agent1.schedule(every=timedelta(minutes=5), after=timedelta(seconds=0))
agent2.schedule(every=timedelta(minutes=5), after=timedelta(seconds=60))
agent3.schedule(every=timedelta(minutes=5), after=timedelta(seconds=120))

# Bad: All fire simultaneously
agent1.schedule(every=timedelta(minutes=5))
agent2.schedule(every=timedelta(minutes=5))
agent3.schedule(every=timedelta(minutes=5))
```

### 6. Use `.publishes()` - Always Define Output

```python
# Good: Clear output type
agent = (
    flock.agent("health")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)

# Bad: No output type (validation error)
agent = (
    flock.agent("health")
    .schedule(every=timedelta(seconds=30))
)
# Raises: "Scheduled agents must have .publishes()"
```

### 7. Use `serve()` for Long-Running Orchestrators

```python
# Good: For orchestrators with timers
await flock.serve()  # Runs until interrupted

# Bad: run_until_idle() never completes with timers
await flock.run_until_idle()  # Blocks forever!
```

---

## Common Pitfalls

### 1. Timer + Batch = Error

```python
# WRONG: Cannot combine .schedule() with .batch()
agent = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=5))
    .consumes(Order, batch=BatchSpec(size=100))  # ERROR!
    .publishes(Report)
)
# Raises: "Cannot combine .schedule() with .batch() - mutually exclusive"
```

**Why?** Timers and batching are different trigger mechanisms. Use one or the other.

### 2. Timers Don't Persist Across Restarts

```python
# First run:  iteration = 0, 1, 2, 3
# [Restart orchestrator]
# Second run: iteration = 0, 1, 2, 3  (not 4, 5, 6...)
```

**Solution:** If you need persistent state, use external storage (database, file system).

### 3. Slow Agents Can Queue Up

**Problem:** Timer fires every 10 seconds, but agent takes 15 seconds to execute.

**Result:** Executions queue up (T=0, T=10, T=20 all pending).

**Solution:** Use `max_concurrency` to prevent queue buildup:

```python
agent = (
    flock.agent("slow_agent")
    .schedule(every=timedelta(seconds=10))
    .max_concurrency(1)  # Only 1 execution at a time
    .publishes(Result)
)
```

### 4. Timer Precision ±1 Second

**Reality:** Timers use `asyncio.sleep()`, which has ~1 second resolution.

**Impact:** Timer may drift slightly over time due to:
- Agent execution time
- System load
- Python GIL contention

**Solution:** For high-precision timing, use dedicated scheduler components.

### 5. Context Providers Apply to Timers

Timer-triggered agents respect global and per-agent context providers:

### 6. Datetime Without max_repeats Is One-Time

When you schedule with a specific `datetime` and do not provide `max_repeats`, the timer fires once and stops automatically.

```python
# Global filter: Only urgent items
urgent_provider = FilteredContextProvider(FilterConfig(tags={"urgent"}))
flock = Flock("openai/gpt-4.1", context_provider=urgent_provider)

# Timer agent ONLY sees urgent artifacts
agent = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=5))
    .publishes(Report)
)
# ctx.get_artifacts() returns ONLY urgent-tagged artifacts
```

---

## Execution Semantics

### Timer-Triggered vs Artifact-Triggered

| Property | Artifact-Triggered | Timer-Triggered |
|----------|-------------------|-----------------|
| **Trigger** | Artifact published matching `.consumes()` | Timer fires based on `.schedule()` |
| **Input** | `ctx.artifacts = [TriggerArtifact]` | `ctx.artifacts = []` |
| **Context** | All blackboard artifacts | All blackboard artifacts |
| **Filtering** | `.consumes()` filters TRIGGERS | `.consumes()` filters CONTEXT |
| **Metadata** | `ctx.trigger_type = "artifact"` | `ctx.trigger_type = "timer"` |
| **Special Props** | N/A | `ctx.timer_iteration`, `ctx.fire_time` |

### Timer Lifecycle

```
1. Orchestrator Startup
   ↓
2. TimerComponent.on_initialize()
   - Create background task per scheduled agent
   ↓
3. Timer Loop (per agent)
   - Wait for initial delay (if configured)
   - Loop:
     - Wait for next fire time
     - Publish TimerTick artifact (internal)
     - Increment iteration counter
     - Check max_repeats limit
   ↓
4. Subscription Matching
   - Agent auto-subscribed to own TimerTicks
   - Filter: tick.timer_name == agent.name
   ↓
5. Agent Execution
   - ctx.artifacts presented as []
   - ctx.timer_iteration = N
   - ctx.trigger_type = "timer"
   ↓
6. Output Publishing
   - Outputs cascade normally to other agents
   ↓
7. Orchestrator Shutdown
   - TimerComponent.on_shutdown()
   - Cancel all timer tasks
   - Wait for graceful completion
```

---

## Advanced Patterns

### Pattern 1: Periodic Batch Processing

Process accumulated data at regular intervals:

```python
# Continuous data collection (from external source)
for data_point in stream:
    await flock.publish(DataPoint(value=data_point))

# Periodic aggregation
batch_processor = (
    flock.agent("batch_processor")
    .description("Process sensor data every 10 minutes")
    .schedule(every=timedelta(minutes=10))
    .consumes(DataPoint)
    .publishes(AggregatedData)
)

# Implementation
async def process_batch(ctx: AgentContext) -> list[AggregatedData]:
    data_points = ctx.get_artifacts(DataPoint)

    # Group by sensor_id
    by_sensor = defaultdict(list)
    for point in data_points:
        by_sensor[point.sensor_id].append(point)

    # Aggregate each sensor
    return [
        AggregatedData(
            sensor_id=sensor_id,
            avg_value=mean(p.value for p in points),
            count=len(points)
        )
        for sensor_id, points in by_sensor.items()
    ]
```

### Pattern 2: Time-Window Analysis

Analyze data within specific time windows:

```python
# Daily report analyzes last 24 hours
daily_report = (
    flock.agent("daily_report")
    .description("Generate end-of-day financial report")
    .schedule(at=time(hour=17, minute=0))  # 5 PM daily
    .consumes(Transaction)
    .publishes(DailyReport)
)

async def generate_report(ctx: AgentContext) -> DailyReport:
    transactions = ctx.get_artifacts(Transaction)
    today = datetime.now().date()

    # Filter to today's transactions
    today_txns = [
        t for t in transactions
        if t.timestamp.date() == today
    ]

    return DailyReport(
        date=today,
        total_transactions=len(today_txns),
        total_revenue=sum(t.amount for t in today_txns)
    )
```

### Pattern 3: Multi-Stage Timer Pipeline

Chain timer-triggered agents:

```python
# Stage 1: Collect metrics every 30s
collector = (
    flock.agent("collector")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthMetric)
)

# Stage 2: Alert on high usage (reactive, not scheduled)
monitor = (
    flock.agent("monitor")
    .consumes(HealthMetric, where=lambda m: m.cpu > 80)
    .publishes(HealthAlert)
)

# Stage 3: Daily summary at midnight
summarizer = (
    flock.agent("summarizer")
    .schedule(at=time(hour=0, minute=0))
    .consumes(HealthMetric, HealthAlert)
    .publishes(DailyHealthSummary)
)
```

### Pattern 4: Conditional Timer Logic

Use timer metadata to implement conditional behavior:

```python
async def periodic_cleanup(ctx: AgentContext) -> CleanupResult:
    # Every 10th iteration, do full cleanup
    if ctx.timer_iteration % 10 == 0:
        return await full_cleanup()
    else:
        return await quick_cleanup()
```

### Pattern 5: Dynamic Filtering Based on Time

```python
async def time_based_analysis(ctx: AgentContext) -> Report:
    current_hour = datetime.now().hour

    # Different filters based on time of day
    if current_hour < 6:  # Night (12 AM - 6 AM)
        logs = ctx.get_artifacts(LogEntry, where=lambda l: l.level == "ERROR")
    elif current_hour < 18:  # Day (6 AM - 6 PM)
        logs = ctx.get_artifacts(LogEntry, where=lambda l: l.level in ["WARN", "ERROR"])
    else:  # Evening (6 PM - 12 AM)
        logs = ctx.get_artifacts(LogEntry)  # All logs

    return Report(logs=logs)
```

---

## Comparison with Other Patterns

### vs. Batching

```python
# Batching: Wait for N artifacts, then process
batch_agent = (
    flock.agent("batch")
    .consumes(Order, batch=BatchSpec(size=100, timeout=timedelta(minutes=5)))
    .publishes(Report)
)
# Triggers when: 100 Orders collected OR 5 minutes elapsed

# Timer: Process every N time units
timer_agent = (
    flock.agent("timer")
    .schedule(every=timedelta(minutes=5))
    .consumes(Order)
    .publishes(Report)
)
# Triggers every: 5 minutes (regardless of Order count)
```

**Use Batching When:** You want to process a specific number of items
**Use Timers When:** You want to process on a schedule

### vs. Join Operations

```python
# Join: Wait for correlated artifacts, then process
join_agent = (
    flock.agent("join")
    .consumes(
        UserProfile, OrderHistory,
        join=JoinSpec(
            on=lambda u, o: u.user_id == o.user_id,
            timeout=timedelta(seconds=30)
        )
    )
    .publishes(Recommendation)
)
# Triggers when: UserProfile + OrderHistory match on user_id

# Timer: Periodic processing with context
timer_agent = (
    flock.agent("timer")
    .schedule(every=timedelta(minutes=5))
    .consumes(UserProfile, OrderHistory)
    .publishes(Report)
)
# Triggers every: 5 minutes, sees all UserProfiles and OrderHistories
```

**Use Joins When:** You need to correlate related artifacts
**Use Timers When:** You want periodic aggregation

---

## Troubleshooting

### Timer Not Firing

**Problem:** Agent never executes.

**Check:**
1. Is orchestrator running? (`await flock.serve()`)
2. Is schedule valid? (check validation errors)
3. Is timer name unique? (agent names must be unique)

### Agent Executes Too Frequently

**Problem:** Agent running more often than expected.

**Check:**
1. Verify `every=` interval is correct
2. Check for multiple timer definitions
3. Ensure no duplicate agents with same name

### Context is Empty

**Problem:** `ctx.get_artifacts()` returns empty list.

**Check:**
1. Are artifacts actually on the blackboard?
2. Is context provider filtering them out?
3. Is `.consumes()` filter too restrictive?

### run_until_idle() Never Completes

**Problem:** `await flock.run_until_idle()` hangs.

**Cause:** Timers keep orchestrator busy indefinitely.

**Solution:** Use `await flock.serve()` instead for long-running orchestrators.

---

## API Reference

### `.schedule()` Method

```python
def schedule(
    self,
    every: timedelta | None = None,
    at: time | datetime | None = None,
    after: timedelta | None = None,
    max_repeats: int | None = None,
) -> "AgentBuilder":
    """Schedule periodic agent execution.

    Args:
        every: Execute at regular intervals
        at: Execute at specific time (daily if `time`, once if `datetime`)
        after: Initial delay before first execution
        max_repeats: Maximum executions (None = infinite)

    Returns:
        AgentBuilder for method chaining
    """
```

### Validation Rules

1. **Exactly one trigger type:** Must specify `every=` OR `at=` (not both, not neither)
2. **Mutually exclusive:** Cannot combine `.schedule()` with `.batch()`
3. **Output required:** Must have `.publishes()` type
4. **Positive values:** `after` and `max_repeats` must be positive
5. **Unique names:** Timer names (agent names) must be unique

---

## Next Steps

- **Tutorial:** See [Scheduled Agents Tutorial](../tutorials/scheduled-agents.md) for step-by-step examples
- **Examples:** Check `examples/09-scheduling/` for working code
- **Design:** Read `.flock/schedule/DESIGN.md` for implementation details
- **AGENTS.md:** Quick reference for `.schedule()` API

---

**Timer scheduling is available in Flock v0.6.0 and later.**
