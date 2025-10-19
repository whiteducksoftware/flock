"""
Getting Started: News Agency

This example demonstrates a realistic multi-agent workflow simulating a news
organization with reporters, editors, and publishers.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class NewsEvent(BaseModel):
    headline: str
    location: str
    timestamp: datetime
    initial_details: str
    source_credibility: float = Field(ge=0.0, le=1.0)


@flock_type
class NewsArticle(BaseModel):
    title: str
    byline: str
    lead_paragraph: str
    body: str
    quotes: list[str]
    fact_check_status: str
    urgency_level: str


@flock_type
class EditorialDecision(BaseModel):
    article_approved: bool
    priority_level: str
    publication_timing: str
    required_edits: list[str]
    legal_review_needed: bool


@flock_type
class PublishedStory(BaseModel):
    final_headline: str
    publication_time: datetime
    distribution_channels: list[str]
    expected_reach: int
    follow_up_needed: bool


flock = Flock()

reporter = (
    flock.agent("reporter")
    .description("Investigates news events and writes articles")
    .consumes(NewsEvent)
    .publishes(NewsArticle)
)

editor = (
    flock.agent("editor")
    .description("Reviews articles for accuracy, quality, and publication decisions")
    .consumes(NewsArticle)
    .publishes(EditorialDecision)
)

publisher = (
    flock.agent("publisher")
    .description("Manages publication process and distribution")
    .consumes(EditorialDecision)
    .consumes(NewsArticle)
    .publishes(PublishedStory)
)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    event = NewsEvent(
        headline="Major Tech Company Announces Breakthrough in Quantum Computing",
        location="Silicon Valley, CA",
        timestamp=datetime.now(timezone.utc),
        initial_details="Leading technology corporation claims quantum supremacy with new 1000-qubit processor.",
        source_credibility=0.9,
    )

    print(f"🔴 Breaking: {event.headline}\n")

    await flock.publish(event)
    await flock.run_until_idle()

    published = await flock.store.get_by_type(PublishedStory)

    if published:
        story = published[0]
        print("📰 PUBLISHED:")
        print(f"   {story.final_headline}")
        print(f"   Channels: {', '.join(story.distribution_channels)}")
        print(f"   Expected reach: {story.expected_reach:,}")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
