"""
Dynamic Fan-Out: Context-Aware Idea Generation
This example demonstrates the dynamic fan-out feature:
- fan_out=(min, max) lets the engine choose how many artifacts to generate
- min/max apply to the RAW engine output list
- where/validate are applied AFTER range checks
"""
import asyncio
from pydantic import BaseModel, Field
from flock import Flock
from flock.registry import flock_type
@flock_type
class BlogBrief(BaseModel):
    topic: str = Field(description="Topic to write about")
    target_audience: str = Field(description="Intended audience")
    complexity: str = Field(
        description="rough complexity: simple, normal, complex",
        default="normal",
    )
@flock_type
class BlogIdea(BaseModel):
    title: str
    angle: str
    score: float = Field(
        description="quality score from 0-10 (higher is better)",
        ge=0,
        le=10,
    )
flock = Flock()
idea_agent = (
    flock.agent("dynamic_blog_ideas")
    .description(
        "Generate a variable number of blog ideas based on brief complexity. "
        "For simple briefs, generate fewer ideas; for complex briefs, generate more. "
        "Assign each idea a quality score between 0 and 10."
    )
    .consumes(BlogBrief)
    .publishes(
        BlogIdea,
        fan_out=(5, 20),  # Engine decides how many ideas between 5 and 20
        where=lambda i: i.score >= 7.5,  # Only keep high-quality ideas
    )
)
async def main():
    simple_brief = BlogBrief(
        topic="Writing good commit messages",
        target_audience="junior developers",
        complexity="simple",
    )
    complex_brief = BlogBrief(
        topic="Building resilient distributed systems with event sourcing",
        target_audience="senior platform engineers",
        complexity="complex",
    )
    print("\n=== Simple Brief (expected fewer raw ideas) ===")
    await flock.publish(simple_brief)
    await flock.run_until_idle()
    print("\n=== Complex Brief (expected more raw ideas) ===")
    await flock.publish(complex_brief)
    await flock.run_until_idle()
    # Inspect published ideas
    all_artifacts = await flock.store.list()
    ideas = [a for a in all_artifacts if "BlogIdea" in a.type]
    print(f"\nTotal BlogIdea artifacts after filtering: {len(ideas)}")
    for a in ideas:
        idea = BlogIdea(**a.payload)
        print(f"- {idea.title} (score={idea.score})")
if __name__ == "__main__":
    asyncio.run(main())
