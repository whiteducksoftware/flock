"""
🎬 THE MOVIE STUDIO: Complex Types Edition
===========================================

You've mastered the basics. Now let's level up with REAL complexity:
- Nested types (Characters inside Movies!)
- Field constraints (runtime MUST be 200-240 minutes)
- Literal types (genre can only be action, sci-fi, etc.)
- Rich descriptions that guide (but don't replace) schemas

🎯 THE QUESTION:
"How do I express complex business logic without writing prompts?"

🎓 THE ANSWER:
Pydantic Field constraints. They're validation rules AND LLM instructions.

⏱️  TIME: 10 minutes
💡 DIFFICULTY: ⭐⭐ Beginner-friendly with substance
"""

import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 STEP 1: Define Complex, Nested Types
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@flock_type
class MovieIdea(BaseModel):
    """
    INPUT: A vague movie concept (just like how producers pitch ideas!)

    Example:
    - "A movie about cat owners during the rise of AI"
    - "Basically Die Hard but underwater"
    - "What if Inception met The Office?"
    """

    idea: str


# 🎨 NESTED TYPE #1: Character (this will go INSIDE Movie)
# Notice: We're building composable data structures, not flat dictionaries
@flock_type
class Character(BaseModel):
    """
    A movie character with depth, backstory, and casting suggestions.

    This is a NESTED type - it doesn't live on the blackboard alone.
    It's a building block for the Movie type.
    """

    name: str  # "Tony Stark" or "Elle Woods" vibes
    role: str  # "Protagonist", "Villain", "Comic Relief"
    backstory: str  # Where they came from, what drives them
    catchphrase: str  # Every good character needs one!
    emoji: str  # Because why not? 🎭

    # 💡 FIELD WITH DESCRIPTION:
    # The description isn't just for humans - it guides the LLM!
    # This is like a "soft constraint" - not validation, but intent.
    possible_actors: dict[str, str] = Field(
        ...,  # Required field (the ... means "no default")
        description=(
            "A dictionary of possible actors for this character. "
            "Key = actor name, Value = reasoning with x/10 rating. "
            "Example: {'Ryan Gosling': 'Perfect deadpan delivery, 9/10'}"
        ),
    )


# 🎬 NESTED TYPE #2: Movie (the big kahuna!)
# This contains multiple Characters - that's the nested part
@flock_type
class Movie(BaseModel):
    """
    OUTPUT: A complete movie concept with characters, plot, and metadata.

    Notice all the constraints:
    - Field descriptions guide LLM behavior
    - Literal types limit choices (no "mystery" genre if not listed!)
    - min/max constraints enforce business rules
    - Nested list of Characters shows composability
    """

    # ✨ FIELD WITH DESCRIPTION (guides LLM output style)
    fun_title: str = Field(..., description="A catchy and fun title for the movie. IN ALL CAPS")

    # 🎯 FIELD WITH CONSTRAINTS (ge = greater-or-equal, le = less-or-equal)
    # This ENFORCES the runtime is between 200-240 minutes
    # The LLM will respect this! And Pydantic will validate it!
    runtime: int = Field(
        ...,
        ge=200,  # Must be >= 200 minutes (why? because we're making epics!)
        le=240,  # Must be <= 240 minutes (gotta have SOME limits)
        description="Runtime in minutes. Epic films only - no short stuff!",
    )

    synopsis: str  # Quick elevator pitch
    plot: str  # Full story arc

    # 🎪 LITERAL TYPE: The genre can ONLY be one of these exact strings
    # Try to make it output "western"? Pydantic will reject it!
    # The LLM learns to pick from the allowed list.
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

    # 🎭 NESTED LIST WITH CONSTRAINTS:
    # - Must have at least 5 characters (min_length)
    # - Can't have more than 10 (max_length)
    # - Each item is a full Character object (nested!)
    characters: list[Character] = Field(
        ...,
        min_length=5,
        max_length=10,
        description="Main characters with full backstories and casting ideas",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🤖 STEP 2: Create the Agent (Still Zero Prompts!)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock("openai/gpt-4.1")

movie_master = (
    flock.agent("movie_master")
    # 🎯 DESCRIPTION: This IS where you can add a "system prompt" if needed
    # But notice: It's SHORT. The types do the heavy lifting.
    # You're just clarifying the agent's PERSONALITY, not its task.
    .description("Creates Oscar-worthy movie details from a movie idea.")
    .consumes(MovieIdea)
    .publishes(Movie)
)

# 💡 THE KEY INSIGHT:
# Look at that agent definition. It's TINY.
# All the complexity lives in the Movie schema:
# - 5-10 characters required
# - Runtime 200-240 minutes
# - Genre must be from allowed list
# - Each character needs backstory, catchphrase, emoji, actor suggestions
#
# You didn't write a single line of "Please create characters with backstories..."
# The schema IS the instruction. The LLM reads the type signature and just... does it.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 3: Run and Retrieve Results
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    Let's make a movie! This time we'll also RETRIEVE the results.
    """

    # Create a movie idea
    movie_idea = MovieIdea(idea="A movie about cat owners during the rise of AI")

    print(f"🎬 Pitching: {movie_idea.idea}")
    print("🎭 Movie master is writing the screenplay...\n")

    # Publish and wait
    await flock.publish(movie_idea)
    await flock.run_until_idle()

    # Retrieve the result from flock
    # get_by_type() returns a list of all Movie objects
    movies = await flock.store.get_by_type(Movie)

    if movies:
        movie = movies[0]  # Get the first one
        print("✅ Movie created!\n")
        print(f"🎬 Title: {movie.fun_title}")
        print(f"⏱️  Runtime: {movie.runtime} minutes")
        print(f"🎭 Genre: {movie.genre}")
        print(f"👥 Characters: {len(movie.characters)}")
        print(f"\n📖 Synopsis:\n{movie.synopsis}\n")

        # Show off the first character
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 WHAT YOU JUST LEARNED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ✅ Nested Types
#    - Character is a type. Movie contains list[Character].
#    - Composability without complexity.
#
# ✅ Field Constraints
#    - ge/le for numeric ranges (runtime: 200-240)
#    - min_length/max_length for lists (5-10 characters)
#    - Constraints are ENFORCED by Pydantic, respected by LLM
#
# ✅ Literal Types
#    - Genre can ONLY be one of 9 allowed values
#    - No "western"? LLM can't output it. Guaranteed.
#
# ✅ Descriptions Guide Behavior
#    - fun_title description says "IN ALL CAPS"
#    - LLM follows it without being a hard constraint
#    - Like "soft hints" vs "hard rules"
#
# ✅ Retrieving Results
#    - flock.store.get_by_type(Movie) returns list[Movie]
#    - Type-safe! No casting, no .data access, just clean objects
#
# 💡 THE BIG IDEA:
# Business logic lives in types, not prompts.
# - "Runtime 200-240" → Field(ge=200, le=240)
# - "5-10 characters" → Field(min_length=5, max_length=10)
# - "Genre must be valid" → Literal[allowed_genres]
#
# When requirements change, you update the TYPE, not scattered prompts.
#
# 🚀 NEXT STEP: Run 03_mcp_and_tools.py to make agents DO things!
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
