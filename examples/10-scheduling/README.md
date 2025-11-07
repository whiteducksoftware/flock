# Timer Scheduling Examples

Welcome to the Flock timer scheduling examples! This directory contains 6 production-ready examples demonstrating different timer scheduling patterns introduced in Flock v0.5.30.

## Overview

Timer scheduling allows agents to execute at regular intervals or specific times, independent of artifact triggers. This is perfect for:

- **Periodic monitoring** - Health checks, metric collection, heartbeats
- **Batch processing** - Aggregating accumulated data at intervals
- **Scheduled reports** - Daily summaries, end-of-day reports
- **Time-based actions** - Reminders, scheduled notifications
- **Data analysis** - Periodic log analysis, error monitoring

## Core Concepts

### Timer Triggers vs Artifact Triggers

**Artifact Trigger** (Traditional):
```python
agent.consumes(Order).publishes(Receipt)
# Agent executes when Order artifact is published
# ctx.artifacts = [<the triggering Order>]
```

**Timer Trigger** (New in v0.5.30):
```python
agent.schedule(every=timedelta(minutes=5)).consumes(Order).publishes(Report)
# Agent executes every 5 minutes (timer-triggered)
# ctx.artifacts = []  (no input)
# ctx.get_artifacts(Order) - access ALL Orders on blackboard
```

### Key Differences

| Aspect | Artifact Trigger | Timer Trigger |
|--------|------------------|---------------|
| **Trigger** | New artifact published | Time-based schedule |
| **Input** | `ctx.artifacts` = triggering artifact | `ctx.artifacts` = [] (empty) |
| **Context** | Specific artifact | All matching artifacts via `ctx.get_artifacts()` |
| **Use Case** | React to events | Periodic processing |

### Timer Context Properties

```python
async def my_agent(ctx: AgentContext) -> Result:
    ctx.trigger_type      # "timer" for scheduled agents
    ctx.timer_iteration   # 0, 1, 2, ... (increments each fire)
    ctx.fire_time         # datetime when timer fired
    ctx.artifacts         # [] (always empty for timer triggers)
```

## Examples

### 01. Simple Health Monitor
**Pattern:** Interval Scheduling
**Schedule:** `every=timedelta(seconds=30)`
**Use Case:** Regular system monitoring, periodic health checks

```bash
python 01_simple_health_monitor.py
```

Demonstrates the simplest timer pattern - running at fixed intervals. The health monitor collects CPU, memory, and disk metrics every 30 seconds.

**Key Learnings:**
- Basic `.schedule(every=...)` syntax
- Accessing timer metadata (`timer_iteration`, `fire_time`)
- Timer triggers have no input artifacts

---

### 02. Error Log Analyzer
**Pattern:** Timer + Context Filter
**Schedule:** `every=timedelta(minutes=5)`
**Use Case:** Periodic analysis of specific artifact subsets

```bash
python 02_error_log_analyzer.py
```

Shows how to combine timer scheduling with context filtering. Two agents run:
- `log_collector`: Publishes logs every 10 seconds (all levels)
- `error_analyzer`: Runs every 5 minutes, sees ONLY ERROR logs

**Key Learnings:**
- Using `.consumes(Type, where=...)` with timers
- Context filtering on blackboard
- Multiple scheduled agents in one system

---

### 03. Daily Report Generator
**Pattern:** Time-Based Scheduling (Daily)
**Schedule:** `at=time(hour=17, minute=0)` (5 PM daily)
**Use Case:** Daily reports, end-of-day summaries, scheduled notifications

```bash
python 03_daily_report_generator.py
```

Demonstrates time-based scheduling for daily execution at a specific time. Generates end-of-day financial reports every day at 5 PM.

**Key Learnings:**
- Using `.schedule(at=time(...))` for daily execution
- Aggregating accumulated data
- Real-world reporting pattern

**Note:** Demo mode uses 2-minute intervals. Set `DEMO_MODE = False` for actual 5 PM schedule.

---

### 04. Batch Data Processor
**Pattern:** Batch Aggregation
**Schedule:** `every=timedelta(minutes=10)`
**Use Case:** IoT data processing, metric aggregation, time-window analytics

```bash
python 04_batch_data_processor.py
```

Shows batch processing of accumulated sensor data. Sensors publish data every 5 seconds, and the processor aggregates data every 10 minutes, calculating statistics by sensor.

**Key Learnings:**
- Batch processing pattern with timers
- Grouping and aggregating data
- Calculating statistics over time windows
- Real-world IoT use case

**Note:** Demo mode uses 1-minute intervals. Set `DEMO_MODE = False` for 10-minute intervals.

