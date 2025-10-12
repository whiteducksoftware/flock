import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class Idea(BaseModel):
    idea: str

@flock_type
class BookHook(BaseModel):
    title: str = Field(description="Title in CAPS")
    summary: str = Field(description="Concise summary of the book")

@flock_type
class Review(BaseModel):
    score: int = Field(ge=1, le=10, description="Score from 1 to 10")
    comments: str = Field(description="Review comments with actionable suggestions")

@flock_type
class BookOutline(BaseModel):
    title: str = Field(description="Title of the book")
    chapters: dict[str, str] = Field(
        description="Dict of chapter titles, and content summary of each chapter"
    )

flock = Flock("openai/gpt-4.1")

book_idea_agent = (
    flock.agent("book_idea_agent")
    .description("Generates a compelling book idea.")
    .consumes(Idea)
    .consumes(Review, where=lambda r: r.score <= 8)
    .publishes(BookHook)
)

reviewer_agent = (
    flock.agent("reviewer_agent")
    .description("A harsh critic. Reviews the book idea quality.")
    .consumes(BookHook)
    .publishes(Review)
)

chapter_agent = (
    flock.agent("chapter_agent")
    .description("Generates a detailed outline for the book based on the latest draft.")
    .consumes(Review, where=lambda r: r.score >= 9)
    .publishes(BookOutline)
)

async def main():
    await flock.serve(dashboard=True)

asyncio.run(main())
