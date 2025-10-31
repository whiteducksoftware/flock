---
title: Building Scheduled Agents - Step-by-Step Tutorial
description: Learn timer-based scheduling through hands-on examples from simple monitors to multi-agent workflows
tags:
  - tutorial
  - scheduling
  - timers
  - beginner
  - intermediate
---

# Building Scheduled Agents Tutorial

This tutorial teaches timer-based agent scheduling through **four progressive examples**. Each tutorial builds on concepts from the previous one.

**What you'll build:**
1. **Simple health monitor** - Basic periodic execution
2. **Error log analyzer** - Timer + context filtering
3. **Daily report generator** - Time-based scheduling
4. **Multi-agent monitoring system** - Complex timer workflows

**Prerequisites:**
- Flock v0.6.0 or later
- Python 3.12+
- OpenAI API key

**Time:** ~30 minutes total

> Notes
> - Cron schedules are supported (UTC, 5 fields: `*`, lists, ranges, steps; Sunday 0 or 7).
> - Datetime without `max_repeats` is implicitly one-time.

---

## Tutorial 1: Simple Periodic Health Monitor

**Goal:** Create an agent that checks system health every 30 seconds.

**Concepts:** Periodic execution, timer metadata, empty input

### Step 1: Define the Artifact Types

```python
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from flock import Flock
from flock.core.artifacts import flock_type

@flock_type
class HealthStatus(BaseModel):
    """System health snapshot."""
    cpu_percent: float = Field(description="CPU usage percentage")
    memory_percent: float = Field(description="Memory usage percentage")
    disk_percent: float = Field(description="Disk usage percentage")
    timestamp: datetime = Field(default_factory=datetime.now)
```

**Why these fields?**
- Simple, measurable metrics
- Clear structure for LLM to generate
- Timestamp for tracking

### Step 2: Create the Flock Instance

```python
flock = Flock("openai/gpt-4.1")
```

### Step 3: Define the Scheduled Agent

```python
health_monitor = (
    flock.agent("health_monitor")
    .description("Monitors system health every 30 seconds")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)
```

**What's happening:**
- `.schedule(every=timedelta(seconds=30))` - Execute every 30 seconds
- No `.consumes()` - Agent doesn't wait for artifacts
- `.publishes(HealthStatus)` - Always required for scheduled agents

### Step 4: Implement the Agent Logic

```python
async def check_health(ctx: AgentContext) -> HealthStatus:
    """Check system health metrics."""
    import psutil

    # Timer metadata available
    print(f"Health check iteration #{ctx.timer_iteration}")
    print(f"Triggered at: {ctx.fire_time}")
    print(f"Trigger type: {ctx.trigger_type}")  # "timer"

    # Input is always empty for timer triggers
    assert ctx.artifacts == []

    # Collect metrics
    return HealthStatus(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage('/').percent,
        timestamp=datetime.now()
    )
```

**Key points:**
- `ctx.artifacts == []` - No input artifact
- `ctx.timer_iteration` - Iteration counter (0, 1, 2, ...)
- `ctx.fire_time` - When timer fired
- `ctx.trigger_type == "timer"` - Identifies timer trigger

### Step 5: Run the Orchestrator

```python
# Start the orchestrator
await flock.serve()
```

**Output:**
```
Health check iteration #0
Triggered at: 2025-10-31 10:00:00
Trigger type: timer

Health check iteration #1
Triggered at: 2025-10-31 10:00:30
Trigger type: timer

Health check iteration #2
Triggered at: 2025-10-31 10:01:00
Trigger type: timer
...
```

### Complete Code

