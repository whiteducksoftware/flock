import asyncio

from pydantic import BaseModel

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class BandConcept(BaseModel):
    genre: str
    target_audience: str
    unique_selling_point: str
    inspiration: str

@flock_type
class BandLineup(BaseModel):
    band_name: str
    members: list[dict[str, str]]
    formation_story: str
    musical_style: str

@flock_type
class Album(BaseModel):
    title: str
    tracks: list[dict[str, str]]
    release_date: str
    producer_notes: str
    genre_fusion: list[str]

@flock_type
class MarketingCopy(BaseModel):
    press_release: str
    social_media_hooks: list[str]
    target_demographics: list[str]
    tour_announcement: str

flock = Flock("openai/gpt-4.1")

scout = (
    flock.agent("scout")
    .description("Music scout who assembles bands based on concepts")
    .consumes(BandConcept)
    .publishes(BandLineup)
)

producer = (
    flock.agent("producer")
    .description("Album producer who creates debut albums for new bands")
    .consumes(BandLineup)
    .publishes(Album)
)

marketer = (
    flock.agent("marketer")
    .description("Music marketer who creates promotional campaigns")
    .consumes(Album)
    .publishes(MarketingCopy)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
