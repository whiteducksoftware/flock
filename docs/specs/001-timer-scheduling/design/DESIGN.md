# Timer-Based Agent Scheduling - Design Document

**Status:** Design Phase
**Author:** Design discussion 2025-10-30
**Target Version:** 0.6.0

---

## 🎯 **Overview**

This document defines the design for **timer-based agent scheduling** in Flock - enabling agents to execute periodically or at specific times without requiring artifact triggers.

### **Goals**

1. **Elegant API**: Timer scheduling should feel native to Flock's fluent builder pattern
2. **Artifact-Driven**: Maintain Flock's core philosophy - timers publish artifacts under the hood
3. **Composable**: Timer scheduling should work seamlessly with existing features (batching, joins, context providers)
4. **Flexible**: Support periodic intervals, specific times, cron expressions, and one-time execution
5. **Production-Ready**: Handle edge cases (shutdown, backpressure, long-running tasks)

### **Non-Goals**

- Distributed timer coordination (multi-instance orchestrators)
- Persistent timer state across restarts (timers reset on startup)
- Sub-second precision (minimum resolution: 1 second)

---

## 🏗️ **Architecture**

### **Core Principle: Timers Are Artifact Producers**

Timers internally publish `TimerTick` artifacts that trigger subscribed agents. This maintains Flock's artifact-driven architecture while providing a clean API abstraction.

```
Timer Component (Background Task)
    ↓ (every N seconds)
Publish TimerTick Artifact
    ↓
Subscription Matching (agent auto-subscribed)
    ↓
Agent Execution (ctx.artifacts = [], ctx.timer_iteration = N)
```

### **Component Integration**

```
┌─────────────────────────────────────────────┐
│         Flock Orchestrator                  │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │   TimerComponent                   │    │
│  │   - Manages background tasks       │    │
│  │   - Publishes TimerTick artifacts  │    │
│  └────────────────────────────────────┘    │
│                   ↓                         │
│  ┌────────────────────────────────────┐    │
│  │   Blackboard Store                 │    │
│  │   TimerTick(timer_name="health",   │    │
│  │             fire_time=...,         │    │
│  │             iteration=5)           │    │
│  └────────────────────────────────────┘    │
│                   ↓                         │
│  ┌────────────────────────────────────┐    │
│  │   Agent Scheduler                  │    │
│  │   - Matches TimerTick → Agent      │    │
│  │   - Filters by timer_name          │    │
│  └────────────────────────────────────┘    │
│                   ↓                         │
│  ┌────────────────────────────────────┐    │
│  │   Scheduled Agent Execution        │    │
│  │   - ctx.artifacts = []             │    │
│  │   - ctx.timer_iteration = 5        │    │
│  │   - ctx.trigger_type = "timer"     │    │
│  └────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 🎨 **API Design**

### **1. Simple Periodic Execution** ⭐ **PRIMARY USE CASE**

```python
from datetime import timedelta

# Execute every 30 seconds
health_monitor = (
    flock.agent("health_monitor")
    .description("Monitors system health")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)
```

**Agent receives:**
- `ctx.artifacts = []` (no input artifact)
- `ctx.trigger_type = "timer"`
- `ctx.timer_iteration = N` (starts at 0)
- `ctx.fire_time = datetime(...)` (when timer fired)
- `ctx.get_artifacts(Type)` → All artifacts on blackboard (filtered by context provider)

### **2. Scheduled with Initial Delay**

```python
# Wait 60 seconds before first execution, then every 5 minutes
warmup_agent = (
    flock.agent("warmup")
    .schedule(
        every=timedelta(minutes=5),
        after=timedelta(seconds=60)
    )
    .publishes(WarmupResult)
)
```

### **3. Limited Repeats**

```python
# Execute 10 times then stop
reminder = (
    flock.agent("reminder")
    .schedule(
        every=timedelta(hours=1),
        max_repeats=10
    )
    .publishes(Reminder)
)
```

### **4. Specific Time Execution**

```python
from datetime import time, datetime