---

### 05. One-Time Reminder
**Pattern:** DateTime-Based One-Time Scheduling
**Schedule:** `at=datetime(2025, 11, 1, 8, 55)`
**Use Case:** Reminders, scheduled notifications, future actions

```bash
python 05_one_time_reminder.py
```

Demonstrates one-time execution at a specific datetime. Perfect for reminders, scheduled notifications, or future task execution.

**Key Learnings:**
- Using `.schedule(at=datetime(...))` for one-time execution
- `max_repeats=1` is implicit for datetime scheduling
- `timer_iteration` is always 0 for one-time execution
- Scheduling future actions

**Note:** Demo mode schedules 30 seconds ahead. Set `DEMO_MODE = False` for actual datetime scheduling.

---

### 06. Cron Schedule Demo
**Pattern:** Cron-Based Scheduling (UTC)
**Schedule:** `cron="*/1 * * * *"` (every minute UTC)
**Use Case:** Cron-style scheduling, UTC timezone support, periodic tasks

```bash
python 06_cron_demo.py
```

Demonstrates cron expression scheduling for precise time-based execution. The agent fires every minute on UTC boundaries, perfect for scheduled tasks that need exact timing.

**Key Learnings:**
- Using `.schedule(cron="...")` for cron expressions
- UTC timezone interpretation
- Using `.calls(...)` for side effects after publishing
- Cron expression syntax (minute hour day month weekday)

**Cron Examples:**
- `"*/5 * * * *"` - Every 5 minutes
- `"0 9 * * 1-5"` - Weekdays at 9 AM UTC
- `"0 0 1 * *"` - First day of month at midnight UTC

**Note:** Cron expressions are always interpreted in UTC. For local time scheduling, use `.schedule(at=time(...))` instead.

---

## Configuration: CLI vs Dashboard Mode

**All examples support two modes** via the `USE_DASHBOARD` flag:

```python
# At the top of each file:
USE_DASHBOARD = False  # CLI mode
USE_DASHBOARD = True   # Dashboard mode
```

### CLI Mode (Default)
- **Best for:** Learning, quick testing, integration
- **Output:** Terminal output with results
- **Speed:** Instant execution
- **Demo:** Runs for limited time to show pattern

### Dashboard Mode
- **Best for:** Visualization, debugging, understanding flow
- **Output:** Web UI at `http://localhost:8344`
- **Speed:** Runs until interrupted
- **Visualization:** See timers firing, agents executing, artifacts flowing

## Quick Start

### 1. Run Your First Example

```bash
# Start with the simplest pattern
python 01_simple_health_monitor.py

# Watch it run for 2 minutes, collecting metrics every 30 seconds
```

### 2. Try Context Filtering

```bash
# See timer + context filter in action
python 02_error_log_analyzer.py

# Observe how analyzer only sees ERROR logs
```

### 3. Enable Dashboard Visualization

```bash
# Edit any example file:
USE_DASHBOARD = True

# Run with dashboard
python 03_daily_report_generator.py

# Open browser to http://localhost:8344
# Watch timers fire and data flow in real-time
```

## Scheduling Modes Reference

### 1. Interval-Based (Periodic)
```python
.schedule(every=timedelta(seconds=30))   # Every 30 seconds
.schedule(every=timedelta(minutes=5))    # Every 5 minutes
.schedule(every=timedelta(hours=1))      # Every hour
.schedule(every=timedelta(days=1))       # Every day
```

### 2. Time-Based (Daily)
```python
.schedule(at=time(hour=17, minute=0))    # Daily at 5:00 PM
.schedule(at=time(hour=0, minute=0))     # Daily at midnight
.schedule(at=time(hour=9, minute=30))    # Daily at 9:30 AM
```

### 3. DateTime-Based (One-Time)
```python
.schedule(at=datetime(2025, 11, 1, 9, 0))        # Specific datetime
.schedule(at=datetime.now() + timedelta(hours=1)) # 1 hour from now
```

### 4. Cron-Based (UTC)
```python
# Every minute (UTC)
.schedule(cron="*/1 * * * *")

# Every 5 minutes (UTC)
.schedule(cron="*/5 * * * *")

# Every day at 17:00 UTC
.schedule(cron="0 17 * * *")

# Weekdays at 9,11,13,15,17 UTC
.schedule(cron="0 9-17/2 * * 1-5")
```

### 4. With Options
```python
# Initial delay before first execution
.schedule(every=timedelta(minutes=5), after=timedelta(seconds=60))

# Limit number of executions
.schedule(every=timedelta(hours=1), max_repeats=10)
```

