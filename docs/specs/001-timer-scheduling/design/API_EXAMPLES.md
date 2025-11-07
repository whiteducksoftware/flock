# Timer-Based Scheduling - API Examples

**Quick reference for the timer scheduling API**

---

## 🎯 **Basic Usage**

### **Simple Periodic Execution**

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

# Agent implementation
async def check_health(ctx: AgentContext) -> HealthStatus:
    # ctx.artifacts = []  ← No input artifact
    # ctx.trigger_type = "timer"
    # ctx.timer_iteration = 0, 1, 2, ...

    return HealthStatus(
        cpu_percent=get_cpu_usage(),
        timestamp=datetime.now()
    )
```

---

## ⏰ **Scheduling Modes**

### **1. Interval-Based (Periodic)**

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

### **2. Time-Based (Daily)**

```python
from datetime import time

# Every day at 5 PM
agent.schedule(at=time(hour=17, minute=0))

# Every day at midnight
agent.schedule(at=time(hour=0, minute=0))

# Every day at 2:30 AM
agent.schedule(at=time(hour=2, minute=30))
```

### **3. DateTime-Based (One-Time)**

```python
from datetime import datetime

# Execute once at specific datetime
agent.schedule(at=datetime(2025, 11, 1, 9, 0))

# Execute once in 1 hour
agent.schedule(at=datetime.now() + timedelta(hours=1))
```

### **4. With Initial Delay**

```python
# Wait 60 seconds before first execution
agent.schedule(
    every=timedelta(minutes=5),
    after=timedelta(seconds=60)
)
```

### **5. With Repeat Limit**

```python
# Execute only 10 times then stop
agent.schedule(
    every=timedelta(hours=1),
    max_repeats=10
)