# Daily at 5 PM
daily_report = (
    flock.agent("daily_report")
    .schedule(at=time(hour=17, minute=0))
    .publishes(DailyReport)
)

# One-time execution
reminder = (
    flock.agent("reminder")
    .schedule(at=datetime(2025, 11, 1, 9, 0))
    .publishes(Reminder)
)
```

### **5. Cron Expression** (Future Enhancement)

```python
# Every Monday at 2 AM
backup = (
    flock.agent("backup")
    .schedule(cron="0 2 * * MON")
    .publishes(BackupResult)
)
```

### **6. Timer + Context Filtering** 🔥 **POWERFUL PATTERN**

```python
# Run every 5 minutes, but ONLY see ERROR-level logs
error_analyzer = (
    flock.agent("error_analyzer")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)

# Agent execution:
async def evaluate(self, ctx: AgentContext) -> ErrorReport:
    # ctx.artifacts = []  (timer-triggered, not artifact-triggered)

    # ctx.get_artifacts(LogEntry) returns ONLY ERROR logs
    # because .consumes() acts as a CONTEXT FILTER (not a trigger)
    error_logs = ctx.get_artifacts(LogEntry)

    return ErrorReport(errors=error_logs)
```

**Key Insight:** `.consumes()` serves dual purposes:
- **With artifact triggers**: Defines WHAT triggers the agent
- **With timer triggers**: Defines WHAT CONTEXT the agent sees (filtering, not triggering)

### **7. Hybrid Context - Multiple Types**

```python
# Timer agent that sees metrics AND alerts (filtered by tags)
aggregator = (
    flock.agent("aggregator")
    .schedule(every=timedelta(hours=1))
    .consumes(Metric, Alert, tags={"critical"})
    .publishes(AggregatedReport)
)

# Agent sees:
# - ctx.get_artifacts(Metric) → Only Metrics with tag "critical"
# - ctx.get_artifacts(Alert) → Only Alerts with tag "critical"
```

---

## 🔧 **Implementation Details**

### **1. ScheduleSpec Data Model**

**Location:** `src/flock/core/subscription.py`

```python
from dataclasses import dataclass
from datetime import timedelta, time, datetime

@dataclass
class ScheduleSpec:
    """Timer specification for periodic agent triggering.

    Exactly one of `interval`, `at`, or `cron` must be specified.

    Attributes:
        interval: Periodic execution interval (e.g., timedelta(seconds=30))
        at: Specific time (daily) or datetime (one-time)
        cron: Cron expression (future enhancement)
        after: Initial delay before first execution
        max_repeats: Maximum number of executions (None = infinite)
    """
    interval: timedelta | None = None
    at: time | datetime | None = None
    cron: str | None = None
    after: timedelta | None = None
    max_repeats: int | None = None

    def __post_init__(self):
        """Validate that exactly one trigger type is specified."""
        trigger_count = sum([
            self.interval is not None,
            self.at is not None,
            self.cron is not None
        ])
        if trigger_count != 1:
            raise ValueError(
                "Exactly one of 'interval', 'at', or 'cron' must be specified"
            )
```

### **2. TimerTick System Artifact**

**Location:** `src/flock/models/system_artifacts.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from flock.core.artifacts import flock_type

@flock_type
class TimerTick(BaseModel):
    """System artifact published when a timer fires.

    This is an internal infrastructure artifact. User agents receive
    empty input (ctx.artifacts = []) with timer metadata in context.
    """
    timer_name: str
    fire_time: datetime = Field(default_factory=datetime.now)
    iteration: int = Field(default=0, description="Number of times timer has fired")
    schedule_spec: dict = Field(default_factory=dict, description="Original schedule config")

    class Config:
        frozen = True  # Immutable
```

### **3. AgentBuilder.schedule() Method**

**Location:** `src/flock/core/agent.py` (AgentBuilder class)

```python
from datetime import timedelta, time, datetime
from flock.core.subscription import ScheduleSpec
from flock.models.system_artifacts import TimerTick

