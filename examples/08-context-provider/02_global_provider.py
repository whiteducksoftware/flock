"""
🌍 Example 02: Global Provider Configuration

This example shows how to configure a custom Context Provider globally for all agents.
You'll learn about FilteredContextProvider and how to apply consistent filtering rules.

Concepts:
- FilterConfig for declarative filtering
- FilteredContextProvider with tag-based filtering
- Global provider configuration via Flock()
- Consistent filtering across all agents

Run: uv run examples/08-context-provider/02_global_provider.py
"""

import asyncio
import sys
from pydantic import BaseModel

from flock import Flock
from flock.context_provider import FilteredContextProvider
from flock.store import FilterConfig
from flock.visibility import PublicVisibility

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


# Define our data models
class Task(BaseModel):
    """A task with priority and tags."""

    name: str
    priority: int
    tags: set[str] = set()


class TaskSummary(BaseModel):
    """Summary of tasks processed."""

    agent_name: str
    tasks_seen: int
    task_names: list[str]
    average_priority: float


async def main():
    """Demonstrate global provider configuration with filtering."""
    print("🌍 GLOBAL CONTEXT PROVIDER DEMO")
    print("=" * 60)
    print()

    # Create a FilteredContextProvider that only shows "urgent" tasks
    print("🔧 Configuring global provider...")
    print("   Filter: Only show tasks tagged as 'urgent'")
    print()

    urgent_only_provider = FilteredContextProvider(
        FilterConfig(tags={"urgent"}),  # Only artifacts with "urgent" tag
        limit=100  # Maximum artifacts to return
    )

    # Create orchestrator WITH global provider
    flock = Flock(
        "openai/gpt-4o-mini",
        context_provider=urgent_only_provider  # 🎯 ALL agents will use this!
    )

    # Create a shared correlation ID for this conversation
    from uuid import uuid4
    conversation_id = uuid4()

    # Create agents - they'll all use the global provider
    summarizer = (
        flock.agent("summarizer")
        .description("Summarizes tasks it can see")
        .consumes(Task)
        .publishes(TaskSummary)
        .agent
    )

    # Publish various tasks with different tags
    print("📤 Publishing tasks...")
    print()

    tasks_data = [
        ("Update docs", 1, {"documentation", "low-priority"}),
        ("Fix critical bug", 10, {"urgent", "bug", "critical"}),
        ("Refactor code", 3, {"refactoring", "nice-to-have"}),
        ("Security patch", 9, {"urgent", "security"}),
        ("Add tests", 2, {"testing", "low-priority"}),
        ("Deploy hotfix", 10, {"urgent", "deployment"}),
    ]

    for name, priority, tags in tasks_data:
        task = Task(name=name, priority=priority, tags=tags)

        # Tag the artifact so FilteredContextProvider can filter by it
        await flock.publish(
            task,
            visibility=PublicVisibility(),
            correlation_id=conversation_id,
            tags=tags  # 🎯 These tags are used for filtering!
        )

        tag_indicator = "🔥 URGENT" if "urgent" in tags else "📝 Normal"
        print(f"{tag_indicator} Published: {name} (priority={priority})")

    print()

    # Wait for processing
    print("⏳ Agent processing (with global provider filter)...")
    await flock.run_until_idle()
    print()

    # Retrieve results
    print("📊 RESULTS:")
    print("=" * 60)
    print()

    all_artifacts = await flock.store.list()
    summaries = [a for a in all_artifacts if "TaskSummary" in a.type]

    for summary_artifact in summaries:
        summary = TaskSummary(**summary_artifact.payload)
        print(f"👤 Agent: {summary.agent_name}")
        print(f"   Tasks seen: {summary.tasks_seen}")
        print(f"   Average priority: {summary.average_priority:.1f}")
        print(f"   Task names:")
        for task_name in summary.task_names:
            print(f"     🔥 {task_name}")
        print()

    print()
    print("🎯 KEY TAKEAWAYS:")
    print("=" * 60)
    print("1. Global provider applies to ALL agents")
    print("2. Agent only saw 3 tasks (the urgent ones)")
    print("3. FilterConfig provides declarative filtering")
    print("4. Tags enable flexible categorization")
    print("5. Visibility is STILL enforced on top of filtering!")
    print()
    print("💡 TIP: Global providers are perfect for:")
    print("   - Consistent filtering policies")
    print("   - Organization-wide rules")
    print("   - Security boundaries")


if __name__ == "__main__":
    asyncio.run(main())
