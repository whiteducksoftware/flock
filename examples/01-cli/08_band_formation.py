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

async def main():
    concept = BandConcept(
        genre="Folk-Electronic Fusion",
        target_audience="Millennials who love both nature and technology",
        unique_selling_point="Acoustic instruments processed through AI-generated harmonies",
        inspiration="What if Bon Iver collaborated with Daft Punk?"
    )

    print(f"🎵 Starting band formation: {concept.genre}\n")

    await flock.publish(concept)
    await flock.run_until_idle()

    marketing_materials = await flock.store.get_by_type(MarketingCopy)

    if marketing_materials:
        copy = marketing_materials[0]
        print(f"🎯 MARKETING CAMPAIGN:")
        print(f"   Press Release: {copy.press_release[:200]}...")
        print(f"   Social Hooks: {copy.social_media_hooks[:2]}")
        print(f"   Demographics: {copy.target_demographics}")

if __name__ == "__main__":
    asyncio.run(main())
