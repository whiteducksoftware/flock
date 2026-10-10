---
title: Timer-Based Agent Scheduling
description: Schedule agents to run periodically or at specific times without an artifact trigger
tags:
  - scheduling
  - timers
  - guide
  - advanced
search:
  boost: 1.5
---

# Timer-Based Agent Scheduling

A scheduled agent runs on a timer instead of waiting for an artifact. Use it for health checks, periodic reports, aggregation of accumulated data, cleanup jobs and reminders.

A scheduled agent is an ordinary Flock agent: it runs its engine (the LLM-backed `DSPyEngine` by default, or your own engine), reads blackboard context and publishes typed artifacts. Only the trigger is different.

---

## Quick Start

```python
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock, flock_type


@flock_type
class HealthStatus(BaseModel):
    cpu_percent: float = Field(description="CPU usage percentage (0-100)")
    memory_percent: float = Field(description="Memory usage percentage (0-100)")
    status: str = Field(description="healthy, warning or critical")
    timestamp: datetime


flock = Flock("openai/gpt-4.1")

health_monitor = (
    flock.agent("health_monitor")
    .description("Report realistic CPU and memory usage and an overall status.")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)

await flock.serve(dashboard=True)  # timers run until the server stops
```

Every 30 seconds the agent runs and publishes a `HealthStatus`. A scheduled agent must declare `.publishes()`; otherwise the first run fails with `ValueError: Scheduled agent 'health_monitor' must declare .publishes()`.

---

## Schedules

`.schedule()` takes exactly one of `every`, `at` or `cron`, plus the options `after` and `max_repeats`.

| Schedule | Fires | Example |
|---|---|---|
| `every=timedelta(...)` | Immediately, then after each interval | `.schedule(every=timedelta(minutes=5))` |
| `at=time(...)` | Daily at that time, **in UTC** | `.schedule(at=time(hour=17))` |
| `at=datetime(...)` | Once, at that moment | `.schedule(at=datetime(2026, 11, 2, 9, 0, tzinfo=UTC))` |
| `cron="..."` | On a 5-field cron expression, **in UTC** | `.schedule(cron="0 9 * * 1-5")` |

| Option | Effect |
|---|---|
| `after=timedelta(...)` | Waits this long before the schedule starts |
| `max_repeats=n` | Stops after `n` runs (a `datetime` schedule runs once unless you set it) |

```python
from datetime import UTC, datetime, time, timedelta

# Every 10 seconds, at most 5 times, starting after 60 seconds
agent.schedule(every=timedelta(seconds=10), after=timedelta(seconds=60), max_repeats=5)

# Every day at 17:00 UTC
agent.schedule(at=time(hour=17, minute=0))

# Once, 30 seconds from now
agent.schedule(at=datetime.now(UTC) + timedelta(seconds=30))

# Weekdays at 09:00 UTC
agent.schedule(cron="0 9 * * 1-5")
```

Details that matter in practice:

- **Times are UTC.** `at=time(17, 0)` means 17:00 UTC, whatever the time zone of the machine. A `datetime` without `tzinfo` is read as UTC, so `datetime.now() + timedelta(...)` is off by your UTC offset. Use `datetime.now(UTC)`.
- **A `datetime` in the past fires immediately**, once.
- **Intervals are not aligned to the clock.** The next tick is one interval after the previous one. Use `at=` or `cron=` for wall-clock times.
- **An invalid cron expression is not rejected.** The timer then fires every minute, so check expressions before you deploy them.
- **Iterations start at 0 on every start.** Timer state is not persisted; after a restart, `ctx.timer_iteration` counts from 0 again.

---

## What a Timer Run Receives

When the timer fires, Flock publishes a `TimerTick` system artifact (tagged `system` and `timer`) that only this agent subscribes to. The agent then runs like any other:

| What | Where | Content on a timer run |
|---|---|---|
| Input | `inputs.artifacts` (custom engines) | One `TimerTick` |
| Context | `ctx.artifacts` | The artifacts the context provider returns (see below) |
| Trigger | `ctx.trigger_type` | `"timer"` (`"artifact"` for normal runs) |
| Iteration | `ctx.timer_iteration` | `0`, `1`, `2`, ... |
| Fire time | `ctx.fire_time` | The tick's `datetime`, in UTC |

**LLM agents** (the default `DSPyEngine`) get the agent description and the context artifacts in the prompt and produce the declared output type. You don't write code for them: describe the job in `.description()` and control the context, as shown in the next section.

**By default the context is the whole blackboard** the agent may see (visibility still applies): all other agents' artifacts, earlier `TimerTick`s and the agent's own earlier outputs. For anything beyond a demo, give the agent a context provider.

---

## Choosing What a Timer Agent Sees

Context is controlled by [context providers](context-providers.md), set per agent with `.with_context(...)`.

### By type, tag or producer

```python
from flock.core.context_provider import FilteredContextProvider
from flock.core.store import FilterConfig
from flock.registry import type_registry

spending_reporter = (
    flock.agent("spending_reporter")
    .description("Summarize all transactions so far: totals, averages, top category.")
    .schedule(every=timedelta(hours=1))
    .with_context(
        FilteredContextProvider(
            FilterConfig(type_names={type_registry.name_for(Transaction)}), limit=-1
        )
    )
    .publishes(SpendingReport)
)
```

