import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


# 1. Define typed artifacts
@flock_type
class Idea(BaseModel):
    topic: str
    genre: str


@flock_type
class Movie(BaseModel):
    title: str = Field(description="Title in CAPS")
    runtime: int = Field(ge=200, le=400)
    synopsis: str


@flock_type
class Tagline(BaseModel):
    line: str


# 2. Create orchestrator
flock = Flock("openai/gpt-4.1")

# 3. Define agents (they auto-connect through the blackboard!)
movie = (
    flock.agent("movie")
    .description("Generate a compelling movie concept.")
    .consumes(Idea)
    .publishes(Movie)
)

tagline = (
    flock.agent("tagline")
    .description("Write a one-sentence marketing tagline.")
    .consumes(Movie)
    .publishes(Tagline)
)


# 4. Run!
async def main():
    idea = Idea(topic="cat agents collaborating!!!", genre="comedy")
    await flock.publish(idea)
    await flock.run_until_idle()
    print("✅ Movie and tagline generated!")


asyncio.run(main(), debug=True)
