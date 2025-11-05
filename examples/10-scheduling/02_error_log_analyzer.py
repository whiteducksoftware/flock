"""
Timer Scheduling: Error Log Analyzer

This example demonstrates timer scheduling WITH context filtering.
The analyzer runs every 5 minutes and ONLY sees ERROR-level logs.

KEY CONCEPTS:
- .schedule() creates timer trigger
- .consumes(Type, where=...) filters blackboard context
- Agent sees ALL matching artifacts on blackboard (not just new ones)
- Separate log collector agent publishes logs continuously

PATTERN: Timer + Context Filter
USE CASE: Periodic analysis of specific artifact subsets, error monitoring, alerts
"""

import asyncio
import random
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.utils.runtime import Context


# ============================================================================
# CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# TYPE REGISTRATION: Define artifact types
# ============================================================================
@flock_type
class LogEntry(BaseModel):
    """A log message with severity level"""

    level: str = Field(description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    message: str = Field(description="Log message content")
    timestamp: datetime = Field(description="When the log was created")
    source: str = Field(description="Source component that generated the log")


@flock_type
class ErrorReport(BaseModel):
    """Analysis report of error logs"""

    error_count: int = Field(description="Number of error logs analyzed")
    error_messages: list[str] = Field(description="List of error messages")
    analysis: str = Field(description="AI-generated analysis of error patterns")
    report_time: datetime = Field(description="When the report was generated")
    iteration: int = Field(description="Timer iteration number")


# ============================================================================
# AGENT SETUP: Create log collector and error analyzer
# ============================================================================
flock = Flock()

# Agent 1: Continuously collect logs (simulated)
# This agent runs every 10 seconds and publishes various log entries
log_collector = (
    flock.agent("log_collector")
    .description(
        "Collects log entries from various system components. "
        "Generates logs at different severity levels for demonstration."
    )
    .schedule(every=timedelta(seconds=10))
    .publishes(LogEntry)
)


# Agent 2: Analyze errors every 5 minutes
# This agent is ALSO scheduled, but ONLY sees ERROR-level logs
# The where clause filters the blackboard context
error_analyzer = (
    flock.agent("error_analyzer")
    .description(
        "Analyzes ERROR-level logs every 5 minutes. "
        "Generates reports on error patterns and suggests fixes."
    )
    .schedule(every=timedelta(minutes=5))
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")  # Context filter!
    .publishes(ErrorReport)
)


# ============================================================================
# AGENT IMPLEMENTATIONS
# ============================================================================
@log_collector.implement
async def collect_logs(ctx: Context) -> list[LogEntry]:
    """
    Simulate collecting logs from various components.

    In production, this might:
    - Read from log files
    - Query a logging service
    - Receive logs from message queue
    """
    # Generate random log entries at different levels
    log_levels = ["DEBUG", "INFO", "INFO", "WARNING", "ERROR", "ERROR"]
    sources = ["api_server", "database", "auth_service", "cache", "worker"]

    log_messages = {
        "DEBUG": ["Connection pool status: healthy", "Cache hit rate: 95%"],
        "INFO": ["Request processed successfully", "User logged in"],
        "WARNING": ["Slow query detected", "High memory usage"],
        "ERROR": [
            "Database connection failed",
            "Authentication timeout",
            "Invalid API key",
            "Service unavailable",
        ],
    }

    logs = []
    for _ in range(random.randint(3, 8)):
        level = random.choice(log_levels)
        source = random.choice(sources)
        message = random.choice(log_messages.get(level, ["Unknown message"]))

        logs.append(
            LogEntry(
                level=level,
                message=f"[{source}] {message}",
                timestamp=datetime.now(),
                source=source,
            )
        )

    print(f"[Log Collector] Published {len(logs)} log entries")
    return logs


@error_analyzer.implement
async def analyze_errors(ctx: Context) -> ErrorReport:
    """
    Analyze ERROR-level logs from the blackboard.

    Timer + Context Filter Behavior:
    - ctx.trigger_type = "timer" (timer triggered, not artifact)
    - ctx.artifacts = []  (no input artifact)
    - ctx.get_artifacts(LogEntry) returns ONLY ERROR logs (due to where clause)
    - Sees ALL ERROR logs on blackboard, not just new ones

    This is different from artifact-triggered agents:
    - Artifact trigger: ctx.artifacts contains the triggering artifact
    - Timer trigger: ctx.artifacts is empty, use ctx.get_artifacts()
    """
    # Verify timer trigger
    assert ctx.trigger_type == "timer"
    assert ctx.artifacts == []

    # Get all ERROR logs from blackboard (filtered by where clause)
    error_logs = ctx.get_artifacts(LogEntry)

    print()
    print("=" * 70)
    print(f"[Error Analyzer] Timer fired - Iteration {ctx.timer_iteration}")
    print(f"[Error Analyzer] Found {len(error_logs)} ERROR logs on blackboard")
    print("=" * 70)

    if not error_logs:
        return ErrorReport(
            error_count=0,
            error_messages=[],
            analysis="No errors found during this period. System is healthy.",
            report_time=datetime.now(),
            iteration=ctx.timer_iteration,
        )

    # Extract error messages
    error_messages = [log.message for log in error_logs]

    # Log details for visibility
    for i, log in enumerate(error_logs[:5], 1):
        print(f"{i}. {log.message} (at {log.timestamp.strftime('%H:%M:%S')})")
    if len(error_logs) > 5:
        print(f"... and {len(error_logs) - 5} more errors")

    # Ask LLM to analyze error patterns
    analysis_prompt = f"""Analyze these {len(error_logs)} error logs and provide:
1. Common patterns or root causes
2. Severity assessment
3. Recommended actions

Error logs:
{chr(10).join(f"- {msg}" for msg in error_messages[:10])}
"""

    print("\nGenerating AI analysis...")

    return ErrorReport(
        error_count=len(error_logs),
        error_messages=error_messages,
        analysis=analysis_prompt,  # LLM will expand this
        report_time=datetime.now(),
        iteration=ctx.timer_iteration,
    )


# ============================================================================
# RUN: Execute the orchestrator
# ============================================================================
async def main_cli():
    """
    CLI mode: Demonstrate timer + context filtering

    Flow:
    1. log_collector runs every 10s, publishes various log levels
    2. error_analyzer runs every 5 minutes, sees ONLY ERROR logs
    3. Demo runs for 6 minutes to show at least 2 analysis cycles
    """
    print("=" * 70)
    print("ERROR LOG ANALYZER - Timer + Context Filter Demo")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    print()
    print("Two agents running:")
    print("  1. Log Collector: every 10 seconds (all log levels)")
    print("  2. Error Analyzer: every 5 minutes (ERROR logs only)")
    print()
    print("Watch how the analyzer ONLY sees ERROR-level logs!")
    print("Demo runs for 6 minutes to show 2 analysis cycles.")
    print("=" * 70)
    print()

    # Start orchestrator
    serve_task = asyncio.create_task(flock.serve())

    try:
        await asyncio.sleep(360)  # 6 minutes
    except KeyboardInterrupt:
        print("\n\nStopping error analyzer...")
    finally:
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass

    print()
    print("=" * 70)
    print("Error analysis demo complete!")
    print("=" * 70)


async def main_dashboard():
    """
    Dashboard mode: Visualize timer + context filtering

    The dashboard will show:
    - log_collector agent firing every 10s
    - LogEntry artifacts accumulating
    - error_analyzer agent firing every 5 minutes
    - ErrorReport artifacts generated
    """
    print("Starting Error Log Analyzer with Dashboard...")
    print("Dashboard will be available at: http://localhost:8344")
    print()
    print("What to watch:")
    print("  - log_collector timer: every 10 seconds")
    print("  - error_analyzer timer: every 5 minutes")
    print("  - Notice analyzer only consumes ERROR logs")
    print()
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