```python
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from flock import Flock
from flock.core.artifacts import flock_type
from flock.core.agent import AgentContext

@flock_type
class HealthStatus(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    timestamp: datetime = Field(default_factory=datetime.now)

async def main():
    flock = Flock("openai/gpt-4.1")

    health_monitor = (
        flock.agent("health_monitor")
        .description("Monitors system health every 30 seconds")
        .schedule(every=timedelta(seconds=30))
        .publishes(HealthStatus)
    )

    # Optional: Subscribe to health status updates
    async def on_health_update(status: HealthStatus):
        print(f"CPU: {status.cpu_percent}%, Memory: {status.memory_percent}%")

    flock.subscribe(HealthStatus, on_health_update)

    await flock.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### What You Learned

- Timer-triggered agents receive **empty input** (`ctx.artifacts = []`)
- Access timer metadata via `ctx.timer_iteration`, `ctx.fire_time`
- Use `timedelta()` to specify intervals
- Use `await flock.serve()` for long-running orchestrators with timers

---

## Tutorial 2: Error Log Analyzer with Context Filtering

**Goal:** Create an agent that runs every 5 minutes and analyzes ONLY error logs.

**Concepts:** Timer + context filtering, predicates, batch processing

### Step 1: Define Artifact Types

```python
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from flock import Flock
from flock.core.artifacts import flock_type

@flock_type
class LogEntry(BaseModel):
    """Application log entry."""
    level: str = Field(description="Log level: DEBUG, INFO, WARN, ERROR")
    message: str = Field(description="Log message")
    source: str = Field(description="Source module/service")
    timestamp: datetime = Field(default_factory=datetime.now)

@flock_type
class ErrorReport(BaseModel):
    """Analysis of error logs."""
    error_count: int
    errors: list[LogEntry]
    analysis: str = Field(description="AI-generated analysis of errors")
    patterns: list[str] = Field(description="Common error patterns identified")
    timestamp: datetime = Field(default_factory=datetime.now)
```

### Step 2: Simulate Log Production

In a real system, logs would come from external sources. For this tutorial, we'll simulate:

```python
import asyncio
import random

async def log_producer(flock: Flock):
    """Simulate continuous log production."""
    sources = ["api", "database", "cache", "auth"]
    levels = ["DEBUG", "INFO", "WARN", "ERROR"]
    messages = {
        "DEBUG": ["Query executed", "Cache hit", "Request received"],
        "INFO": ["User logged in", "Data saved", "Task completed"],
        "WARN": ["Slow query detected", "Cache miss", "Retry attempt"],
        "ERROR": ["Database timeout", "Connection failed", "Invalid input"]
    }

    while True:
        level = random.choices(levels, weights=[40, 40, 15, 5])[0]
        message = random.choice(messages[level])
        source = random.choice(sources)

        await flock.publish(
            LogEntry(level=level, message=message, source=source),
            tags={level.lower()}
        )

        await asyncio.sleep(random.uniform(0.5, 2.0))
```

### Step 3: Define the Scheduled Analyzer

**KEY INSIGHT:** `.consumes()` acts as a **context filter** for timer-triggered agents, not a trigger.

```python
error_analyzer = (
    flock.agent("error_analyzer")
    .description("Analyzes ERROR-level logs every 5 minutes")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)
```

**What's happening:**
- `.schedule(every=timedelta(minutes=5))` - Run every 5 minutes
- `.consumes(LogEntry, where=...)` - **Filter** context to ERROR logs only
- Agent doesn't wait for LogEntry - the timer triggers it
- When triggered, agent sees ONLY ERROR logs via `ctx.get_artifacts(LogEntry)`

### Step 4: Implement the Analyzer

```python
async def analyze_errors(ctx: AgentContext) -> ErrorReport:
    """Analyze accumulated error logs."""
    # Timer metadata
    print(f"Error analysis iteration #{ctx.timer_iteration}")

    # Get ONLY ERROR-level logs (filtered by .consumes())
    errors = ctx.get_artifacts(LogEntry)

    print(f"Found {len(errors)} error logs to analyze")

    if not errors:
        return ErrorReport(
            error_count=0,
            errors=[],
            analysis="No errors detected in this period",
            patterns=[]
        )

    # Group errors by source
    by_source = {}
    for error in errors:
        if error.source not in by_source:
            by_source[error.source] = []
        by_source[error.source].append(error)

    # Identify patterns
    patterns = [
        f"{source}: {len(logs)} errors"
        for source, logs in by_source.items()
    ]

    # Generate AI analysis (this is where LLM does the work)
    analysis = f"""
    Analyzed {len(errors)} error logs from the last 5 minutes.
    Most errors from: {max(by_source, key=lambda k: len(by_source[k]))}
    Common pattern: {errors[0].message if errors else 'N/A'}
    """

    return ErrorReport(
        error_count=len(errors),
        errors=errors,
        analysis=analysis.strip(),
        patterns=patterns
    )