class AgentBuilder:
    # ... existing methods ...

    def schedule(
        self,
        every: timedelta | None = None,
        at: time | datetime | None = None,
        cron: str | None = None,
        after: timedelta | None = None,
        max_repeats: int | None = None,
    ) -> "AgentBuilder":
        """Schedule periodic agent execution.

        The agent will execute on a timer rather than waiting for artifacts.
        Can be combined with .consumes() to filter blackboard context.

        Args:
            every: Execute at regular intervals (e.g., timedelta(seconds=30))
            at: Execute at specific time (daily if `time`, once if `datetime`)
            cron: Execute on cron schedule (future enhancement)
            after: Initial delay before first execution
            max_repeats: Maximum executions (None = infinite)

        Returns:
            AgentBuilder for method chaining

        Example:
            >>> agent = (
            ...     flock.agent("health")
            ...     .schedule(every=timedelta(seconds=30))
            ...     .publishes(HealthStatus)
            ... )
        """
        # Create schedule specification
        self._agent.schedule_spec = ScheduleSpec(
            interval=every,
            at=at,
            cron=cron,
            after=after,
            max_repeats=max_repeats
        )

        # Auto-subscribe to own timer ticks (filtered by timer_name)
        # This is transparent to the user - they don't see TimerTick in their code
        self.consumes(
            TimerTick,
            where=lambda tick: tick.timer_name == self._agent.name
        )

        return self
```

### **4. TimerComponent**

**Location:** `src/flock/components/orchestrator/scheduling/timer.py`

```python
import asyncio
from datetime import datetime, timedelta, time
from flock.components.orchestrator.base import OrchestratorComponent
from flock.models.system_artifacts import TimerTick
from flock.core.orchestrator import Flock

