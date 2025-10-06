"""
Review Pipeline Showcase
========================

This example demonstrates a simple review pipeline using the Blackboard Orchestrator.
The blog writer agent generates a blog post based on an idea, and the SEO optimizer agent reviews it.
This again triggers the blog writer to improve the blog based on the review until a satisfactory review is achieved.
"""

import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_tool, flock_type


# 1. Define typed artifacts
@flock_type
class Idea(BaseModel):
    topic: str


@flock_type
class Blog(BaseModel):
    title: str = Field(description="Title in CAPS")
    sections: dict[str, str] = Field(description="Section titles and content")
    summary: str = Field(description="Concise summary of the blog")
    # html: str = Field(description="A beautifully formatted HTML version with tailwindcss")


@flock_type
class Review(BaseModel):
    score: int = Field(ge=1, le=10, description="Score from 1 to 10")
    comments: str = Field(description="Review comments")


@flock_tool
def write_file(content: str, file_path: str):
    with open(file_path, "w") as f:
        f.write(content)


# 2. Create orchestrator
flock = Flock("openai/gpt-4.1")

# 3. Define agents (they auto-connect through the blackboard!)
blog_writer = (
    flock.agent("blog_writer")
    .description("Generates a compelling blog post.")
    .consumes(Idea)
    .consumes(Review, where=lambda r: r.score <= 8)  # Conditional consumption
    .publishes(Blog)
)

seo_optimizer = (
    flock.agent("seo_optimizer")
    .description(
        "A harsh critic. Reviews the blog for SEO and quality and provides actionable feedback."
    )
    .consumes(Blog)
    .publishes(Review)
)

blog_writer = (
    flock.agent("html_writer")
    .description(
        "Generates a professionally designed blog with the latest draft and writes it to a 'blog.html' file."
        "Uses tailwindcss for styling and js for interactivity."
    )
    .consumes(Review, where=lambda r: r.score >= 9)  # Conditional consumption
    .with_tools([write_file])
)


# 4. Run!
async def main():
    idea = Idea(topic="A ranking of the cutest cat breeds")
    await flock.publish(idea)
    await flock.run_until_idle()
    print("✅ Blog post and review generated!")


asyncio.run(main())
