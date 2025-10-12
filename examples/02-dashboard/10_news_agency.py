import asyncio
from datetime import datetime

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
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

flock = Flock("openai/gpt-4.1")

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

asyncio.run(flock.serve(dashboard=True), debug=True)