class TimerComponent(OrchestratorComponent):
    """Manages timer-based agent execution.

    This component:
    1. Starts background tasks for each scheduled agent
    2. Publishes TimerTick artifacts at configured intervals
    3. Handles graceful shutdown and task cancellation
    """

    name: str = "timer"
    priority: int = 5  # Run before collection component (100)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._timer_tasks: dict[str, asyncio.Task] = {}

    async def on_initialize(self, orchestrator: Flock) -> None:
        """Start timer tasks for all scheduled agents."""
        for agent in orchestrator.agents:
            if hasattr(agent, 'schedule_spec') and agent.schedule_spec:
                task = asyncio.create_task(
                    self._timer_loop(orchestrator, agent.name, agent.schedule_spec)
                )
                self._timer_tasks[agent.name] = task

    async def _timer_loop(
        self,
        orchestrator: Flock,
        agent_name: str,
        spec: "ScheduleSpec"
    ) -> None:
        """Background task that publishes TimerTick artifacts.

        Args:
            orchestrator: Flock instance to publish to
            agent_name: Name of agent being scheduled
            spec: Schedule specification
        """
        try:
            # Initial delay
            if spec.after:
                await asyncio.sleep(spec.after.total_seconds())

            iteration = 0
            while spec.max_repeats is None or iteration < spec.max_repeats:
                # Wait for next fire time
                await self._wait_for_next_fire(spec)

                # Publish timer tick
                tick = TimerTick(
                    timer_name=agent_name,
                    fire_time=datetime.now(),
                    iteration=iteration,
                    schedule_spec={
                        "interval": str(spec.interval) if spec.interval else None,
                        "at": str(spec.at) if spec.at else None,
                    }
                )

                await orchestrator.publish(
                    tick,
                    correlation_id=f"timer:{agent_name}:{iteration}",
                    tags={"system", "timer"}
                )

                iteration += 1

        except asyncio.CancelledError:
            # Graceful shutdown
            pass

    async def _wait_for_next_fire(self, spec: "ScheduleSpec") -> None:
        """Calculate and wait until next timer fire.

        Args:
            spec: Schedule specification
        """
        if spec.interval:
            # Simple interval-based timing
            await asyncio.sleep(spec.interval.total_seconds())

        elif spec.at:
            if isinstance(spec.at, time):
                # Daily execution at specific time
                now = datetime.now()
                target = datetime.combine(now.date(), spec.at)

                # If target time already passed today, schedule for tomorrow
                if target <= now:
                    target = datetime.combine(
                        now.date() + timedelta(days=1),
                        spec.at
                    )

                wait_seconds = (target - now).total_seconds()
                await asyncio.sleep(wait_seconds)

            elif isinstance(spec.at, datetime):
                # One-time execution at specific datetime
                now = datetime.now()
                if spec.at > now:
                    wait_seconds = (spec.at - now).total_seconds()
                    await asyncio.sleep(wait_seconds)
                # After one-time execution, this will exit the loop
                # (max_repeats defaults to 1 for datetime triggers)

        elif spec.cron:
            # Future enhancement: Parse cron expression
            # For now, raise NotImplementedError
            raise NotImplementedError("Cron expressions not yet supported")

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Cancel all timer tasks during shutdown."""
        for task in self._timer_tasks.values():
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete cancellation
        if self._timer_tasks:
            await asyncio.gather(*self._timer_tasks.values(), return_exceptions=True)
```

### **5. AgentContext Enhancements**

**Location:** `src/flock/core/agent.py` (AgentContext class)

```python
class AgentContext:
    # ... existing properties ...

    @property
    def trigger_type(self) -> str:
        """Type of trigger that invoked this agent.

        Returns:
            "artifact" for normal triggers, "timer" for scheduled execution
        """
        if self.artifacts and len(self.artifacts) == 1:
            if isinstance(self.artifacts[0], TimerTick):
                return "timer"
        return "artifact"

    @property
    def timer_iteration(self) -> int | None:
        """Iteration count for timer-triggered agents.

        Returns:
            Iteration number (0-indexed) or None if not timer-triggered
        """
        if self.trigger_type == "timer" and self.artifacts:
            return self.artifacts[0].iteration
        return None

    @property
    def fire_time(self) -> datetime | None:
        """Fire time for timer-triggered agents.

        Returns:
            Datetime when timer fired, or None if not timer-triggered
        """
        if self.trigger_type == "timer" and self.artifacts:
            return self.artifacts[0].fire_time
        return None
```

### **6. Agent.execute() Modifications**

**Behavior:** When executing a timer-triggered agent, hide the `TimerTick` artifact from user code:

```python
async def execute(self, ctx: AgentContext) -> list[Artifact]:
    """Execute agent with timer-aware context handling."""

    # If triggered by TimerTick, expose empty artifacts to user
    if ctx.trigger_type == "timer":
        # Store original for internal use
        original_artifacts = ctx.artifacts

        # Present empty list to user code
        ctx.artifacts = []

        # Add timer metadata to context
        ctx._timer_metadata = {
            'iteration': original_artifacts[0].iteration,
            'fire_time': original_artifacts[0].fire_time,
        }

    # Continue with normal execution...
```

---

## 📊 **Execution Semantics**

### **Timer-Triggered vs Artifact-Triggered Agents**

| Property | Artifact-Triggered | Timer-Triggered |
|----------|-------------------|-----------------|
| **Trigger** | Artifact published matching `.consumes()` | Timer fires based on `.schedule()` |
| **Input** | `ctx.artifacts = [TriggerArtifact]` | `ctx.artifacts = []` |
| **Context** | All blackboard artifacts (via context provider) | All blackboard artifacts (via context provider) |
| **Filtering** | `.consumes(Type, where=...)` filters TRIGGERS | `.consumes(Type, where=...)` filters CONTEXT |
| **Metadata** | `ctx.trigger_type = "artifact"` | `ctx.trigger_type = "timer"` |
| **Special Props** | N/A | `ctx.timer_iteration`, `ctx.fire_time` |

### **Timer Lifecycle**

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
     - Publish TimerTick artifact
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
   - Outputs cascade normally
   ↓
7. Orchestrator Shutdown
   - TimerComponent.on_shutdown()
   - Cancel all timer tasks
   - Wait for graceful completion
```

---

## 🎯 **Usage Examples**

### **Example 1: Health Monitor (Simple Periodic)**

```python
from datetime import timedelta
from pydantic import BaseModel
from flock import Flock
from flock.core.artifacts import flock_type

@flock_type
class HealthStatus(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    timestamp: datetime

flock = Flock("openai/gpt-4.1")

health_monitor = (
    flock.agent("health_monitor")
    .description("Monitors system health every 30 seconds")
    .schedule(every=timedelta(seconds=30))
    .publishes(HealthStatus)
)

# Agent implementation
async def check_health(ctx: AgentContext) -> HealthStatus:
    # ctx.artifacts = []
    # ctx.timer_iteration = 0, 1, 2, ...
    # ctx.trigger_type = "timer"

    import psutil
    return HealthStatus(
        cpu_percent=psutil.cpu_percent(),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage('/').percent,
        timestamp=datetime.now()
    )

# Run
await flock.serve()  # Timers start automatically
```

### **Example 2: Error Analyzer (Timer + Context Filter)**

```python
from datetime import timedelta

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

# Publish logs continuously (from other agents or external sources)
await flock.publish(LogEntry(level="INFO", message="Request processed"))
await flock.publish(LogEntry(level="ERROR", message="Database timeout"))
await flock.publish(LogEntry(level="ERROR", message="API failure"))

# Analyzer runs every 5 minutes and ONLY sees ERROR logs
error_analyzer = (
    flock.agent("error_analyzer")
    .description("Analyzes error logs every 5 minutes")
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")
    .publishes(ErrorReport)
)

# Implementation
async def analyze_errors(ctx: AgentContext) -> ErrorReport:
    # ctx.get_artifacts(LogEntry) returns ONLY ERROR-level logs
    errors = ctx.get_artifacts(LogEntry)

    return ErrorReport(
        error_count=len(errors),
        errors=errors,
        analysis=f"Found {len(errors)} errors in last 5 minutes"
    )
```

### **Example 3: Daily Report (Scheduled Time)**

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

# Runs every day at 5 PM
daily_report = (
    flock.agent("daily_report")
    .description("Generate end-of-day financial report")
    .schedule(at=time(hour=17, minute=0))
    .consumes(Transaction)  # Context filter: see all transactions
    .publishes(DailyReport)
)

async def generate_report(ctx: AgentContext) -> DailyReport:
    # Runs at 5 PM daily
    # ctx.timer_iteration = 0 (first day), 1 (second day), ...

    transactions = ctx.get_artifacts(Transaction)
    today = datetime.now().date()

    # Filter transactions from today
    today_txns = [t for t in transactions if t.timestamp.date() == today]

    return DailyReport(
        date=today,
        total_transactions=len(today_txns),
        total_revenue=sum(t.amount for t in today_txns)
    )
```

### **Example 4: Reminder (One-Time Execution)**

```python
from datetime import datetime

@flock_type
class Reminder(BaseModel):
    message: str
    timestamp: datetime

# Execute once at specific datetime
reminder = (
    flock.agent("meeting_reminder")
    .schedule(at=datetime(2025, 11, 1, 9, 0))  # Nov 1, 2025 at 9 AM
    .publishes(Reminder)
)

async def send_reminder(ctx: AgentContext) -> Reminder:
    # Executes once at scheduled time
    return Reminder(
        message="Team meeting starts in 5 minutes!",
        timestamp=datetime.now()
    )
```

### **Example 5: Aggregator (Multi-Type Context)**

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

# Runs hourly, sees ONLY critical-tagged metrics and alerts
aggregator = (
    flock.agent("aggregator")
    .schedule(every=timedelta(hours=1))
    .consumes(Metric, Alert, tags={"critical"})
    .publishes(AggregatedReport)
)

async def aggregate(ctx: AgentContext) -> AggregatedReport:
    # Both filtered by "critical" tag
    metrics = ctx.get_artifacts(Metric)
    alerts = ctx.get_artifacts(Alert)

    return AggregatedReport(
        critical_metrics=metrics,
        critical_alerts=alerts,
        summary=f"Hourly aggregation: {len(metrics)} metrics, {len(alerts)} alerts"
    )
```

---

## 🚧 **Edge Cases & Considerations**

### **1. Timer Fires During Slow Agent Execution**

**Scenario:** Timer fires every 10 seconds, but agent takes 15 seconds to execute.

**Behavior:**
- Timer publishes `TimerTick` at T=0, T=10, T=20
- Agent starts at T=0, finishes at T=15
- At T=10, second `TimerTick` is published
- At T=15, agent finishes and second execution starts (sees T=10 tick)
- Result: Executions may queue up if agent is slower than timer

**Mitigation:**
```python
# Use max_concurrency to prevent queue buildup
agent = (
    flock.agent("slow_agent")
    .schedule(every=timedelta(seconds=10))
    .max_concurrency(1)  # Only 1 execution at a time
    .publishes(Result)
)
```

### **2. Orchestrator Shutdown During Timer Execution**

**Behavior:**
- `TimerComponent.on_shutdown()` cancels all timer tasks
- In-flight agent executions complete gracefully
- No new timer ticks published after shutdown initiated

### **3. Timer + BatchSpec Interaction**

**Question:** What happens if agent has both `.schedule()` and `.batch()`?

```python
agent = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=5))
    .consumes(Order, batch=BatchSpec(size=100, timeout=timedelta(minutes=1)))
    .publishes(Report)
)
```

**Answer:** This is currently **undefined behavior** and should raise a validation error:
- `.schedule()` means "run on timer" (no artifact trigger)
- `.batch()` means "wait for N artifacts" (artifact trigger)
- These are mutually exclusive

**Validation:** `AgentBuilder.build()` should check:
```python
if agent.schedule_spec and any(sub.batch for sub in agent.subscriptions):
    raise ValueError("Cannot combine .schedule() with .batch() - mutually exclusive")
```

### **4. Long-Running Tasks and Idle Detection**

**Question:** Does `run_until_idle()` complete if timers are active?

**Answer:** No - timers keep the orchestrator "busy":
```python
# This will NOT complete (timers run indefinitely)
await flock.run_until_idle()

# Use serve() for long-running orchestrators with timers
await flock.serve()  # Runs forever (or until interrupted)
```

### **5. Timer Precision and Drift**

**Precision:** Timer resolution is approximately 1 second (limited by `asyncio.sleep()`).

**Drift:** Timers may drift over time due to:
- Agent execution time
- System load
- Python GIL contention

**Mitigation:** For high-precision timing, consider using a dedicated scheduler component.

### **6. Context Provider Interaction**

Timer-triggered agents respect context providers:

```python
# Global context provider: Only show urgent items
urgent_provider = FilteredContextProvider(FilterConfig(tags={"urgent"}))
flock = Flock("openai/gpt-4.1", context_provider=urgent_provider)

# Timer agent sees ONLY urgent artifacts
agent = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=5))
    .publishes(Report)
)

# Agent receives:
# - ctx.artifacts = []
# - ctx.get_artifacts(Metric) → ONLY Metrics with "urgent" tag
```

---

## 🔮 **Future Enhancements**

### **Phase 2: Cron Expression Support**

```python
from croniter import croniter

agent = (
    flock.agent("backup")
    .schedule(cron="0 2 * * MON")  # Every Monday at 2 AM
    .publishes(BackupResult)
)
```

**Implementation:** Use `croniter` library to calculate next fire time.

### **Phase 3: Persistent Timer State**

**Problem:** Timers reset on orchestrator restart (lose iteration count).

**Solution:** Persist timer state to SQLite store:
```python
# Store last fire time and iteration
await store.set_timer_state(
    timer_name="health_monitor",
    last_fire=datetime.now(),
    iteration=42
)
```

### **Phase 4: Distributed Timer Coordination**

**Problem:** Multiple orchestrator instances create duplicate timer ticks.

**Solution:** Leader election using Redis/etcd:
```python
# Only leader orchestrator runs timers
if await timer_component.is_leader():
    await publish_timer_tick()
```

### **Phase 5: Dynamic Timer Management**

```python
# Start/stop timers at runtime
await flock.start_timer("health_monitor")
await flock.stop_timer("health_monitor")
await flock.pause_timer("health_monitor", duration=timedelta(minutes=10))
```

### **Phase 6: Timer Analytics in Dashboard**

- Show active timers with countdown
- Display fire history and iteration count
- Visualize timer-triggered agent executions
- Alert on missed timer fires (if agent too slow)

---

## ✅ **Validation Rules**

The following validation rules will be enforced in `AgentBuilder.build()`:

1. **Mutually Exclusive Triggers:**
   - Cannot combine `.schedule()` with `.batch()` (different trigger mechanisms)
   - Can combine `.schedule()` with `.consumes()` (consumes = context filter)

2. **Schedule Spec Validation:**
   - Exactly one of `interval`, `at`, or `cron` must be set
   - `after` must be positive if specified
   - `max_repeats` must be positive if specified

3. **Timer Name Uniqueness:**
   - Agent names with `.schedule()` must be unique (timer_name = agent_name)

4. **Output Type Required:**
   - Scheduled agents must have `.publishes()` (what's the point otherwise?)

---

## 📖 **Documentation Plan**

### **User Guide** (`docs/guides/scheduling.md`)

- Overview of timer-based agents
- Common use cases (health checks, reports, cleanup)
- API reference with examples
- Best practices and performance tips

### **Tutorial** (`docs/tutorials/scheduled-agents.md`)

Step-by-step guide:
1. Simple periodic agent
2. Scheduled agent with context filtering
3. Daily report generation
4. Multi-type context aggregation

### **API Reference** (auto-generated from docstrings)

- `AgentBuilder.schedule()` method
- `ScheduleSpec` dataclass
- `TimerComponent` hooks
- `AgentContext.timer_*` properties

---

## 🧪 **Testing Strategy**

### **Unit Tests**

**Location:** `tests/unit/test_timer_component.py`

```python
# Test timer loop publishes TimerTick artifacts
async def test_timer_publishes_ticks():
    spec = ScheduleSpec(interval=timedelta(seconds=1))
    # Verify TimerTick published every second

# Test initial delay
async def test_timer_initial_delay():
    spec = ScheduleSpec(interval=timedelta(seconds=1), after=timedelta(seconds=2))
    # Verify first tick after 2 seconds

# Test max_repeats limit
async def test_timer_max_repeats():
    spec = ScheduleSpec(interval=timedelta(seconds=1), max_repeats=3)
    # Verify exactly 3 ticks published

# Test graceful shutdown
async def test_timer_shutdown():
    # Start timer, trigger shutdown, verify task cancelled
```

### **Integration Tests**

**Location:** `tests/integration/test_scheduled_agents.py`

```python
# Test scheduled agent execution
async def test_scheduled_agent_executes():
    agent = flock.agent("test").schedule(every=timedelta(seconds=1)).publishes(Result)
    # Verify agent executes on timer

# Test timer + context filter
async def test_timer_with_context_filter():
    agent = (
        flock.agent("test")
        .schedule(every=timedelta(seconds=1))
        .consumes(Log, where=lambda l: l.level == "ERROR")
        .publishes(Report)
    )
    # Verify agent only sees ERROR logs

# Test validation errors
async def test_schedule_batch_mutual_exclusion():
    with pytest.raises(ValueError, match="mutually exclusive"):
        agent = (
            flock.agent("test")
            .schedule(every=timedelta(seconds=1))
            .consumes(Order, batch=BatchSpec(size=10))
        )
```

### **Example Scripts**

**Location:** `examples/09-scheduling/`

- `01_simple_health_monitor.py` - Basic periodic execution
- `02_error_analyzer_with_filter.py` - Timer + context filtering
- `03_daily_report.py` - Scheduled time execution
- `04_multi_type_aggregator.py` - Multiple context types
- `05_one_time_reminder.py` - One-time datetime execution

---

## 🎯 **Success Criteria**

This feature is considered complete when:

1. ✅ Users can schedule agents with `.schedule()` method
2. ✅ All scheduling modes work: `every`, `at` (time/datetime)
3. ✅ Timer + context filtering works (`.consumes()` as filter)
4. ✅ Agent receives empty input with timer metadata in context
5. ✅ Timers start on orchestrator startup and stop on shutdown
6. ✅ Validation prevents invalid configurations (schedule + batch)
7. ✅ Documentation and examples are complete
8. ✅ Test coverage > 90% for timer component
9. ✅ Dashboard shows timer agents with iteration count (future)

---

## 🚀 **Implementation Roadmap**

### **Milestone 1: Core Timer Infrastructure** (Week 1)

- [ ] Implement `ScheduleSpec` dataclass
- [ ] Create `TimerTick` system artifact
- [ ] Build `TimerComponent` with basic interval support
- [ ] Add `AgentBuilder.schedule()` method
- [ ] Unit tests for timer loop logic

### **Milestone 2: Context Integration** (Week 2)

- [ ] Enhance `AgentContext` with timer properties
- [ ] Implement timer tick filtering in agent execution
- [ ] Support `.consumes()` as context filter for timer agents
- [ ] Integration tests for timer + context

### **Milestone 3: Advanced Scheduling** (Week 3)

- [ ] Add `at` (time) support for daily execution
- [ ] Add `at` (datetime) support for one-time execution
- [ ] Implement `after` (initial delay)
- [ ] Implement `max_repeats` limit
- [ ] Validation for mutually exclusive configurations

### **Milestone 4: Documentation & Examples** (Week 4)

- [ ] User guide (`docs/guides/scheduling.md`)
- [ ] Tutorial (`docs/tutorials/scheduled-agents.md`)
- [ ] 5 example scripts in `examples/09-scheduling/`
- [ ] Update `AGENTS.md` with timer patterns
- [ ] API reference docstrings

### **Milestone 5: Polish & Release** (Week 5)

- [ ] Dashboard integration (show timer status)
- [ ] Performance testing (100+ concurrent timers)
- [ ] Edge case handling (shutdown, errors)
- [ ] Version bump to 0.6.0
- [ ] Release notes and changelog

---

## 📝 **Open Questions**

### **1. Should timers run during `run_until_idle()`?**

**Option A:** Timers pause when orchestrator idle (only during active workflows)
**Option B:** Timers run independently (publish ticks even when idle)

**Current Decision:** Option B - timers are independent background tasks.

### **2. How should `traced_run()` interact with timers?**

```python
async with flock.traced_run("workflow"):
    # Should timer ticks be grouped in this trace?
```

**Current Decision:** Timer ticks outside `traced_run()` get their own correlation ID (`timer:{agent_name}:{iteration}`). Ticks inside `traced_run()` inherit the trace correlation ID.

### **3. Should we support dual-mode triggering (timer OR artifact)?**

```python
# Agent triggered by EITHER timer OR Order artifact
agent = (
    flock.agent("processor")
    .schedule(every=timedelta(minutes=5))
    .consumes(Order)  # Also trigger on Order?
    .publishes(Report)
)
```

**Current Decision:** Not in initial release. Revisit based on user feedback.

### **4. What happens to timer state during orchestrator restart?**

**Current Decision:** Timers reset (iteration = 0). Persistent state is a future enhancement (Phase 2).

---

## 🎉 **Summary**

This design provides:

✅ **Elegant API** - `.schedule()` feels natural in Flock's fluent style
✅ **Artifact-Driven** - Timers publish `TimerTick` internally, maintaining core architecture
✅ **Composable** - Works seamlessly with context providers, filters, and visibility
✅ **Flexible** - Supports intervals, specific times, initial delays, and max repeats
✅ **Production-Ready** - Handles shutdown, backpressure, and edge cases
✅ **Future-Proof** - Clear path to cron, persistence, and distributed coordination

**Next Steps:** Review, approve, and move to implementation! 🚀