```

### Step 5: Run the Complete System

```python
async def main():
    flock = Flock("openai/gpt-4.1")

    # Define analyzer
    error_analyzer = (
        flock.agent("error_analyzer")
        .description("Analyzes ERROR-level logs every 5 minutes")
        .schedule(every=timedelta(minutes=5))
        .consumes(LogEntry, where=lambda log: log.level == "ERROR")
        .publishes(ErrorReport)
    )

    # Subscribe to reports
    async def on_report(report: ErrorReport):
        print("\n" + "="*50)
        print(f"ERROR REPORT - {report.timestamp}")
        print("="*50)
        print(f"Error count: {report.error_count}")
        print(f"Analysis: {report.analysis}")
        print(f"Patterns: {', '.join(report.patterns)}")
        print("="*50 + "\n")

    flock.subscribe(ErrorReport, on_report)

    # Start log producer in background
    asyncio.create_task(log_producer(flock))

    # Start orchestrator
    await flock.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Expected Output

```
Publishing log: INFO - User logged in (source: api)
Publishing log: DEBUG - Query executed (source: database)
Publishing log: ERROR - Database timeout (source: database)
Publishing log: WARN - Slow query detected (source: api)
Publishing log: ERROR - Connection failed (source: cache)
...

Error analysis iteration #0
Found 3 error logs to analyze

==================================================
ERROR REPORT - 2025-10-31 10:05:00
==================================================
Error count: 3
Analysis: Analyzed 3 error logs from the last 5 minutes.
Most errors from: database
Common pattern: Database timeout
Patterns: database: 2 errors, cache: 1 errors
==================================================

...

Error analysis iteration #1
Found 5 error logs to analyze

==================================================
ERROR REPORT - 2025-10-31 10:10:00
==================================================
Error count: 5
Analysis: Analyzed 5 error logs from the last 5 minutes.
Most errors from: database
Common pattern: Database timeout
Patterns: database: 3 errors, cache: 1 errors, api: 1 errors
==================================================
```

### What You Learned

- `.consumes()` with timers acts as a **context filter**, not a trigger
- `ctx.get_artifacts(Type)` returns filtered artifacts based on `.consumes()`
- Timers enable **batch processing** of accumulated data
- Combine predicates (`where=`) with timers for powerful filtering

---

## Tutorial 3: Daily Report Generator

**Goal:** Create an agent that generates a financial report every day at 5 PM.

**Concepts:** Time-based scheduling, time window filtering, daily aggregation

### Step 1: Define Artifact Types

```python
from datetime import datetime, timedelta, time, date
from pydantic import BaseModel, Field
from flock import Flock
from flock.core.artifacts import flock_type

@flock_type
class Transaction(BaseModel):
    """Financial transaction."""
    transaction_id: str
    amount: float
    user_id: str
    category: str
    timestamp: datetime = Field(default_factory=datetime.now)

@flock_type
class DailyReport(BaseModel):
    """End-of-day financial report."""
    date: date
    total_transactions: int
    total_revenue: float
    avg_transaction: float
    top_category: str
    top_user: str
    summary: str
    timestamp: datetime = Field(default_factory=datetime.now)
```

### Step 2: Simulate Transaction Stream

```python
import asyncio
import random
import uuid

async def transaction_producer(flock: Flock):
    """Simulate continuous transaction stream."""
    categories = ["food", "transport", "entertainment", "shopping", "utilities"]
    user_ids = [f"user_{i}" for i in range(10)]

    while True:
        transaction = Transaction(
            transaction_id=str(uuid.uuid4())[:8],
            amount=round(random.uniform(5.0, 500.0), 2),
            user_id=random.choice(user_ids),
            category=random.choice(categories)
        )

        await flock.publish(transaction, tags={"financial"})
        print(f"Transaction: {transaction.user_id} - ${transaction.amount:.2f} ({transaction.category})")

        await asyncio.sleep(random.uniform(1.0, 5.0))
```

### Step 3: Define the Daily Report Agent

