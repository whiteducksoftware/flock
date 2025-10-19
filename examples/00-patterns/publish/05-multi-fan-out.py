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
    title: str
    characters: list[str] = Field(min_length=5)
    chapter_headings: list[str] = Field(min_length=5)
    scenes: list[str] = Field(min_length=5)
    pages: int = Field(ge=50, le=200)


@flock_type
class MovieCampaign(BaseModel):
    title: str
    taglines: list[str] = Field(..., description="Catchy phrases to promote the movie. IN ALL CAPS")
    poster_descriptions: list[str] = Field(max_length=3)


flock = Flock()


# Multi-Publish
# - 9 complex artifacts
# - ~100+ individual fields across all artifacts
# - Pydantic validation on every field (min_length, ge/le constraints, custom descriptions)
# - All generated coherently in ONE LLM call!
multi_master = (
    flock.agent("multi_master").consumes(Idea).publishes(Movie, MovieScript, MovieCampaign, fan_out=3)
)

# compare with

# multi_master = (
#     flock.agent("multi_master").consumes(Idea).publishes(Movie, MovieScript, MovieCampaign).publishes(Movie, MovieScript, MovieCampaign).publishes(Movie, MovieScript, MovieCampaign)
# )

# or

# multi_master = (
#     flock.agent("multi_master").consumes(Idea).publishes(Movie, fan_out=3).publishes(MovieScript, fan_out=3).publishes(MovieCampaign, fan_out=3)
# )

async def main():
    idea = Idea(story_idea="An action thriller set in space")
    await flock.publish(idea)
    await flock.run_until_idle()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
