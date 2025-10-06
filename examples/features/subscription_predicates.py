"""
Feature Example: Subscription Predicates

Validates: where= predicates for filtering which artifacts agents consume
"""

import asyncio

from pydantic import BaseModel, Field

from flock.components import EngineComponent
from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.runtime import EvalInputs


@flock_type
class Task(BaseModel):
    """A task with priority level."""

    name: str = Field(description="Task name")
    priority: int = Field(ge=1, le=5, description="Priority (1=low, 5=high)")


@flock_type
class Report(BaseModel):
    """A report generated after task processing."""

    text: str = Field(description="Report text")


# Custom engine that processes tasks and generates reports
class TaskProcessor(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> Report:
        # Just return the model - framework handles EvalResult wrapping
        task = inputs.first_as(Task)
        return Report(text=f"== Report ==\nProcessed: {task.name}")


async def main():
    print("🔍 Feature: Subscription Predicates\n")

    orchestrator = Flock()

    # Agent 1: Only processes high-priority tasks (priority >= 4)
    (
        orchestrator.agent("high_priority")
        .description("Handles urgent tasks")
        .consumes(Task, where=lambda t: t.priority >= 4)
        .publishes(Report)
        .with_engines(TaskProcessor())
    )

    # Agent 2: Only processes low-priority tasks (priority <= 2)
    (
        orchestrator.agent("low_priority")
        .description("Handles routine tasks")
        .consumes(Task, where=lambda t: t.priority <= 2)
        .publishes(Report)
        .with_engines(TaskProcessor())
    )

    # Create tasks with different priorities
    tasks = [
        Task(name="Critical bug fix", priority=5),  # High priority only
        Task(name="Security patch", priority=4),  # High priority only
        Task(name="Code review", priority=3),  # Neither (filtered out)
        Task(name="Update documentation", priority=2),  # Low priority only
        Task(name="Typo fix", priority=1),  # Low priority only
    ]

    # Submit all tasks

    await orchestrator.publish_many(tasks)
    await orchestrator.run_until_idle()

    all_reports = await orchestrator.store.list_by_type("Report")

    for r in all_reports:
        print(f"📝 {r.payload['text']} (produced by {r.produced_by})")


if __name__ == "__main__":
    asyncio.run(main())