`FilteredContextProvider` returns at most `limit` artifacts, oldest first, and `limit` defaults to 50. A timer agent that should see everything so far needs `limit=-1`.

`FilterConfig` also takes `produced_by`, `correlation_id` and `tags`; criteria combine with AND, and an artifact must carry all the given tags. Tags are set when publishing, for example `await flock.publish(entry, tags={"error"})`.

### By time

`FilterConfig` holds fixed values, so a window that moves with each run needs a small provider. Every artifact has a `created_at` timestamp (UTC), and `FilterConfig(start=...)` selects on it. This provider returns today's artifacts of the given types:

```python
from datetime import UTC, datetime

from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.context_provider import BaseContextProvider, ContextRequest


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


daily_reporter = (
    flock.agent("daily_reporter")
    .description("Summarize today's transactions: totals, averages, top category.")
    .schedule(at=time(hour=17, minute=0))
    .with_context(Today(Transaction))
    .publishes(DailyReport)
)
```

`BaseContextProvider` still applies visibility to whatever `get_artifacts` returns.

### By payload content

For conditions on the payload, filter in the provider:

```python
class ErrorLogs(BaseContextProvider):
    """Only ERROR-level log entries."""

    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        logs, _ = await request.store.query_artifacts(
            FilterConfig(type_names={type_registry.name_for(LogEntry)}), limit=-1
        )
        return [log for log in logs if log.payload.get("level") == "ERROR"]


error_analyzer = (
    flock.agent("error_analyzer")
    .description("Find patterns in the ERROR logs and suggest fixes.")
    .schedule(every=timedelta(minutes=5))
    .with_context(ErrorLogs())
    .publishes(ErrorReport)
)
```

### `.consumes()` adds triggers, it does not filter context

`.consumes()` on a scheduled agent subscribes it to artifacts *in addition to* the timer:

```python
# Runs every 5 minutes AND on every ERROR LogEntry
watcher = (
    flock.agent("watcher")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)
```

Use this only when you want both triggers. To choose what the agent *sees* on a timer run, use `.with_context(...)`.

---

## Custom Logic: Engines

When a timer agent should compute something instead of asking an LLM, give it an engine. The engine reads the context from `ctx.artifacts` and returns its output:

```python
from flock.components.agent import EngineComponent
from flock.utils.runtime import EvalResult


class ErrorReportEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        logs = [LogEntry(**artifact.payload) for artifact in ctx.artifacts]
        report = ErrorReport(
            error_count=len(logs),
            error_messages=[log.message for log in logs],
            iteration=ctx.timer_iteration,
        )
        return EvalResult.from_object(report, agent=agent)


error_counter = (
    flock.agent("error_counter")
    .schedule(every=timedelta(minutes=5))
    .with_context(ErrorLogs())
    .with_engines(ErrorReportEngine())
    .publishes(ErrorReport)
)
```

`ctx.trigger_type` tells an engine whether it was started by the timer or by an artifact, which is useful when an agent has both triggers.

---

## Timers and Reactive Agents

A timer agent's output is an ordinary artifact, so other agents can react to it:

```python
# Timer: collect a metric every 30 seconds
collector = (
    flock.agent("collector")
    .schedule(every=timedelta(seconds=30))
    .publishes(Metric)
)

# Reactive: alert on high values as soon as they appear
alerter = (
    flock.agent("alerter")
    .consumes(Metric, where=lambda m: m.value > 90)
    .publishes(Alert)
)
```

---

## Running and Stopping

Timers start when the orchestrator starts and stop when it stops.

```python
# Long-running service: timers run until the server stops
await flock.serve(dashboard=True)

# Script or demo: run for a fixed time, then stop the timers
await flock.run_until_idle(timeout=120)

# Finite schedules: returns once every timer reached max_repeats
await flock.run_until_idle()
```

`run_until_idle()` counts running timers as work, so without `timeout` it never returns while an unlimited timer is active. With `timeout` it returns after that many seconds and cancels the timers.

---

## Rules and Limits

| Rule | What happens otherwise |
|---|---|
| A scheduled agent needs `.publishes()` | `ValueError` on the first run |
| `.schedule()` cannot be combined with a batch subscription | `ValueError`, in either order |
| Times are UTC | Local times are shifted by the UTC offset |
| Timer state is not persisted | Iterations restart at 0 after a restart |

---

## Examples

Runnable examples live in [`examples/10-scheduling/`](https://github.com/whiteducksoftware/flock/tree/main/examples/10-scheduling):

| Example | Shows |
|---|---|
| `01_simple_health_monitor.py` | Interval schedule, LLM agent |
| `02_error_log_analyzer.py` | Two timers; a custom context provider for ERROR logs |
| `03_daily_report_generator.py` | Daily `at=time(...)` schedule; today's transactions as context |
| `04_batch_data_processor.py` | Periodic aggregation with dynamic fan-out |
| `05_one_time_reminder.py` | One-time `at=datetime(...)` schedule |
| `06_cron_demo.py` | Cron schedule |

## See Also

- [Scheduled Agents Tutorial](../tutorials/scheduled-agents.md): step-by-step from a single timer to a multi-agent system
- [Context Providers](context-providers.md): everything about controlling agent context
- [Custom Engines](../tutorials/custom-engines.md): writing your own engine
