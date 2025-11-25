"""
Hackathon Track 06: Timer Scheduling

🎓 LEARNING OBJECTIVE:
Learn how to schedule agents to run periodically or at specific times.
This enables monitoring, reporting, and automated workflows without manual triggers.

KEY CONCEPTS:
- Periodic execution (schedule(every=...))
- Scheduled execution (schedule(at=...))
- Cron expressions (schedule(cron=...))
- Timer-triggered agents (no input artifacts)

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from datetime import datetime, timedelta, time

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# STEP 1: Define Types
# ============================================================================

@flock_type
class SystemMetrics(BaseModel):
    """System health metrics collected periodically."""
    timestamp: datetime = Field(default_factory=datetime.now)
    cpu_percent: float = Field(ge=0, le=100, description="CPU usage percentage")
    memory_percent: float = Field(ge=0, le=100, description="Memory usage percentage")
    disk_percent: float = Field(ge=0, le=100, description="Disk usage percentage")
    status: str = Field(description="Overall status: healthy, warning, or critical")


@flock_type
class HealthAlert(BaseModel):
    """Alert generated when system health is poor."""
    timestamp: datetime
    severity: str = Field(description="Alert severity: warning or critical")
    metric: str = Field(description="Which metric triggered the alert")
    value: float = Field(description="Current value")
    threshold: float = Field(description="Threshold that was exceeded")
    message: str = Field(description="Alert message")


# ============================================================================
# STEP 2: Create the Orchestrator
# ============================================================================

flock = Flock()


# ============================================================================
# STEP 3: Define Scheduled Agents
# ============================================================================
# Timer scheduling lets agents run WITHOUT input artifacts.
# They execute on a schedule: every N seconds, at specific times, or via cron.
#
# Key points:
# - Timer-triggered agents have NO input artifacts (ctx.artifacts = [])
# - They can still access blackboard context via .consumes()
# - Use ctx.timer_iteration to track execution count
# - Use ctx.fire_time to know when the timer fired
# ============================================================================

# Agent 1: Runs every 30 seconds to collect metrics
metrics_collector = (
    flock.agent("metrics_collector")
    .description(
        "Collects system health metrics every 30 seconds. "
        "Generate realistic CPU (10-90%), memory (30-80%), and disk (40-70%) usage."
    )
    .schedule(every=timedelta(seconds=30))  # Periodic execution
    .publishes(SystemMetrics)
)

# Agent 2: Runs every minute to check for alerts
# This agent consumes SystemMetrics but is ALSO timer-scheduled
# So it runs on schedule AND when metrics are published
alert_monitor = (
    flock.agent("alert_monitor")
    .description(
        "Monitors system metrics and generates alerts for unhealthy conditions. "
        "Triggers warning if any metric > 80%, critical if > 90%."
    )
    .schedule(every=timedelta(minutes=1))  # Also runs on timer
    .consumes(SystemMetrics)  # But also reacts to metrics
    .publishes(HealthAlert)
)


# ============================================================================
# STEP 4: Run and Observe Scheduled Execution
# ============================================================================

async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("=" * 70)
    print("⏰ TIMER SCHEDULING EXAMPLE - System Health Monitor")
    print("=" * 70)
    print()
    print("📊 Scheduled Agents:")
    print("   • metrics_collector: Runs every 30 seconds")
    print("   • alert_monitor: Runs every 1 minute")
    print()
    print("⏳ Running for 2 minutes to demonstrate scheduled execution...")
    print("   (Press Ctrl+C to stop early)")
    print()
    
    # Run with timeout - timers run indefinitely
    # For demo, we'll run for 2 minutes
    try:
        await flock.run_until_idle(timeout=120)  # 2 minutes
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    
    # Retrieve collected metrics and alerts
    metrics = await flock.store.get_by_type(SystemMetrics)
    alerts = await flock.store.get_by_type(HealthAlert)
    
    print()
    print("=" * 70)
    print("📊 COLLECTED DATA")
    print("=" * 70)
    
    print(f"\n📈 System Metrics Collected: {len(metrics)}")
    if metrics:
        print("\n   Recent Metrics:")
        for metric in metrics[-5:]:  # Show last 5
            print(f"   • {metric.timestamp.strftime('%H:%M:%S')}: "
                  f"CPU={metric.cpu_percent:.1f}% "
                  f"Memory={metric.memory_percent:.1f}% "
                  f"Disk={metric.disk_percent:.1f}% "
                  f"Status={metric.status}")
    
    print(f"\n🚨 Health Alerts Generated: {len(alerts)}")
    if alerts:
        print("\n   Alerts:")
        for alert in alerts[-5:]:  # Show last 5
            print(f"   • [{alert.severity.upper()}] {alert.metric}: "
                  f"{alert.value:.1f}% (threshold: {alert.threshold}%)")
            print(f"     {alert.message}")
    
    print()
    print("=" * 70)
    print("💡 Key Insights:")
    print("   - metrics_collector ran ~4 times (every 30s for 2min)")
    print("   - alert_monitor ran ~2 times (every 1min for 2min)")
    print("   - Timers run independently of artifact triggers")
    print("   - Agents can be BOTH timer-scheduled AND artifact-triggered!")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to watch scheduled agents!")
    print()
    print("💡 Watch agents execute automatically on their schedules!")
    print("   metrics_collector fires every 30 seconds")
    print("   alert_monitor fires every 1 minute")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# 🎓 NOW IT'S YOUR TURN!
# ============================================================================
# 
# EXPERIMENT 1: Different Schedule Intervals
# -------------------------------------------
# Try different intervals:
#   .schedule(every=timedelta(seconds=10))   # Every 10 seconds
#   .schedule(every=timedelta(minutes=5))    # Every 5 minutes
#   .schedule(every=timedelta(hours=1))      # Every hour
#
# How does execution frequency change?
#
#
# EXPERIMENT 2: Scheduled Execution at Specific Time
# ---------------------------------------------------
# Run agent at a specific time:
#   daily_report = (
#       flock.agent("daily_report")
#       .description("Generates daily summary report at 9 AM")
#       .schedule(at=time(hour=9, minute=0))  # 9:00 AM every day
#       .publishes(DailyReport)
#   )
#
# What happens if you run this before 9 AM? After 9 AM?
#
#
# EXPERIMENT 3: Cron Expressions
# -------------------------------
# Use cron for complex schedules:
#   workday_reports = (
#       flock.agent("workday_reports")
#       .description("Runs every weekday at 9 AM")
#       .schedule(cron="0 9 * * 1-5")  # Mon-Fri at 9 AM
#       .publishes(DailyReport)
#   )
#
# Cron format: "minute hour day month weekday"
# Try: "0 */2 * * *" (every 2 hours)
# Try: "*/15 * * * *" (every 15 minutes)
#
#
# EXPERIMENT 4: Timer with Initial Delay
# ----------------------------------------
# Wait before first execution:
#   delayed_monitor = (
#       flock.agent("delayed_monitor")
#       .schedule(
#           every=timedelta(minutes=1),
#           after=timedelta(seconds=30)  # Wait 30s before first run
#       )
#       .publishes(SystemMetrics)
#   )
#
# When does the first execution happen?
#
#
# EXPERIMENT 5: Limited Repeats
# -------------------------------
# Run only N times:
#   limited_collector = (
#       flock.agent("limited_collector")
#       .schedule(
#           every=timedelta(seconds=10),
#           max_repeats=5  # Run 5 times then stop
#       )
#       .publishes(SystemMetrics)
#   )
#
# How many times does it execute?
#
#
# EXPERIMENT 6: Timer + Context Filtering
# -----------------------------------------
# Schedule agent that only sees recent artifacts:
#   recent_alert_monitor = (
#       flock.agent("recent_alert_monitor")
#       .schedule(every=timedelta(minutes=1))
#       .consumes(
#           SystemMetrics,
#           where=lambda m: (datetime.now() - m.timestamp).total_seconds() < 60
#       )
#       .publishes(HealthAlert)
#   )
#
# This agent runs every minute but only processes metrics from the last minute!
#
#
# EXPERIMENT 7: Access Timer Metadata
# ------------------------------------
# Use timer context in agent logic:
#   from flock.core.runtime import AgentContext
#
#   async def my_agent(ctx: AgentContext) -> SystemMetrics:
#       if ctx.trigger_type == "timer":
#           iteration = ctx.timer_iteration  # 0, 1, 2, ...
#           fire_time = ctx.fire_time        # datetime when fired
#           # Generate metrics based on iteration
#       return SystemMetrics(...)
#
# How can you use iteration to vary metrics?
#
#
# CHALLENGE: Build a Complete Monitoring System
# ----------------------------------------------
# Create a production monitoring system:
#   1. Metrics collector: Runs every 30s, collects system metrics
#   2. Alert monitor: Runs every 1min, checks for issues
#   3. Daily reporter: Runs at 9 AM daily, generates summary
#   4. Weekly analyzer: Runs Monday 8 AM, analyzes week's data
#   5. Health checker: Runs every 5min, validates system health
#
# How do you coordinate these? What visibility/tags do you use?
# How do you prevent duplicate alerts?
#
# ============================================================================

