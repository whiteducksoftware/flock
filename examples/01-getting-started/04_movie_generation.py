"""
Getting Started: Movie Generation with Validation

This example demonstrates creating complex structured outputs with nested types
and field validation rules.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class MovieIdea(BaseModel):
    idea: str


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


flock = Flock()

movie_master = (
    flock.agent("movie_master")
    .description("Creates Oscar-worthy movie details from a movie idea.")
    .consumes(MovieIdea)
    .publishes(Movie)
)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    movie_idea = MovieIdea(idea="A movie about cat owners during the rise of AI")
    await flock.publish(movie_idea)
    await flock.run_until_idle()
    movies = await flock.store.get_by_type(Movie)
    print(f"🎬 Title: {movies[0].fun_title}")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
