import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


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

flock = Flock("openai/gpt-4.1")

movie_master = (
    flock.agent("movie_master")
    .description("Creates Oscar-worthy movie details from a movie idea.")
    .consumes(MovieIdea)
    .publishes(Movie)
)

async def main():
    movie_idea = MovieIdea(idea="A movie about cat owners during the rise of AI")
    print(f"🎬 Pitching: {movie_idea.idea}")
    print("🎭 Movie master is writing the screenplay...\n")
    await flock.publish(movie_idea)
    await flock.run_until_idle()
    movies = await flock.store.get_by_type(Movie)
    if movies:
        movie = movies[0]
        print("✅ Movie created!\n")
        print(f"🎬 Title: {movie.fun_title}")
        print(f"⏱️  Runtime: {movie.runtime} minutes")
        print(f"🎭 Genre: {movie.genre}")
        print(f"👥 Characters: {len(movie.characters)}")
        print(f"\n📖 Synopsis:\n{movie.synopsis}\n")
        if movie.characters:
            char = movie.characters[0]
            print("⭐ Featured Character:")
            print(f"   Name: {char.name} {char.emoji}")
            print(f"   Role: {char.role}")
            print(f'   Catchphrase: "{char.catchphrase}"')
            if char.possible_actors:
                actor, reason = next(iter(char.possible_actors.items()))
                print(f"   Casting idea: {actor} - {reason}")
    else:
        print("❌ No movie was created!")

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