## Common Patterns

### Pattern 1: Regular Monitoring
```python
# Check health every 30 seconds
health_monitor = (
    flock.agent("health_monitor")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)
```

### Pattern 2: Filtered Analysis
```python
# Analyze only ERROR logs every 5 minutes
error_analyzer = (
    flock.agent("error_analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)
```

### Pattern 3: Daily Reports
```python
# Generate report every day at 5 PM
daily_report = (
    flock.agent("daily_report")
    .schedule(at=time(hour=17, minute=0))
    .consumes(Transaction)
    .publishes(DailyReport)
)
```

### Pattern 4: Batch Processing
```python
# Process accumulated data every 10 minutes
batch_processor = (
    flock.agent("batch_processor")
    .schedule(every=timedelta(minutes=10))
    .consumes(DataPoint)
    .publishes(AggregatedData)
)
```

### Pattern 5: One-Time Execution
```python
# Send reminder at specific time
reminder = (
    flock.agent("reminder")
    .schedule(at=datetime(2025, 11, 1, 8, 55))
    .publishes(Reminder)
)
```

## Important Notes

### Timer Triggers vs Artifact Triggers

**Timer triggers work differently:**
- `ctx.artifacts` is always `[]` (empty)
- Use `ctx.get_artifacts(Type)` to access blackboard
- Context filters (`.consumes()`) filter blackboard, not input

**Cannot combine with batch triggers:**
```python
# ❌ ERROR: Cannot combine timer and batch
agent.schedule(every=...).consumes(Order, batch=BatchSpec(...))
```

### Running With Timers

**Use `serve()`, not `run_until_idle()`:**
```python
# ❌ WRONG: run_until_idle() blocks forever with timers
await flock.run_until_idle()

# ✅ CORRECT: Use serve() for long-running orchestrators
await flock.serve()
```

### Timer State

**Timers don't persist across restarts:**
- Iteration counters reset to 0 on restart
- Use external storage for continuity if needed

## Learning Path

**Recommended order:**

1. **01_simple_health_monitor.py** - Understand basic timer pattern
2. **02_error_log_analyzer.py** - Learn context filtering
3. **04_batch_data_processor.py** - See batch aggregation in action
4. **03_daily_report_generator.py** - Master time-based scheduling
5. **05_one_time_reminder.py** - Explore one-time execution
6. **06_cron_demo.py** - Learn cron expression scheduling

## Tips

### Demo Mode vs Production Mode

Most examples have a `DEMO_MODE` flag for faster demonstration:

```python
DEMO_MODE = True   # Shorter intervals for demo (e.g., 2 minutes)
DEMO_MODE = False  # Production intervals (e.g., 5 PM daily)
```

### Customizing Examples

Feel free to modify:
- **Intervals:** Change `timedelta(...)` values
- **Times:** Adjust `time(hour=..., minute=...)`
- **Logic:** Modify agent implementations
- **Artifacts:** Add new fields or types

### Debugging

Enable tracing for detailed execution logs:
```bash
FLOCK_AUTO_TRACE=true python 01_simple_health_monitor.py
```

## Next Steps

After mastering these examples:

- **Advanced patterns:** Check `../02-patterns/` for specialized patterns
- **MCP integration:** See `../01-getting-started/05_mcp_and_tools.py`
- **Batch processing:** Review `../01-getting-started/14_ecommerce_batch_processing.py`
- **Production deployment:** Explore `../04-misc/` for production examples

## Documentation

For complete timer scheduling documentation:
- **[Timer Scheduling Guide](../../docs/guides/scheduling.md)** - Complete scheduling reference
- **[Scheduled Agents Tutorial](../../docs/tutorials/scheduled-agents.md)** - Step-by-step examples
- **AGENTS.md** - Timer scheduling section in main guide

## Troubleshooting

### Agent Not Executing

- Check that orchestrator is running with `serve()`, not `run_until_idle()`
- Verify timer schedule is in the future (for datetime-based)
- Enable tracing: `FLOCK_AUTO_TRACE=true`

### Dashboard Not Showing Timers

- Ensure `USE_DASHBOARD = True` in the example
- Wait for timer interval to elapse
- Check browser console for WebSocket connection

### Examples Run Too Long

- All CLI examples have time limits (2-6 minutes)
- Press Ctrl+C to stop early
- Adjust `await asyncio.sleep(...)` duration

---

**Happy Scheduling!** 🎯⏰

For questions or issues, refer to the main Flock documentation or the API examples in `.flock/schedule/API_EXAMPLES.md`.