```python
daily_report = (
    flock.agent("daily_report")
    .description("Generate end-of-day financial report at 5 PM")
    .schedule(at=time(hour=17, minute=0))  # Daily at 5 PM
    .consumes(Transaction)
    .publishes(DailyReport)
)
```

**Key difference:** `.schedule(at=time(...))` instead of `every=timedelta(...)`

### Step 4: Implement Report Generation

```python
from collections import Counter

async def generate_daily_report(ctx: AgentContext) -> DailyReport:
    """Generate end-of-day financial report."""
    print(f"\nGenerating daily report (day #{ctx.timer_iteration})")
    print(f"Report time: {ctx.fire_time}")

    # Get all transactions
    all_transactions = ctx.get_artifacts(Transaction)
    today = datetime.now().date()

    # Filter to today's transactions
    today_txns = [
        t for t in all_transactions
        if t.timestamp.date() == today
    ]

    print(f"Analyzing {len(today_txns)} transactions from {today}")

    if not today_txns:
        return DailyReport(
            date=today,
            total_transactions=0,
            total_revenue=0.0,
            avg_transaction=0.0,
            top_category="N/A",
            top_user="N/A",
            summary="No transactions today"
        )

    # Calculate metrics
    total_revenue = sum(t.amount for t in today_txns)
    avg_transaction = total_revenue / len(today_txns)

    # Find top category
    category_counts = Counter(t.category for t in today_txns)
    top_category = category_counts.most_common(1)[0][0]

    # Find top user
    user_totals = {}
    for t in today_txns:
        user_totals[t.user_id] = user_totals.get(t.user_id, 0) + t.amount
    top_user = max(user_totals, key=user_totals.get)

    # Generate summary (LLM does this)
    summary = f"""
    Daily financial summary for {today}:
    - {len(today_txns)} transactions processed
    - Total revenue: ${total_revenue:.2f}
    - Average transaction: ${avg_transaction:.2f}
    - Most popular category: {top_category}
    - Top spending user: {top_user} (${user_totals[top_user]:.2f})
    """

    return DailyReport(
        date=today,
        total_transactions=len(today_txns),
        total_revenue=round(total_revenue, 2),
        avg_transaction=round(avg_transaction, 2),
        top_category=top_category,
        top_user=top_user,
        summary=summary.strip()
    )
```

### Step 5: Run the System

For testing, you'll want to test with a shorter interval instead of waiting until 5 PM:

```python
async def main():
    flock = Flock("openai/gpt-4.1")

    # FOR TESTING: Use short interval instead of daily schedule
    daily_report = (
        flock.agent("daily_report")
        .description("Generate financial report")
        .schedule(every=timedelta(minutes=1))  # Every minute for testing
        # .schedule(at=time(hour=17, minute=0))  # Use this in production
        .consumes(Transaction)
        .publishes(DailyReport)
    )

    # Subscribe to reports
    async def on_report(report: DailyReport):
        print("\n" + "="*60)
        print(f"DAILY FINANCIAL REPORT - {report.date}")
        print("="*60)
        print(report.summary)
        print("="*60 + "\n")

    flock.subscribe(DailyReport, on_report)

    # Start transaction producer
    asyncio.create_task(transaction_producer(flock))

    # Start orchestrator
    await flock.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Expected Output

```
Transaction: user_3 - $45.67 (food)
Transaction: user_1 - $123.45 (entertainment)
Transaction: user_7 - $89.12 (transport)
...

