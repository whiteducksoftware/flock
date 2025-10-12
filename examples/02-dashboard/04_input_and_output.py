import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class MovieIdea(BaseModel):
    idea: str = Field(default="A movie about cat owners during the rise of AI", description="A short description of a movie idea")

@flock_type
class Character(BaseModel):
    name: str
    role: str
    backstory: str
    catchphrase: str
    emoji: str
    possible_actors: dict[str, str] = Field(
        ...,
        description=(
            "A dictionary of possible actors for this character. "
            "Key = actor name, Value = reasoning with x/10 rating. "
            "Example: {'Ryan Gosling': 'Perfect deadpan delivery, 9/10'}"
        ),
    )

@flock_type
class Movie(BaseModel):
    fun_title: str = Field(..., description="A catchy and fun title for the movie. IN ALL CAPS")
    runtime: int = Field(
        ...,
        ge=200,
        le=240,
        description="Runtime in minutes. Epic films only - no short stuff!",
    )
    synopsis: str
    plot: str
    genre: Literal[
        "action",
        "sci-fi",
        "comedy",
        "drama",
        "horror",
        "romance",
        "thriller",
        "fantasy",
        "documentary",
    ]
    characters: list[Character] = Field(
        ...,
        min_length=5,
        max_length=10,
        description="Main characters with full backstories and casting ideas",
    )

flock = Flock("openai/gpt-4.1")

movie_master = (
    flock.agent("movie_master")
    .description("Creates Oscar-worthy movie details from a movie idea.")
    .consumes(MovieIdea)
    .publishes(Movie)
)


asyncio.run(flock.serve(dashboard=True), debug=True)
