import asyncio
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


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


async def main():
    news_events = [
        NewsEvent(
            headline="Major Tech Company Announces Breakthrough in Quantum Computing",
            location="Silicon Valley, CA",
            timestamp=datetime.now(timezone.utc),
            initial_details="Leading technology corporation claims to have achieved quantum supremacy with new 1000-qubit processor, potentially revolutionizing cryptography and scientific computing.",
            source_credibility=0.9,
        ),
        NewsEvent(
            headline="City Council Approves New Climate Action Plan",
            location="Portland, OR",
            timestamp=datetime.now(timezone.utc),
            initial_details="Local government votes 7-2 to implement aggressive carbon reduction targets, including mandatory solar panels on new construction and expanded public transit.",
            source_credibility=0.85,
        ),
        NewsEvent(
            headline="Archaeological Discovery Reveals Ancient Civilization",
            location="Egyptian Desert",
            timestamp=datetime.now(timezone.utc),
            initial_details="International team of archaeologists uncovers 4,000-year-old city with advanced irrigation systems and previously unknown hieroglyphic writing system.",
            source_credibility=0.95,
        ),
    ]

    print("📰 Starting news production pipeline...")

    for event in news_events:
        print(f"🔴 Breaking: {event.headline}")
        await flock.publish(event)

    await flock.run_until_idle()

    articles = await flock.store.get_by_type(NewsArticle)
    decisions = await flock.store.get_by_type(EditorialDecision)
    published = await flock.store.get_by_type(PublishedStory)

    print("\n📊 NEWS PRODUCTION SUMMARY:")
    print(f"   Breaking news events: {len(news_events)}")
    print(f"   Articles written: {len(articles)}")
    print(f"   Editorial decisions: {len(decisions)}")
    print(f"   Stories published: {len(published)}")

    approved_count = sum(1 for d in decisions if d.article_approved)
    print(
        f"   Approval rate: {approved_count}/{len(decisions)} ({approved_count / len(decisions) * 100:.1f}%)"
    )

    print("\n📰 PUBLISHED STORIES:")
    for i, story in enumerate(published):
        print(f"   {i + 1}. {story.final_headline}")
        print(f"      Channels: {', '.join(story.distribution_channels)}")
        print(f"      Expected reach: {story.expected_reach:,}")
        print(f"      Follow-up needed: {story.follow_up_needed}")

    print("\n📈 QUALITY METRICS:")
    if articles:
        fact_checked = sum(1 for a in articles if a.fact_check_status == "verified")
        print(f"   Fact-checked articles: {fact_checked}/{len(articles)}")

        urgent_stories = sum(1 for a in articles if a.urgency_level == "urgent")
        print(f"   Urgent stories: {urgent_stories}")

    if decisions:
        legal_reviews = sum(1 for d in decisions if d.legal_review_needed)
        print(f"   Legal reviews required: {legal_reviews}")


if __name__ == "__main__":
    asyncio.run(main())
