import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.core.context_provider import FilteredContextProvider
from flock.core.store import FilterConfig


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
    urgent_only_provider = FilteredContextProvider(
        FilterConfig(tags={"urgent"}),  # Only artifacts with "urgent" tag
        limit=100,  # Maximum artifacts to return
    )

    flock = Flock(
        context_provider=urgent_only_provider  # 🎯 ALL agents will use this!
    )

    summarizer = (
        flock.agent("summarizer")
        .description("Summarizes tasks it can see")
        .consumes(Task)
        .publishes(TaskSummary)
    )

    await flock.publish(Task(name="DEBUG", priority=1, tags={"auth-service"}))
    await flock.run_until_idle()


asyncio.run(main(), debug=True)
