"""
🎨 Example 04: Custom Filtering with FilterConfig

This example explores advanced FilterConfig options for declarative filtering.
You'll learn to combine multiple filter criteria for sophisticated context control.

Concepts:
- FilterConfig with multiple criteria
- Combining tags, types, and produced_by filters
- Complex filtering logic
- Declarative vs imperative filtering

Run: uv run examples/08-context-provider/04_custom_filtering.py
"""

import asyncio
from pydantic import BaseModel

from flock import Flock
from flock.context_provider import FilteredContextProvider
from flock.store import FilterConfig
from flock.visibility import PublicVisibility


# Define our data models
class Event(BaseModel):
    """An event from our system."""

    event_type: str  # "user_action", "system_alert", "metric"
    severity: str  # "low", "medium", "high"
    source: str
    description: str


class EventReport(BaseModel):
    """Report of events analyzed."""

    agent_name: str
    events_seen: int
    event_types: list[str]
    average_severity: str
    sources: list[str]


async def main():
    """Demonstrate advanced FilterConfig usage."""
    print("🎨 ADVANCED FILTERING WITH FILTERCONFIG")
    print("=" * 60)
    print()

    flock = Flock("openai/gpt-4o-mini")

    # Agent 1: High severity events only (tag-based)
    print("🔧 Configuring agents with different filters...")
    print()

    high_severity_provider = FilteredContextProvider(
        FilterConfig(tags={"high"}),
        limit=100
    )

    critical_monitor = (
        flock.agent("critical_monitor")
        .description("Monitors critical events only")
        .consumes(Event)
        .publishes(EventReport)
        .agent
    )
    critical_monitor.context_provider = high_severity_provider
    print("   🚨 critical_monitor: Filter by tags={'high'}")

    # Agent 2: System alerts from specific sources (tag + type)
    system_alert_provider = FilteredContextProvider(
        FilterConfig(
            tags={"medium", "high"},  # Multiple tags (OR logic)
            type_names={"Event"}  # Only Event type
        ),
        limit=100
    )

    alert_analyzer = (
        flock.agent("alert_analyzer")
        .description("Analyzes system alerts")
        .consumes(Event)
        .publishes(EventReport)
        .agent
    )
    alert_analyzer.context_provider = system_alert_provider
    print("   ⚠️  alert_analyzer: Filter by tags={'medium','high'} + type='Event'")

    # Agent 3: Events from trusted sources only (produced_by filter)
    # Note: For this demo, we'll use tags to simulate this since we control tags
    trusted_source_provider = FilteredContextProvider(
        FilterConfig(tags={"trusted-source"}),
        limit=100
    )

    security_auditor = (
        flock.agent("security_auditor")
        .description("Audits events from trusted sources")
        .consumes(Event)
        .publishes(EventReport)
        .agent
    )
    security_auditor.context_provider = trusted_source_provider
    print("   🔐 security_auditor: Filter by tags={'trusted-source'}")
    print()

    # Publish events with various characteristics
    print("📤 Publishing events with different tags...")
    print()

    events_data = [
        ("user_action", "low", "web-app", "User clicked button", {"low"}),
        ("system_alert", "high", "database", "Connection pool exhausted", {"high", "trusted-source"}),
        ("metric", "low", "api-gateway", "Response time: 50ms", {"low", "metric"}),
        ("system_alert", "medium", "cache", "Cache miss rate increased", {"medium"}),
        ("user_action", "low", "mobile-app", "User logged in", {"low"}),
        ("system_alert", "high", "auth-service", "Multiple failed login attempts", {"high", "trusted-source"}),
        ("metric", "medium", "worker", "Queue depth: 1000", {"medium", "metric"}),
        ("system_alert", "high", "payment-service", "Payment processing failed", {"high"}),
    ]

    for event_type, severity, source, description, tags in events_data:
        event = Event(
            event_type=event_type,
            severity=severity,
            source=source,
            description=description
        )

        await flock.publish(
            event,
            visibility=PublicVisibility(),
            tags=tags  # 🎯 Multiple tags for complex filtering!
        )

        # Visual indicator
        severity_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        trusted = "🔐" if "trusted-source" in tags else "  "
        print(f"{severity_emoji[severity]} {trusted} [{event_type}] {description}")

    print()

    # Wait for processing
    print("⏳ Agents processing with different filters...")
    await flock.run_until_idle()
    print()

    # Retrieve results
    print("📊 RESULTS:")
    print("=" * 60)
    print()

    all_artifacts = await flock.store.list()
    reports = [a for a in all_artifacts if "EventReport" in a.type]

    # Sort by agent name
    reports.sort(key=lambda a: a.payload["agent_name"])

    for report_artifact in reports:
        report = EventReport(**report_artifact.payload)

        print(f"👤 Agent: {report.agent_name}")
        print(f"   Events seen: {report.events_seen}")
        print(f"   Event types: {', '.join(set(report.event_types))}")
        print(f"   Sources: {', '.join(report.sources)}")
        print()

    print()
    print("🎯 KEY TAKEAWAYS:")
    print("=" * 60)
    print("1. FilterConfig supports multiple criteria:")
    print("   - tags: Filter by artifact tags (flexible categorization)")
    print("   - type_names: Filter by artifact type")
    print("   - produced_by: Filter by source agent")
    print("   - correlation_id: Filter by workflow")
    print()
    print("2. Criteria are combined with AND logic")
    print("3. Multiple values in same criterion use OR logic")
    print("4. critical_monitor saw 3 events (high severity only)")
    print("5. alert_analyzer saw 5 events (medium + high)")
    print("6. security_auditor saw 2 events (trusted sources only)")
    print()
    print("💡 FILTERING PATTERNS:")
    print("   - Security: Filter by trust level")
    print("   - Performance: Limit by relevance")
    print("   - Compliance: Track by source")
    print("   - Monitoring: Alert by severity")


if __name__ == "__main__":
    asyncio.run(main())
