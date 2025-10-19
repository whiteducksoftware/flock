"""
Dashboard Edge Case Showcase
========================
This example demonstrates advanced features of the Flock dashboard, including:
- Conditional consumption of artifacts based on their content
- Dynamic updates to the dashboard as new artifacts are published
- Virtual agent edge persistence (e.g., edges from orchestrator.publish())
- Filtered edge count labels showing conditional consumption transparency

How to use:
1. Run this script: `uv run examples/showcase/04b_dashboard_edge_cases.py`
2. Open http://localhost:8344 in your browser
3. Click "Show Controls" to publish an initial Idea artifact
4. Observe the workflow:
   - book_writer creates 3 BookHooks from the Idea
   - seo_optimizer reviews each BookHook (creates 3 Reviews)
   - book_outliner only processes Reviews with score >= 9 (filtered consumption)

Expected behavior:
- External→book_writer edge persists throughout the workflow
- Agent counters: book_writer (↓ 1 in ↑ 3 out), seo_optimizer (↓ 3 in ↑ 3 out), book_outliner (↓ 1 in)
- Edge labels show filtered counts: "Review (3, filtered: 1)" on seo_optimizer→book_outliner

TAKES ROUGHLY 60s to run.

For detailed bug fix documentation, see docs/specs/003-real-time-dashboard/PLAN.md Phase 11.
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


# 1. Define typed artifacts
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


# 2. Create orchestrator
flock = Flock()

# 3. Define agents (they auto-connect through the blackboard!)
book_idea_agent = (
    flock.agent("book_idea_agent")
    .description("Generates a compelling book idea.")
    .consumes(Idea)
    .consumes(Review, where=lambda r: r.score <= 8)  # Conditional consumption
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
    .consumes(Review, where=lambda r: r.score >= 9)  # Conditional consumption
    .publishes(BookOutline)
)


# 4. Run!
async def main():
    await flock.serve(dashboard=True)


asyncio.run(main())
