# example_script.py
import asyncio

from pydantic import BaseModel, Field

from flock.core.logging.logging import configure_logging
from flock.core.registry.decorators import flock_type
from flock.core.util.hydrator import flockclass

configure_logging("DEBUG", "DEBUG")

@flock_type
class Movie(BaseModel):
    title: str
    year: int
    rating: float
    cast: list[str]
    director: str


# --- Define your Pydantic Models ---
@flockclass(model="openai/gpt-5")
class RandomPerson(BaseModel):
    name: str | None = None
    age: int | None = None
    bio: str | None = Field(default=None, description="A short biography")
    job: str | None = None
    fav_animal: str | None = None
    lucky_numbers: list[int] | None = None
    favorite_movies: list[Movie] | None = Field(
        default=None, description="Favorite three movies"
    )


@flockclass(model="openai/gpt-5")
class BlogPostIdea(BaseModel):
    topic: str | None = None
    target_audience: str | None = None
    key_points: list[str] | None = None
    catchy_title: str | None = None


async def main():
    print("--- Hydrating Person ---")
    # Create an instance with some initial data
    person = RandomPerson(
        job="Software Engineer",
    )  # Age is provided, others are None
    print(f"Before hydration: {person}")

    hydrated_person = person.hydrate()

    print(f"After hydration:  {hydrated_person}")
    print(f"Jeff's Job: {hydrated_person.job}")
    print("-" * 20)

    print("\n--- Hydrating Blog Post Idea ---")
    idea = BlogPostIdea(topic="Sustainable Urban Gardening")
    print(f"Before hydration: {idea}")

    hydrated_idea = idea.hydrate()
    print(f"After hydration:  {hydrated_idea}")
    print(f"Catchy Title: {hydrated_idea.catchy_title}")
    print("-" * 20)

    # --- Example: Hydrating from scratch ---
    print("\n--- Hydrating Person (from scratch) ---")
    person_scratch = RandomPerson()  # No fields provided
    print(f"Before hydration: {person_scratch}")
    hydrated_person_scratch = person_scratch.hydrate()
    print(f"After hydration:  {hydrated_person_scratch}")
    print("-" * 20)


if __name__ == "__main__":
    # Make sure necessary API keys are set in environment variables!
    # e.g., OPENAI_API_KEY
    asyncio.run(main())
