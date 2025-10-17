"""
🌍 Example 02: Global Provider Configuration

This example shows how to configure a custom Context Provider globally for all agents.
You'll learn about FilteredContextProvider and how to apply consistent filtering rules.

⚠️  CRITICAL DISTINCTION - Read This First!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Context Provider Filtering ≠ Subscription Filtering - These are TWO different things!

1. SUBSCRIPTION FILTERING (controls WHEN agent triggers):
   agent.consumes(Task, tags={"urgent"})  # ← Triggers ONLY for urgent tasks

2. CONTEXT PROVIDER FILTERING (controls WHAT agent sees in context):
   FilteredContextProvider(tags={"urgent"})  # ← Shows ONLY urgent tasks in context

In this example:
- Agent subscribes to ALL tasks: .consumes(Task)
- Agent TRIGGERS 6 times (once for each published task)
- Agent SEES only 3 urgent tasks in context (filtered by provider)
- Result: Agent runs 6 times but sees filtered context each time

If you want to trigger ONLY on urgent tasks, use subscription filters instead!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

    # Create a FilteredContextProvider that filters what agents SEE in context
    print("🔧 Configuring global provider...")
    print("   ⚠️  Context Provider Filter: Only SHOW tasks tagged as 'urgent'")
    print("   ⚠️  This does NOT control triggering - agents still trigger on ALL tasks!")
    print()

    urgent_only_provider = FilteredContextProvider(
        FilterConfig(tags={"urgent"}),  # Filter context: only show urgent artifacts
        limit=100  # Maximum artifacts to return
    )

    # Create orchestrator WITH global provider
    flock = Flock(
        context_provider=urgent_only_provider  # 🎯 ALL agents will use this!
    )

    # Create a shared correlation ID for this conversation
    from uuid import uuid4
    conversation_id = uuid4()

    # Create agents - they'll all use the global provider for CONTEXT filtering
    summarizer = (
        flock.agent("summarizer")
        .description("Summarizes tasks it can see")
        .consumes(Task)  # ⚠️ Subscribes to ALL tasks (triggers 6 times)
        .publishes(TaskSummary)
    )

    print("📋 Agent Configuration:")
    print("   Subscription: ALL tasks (.consumes(Task))")
    print("   Context Filter: Only urgent tasks (from global provider)")
    print("   Result: Triggers 6 times, sees 3 urgent tasks each time")
    print()

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
            tags=tags  # 🎯 These tags are used for CONTEXT filtering!
        )

        tag_indicator = "🔥 URGENT" if "urgent" in tags else "📝 Normal"
        trigger_msg = "(triggers agent)" if "urgent" in tags else "(triggers agent, but filtered from context)"
        print(f"{tag_indicator} Published: {name} (priority={priority}) {trigger_msg}")

    print()

    # Wait for processing
    print("⏳ Agent processing...")
    print("   ⚠️  Agent will TRIGGER 6 times (once per task)")
    print("   ⚠️  Agent will SEE only 3 urgent tasks in context each time")
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
    print("1. Context Provider ≠ Subscription Filter (DIFFERENT PURPOSES!)")
    print()
    print("2. What happened in this example:")
    print("   - Agent TRIGGERED 6 times (once per task, because .consumes(Task))")
    print("   - Agent SAW only 3 urgent tasks in context (filtered by provider)")
    print("   - Agent produced 6 summaries (one per trigger, each seeing same 3 tasks)")
    print()
    print("3. Global provider filters CONTEXT for ALL agents")
    print("4. FilterConfig provides declarative context filtering")
    print("5. Visibility is STILL enforced on top of filtering!")
    print()
    print("⚠️  COMMON MISTAKE:")
    print("   Don't use context providers to control TRIGGERING!")
    print("   Use subscription filters instead: .consumes(Task, tags={'urgent'})")
    print()
    print("💡 USE CONTEXT PROVIDERS FOR:")
    print("   - Filtering what agents SEE in their context")
    print("   - Organization-wide security policies (e.g., redaction)")
    print("   - Performance optimization (limiting context size)")
    print()
    print("💡 USE SUBSCRIPTION FILTERS FOR:")
    print("   - Controlling WHEN agents trigger")
    print("   - Agent-specific routing and filtering")


if __name__ == "__main__":
    asyncio.run(main())
