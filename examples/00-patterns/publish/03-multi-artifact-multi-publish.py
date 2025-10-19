import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


@flock_type
class Idea(BaseModel):
    story_idea: str


@flock_type
class Character(BaseModel):
    name: str
    potential_actors: dict[str, str] = Field(..., description="Potential actors and reasons why they are a good fit")
    backstory: str

@flock_type
class Movie(BaseModel):
    title: str
    genre: str
    director: str
    characters: list[Character]
    plot_summary: str


@flock_type
class MovieScript(BaseModel):
    characters: list[str] = Field(min_length=5)
    chapter_headings: list[str] = Field(min_length=5)
    scenes: list[str] = Field(min_length=5)
    pages: int = Field(ge=50, le=200)


@flock_type
class MovieCampaign(BaseModel):
    taglines: list[str] = Field(..., description="Catchy phrases to promote the movie. IN ALL CAPS")
    poster_descriptions: list[str] = Field(max_length=3)


flock = Flock()


# Multi-Publish
multi_master = (
    flock.agent("multi_master").consumes(Idea).publishes(Movie).publishes(MovieScript).publishes(MovieCampaign)
)


async def main():
    idea = Idea(story_idea="An action thriller set in space")
    await flock.publish(idea)
    await flock.run_until_idle()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