Generating daily report (day #0)
Report time: 2025-10-31 10:00:00
Analyzing 23 transactions from 2025-10-31

============================================================
DAILY FINANCIAL REPORT - 2025-10-31
============================================================
Daily financial summary for 2025-10-31:
- 23 transactions processed
- Total revenue: $2,456.78
- Average transaction: $106.82
- Most popular category: food
- Top spending user: user_3 ($456.89)
============================================================

...

Generating daily report (day #1)
Report time: 2025-10-31 10:01:00
Analyzing 28 transactions from 2025-10-31
...
```

### Production Configuration

```python
# For production, use actual daily schedule
daily_report = (
    flock.agent("daily_report")
    .description("Generate end-of-day financial report at 5 PM")
    .schedule(at=time(hour=17, minute=0))  # Daily at 5 PM
    .consumes(Transaction)
    .publishes(DailyReport)
)
```

### What You Learned

- Use `.schedule(at=time(...))` for daily execution at specific times
- Filter artifacts by time window in agent logic
- Aggregate data over time periods (daily, hourly, etc.)
- Test with shorter intervals, deploy with production schedules

---

## Tutorial 4: Multi-Agent Monitoring System

**Goal:** Build a complete monitoring system with multiple timer-triggered and reactive agents.

**Concepts:** Multi-agent workflows, timer cascades, hybrid patterns

### Step 1: Define All Artifact Types

```python
from datetime import datetime, timedelta, time, date
from pydantic import BaseModel, Field
from flock import Flock
from flock.core.artifacts import flock_type

@flock_type
class HealthMetric(BaseModel):
    """System health snapshot."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    timestamp: datetime = Field(default_factory=datetime.now)

@flock_type
class HealthAlert(BaseModel):
    """Alert for unhealthy metrics."""
    severity: str = Field(description="critical, warning, info")
    message: str
    metric: HealthMetric
    timestamp: datetime = Field(default_factory=datetime.now)

@flock_type
class DailyHealthSummary(BaseModel):
    """Daily health report."""
    date: date
    avg_cpu: float
    avg_memory: float
    avg_disk: float
    alert_count: int
    critical_alerts: int
    summary: str
    timestamp: datetime = Field(default_factory=datetime.now)
```

### Step 2: Define Agent 1 - Metric Collector (Timer)

Collects metrics every 30 seconds:

```python
health_collector = (
    flock.agent("health_collector")
    .description("Collect system health metrics every 30 seconds")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthMetric)
)

async def collect_metrics(ctx: AgentContext) -> HealthMetric:
    """Collect current system metrics."""
    import psutil

    metric = HealthMetric(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage('/').percent
    )

    print(f"Collected metrics (iteration #{ctx.timer_iteration}): "
          f"CPU={metric.cpu_percent}%, MEM={metric.memory_percent}%")

    return metric
```

### Step 3: Define Agent 2 - Health Monitor (Reactive)

Reacts to high resource usage (NOT timer-based):

```python
health_monitor = (
    flock.agent("health_monitor")
    .description("Alert on high resource usage")
    .consumes(
        HealthMetric,
        where=lambda m: m.cpu_percent > 80 or m.memory_percent > 80
    )
    .publishes(HealthAlert)
)

async def monitor_health(ctx: AgentContext) -> HealthAlert:
    """Generate alerts for unhealthy metrics."""
    metric = ctx.artifacts[0]  # The triggering metric

    # Determine severity
    if metric.cpu_percent > 90 or metric.memory_percent > 90:
        severity = "critical"
        message = f"CRITICAL: Resources critically high!"
    elif metric.cpu_percent > 80 or metric.memory_percent > 80:
        severity = "warning"
        message = f"WARNING: Resources elevated"
    else:
        severity = "info"
        message = "Resource usage normal"

    print(f"Alert: {severity} - {message}")

    return HealthAlert(
        severity=severity,
        message=message,
        metric=metric
    )
```

**Key difference:** This agent is **artifact-triggered**, not timer-triggered!

### Step 4: Define Agent 3 - Daily Summarizer (Timer)

Generates daily summary at midnight:

```python
daily_summarizer = (
    flock.agent("daily_summarizer")
    .description("Generate daily health summary at midnight")
    .schedule(at=time(hour=0, minute=0))  # Daily at midnight
    .consumes(HealthMetric, HealthAlert)
    .publishes(DailyHealthSummary)
)

async def summarize_daily_health(ctx: AgentContext) -> DailyHealthSummary:
    """Generate end-of-day health summary."""
    today = datetime.now().date()

    # Get all metrics from today
    all_metrics = ctx.get_artifacts(HealthMetric)
    today_metrics = [
        m for m in all_metrics
        if m.timestamp.date() == today
    ]

    # Get all alerts from today
    all_alerts = ctx.get_artifacts(HealthAlert)
    today_alerts = [
        a for a in all_alerts
        if a.timestamp.date() == today
    ]

    print(f"\nDaily summary (day #{ctx.timer_iteration})")
    print(f"Metrics: {len(today_metrics)}, Alerts: {len(today_alerts)}")

    if not today_metrics:
        return DailyHealthSummary(
            date=today,
            avg_cpu=0.0,
            avg_memory=0.0,
            avg_disk=0.0,
            alert_count=0,
            critical_alerts=0,
            summary="No metrics collected today"
        )

    # Calculate averages
    avg_cpu = sum(m.cpu_percent for m in today_metrics) / len(today_metrics)
    avg_memory = sum(m.memory_percent for m in today_metrics) / len(today_metrics)
    avg_disk = sum(m.disk_percent for m in today_metrics) / len(today_metrics)

    # Count critical alerts
    critical_alerts = len([a for a in today_alerts if a.severity == "critical"])

    # Generate summary
    summary = f"""
    Daily health summary for {today}:
    - {len(today_metrics)} health checks performed
    - Average CPU: {avg_cpu:.1f}%
    - Average Memory: {avg_memory:.1f}%
    - Average Disk: {avg_disk:.1f}%
    - {len(today_alerts)} alerts generated ({critical_alerts} critical)
    """

    return DailyHealthSummary(
        date=today,
        avg_cpu=round(avg_cpu, 2),
        avg_memory=round(avg_memory, 2),
        avg_disk=round(avg_disk, 2),
        alert_count=len(today_alerts),
        critical_alerts=critical_alerts,
        summary=summary.strip()
    )
```

### Step 5: Assemble the Complete System

```python
async def main():
    flock = Flock("openai/gpt-4.1")

    # Agent 1: Collector (timer: every 30s)
    health_collector = (
        flock.agent("health_collector")
        .description("Collect system health metrics")
        .schedule(every=timedelta(seconds=30))
        .publishes(HealthMetric)
    )

    # Agent 2: Monitor (reactive: high usage)
    health_monitor = (
        flock.agent("health_monitor")
        .description("Alert on high resource usage")
        .consumes(
            HealthMetric,
            where=lambda m: m.cpu_percent > 80 or m.memory_percent > 80
        )
        .publishes(HealthAlert)
    )

    # Agent 3: Summarizer (timer: daily at midnight)
    # FOR TESTING: Use 2 minutes instead of midnight
    daily_summarizer = (
        flock.agent("daily_summarizer")
        .description("Generate daily health summary")
        .schedule(every=timedelta(minutes=2))  # Test mode
        # .schedule(at=time(hour=0, minute=0))  # Production mode
        .consumes(HealthMetric, HealthAlert)
        .publishes(DailyHealthSummary)
    )

    # Subscribe to alerts
    async def on_alert(alert: HealthAlert):
        emoji = "🔴" if alert.severity == "critical" else "🟡"
        print(f"\n{emoji} ALERT: {alert.message}")

    flock.subscribe(HealthAlert, on_alert)

    # Subscribe to daily summaries
    async def on_summary(summary: DailyHealthSummary):
        print("\n" + "="*70)
        print(f"DAILY HEALTH SUMMARY - {summary.date}")
        print("="*70)
        print(summary.summary)
        print("="*70 + "\n")

    flock.subscribe(DailyHealthSummary, on_summary)

    # Start orchestrator
    print("Starting multi-agent monitoring system...")
    print("- health_collector: Running every 30s")
    print("- health_monitor: Reactive (high usage alerts)")
    print("- daily_summarizer: Running every 2 minutes (test mode)")
    print()

    await flock.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Expected Output

```
Starting multi-agent monitoring system...
- health_collector: Running every 30s
- health_monitor: Reactive (high usage alerts)
- daily_summarizer: Running every 2 minutes (test mode)

Collected metrics (iteration #0): CPU=45.2%, MEM=62.1%
Collected metrics (iteration #1): CPU=87.5%, MEM=71.3%

🟡 ALERT: WARNING: Resources elevated

Collected metrics (iteration #2): CPU=92.1%, MEM=88.7%

🔴 ALERT: CRITICAL: Resources critically high!

Collected metrics (iteration #3): CPU=52.3%, MEM=65.4%

Daily summary (day #0)
Metrics: 4, Alerts: 2

======================================================================
DAILY HEALTH SUMMARY - 2025-10-31
======================================================================
Daily health summary for 2025-10-31:
- 4 health checks performed
- Average CPU: 69.3%
- Average Memory: 71.9%
- Average Disk: 45.2%
- 2 alerts generated (1 critical)
======================================================================

Collected metrics (iteration #4): CPU=48.9%, MEM=69.2%
...
```

### Workflow Diagram

```
Time: 0s
  health_collector (timer) → HealthMetric
                             ↓
                          (no trigger - CPU/MEM normal)

Time: 30s
  health_collector (timer) → HealthMetric (CPU > 80%)
                             ↓
                          health_monitor (reactive) → HealthAlert

Time: 60s
  health_collector (timer) → HealthMetric
                             ↓
                          (no trigger - CPU/MEM normal)

Time: 90s
  health_collector (timer) → HealthMetric (MEM > 80%)
                             ↓
                          health_monitor (reactive) → HealthAlert

Time: 120s (2 min)
  daily_summarizer (timer) → DailyHealthSummary
    (reads all HealthMetrics and HealthAlerts from blackboard)
```

### What You Learned

- **Mix timer and reactive agents** for complex workflows
- **Timer cascades**: Timer agents publish → Reactive agents trigger → More processing
- **Periodic aggregation**: Timer agents read accumulated data
- **Multiple scheduling patterns** in one system (every 30s, every 2 min, daily)
- **Context filtering** works across all agent types

---

## Common Patterns Recap

### Pattern 1: Simple Periodic Task

```python
agent = (
    flock.agent("name")
    .schedule(every=timedelta(seconds=30))
    .publishes(Result)
)
```

**Use for:** Health checks, monitoring, polling

### Pattern 2: Timer + Context Filter

```python
agent = (
    flock.agent("name")
    .schedule(every=timedelta(minutes=5))
    .consumes(Log, where=lambda l: l.level == "ERROR")
    .publishes(Report)
)
```

**Use for:** Periodic analysis of filtered data

### Pattern 3: Daily Scheduled Task

```python
agent = (
    flock.agent("name")
    .schedule(at=time(hour=17, minute=0))
    .consumes(Transaction)
    .publishes(DailyReport)
)
```

**Use for:** End-of-day reports, nightly cleanup

### Pattern 4: Timer → Reactive Chain

```python
# Timer agent publishes
collector = flock.agent("collector").schedule(every=...).publishes(Metric)

# Reactive agent consumes
monitor = flock.agent("monitor").consumes(Metric, where=...).publishes(Alert)
```

**Use for:** Continuous monitoring with conditional alerts

### Pattern 5: Multi-Type Aggregation

```python
agent = (
    flock.agent("name")
    .schedule(every=timedelta(hours=1))
    .consumes(Metric, Alert, Log, tags={"critical"})
    .publishes(AggregatedReport)
)
```

**Use for:** Periodic cross-type analysis

---

## Next Steps

### Explore More

- **Scheduling Guide:** [docs/guides/scheduling.md](../guides/scheduling.md) - Complete API reference
- **Context Providers:** [docs/guides/context-providers.md](../guides/context-providers.md) - Advanced filtering
- **Batch Processing:** [docs/guides/batch-processing.md](../guides/batch-processing.md) - Alternative to timers

### Try These Exercises

1. **Exercise:** Add an initial delay to the health collector (wait 10 seconds before first execution)
2. **Exercise:** Modify the error analyzer to group errors by source module
3. **Exercise:** Create a weekly report agent that runs every Monday at 9 AM
4. **Exercise:** Build a cleanup agent that deletes old metrics (older than 7 days)

### Build Your Own

Apply timer scheduling to your use cases:
- **DevOps:** Log aggregation, metric collection, alert fatigue reduction
- **Finance:** Transaction summaries, reconciliation reports, fraud detection
- **Healthcare:** Patient monitoring, appointment reminders, daily check-ins
- **E-commerce:** Inventory checks, price updates, abandoned cart reminders

---

**Timer scheduling is available in Flock v0.6.0 and later.**
