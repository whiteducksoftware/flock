import asyncio

from pydantic import BaseModel

from flock import Flock
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



flock = Flock()

# Single Publish
fan_out_movie_master = flock.agent("fan_out_movie_master").consumes(Idea).publishes(Movie,fan_out=4)


async def main():
    idea = Idea(story_idea="A sci-fi about cats discovering how to use AI")
    await flock.publish(idea)
    await flock.run_until_idle()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
