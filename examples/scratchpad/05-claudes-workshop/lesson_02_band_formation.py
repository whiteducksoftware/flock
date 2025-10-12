"""
🎸 LESSON 02: The Band Formation Pipeline
=========================================

🎯 LEARNING OBJECTIVES:
----------------------
In this lesson, you'll learn:
1. How agents auto-chain through the blackboard (no graph wiring!)
2. Multi-step workflows emerge from type subscriptions
3. Why blackboard beats explicit graphs
4. Data flow visualization through artifacts

🎬 THE SCENARIO:
---------------
You're building a music industry platform. Starting with a band concept,
you need a pipeline that:
1. Scout generates the band lineup
2. Producer creates their debut album
3. Marketer writes promotional copy

Three agents. Zero graph edges. Pure blackboard magic.

⏱️  TIME: 15 minutes
💡 COMPLEXITY: ⭐⭐ Intermediate

Let's rock! 🎸👇
"""

import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 STEP 1: Define the Artifact Chain
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🎯 KEY INSIGHT: Notice the data flow pattern:
# BandConcept → BandLineup → Album → MarketingCopy
#
# Each artifact is produced by one agent and consumed by another.
# No one "tells" agents to chain - they just subscribe to types!


@flock_type
class BandConcept(BaseModel):
    """
    STEP 1 INPUT: The initial idea for a band
    """

    genre: str = Field(description="Musical genre (rock, jazz, metal, pop, etc.)")
    vibe: str = Field(description="The band's vibe or aesthetic")
    target_audience: str = Field(description="Who should love this band?")


@flock_type
class BandLineup(BaseModel):
    """
    STEP 2 OUTPUT → STEP 3 INPUT: The complete band roster

    🔥 CHAINING MAGIC:
    - Produced by: talent_scout
    - Consumed by: music_producer
    No explicit edge needed!
    """

    band_name: str = Field(description="Cool band name")
    members: list[dict[str, str]] = Field(
        description="List of band members with their roles",
        examples=[[{"name": "Alex Thunder", "role": "Lead Guitar", "background": "..."}]],
    )
    origin_story: str = Field(
        description="How the band formed",
        min_length=100,
    )
    signature_sound: str = Field(description="What makes their sound unique")


@flock_type
class Album(BaseModel):
    """
    STEP 3 OUTPUT → STEP 4 INPUT: Their debut album

    🔥 MORE CHAINING:
    - Produced by: music_producer
    - Consumed by: marketing_guru
    Again, no edges! Just type subscriptions.
    """

    title: str = Field(description="Album title in ALL CAPS")
    tracklist: list[dict[str, str]] = Field(
        description="Songs with titles and brief descriptions",
        min_length=8,
        max_length=12,
    )
    genre_fusion: str = Field(description="How this album blends genres")
    standout_track: str = Field(description="The track that'll be a hit")
    production_notes: str = Field(description="Special production techniques or instruments used")


