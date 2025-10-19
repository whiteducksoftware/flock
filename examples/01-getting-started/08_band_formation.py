"""
Getting Started: Band Formation

This example demonstrates a multi-agent pipeline where each agent depends on
the output of the previous one, creating a complete workflow.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.registry import flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


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


flock = Flock()

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


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    concept = BandConcept(
        genre="Folk-Electronic Fusion",
        target_audience="Millennials who love both nature and technology",
        unique_selling_point="Acoustic instruments processed through AI-generated harmonies",
        inspiration="What if Bon Iver collaborated with Daft Punk?",
    )

    print(f"🎵 Starting band formation: {concept.genre}\n")

    await flock.publish(concept)
    await flock.run_until_idle()

    marketing_materials = await flock.store.get_by_type(MarketingCopy)

    if marketing_materials:
        copy = marketing_materials[0]
        print("🎯 MARKETING CAMPAIGN:")
        print(f"   Press Release: {copy.press_release[:200]}...")
        print(f"   Social Hooks: {copy.social_media_hooks[:2]}")
        print(f"   Demographics: {copy.target_demographics}")


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