# One-time execution (max_repeats=1 is implicit for datetime)
agent.schedule(at=datetime(2025, 11, 1, 9, 0))
```

---

## 🎯 **Timer + Context Filtering**

### **Filter by Artifact Type**

```python
# Runs every 5 minutes
# ONLY sees LogEntry artifacts (no other types)
agent = (
    flock.agent("log_analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry)  # Context filter: only LogEntry
    .publishes(LogReport)
)

# In agent:
async def analyze(ctx: AgentContext) -> LogReport:
    logs = ctx.get_artifacts(LogEntry)  # All LogEntry on blackboard
    return LogReport(log_count=len(logs))
```

### **Filter by Predicate**

```python
# Runs every 5 minutes
# ONLY sees ERROR-level logs
error_analyzer = (
    flock.agent("error_analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)

# In agent:
async def analyze(ctx: AgentContext) -> ErrorReport:
    errors = ctx.get_artifacts(LogEntry)  # ONLY ERROR logs
    return ErrorReport(error_count=len(errors))
```

### **Filter by Tags**

```python
# Runs hourly
# ONLY sees artifacts tagged "critical"
agent = (
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

### **Filter by Source Agent**

```python
# Runs every 10 minutes
# ONLY sees artifacts from "data_collector" agent
agent = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=10))
    .consumes(DataPoint, from_agents=["data_collector"])
    .publishes(ProcessedData)
)
```

### **Filter by Semantic Match**

```python
# Runs every 5 minutes
# ONLY sees tickets semantically matching "billing issue"
agent = (
    flock.agent("billing_handler")
    .schedule(every=timedelta(minutes=5))
    .consumes(Ticket, semantic_match="billing payment refund issue")
    .publishes(BillingResponse)
)
```

---

## 🔍 **Accessing Timer Metadata**

### **In Agent Context**

```python
async def my_agent(ctx: AgentContext) -> Result:
    # Check trigger type
    if ctx.trigger_type == "timer":
        print("Timer-triggered!")

    # Get iteration count
    iteration = ctx.timer_iteration  # 0, 1, 2, ...

    # Get fire time
    fire_time = ctx.fire_time  # datetime when timer fired

    # Input is empty for timer triggers
    assert ctx.artifacts == []

    # Access blackboard context
    all_metrics = ctx.get_artifacts(Metric)

    return Result(...)
```

---

## 🎨 **Real-World Examples**

### **Example 1: Health Monitor**

```python
from datetime import timedelta
from pydantic import BaseModel
from flock.core.artifacts import flock_type

@flock_type
class HealthStatus(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    timestamp: datetime

# Check health every 30 seconds
health_monitor = (
    flock.agent("health_monitor")
    .description("Monitors system health metrics")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)
```

### **Example 2: Error Log Analyzer**

```python
@flock_type
class LogEntry(BaseModel):
    level: str
    message: str
    timestamp: datetime

@flock_type
class ErrorReport(BaseModel):
    error_count: int
    errors: list[LogEntry]
    analysis: str

# Analyze errors every 5 minutes
error_analyzer = (
    flock.agent("error_analyzer")
    .description("Analyzes ERROR logs every 5 minutes")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)
```

### **Example 3: Daily Report Generator**

```python
from datetime import time

@flock_type
class Transaction(BaseModel):
    amount: float
    user_id: str
    timestamp: datetime

@flock_type
class DailyReport(BaseModel):
    date: date
    total_transactions: int
    total_revenue: float

# Generate report every day at 5 PM
daily_report = (
    flock.agent("daily_report")
    .description("Generate end-of-day financial report")
    .schedule(at=time(hour=17, minute=0))
    .consumes(Transaction)
    .publishes(DailyReport)
)
```

### **Example 4: Batch Data Processor**

```python
@flock_type
class DataPoint(BaseModel):
    value: float
    sensor_id: str
    timestamp: datetime

@flock_type
class AggregatedData(BaseModel):
    sensor_id: str
    avg_value: float
    count: int
    period_start: datetime
    period_end: datetime

# Process accumulated data every 10 minutes
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
    by_sensor = {}
    for point in data_points:
        if point.sensor_id not in by_sensor:
            by_sensor[point.sensor_id] = []
        by_sensor[point.sensor_id].append(point)

    # Aggregate each sensor
    results = []
    for sensor_id, points in by_sensor.items():
        results.append(AggregatedData(
            sensor_id=sensor_id,
            avg_value=sum(p.value for p in points) / len(points),
            count=len(points),
            period_start=min(p.timestamp for p in points),
            period_end=max(p.timestamp for p in points)
        ))

    return results
```

### **Example 5: Multi-Type Aggregator**

```python
@flock_type
class Metric(BaseModel):
    name: str
    value: float
    tags: set[str] = set()

@flock_type
class Alert(BaseModel):
    severity: str
    message: str
    tags: set[str] = set()

@flock_type
class AggregatedReport(BaseModel):
    critical_metrics: list[Metric]
    critical_alerts: list[Alert]
    summary: str
    timestamp: datetime

# Aggregate critical items every hour
aggregator = (
    flock.agent("critical_aggregator")
    .description("Hourly aggregation of critical metrics and alerts")
    .schedule(every=timedelta(hours=1))
    .consumes(Metric, Alert, tags={"critical"})
    .publishes(AggregatedReport)
)

# Implementation
async def aggregate(ctx: AgentContext) -> AggregatedReport:
    metrics = ctx.get_artifacts(Metric)
    alerts = ctx.get_artifacts(Alert)

    return AggregatedReport(
        critical_metrics=metrics,
        critical_alerts=alerts,
        summary=f"Hour {ctx.timer_iteration}: {len(metrics)} metrics, {len(alerts)} alerts",
        timestamp=datetime.now()
    )
```

### **Example 6: One-Time Reminder**

```python
from datetime import datetime

@flock_type
class Reminder(BaseModel):
    message: str
    timestamp: datetime

# Execute once at specific time
meeting_reminder = (
    flock.agent("meeting_reminder")
    .description("Send meeting reminder")
    .schedule(at=datetime(2025, 11, 1, 8, 55))  # Nov 1 at 8:55 AM
    .publishes(Reminder)
)

# Implementation
async def send_reminder(ctx: AgentContext) -> Reminder:
    return Reminder(
        message="Team meeting starts in 5 minutes!",
        timestamp=datetime.now()
    )
```

### **Example 7: Cleanup Task**

```python
@flock_type
class StaleRecord(BaseModel):
    record_id: str
    last_accessed: datetime

@flock_type
class CleanupResult(BaseModel):
    deleted_count: int
    freed_space_mb: float

# Run cleanup every day at 2 AM
cleanup_agent = (
    flock.agent("cleanup")
    .description("Clean up stale records daily")
    .schedule(at=time(hour=2, minute=0))
    .consumes(StaleRecord)
    .publishes(CleanupResult)
)

# Implementation
async def cleanup(ctx: AgentContext) -> CleanupResult:
    stale = ctx.get_artifacts(StaleRecord)

    # Filter records older than 30 days
    cutoff = datetime.now() - timedelta(days=30)
    to_delete = [r for r in stale if r.last_accessed < cutoff]

    # Perform cleanup (delete from database, etc.)
    deleted_count = len(to_delete)
    freed_space_mb = deleted_count * 0.5  # Estimate

    return CleanupResult(
        deleted_count=deleted_count,
        freed_space_mb=freed_space_mb
    )
```

---

## ❌ **What NOT to Do**

### **Don't Combine .schedule() with .batch()**

```python
# ❌ WRONG: Mutually exclusive
agent = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=5))  # Timer trigger
    .consumes(Order, batch=BatchSpec(size=100))  # Artifact trigger
    .publishes(Report)
)
# This will raise ValueError: "Cannot combine .schedule() with .batch()"
```

### **Don't Use run_until_idle() with Timers**

```python
# ❌ WRONG: run_until_idle() will never complete with active timers
await flock.run_until_idle()  # Blocks forever!

# ✅ CORRECT: Use serve() for long-running orchestrators
await flock.serve()  # Runs until interrupted
```

### **Don't Expect Timers to Persist Across Restarts**

```python
# ❌ WRONG: Iteration counter resets on restart
# First run: iteration = 0, 1, 2, 3
# [Restart orchestrator]
# Second run: iteration = 0, 1, 2, 3 (not 4, 5, 6...)

# ✅ Use persistent storage if you need continuity
```

---

## 🎯 **Comparison: Timer vs Normal Trigger**

### **Normal Artifact Trigger**

```python
# Agent triggered when Order artifact published
processor = (
    flock.agent("processor")
    .consumes(Order)
    .publishes(Receipt)
)

# In agent:
async def process(ctx: AgentContext) -> Receipt:
    order = ctx.artifacts[0]  # The triggering Order
    # Process the specific order
    return Receipt(order_id=order.id)
```

### **Timer Trigger**

```python
# Agent triggered every 5 minutes
processor = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=5))
    .consumes(Order)  # Context filter (not trigger!)
    .publishes(Report)
)

# In agent:
async def process(ctx: AgentContext) -> Report:
    orders = ctx.get_artifacts(Order)  # ALL orders on blackboard
    # Process batch of orders
    return Report(processed_count=len(orders))
```

**Key Difference:**
- **Artifact trigger**: Agent receives the specific artifact that triggered it
- **Timer trigger**: Agent receives empty input, accesses blackboard for context

---

## 🚀 **Complete Example: Multi-Agent System**

```python
from datetime import timedelta, time
from flock import Flock
from flock.core.artifacts import flock_type
from pydantic import BaseModel

# Define artifact types
@flock_type
class HealthMetric(BaseModel):
    cpu: float
    memory: float
    timestamp: datetime

@flock_type
class HealthAlert(BaseModel):
    severity: str
    message: str
    metric: HealthMetric

@flock_type
class DailyHealthSummary(BaseModel):
    date: date
    avg_cpu: float
    avg_memory: float
    alert_count: int

# Create orchestrator
flock = Flock("openai/gpt-4.1")

# Agent 1: Collect metrics every 30 seconds
collector = (
    flock.agent("health_collector")
    .description("Collect system health metrics")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthMetric)
)

# Agent 2: Monitor for high usage (reactive, not scheduled)
monitor = (
    flock.agent("health_monitor")
    .description("Alert on high resource usage")
    .consumes(HealthMetric, where=lambda m: m.cpu > 80 or m.memory > 80)
    .publishes(HealthAlert)
)

# Agent 3: Generate daily summary at midnight
summarizer = (
    flock.agent("daily_summarizer")
    .description("Generate daily health summary")
    .schedule(at=time(hour=0, minute=0))
    .consumes(HealthMetric, HealthAlert)
    .publishes(DailyHealthSummary)
)

# Run orchestrator
await flock.serve()
```

**Workflow:**
1. `collector` runs every 30s → publishes `HealthMetric`
2. `monitor` triggers when CPU/memory > 80% → publishes `HealthAlert`
3. `summarizer` runs daily at midnight → aggregates metrics and alerts → publishes `DailyHealthSummary`

---

## 📋 **Quick Reference**

### **Scheduling Modes**

| Mode | Syntax | Behavior |
|------|--------|----------|
| **Periodic** | `schedule(every=timedelta(...))` | Repeats at interval |
| **Daily** | `schedule(at=time(...))` | Repeats daily at time |
| **One-time** | `schedule(at=datetime(...))` | Executes once |

### **Options**

| Option | Purpose | Example |
|--------|---------|---------|
| `after` | Initial delay | `schedule(every=..., after=timedelta(seconds=60))` |
| `max_repeats` | Repeat limit | `schedule(every=..., max_repeats=10)` |

### **Context Properties**

| Property | Type | Description |
|----------|------|-------------|
| `ctx.trigger_type` | `str` | `"timer"` or `"artifact"` |
| `ctx.timer_iteration` | `int \| None` | Iteration count (0-indexed) |
| `ctx.fire_time` | `datetime \| None` | When timer fired |
| `ctx.artifacts` | `list` | Always `[]` for timer triggers |

### **Context Filters**

| Filter | Example |
|--------|---------|
| Type | `.consumes(LogEntry)` |
| Predicate | `.consumes(LogEntry, where=lambda l: l.level == "ERROR")` |
| Tags | `.consumes(Metric, tags={"critical"})` |
| Source | `.consumes(Data, from_agents=["collector"])` |
| Semantic | `.consumes(Ticket, semantic_match="billing issue")` |

---

**Next Steps:** Read `.flock/schedule/DESIGN.md` for complete design details!
