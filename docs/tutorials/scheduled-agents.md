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

This tutorial builds four scheduled systems, each adding one idea:

1. **Health monitor:** an agent that runs every 30 seconds.
2. **Error log analyzer:** a timer agent that sees only the artifacts it needs.
3. **Daily report:** a daily schedule, and custom code instead of an LLM.
4. **Monitoring system:** timer agents and reactive agents working together.

**Prerequisites:** Flock installed, `OPENAI_API_KEY` set, and the basics from [Getting Started](../getting-started/quick-start.md).

**Time:** about 30 minutes.

The finished versions of systems 1–3 are in [`examples/10-scheduling/`](https://github.com/whiteducksoftware/flock/tree/main/examples/10-scheduling).

---

## Tutorial 1: Health Monitor

**Goal:** publish a `HealthStatus` every 30 seconds.

### Step 1: Define the output type

```python
from datetime import datetime

from pydantic import BaseModel, Field

from flock import Flock, flock_type


@flock_type
class HealthStatus(BaseModel):
    cpu_percent: float = Field(description="CPU usage percentage (0-100)")
    memory_percent: float = Field(description="Memory usage percentage (0-100)")
    disk_percent: float = Field(description="Disk usage percentage (0-100)")
    status: str = Field(description="healthy, warning or critical")
    timestamp: datetime
```

The field descriptions go into the prompt, so they double as instructions for the LLM.

### Step 2: Schedule the agent

```python
from datetime import timedelta

flock = Flock("openai/gpt-4.1")

health_monitor = (
    flock.agent("health_monitor")
    .description(
        "Generate realistic CPU, memory and disk usage percentages. Set status to "
        "'healthy' if all are under 80, 'warning' if any is 80-90, 'critical' above 90."
    )
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)
```

There is no `.consumes()`: the timer is the trigger. On each tick Flock publishes a `TimerTick` that only this agent receives, and the agent runs its engine, here the default LLM engine, which turns the description into a `HealthStatus`.

`.publishes()` is required for scheduled agents.

### Step 3: Run it

```python
import asyncio


async def main():
    # Runs for 2 minutes, then stops the timer
    await flock.run_until_idle(timeout=120)
    for status in await flock.store.get_by_type(HealthStatus):
        print(f"{status.timestamp:%H:%M:%S}  cpu {status.cpu_percent:5.1f}%  {status.status}")


asyncio.run(main())
```

An interval timer fires immediately and then every 30 seconds, so two minutes give you four or five statuses.

`run_until_idle()` waits while timers are running, so without `timeout` it would not return. For a service, use `await flock.serve(dashboard=True)` instead; timers then run until the server stops.

### What you learned

- `.schedule(every=...)` replaces `.consumes()` as the trigger.
- Scheduled agents must declare `.publishes()`.
- `run_until_idle(timeout=...)` for scripts, `serve()` for services.

---

## Tutorial 2: Error Log Analyzer

**Goal:** a collector publishes log entries of all levels; every two minutes an analyzer reports on the ERROR entries only.

### Step 1: Define the types

```python
@flock_type
class LogEntry(BaseModel):
    level: str = Field(description="DEBUG, INFO, WARNING or ERROR")
    message: str
    source: str = Field(description="api_server, database or auth_service")
    timestamp: datetime


@flock_type
class ErrorReport(BaseModel):
    error_count: int
    error_messages: list[str]
    analysis: str = Field(description="Patterns in the errors and suggested fixes")
```

### Step 2: A timer that produces data

```python
log_collector = (
    flock.agent("log_collector")
    .description("Publish one realistic log entry; about one in four is an ERROR.")
    .schedule(every=timedelta(seconds=30))
    .publishes(LogEntry)
)
```

### Step 3: Decide what the analyzer sees

On a timer run, an agent's context is the whole blackboard by default: every log entry, but also its own earlier reports and the timer ticks. A **context provider** decides what it sees instead. This one returns only ERROR entries:

```python
from flock.core.artifacts import Artifact
from flock.core.context_provider import BaseContextProvider, ContextRequest
from flock.core.store import FilterConfig
from flock.registry import type_registry


class ErrorLogs(BaseContextProvider):
    """Only ERROR-level log entries."""

    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        logs, _ = await request.store.query_artifacts(
            FilterConfig(type_names={type_registry.name_for(LogEntry)}), limit=-1
        )
        return [log for log in logs if log.payload.get("level") == "ERROR"]
```

`BaseContextProvider` still applies visibility to whatever `get_artifacts` returns.

### Step 4: The analyzer

```python
error_analyzer = (
    flock.agent("error_analyzer")
    .description("Count the ERROR logs, list their messages and suggest fixes.")
    .schedule(every=timedelta(minutes=2))
    .with_context(ErrorLogs())
    .publishes(ErrorReport)
)
```

!!! warning "`.consumes()` is not a context filter"
    `.consumes(LogEntry, where=lambda log: log.level == "ERROR")` on this agent would not filter its context. It would add a second trigger: the analyzer would then also run on every ERROR entry. Use `.with_context(...)` to choose what a timer agent sees.

### Step 5: Run both timers

```python
async def main():
    await flock.run_until_idle(timeout=360)  # 6 minutes: ~12 log entries, 3-4 reports
    for report in await flock.store.get_by_type(ErrorReport):
        print(report.error_count, report.error_messages)


asyncio.run(main())
```

Each report counts all ERROR entries published so far, because the context is the blackboard, not only what is new since the last run.

### What you learned

- A timer agent's context is the blackboard; `.with_context(provider)` narrows it.
- A custom provider can filter on payload content.
- `.consumes()` adds triggers, it does not filter.

---

## Tutorial 3: Daily Report with Custom Logic

**Goal:** at 17:00 UTC every day, compute the day's transaction totals with plain Python instead of an LLM.

### Step 1: Types

```python
@flock_type
class Transaction(BaseModel):
    amount: float
    category: str
    status: str = Field(description="completed or failed")


@flock_type
class DailyReport(BaseModel):
    total_transactions: int
    total_revenue: float
    failed_count: int
    top_category: str
    run: int
```

### Step 2: Only today's transactions

A daily report should see today's transactions, not every transaction ever published. Every artifact carries a `created_at` timestamp (UTC), and `FilterConfig(start=...)` selects on it. Because the window moves every day, it is computed in a small provider on each run:

```python
from datetime import UTC


class Today(BaseContextProvider):
    """Artifacts of the given types published since 00:00 UTC today."""

    def __init__(self, *types: type[BaseModel]):
        self.type_names = {type_registry.name_for(t) for t in types}

    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        artifacts, _ = await request.store.query_artifacts(
            FilterConfig(type_names=self.type_names, start=midnight), limit=-1
        )
        return artifacts
```

`limit=-1` returns all matches. Without it, store queries return the oldest 50.

For fixed filters on type, tags or producer, the built-in `FilteredContextProvider(FilterConfig(...), limit=-1)` needs no code.

### Step 3: A custom engine

An engine is the part of an agent that produces its output. Instead of the LLM engine, this one computes the report. It reads the context from `ctx.artifacts` and the timer data from `ctx.timer_iteration`:

```python
from collections import Counter

from flock.components.agent import EngineComponent
from flock.utils.runtime import EvalResult


class DailyReportEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        transactions = [Transaction(**artifact.payload) for artifact in ctx.artifacts]
        completed = [t for t in transactions if t.status == "completed"]
        categories = Counter(t.category for t in transactions)
        report = DailyReport(
            total_transactions=len(transactions),
            total_revenue=sum(t.amount for t in completed),
            failed_count=len(transactions) - len(completed),
            top_category=categories.most_common(1)[0][0] if categories else "none",
            run=ctx.timer_iteration,
        )
        return EvalResult.from_object(report, agent=agent)
```

On a timer run, `inputs.artifacts` holds the `TimerTick`, `ctx.trigger_type` is `"timer"`, and `ctx.fire_time` is the tick's time in UTC.

### Step 4: Schedule it daily

```python
from datetime import time

daily_reporter = (
    flock.agent("daily_reporter")
    .schedule(at=time(hour=17, minute=0))  # 17:00 UTC, every day
    .with_context(Today(Transaction))
    .with_engines(DailyReportEngine())
    .publishes(DailyReport)
)
```

`at=time(...)` is always UTC. To try it without waiting, swap in `every=timedelta(seconds=10)` and publish a few transactions first:

```python
async def main():
    for amount, category, status in [(42.0, "food", "completed"), (19.5, "travel", "failed")]:
        await flock.publish(Transaction(amount=amount, category=category, status=status))
    await flock.run_until_idle(timeout=15)
    print(await flock.store.get_by_type(DailyReport))
```

### What you learned

- `at=time(...)` runs daily in UTC; `at=datetime(...)` runs once.
- A provider can compute its filter on each run, for example today's artifacts via `FilterConfig(start=...)`.
- `FilteredContextProvider` covers fixed type, tag and producer filters; pass `limit=-1` to get more than 50 artifacts.
- A custom engine reads `ctx.artifacts` and `ctx.timer_iteration` and returns an `EvalResult`.

---

## Tutorial 4: Monitoring System

**Goal:** combine timers with reactive agents.

```
collector (every 10 s) ──Metric──▶ alerter (reacts when value > 90) ──Alert──▶ blackboard
                                                                                  │
daily_summary (23:55 UTC) ◀──────────── context: today's Alerts ──────────────────┘
```

### Step 1: Types

```python
@flock_type
class Metric(BaseModel):
    name: str = Field(description="cpu, memory or disk")
    value: float = Field(description="Usage in percent (0-100)")
    timestamp: datetime


@flock_type
class Alert(BaseModel):
    metric_name: str
    value: float
    severity: str = Field(description="warning or critical")
    message: str


@flock_type
class DailySummary(BaseModel):
    alert_count: int
    critical_count: int
    most_affected_metric: str
    summary: str
```

### Step 2: The agents

```python
collector = (
    flock.agent("collector")
    .description(
        "Report one system metric: cpu, memory or disk usage in percent. "
        "Values are usually 20-70, but about one in three readings is above 90."
    )
    .schedule(every=timedelta(seconds=10))
    .publishes(Metric)
)

# Reactive: runs as soon as a high metric appears
alerter = (
    flock.agent("alerter")
    .description("Raise an alert for a high metric: critical above 95, otherwise warning.")
    .consumes(Metric, where=lambda m: m.value > 90)
    .publishes(Alert)
)

# Timer: summarizes the day's alerts
daily_summary = (
    flock.agent("daily_summary")
    .description("Summarize today's alerts: count, critical count and the most affected metric.")
    .schedule(at=time(hour=23, minute=55))
    .with_context(Today(Alert))  # the provider from tutorial 3
    .publishes(DailySummary)
)
```

The timer agent's output is an ordinary artifact, so the alerter subscribes to it like to any other type. The `where=` predicate on a reactive agent decides *when it runs*; the context provider on the summary decides *what it sees*.

### Step 3: Run it

```python
async def main():
    await flock.serve(dashboard=True)


asyncio.run(main())
```

In the dashboard, the collector publishes a `Metric` every 10 seconds, the alerter runs only for values above 90, and at 23:55 UTC the summary reads the alerts. For a quick test, give the summary `every=timedelta(seconds=1), after=timedelta(seconds=60), max_repeats=1`, give the collector `max_repeats=6`, and use `await flock.run_until_idle()`: it returns once both timers are done.

### What you learned

- Timer and reactive agents combine through the blackboard like any other agents.
- `where=` decides when a reactive agent runs; a context provider decides what an agent sees.
- `max_repeats` makes timers finite, so `run_until_idle()` returns on its own.

---

## Patterns Recap

```python
# Periodic task
flock.agent("monitor").schedule(every=timedelta(seconds=30)).publishes(Status)

# Periodic task over selected context
flock.agent("analyzer").schedule(every=timedelta(minutes=5)).with_context(ErrorLogs()).publishes(Report)

# Daily task (UTC)
flock.agent("daily").schedule(at=time(hour=17)).publishes(DailyReport)

# One-time task
flock.agent("reminder").schedule(at=datetime.now(UTC) + timedelta(minutes=10)).publishes(Reminder)

# Cron (UTC), weekdays at 09:00
flock.agent("workdays").schedule(cron="0 9 * * 1-5").publishes(WorkdayReport)

# Timer output feeding a reactive agent
flock.agent("alerter").consumes(Metric, where=lambda m: m.value > 90).publishes(Alert)
```

## Next Steps

- [Timer Scheduling Guide](../guides/scheduling.md): all schedule options, rules and limits
- [Context Providers](../guides/context-providers.md): more ways to shape agent context
- [Custom Engines](custom-engines.md): more about engines
