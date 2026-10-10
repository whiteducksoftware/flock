# Timer Scheduling Examples

Six examples of agents that run on a timer instead of waiting for an artifact: interval, daily, one-time and cron schedules, plus timer agents that read filtered blackboard context.

All examples use the default LLM engine, so set `OPENAI_API_KEY` (and optionally `DEFAULT_MODEL`) first. Run them from the repository root:

```bash
uv run python examples/10-scheduling/01_simple_health_monitor.py
```

## How timer agents work

- `.schedule(...)` starts a timer when the orchestrator starts. On each tick the agent receives a `TimerTick` as input and runs its engine.
- **Context:** a timer run sees the blackboard. `.with_context(provider)` narrows what it sees, for example to one artifact type or to ERROR logs only.
- `.consumes()` on a scheduled agent adds artifact triggers; it does not filter context.
- Engines can read `ctx.trigger_type` (`"timer"`), `ctx.timer_iteration` (0, 1, 2, ...) and `ctx.fire_time`.
- Times are UTC. A `datetime` without a time zone is read as UTC.
- Scheduled agents must declare `.publishes()`.

## Examples

| Example | Schedule | Shows | CLI run time |
|---|---|---|---|
| `01_simple_health_monitor.py` | `every=30s` | The basic interval timer | 2 min |
| `02_error_log_analyzer.py` | `every=30s` and `every=2min` | A custom context provider: the analyzer sees ERROR logs only | 6 min |
| `03_daily_report_generator.py` | `every=15s` and `every=2min` (production: `at=time(17, 0)` UTC) | Daily schedule; context filtered to `Transaction` | 5 min |
| `04_batch_data_processor.py` | `every=5s` and `every=1min` (production: 10 min) | Periodic aggregation; one `AggregatedData` per sensor via `fan_out=(1, 10)` | 3 min |
| `05_one_time_reminder.py` | `at=datetime.now(UTC) + 30s` | One-time schedule; the reminder reads the published meeting | 45 s |
| `06_cron_demo.py` | `cron="*/1 * * * *"` | Cron schedule (UTC) | 70 s |

### 01. Simple health monitor

```python
health_monitor = (
    flock.agent("health_monitor")
    .description("Generate realistic CPU, memory and disk usage ...")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)
```

### 02. Error log analyzer

A collector publishes log entries of all levels; the analyzer runs every 2 minutes and gets only the ERROR entries as context:

```python
class ErrorLogs(BaseContextProvider):
    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        logs, _ = await request.store.query_artifacts(
            FilterConfig(type_names={type_registry.name_for(LogEntry)}), limit=-1
        )
        return [log for log in logs if log.payload.get("level") == "ERROR"]


error_analyzer = (
    flock.agent("error_analyzer")
    .schedule(every=timedelta(minutes=2))
    .with_context(ErrorLogs())
    .publishes(ErrorReport)
)
```

### 03. Daily report generator

The reporter runs on its timer only and sees only `Transaction` artifacts:

```python
transactions_only = FilteredContextProvider(
    FilterConfig(type_names={type_registry.name_for(Transaction)})
)

daily_reporter = (
    flock.agent("daily_reporter")
    .schedule(at=time(hour=17, minute=0))  # 17:00 UTC
    .with_context(transactions_only)
    .publishes(DailyReport)
)
```

Set `DEMO_MODE = False` for the daily schedule; the demo runs every 2 minutes.

### 04. Batch data processor

A simulator publishes a reading every 5 seconds; the processor aggregates the readings per sensor every minute. Dynamic fan-out lets it publish one result per sensor:

```python
batch_processor = (
    flock.agent("batch_processor")
    .schedule(every=timedelta(minutes=1))
    .with_context(
        FilteredContextProvider(FilterConfig(type_names={type_registry.name_for(DataPoint)}))
    )
    .publishes(AggregatedData, fan_out=(1, 10))
)
```

The context holds all readings published so far, not only those since the last run.

### 05. One-time reminder

```python
reminder_time = datetime.now(UTC) + timedelta(seconds=30)

meeting_reminder = (
    flock.agent("meeting_reminder")
    .schedule(at=reminder_time)  # fires once
    .with_context(
        FilteredContextProvider(FilterConfig(type_names={type_registry.name_for(MeetingSchedule)}))
    )
    .publishes(Reminder)
    .calls(print_reminder)
)
```

### 06. Cron demo

```python
flock.agent("cron_pinger").schedule(cron="*/1 * * * *").publishes(Ping).calls(on_ping)
```

## CLI and dashboard mode

Each example has a `USE_DASHBOARD` flag at the top:

- `False` (default): runs with `run_until_idle(timeout=...)` for the time in the table, then stops the timers.
- `True`: runs `serve(dashboard=True)`; timers fire until you stop the server. Open http://localhost:8344.

`run_until_idle()` without a timeout does not return while an unlimited timer is active.

## Troubleshooting

- **A daily or one-time agent never runs:** times are UTC. `time(hour=17)` is 17:00 UTC, and `datetime.now()` without `UTC` is shifted by your UTC offset.
- **An agent sees unrelated artifacts:** the default context is the whole blackboard; add `.with_context(...)`.
- **An agent runs more often than its schedule:** a `.consumes()` on a scheduled agent adds artifact triggers.
- **Tracing:** `FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true uv run python examples/10-scheduling/02_error_log_analyzer.py`, then query `.flock/traces.duckdb`.

## Documentation

- [Timer Scheduling Guide](../../docs/guides/scheduling.md)
- [Scheduled Agents Tutorial](../../docs/tutorials/scheduled-agents.md)
- [Context Providers](../../docs/guides/context-providers.md)
