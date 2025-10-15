import asyncio

from pydantic import BaseModel

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class Idea(BaseModel):
    story_idea: str


@flock_type
class Movie(BaseModel):
    title: str
    genre: str
    director: str
    cast: list[str]
    plot_summary: str


@flock_type
class Book(BaseModel):
    title: str
    author: str
    genre: str
    summary: str


flock = Flock()


# Multi-Publish
multi_master = flock.agent("multi_master").consumes(Idea).publishes(Movie, Book)


async def main():
    idea = Idea(story_idea="An action thriller set in space")
    await flock.publish(idea)
    await flock.run_until_idle()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