@flock_type
class MarketingCopy(BaseModel):
    """
    FINAL OUTPUT: Ready-to-publish promotional material

    This is the end of the chain. No agent consumes this (yet!).
    """

    press_release: str = Field(
        description="Professional press release announcing the album",
        min_length=200,
    )
    social_media_hook: str = Field(
        description="Catchy social post (280 chars max)",
        max_length=280,
    )
    billboard_tagline: str = Field(
        description="10-word tagline for billboards",
        max_length=100,
    )
    target_playlists: list[str] = Field(
        description="Spotify/Apple Music playlists to pitch to",
        min_length=3,
        max_length=5,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 STEP 2: Create the Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock("openai/gpt-4.1")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎸 STEP 3: Define the Agent Chain (NO GRAPH EDGES!)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🕵️ Agent 1: The Talent Scout
# Watches for: BandConcept
# Produces: BandLineup

talent_scout = (
    flock.agent("talent_scout")
    .description(
        "A legendary talent scout who assembles perfect band lineups based on genre and vibe"
    )
    .consumes(BandConcept)
    .publishes(BandLineup)
)

# 🎵 Agent 2: The Music Producer
# Watches for: BandLineup ← AUTOMATICALLY CHAINS after talent_scout!
# Produces: Album

music_producer = (
    flock.agent("music_producer")
    .description("A visionary music producer who creates debut album concepts for new bands")
    .consumes(BandLineup)  # ← This creates the chain!
    .publishes(Album)
)

# 📢 Agent 3: The Marketing Guru
# Watches for: Album ← AUTOMATICALLY CHAINS after music_producer!
# Produces: MarketingCopy

marketing_guru = (
    flock.agent("marketing_guru")
    .description("A marketing genius who writes compelling promotional copy for albums")
    .consumes(Album)  # ← This extends the chain!
    .publishes(MarketingCopy)
)

# 💡 WHAT JUST HAPPENED?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# We created a 3-agent pipeline WITHOUT any graph edges!
#
# The chain emerges from type subscriptions:
#   BandConcept → [talent_scout] → BandLineup
#   BandLineup → [music_producer] → Album
#   Album → [marketing_guru] → MarketingCopy
#
# 🆚 COMPARISON TO GRAPH-BASED FRAMEWORKS:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❌ Graph-based approach:
#     graph.add_edge("talent_scout", "music_producer")
#     graph.add_edge("music_producer", "marketing_guru")
#     # Want to add another agent? Rewrite edges!
#
# ✅ Flock's subscription approach:
#     Just define what types each agent consumes/publishes
#     The chain emerges automatically from the blackboard

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 4: Run the Pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    Watch the magic happen:
    1. We publish ONE artifact (BandConcept)
    2. Three agents execute IN SEQUENCE automatically
    3. Four artifacts end up on the blackboard
    4. No workflow graph needed!
    """

    print("🎸 Starting the Band Formation Pipeline...\n")

    # 🎯 Create the initial concept (our seed data)
    concept = BandConcept(
        genre="cyberpunk synthwave",
        vibe="dystopian future meets 80s nostalgia",
        target_audience="gamers, sci-fi fans, and retro-futurists",
    )

    print("=" * 70)
    print("📝 BAND CONCEPT SUBMITTED")
    print("=" * 70)
    print(f"Genre: {concept.genre}")
    print(f"Vibe: {concept.vibe}")
    print(f"Target Audience: {concept.target_audience}")
    print("=" * 70)
    print()

    # 📤 Publish the concept to the blackboard
    print("📤 Publishing concept to blackboard...")
    await flock.publish(concept)

    # ⏳ Wait for the cascade to complete
    # This will execute: talent_scout → music_producer → marketing_guru
    print("⏳ Agents are working...\n")
    print("   🕵️  Talent scout is assembling the lineup...")
    await flock.run_until_idle()

    # 📊 Retrieve all artifacts to show the complete pipeline
    print("\n" + "=" * 70)
    print("🎉 PIPELINE COMPLETE!")
    print("=" * 70)

    # Get the band lineup
    lineups = await flock.store.get_by_type(BandLineup)
    if lineups:
        lineup = lineups[-1]
        print(f"\n🎸 BAND FORMED: {lineup.band_name}")
        print("\n📖 Origin Story:")
        print(f"   {lineup.origin_story[:200]}...")
        print(f"\n🎵 Signature Sound: {lineup.signature_sound}")
        print("\n👥 Members:")
        for member in lineup.members:
            print(f"   - {member.get('name', 'Unknown')}: {member.get('role', 'Unknown')}")

    # Get the album
    albums = await flock.store.get_artifacts_by_type("Album")
    if albums:
        album = albums[-1].obj
        print(f"\n💿 DEBUT ALBUM: {album.title}")
        print(f"\n🎼 Genre Fusion: {album.genre_fusion}")
        print(f"\n⭐ Standout Track: {album.standout_track}")
        print(f"\n📀 Tracklist ({len(album.tracklist)} tracks):")
        for i, track in enumerate(album.tracklist[:3], 1):  # Show first 3
            print(f"   {i}. {track.get('title', 'Unknown')}")
        if len(album.tracklist) > 3:
            print(f"   ... and {len(album.tracklist) - 3} more tracks")

    # Get the marketing copy
    marketing = await flock.store.get_artifacts_by_type("MarketingCopy")
    if marketing:
        copy = marketing[-1].obj
        print("\n📢 MARKETING READY!")
        print("\n🔥 Billboard Tagline:")
        print(f'   "{copy.billboard_tagline}"')
        print("\n📱 Social Media Hook:")
        print(f"   {copy.social_media_hook}")
        print("\n🎯 Target Playlists:")
        for playlist in copy.target_playlists:
            print(f"   - {playlist}")

    print("\n" + "=" * 70)
    print("✨ From concept to market-ready in one blackboard cascade!")
    print("=" * 70)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 LEARNING CHECKPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
🎉 CONGRATULATIONS! You just built a multi-agent chain with ZERO graph wiring!

🔑 KEY TAKEAWAYS:
-----------------

1️⃣ EMERGENT WORKFLOWS
   - No add_edge() calls needed
   - Agents chain automatically through type subscriptions
   - The blackboard handles all routing

2️⃣ TYPE-DRIVEN COMPOSITION
   - talent_scout publishes BandLineup
   - music_producer consumes BandLineup
   - They auto-connect through the blackboard!

3️⃣ SEQUENTIAL EXECUTION
   - publish(BandConcept) triggers talent_scout
   - talent_scout publishes BandLineup, which triggers music_producer
   - music_producer publishes Album, which triggers marketing_guru
   - All automatic!

4️⃣ DECOUPLED AGENTS
   - Agents don't know about each other
   - They only know data types
   - Adding a new agent? Just subscribe to a type!

🆚 VS GRAPH-BASED FRAMEWORKS:
-----------------------------
Traditional graph-based orchestration requires explicit workflow graphs:
```python
graph = StateGraph()
graph.add_node("talent_scout", talent_scout_func)
graph.add_node("music_producer", producer_func)
graph.add_node("marketing_guru", marketing_func)
graph.add_edge("talent_scout", "music_producer")  # Explicit wiring!
graph.add_edge("music_producer", "marketing_guru")  # More wiring!
graph.set_entry_point("talent_scout")
compiled = graph.compile()
```

Flock's subscription-based approach:
```python
# Just define what types agents consume/publish
talent_scout.consumes(BandConcept).publishes(BandLineup)
music_producer.consumes(BandLineup).publishes(Album)
marketing_guru.consumes(Album).publishes(MarketingCopy)
# Chain emerges automatically! 🎉
```

💡 WHY THIS MATTERS:
-------------------
Imagine you want to add a "quality_checker" agent between music_producer and marketing_guru:

❌ Graph way:
```python
# Remove existing edge
graph.remove_edge("music_producer", "marketing_guru")
# Add new edges
graph.add_edge("music_producer", "quality_checker")
graph.add_edge("quality_checker", "marketing_guru")
# Recompile entire graph
```

✅ Flock way:
```python
# Just insert a new agent
quality_checker = (
    flock.agent("quality_checker")
    .consumes(Album)  # Intercepts album
    .publishes(ApprovedAlbum)  # New type
)
# Update marketing_guru to consume ApprovedAlbum instead
marketing_guru.consumes(ApprovedAlbum)  # Change one line
# Done! No graph rewiring!
```

🧪 EXPERIMENT IDEAS:
-------------------
Try extending this pipeline:

1. Add a 4th agent:
   - Create a ReviewCritic type
   - Make a "critic" agent that consumes Album and publishes ReviewCritic
   - Watch it execute in parallel with marketing_guru!

2. Add intermediate validation:
   - Create ValidatedLineup type
   - Add a "validator" between scout and producer
   - See how the chain adapts

3. Make it branching:
   - Create a "radio_promoter" that also consumes Album
   - Watch two agents process Album in parallel

4. Enable tracing:
   - Run with FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
   - Query .flock/traces.duckdb to see execution order
   - Verify sequential vs parallel execution

📈 NEXT LESSON:
--------------
Lesson 03: The Quality Gate System
- Learn conditional consumption with where=lambda
- Build decision trees without graphs
- Dynamic routing based on data content

🎯 READY TO CONTINUE?
Run: uv run examples/claudes-flock-course/lesson_03_quality_gate.py
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
