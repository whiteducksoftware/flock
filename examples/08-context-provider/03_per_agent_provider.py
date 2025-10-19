"""
🎯 Example 03: Per-Agent Provider Overrides

This example demonstrates how individual agents can override the global provider.
You'll see provider priority: per-agent > global > default.

⚠️  CRITICAL DISTINCTION - Read This First!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Context Provider Filtering ≠ Subscription Filtering - These are TWO different things!

1. SUBSCRIPTION FILTERING (controls WHEN agent triggers):
   agent.consumes(LogEntry, tags={"ERROR"})  # ← Triggers ONLY for ERROR logs

2. CONTEXT PROVIDER FILTERING (controls WHAT agent sees in context):
   FilteredContextProvider(tags={"ERROR"})  # ← Shows ONLY ERROR logs in context

In this example:
- All agents subscribe to ALL log entries: .consumes(LogEntry)
- All agents TRIGGER 8 times (once for each published log entry)
- Each agent SEES different logs in context (based on their provider)
- Result: Same triggering, different context per agent

If you want agents to trigger on DIFFERENT log levels, use subscription filters!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Concepts:
- Per-agent provider configuration
- Provider priority hierarchy
- agent.context_provider attribute
- Different filtering for different agents

Run: uv run examples/08-context-provider/03_per_agent_provider.py
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.core.context_provider import FilteredContextProvider
from flock.core.store import FilterConfig
from flock.core.visibility import PublicVisibility


# Define our data models
class LogEntry(BaseModel):
    """A log entry with level and message."""

    level: str  # "DEBUG", "INFO", "WARN", "ERROR"
    message: str
    service: str


class LogAnalysis(BaseModel):
    """Analysis of logs seen by an agent."""

    agent_name: str
    entries_analyzed: int
    levels_seen: list[str]
    most_common_level: str


async def main():
    """Demonstrate per-agent provider overrides."""
    print("🎯 PER-AGENT PROVIDER OVERRIDE DEMO")
    print("=" * 60)
    print()

    # Set up global provider: only show ERROR logs in CONTEXT
    print("🔧 Configuration:")
    print("   Global Context Provider: Only show ERROR logs")
    print("   ⚠️  This filters CONTEXT, not triggering!")
    print()

    global_provider = FilteredContextProvider(FilterConfig(tags={"ERROR"}), limit=100)

    flock = Flock(
        context_provider=global_provider  # Default for all agents
    )

    # Create agents with different provider configurations
    print("👥 Creating agents...")
    print()

    # Agent 1: Uses global provider (ERROR only in CONTEXT)
    error_analyzer = (
        flock.agent("error_analyzer")
        .description("Analyzes errors (uses global provider)")
        .consumes(LogEntry)  # ⚠️ Subscribes to ALL log entries (triggers 8 times)
        .publishes(LogAnalysis)
        .agent
    )
    print("   ✅ error_analyzer:")
    print("      Subscription: ALL logs (.consumes(LogEntry))")
    print("      Context: Only ERROR logs (global provider)")

    # Agent 2: Override with custom provider (WARN + ERROR in CONTEXT)
    warn_and_error_provider = FilteredContextProvider(
        FilterConfig(tags={"WARN", "ERROR"}),  # More permissive context!
        limit=100,
    )

    warn_analyzer = (
        flock.agent("warn_analyzer")
        .description("Analyzes warnings and errors")
        .consumes(LogEntry)  # ⚠️ Subscribes to ALL log entries (triggers 8 times)
        .publishes(LogAnalysis)
        .agent
    )
    # Override the global provider for this specific agent
    warn_analyzer.context_provider = warn_and_error_provider
    print("   ✅ warn_analyzer:")
    print("      Subscription: ALL logs (.consumes(LogEntry))")
    print("      Context: WARN + ERROR logs (custom provider)")

    # Agent 3: Override to see everything in CONTEXT
    all_logs_provider = FilteredContextProvider(
        FilterConfig(tags={"DEBUG", "INFO", "WARN", "ERROR"}), limit=100
    )

    full_analyzer = (
        flock.agent("full_analyzer")
        .description("Analyzes all logs")
        .consumes(LogEntry)  # ⚠️ Subscribes to ALL log entries (triggers 8 times)
        .publishes(LogAnalysis)
        .agent
    )
    full_analyzer.context_provider = all_logs_provider
    print("   ✅ full_analyzer:")
    print("      Subscription: ALL logs (.consumes(LogEntry))")
    print("      Context: ALL logs (custom provider)")
    print()
    print("⚠️  IMPORTANT: All 3 agents TRIGGER 8 times (once per log)")
    print("   They just SEE different logs in their context!")
    print()

    # Publish logs with different levels
    print("📤 Publishing log entries...")
    print()

    logs_data = [
        ("DEBUG", "Entering function main()", "auth-service"),
        ("INFO", "User logged in successfully", "auth-service"),
        ("WARN", "Rate limit approaching", "api-gateway"),
        ("DEBUG", "Cache hit for key:user123", "cache-service"),
        ("ERROR", "Database connection failed", "db-service"),
        ("INFO", "Request processed in 45ms", "api-gateway"),
        ("WARN", "Memory usage at 85%", "worker-service"),
        ("ERROR", "Failed to send email", "notification-service"),
    ]

    for level, message, service in logs_data:
        log_entry = LogEntry(level=level, message=message, service=service)

        # Tag with level so FilteredContextProvider can filter
        await flock.publish(
            log_entry,
            visibility=PublicVisibility(),
            tags={level},  # 🎯 Tag with log level!
        )

        # Color-code output
        emoji_map = {"DEBUG": "🔍", "INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌"}
        print(f"{emoji_map[level]} [{level}] {message}")

    print()

    # Wait for processing
    print("⏳ Agents processing...")
    await flock.run_until_idle()
    print()

    # Retrieve and display results
    print("📊 RESULTS:")
    print("=" * 60)
    print()

    all_artifacts = await flock.store.list()
    analyses = [a for a in all_artifacts if "LogAnalysis" in a.type]

    # Sort by agent name for consistent output
    analyses.sort(key=lambda a: a.payload["agent_name"])

    for analysis_artifact in analyses:
        analysis = LogAnalysis(**analysis_artifact.payload)

        # Visual indicator of provider used
        if "error_analyzer" in analysis.agent_name:
            provider_info = "Global Provider (ERROR only)"
        elif "warn_analyzer" in analysis.agent_name:
            provider_info = "Custom Provider (WARN + ERROR)"
        else:
            provider_info = "Custom Provider (ALL levels)"

        print(f"👤 Agent: {analysis.agent_name}")
        print(f"   Provider: {provider_info}")
        print(f"   Entries analyzed: {analysis.entries_analyzed}")
        print(f"   Levels seen: {', '.join(analysis.levels_seen)}")
        print(f"   Most common: {analysis.most_common_level}")
        print()

    print()
    print("🎯 KEY TAKEAWAYS:")
    print("=" * 60)
    print("1. Context Provider ≠ Subscription Filter (DIFFERENT PURPOSES!)")
    print()
    print("2. What happened in this example:")
    print("   - ALL agents TRIGGERED 8 times (once per log, .consumes(LogEntry))")
    print("   - Each agent SAW different logs in context (per-agent providers)")
    print("     • error_analyzer saw 2 logs (ERROR only)")
    print("     • warn_analyzer saw 4 logs (WARN + ERROR)")
    print("     • full_analyzer saw 8 logs (ALL levels)")
    print()
    print("3. Per-agent providers OVERRIDE global provider")
    print("4. Provider priority: per-agent > global > default")
    print("5. Each agent gets customized CONTEXT (not customized triggering!)")
    print()
    print("⚠️  COMMON MISTAKE:")
    print("   Don't use context providers to control TRIGGERING!")
    print("   Use subscription filters: .consumes(LogEntry, tags={'ERROR'})")
    print()
    print("💡 USE CONTEXT PROVIDERS FOR:")
    print("   - Different agents need different CONTEXT visibility")
    print("   - Security levels vary by agent role (RBAC in context)")
    print("   - Performance optimization (limit context size per agent)")
    print()
    print("💡 USE SUBSCRIPTION FILTERS FOR:")
    print("   - Different agents trigger on DIFFERENT events")
    print("   - Routing and conditional execution")


if __name__ == "__main__":
    asyncio.run(main())
