# Multi-Agent Workflow

**Difficulty:** ⭐⭐ Intermediate | **Time:** 30 minutes

Learn how agents automatically chain through the blackboard without explicit graph wiring. Build a 3-agent pipeline with zero coordination code!

**Prerequisites:** Complete [Your First Agent](your-first-agent.md)

## What You'll Build

A music industry platform with three agents that automatically chain together:

1. **Talent Scout** generates band lineup
2. **Music Producer** creates their debut album
3. **Marketing Guru** writes promotional copy

Three agents. Zero graph edges. Pure blackboard magic.

## The Problem with Graph-Based Frameworks

Traditional frameworks require explicit workflow graphs:

```python
# ❌ Traditional graph-based approach
graph = StateGraph()
graph.add_node("talent_scout", talent_scout_func)
graph.add_node("music_producer", producer_func)
graph.add_node("marketing_guru", marketing_func)
graph.add_edge("talent_scout", "music_producer")  # Explicit wiring!
graph.add_edge("music_producer", "marketing_guru")  # More wiring!
graph.set_entry_point("talent_scout")
compiled = graph.compile()
```

**Problems:**

- Manual edge management
- Tight coupling between nodes
- Want to add another agent? Rewrite edges!
- O(n²) complexity as agents grow

## The Flock Way: Type-Driven Composition

```python
# ✅ Flock's subscription-based approach
talent_scout.consumes(BandConcept).publishes(BandLineup)
music_producer.consumes(BandLineup).publishes(Album)
marketing_guru.consumes(Album).publishes(MarketingCopy)
# Chain emerges automatically! 🎉
```

**Benefits:**

- Zero edges to manage
- Loose coupling via types
- Adding agent = one line
- O(n) complexity

## Step 1: Define the Artifact Chain

Notice the data flow pattern:

```
BandConcept → BandLineup → Album → MarketingCopy
```

Each artifact is produced by one agent and consumed by another. No one "tells" agents to chain—they just subscribe to types!

```python
from pydantic import BaseModel, Field
from flock import Flock
from flock.registry import flock_type

@flock_type
class BandConcept(BaseModel):
    """STEP 1 INPUT: The initial idea for a band"""
    genre: str = Field(description="Musical genre (rock, jazz, metal, pop, etc.)")
    vibe: str = Field(description="The band's vibe or aesthetic")
    target_audience: str = Field(description="Who should love this band?")

@flock_type
class BandLineup(BaseModel):
    """
    STEP 2 OUTPUT → STEP 3 INPUT

    🔥 CHAINING MAGIC:
    - Produced by: talent_scout
    - Consumed by: music_producer
    No explicit edge needed!
    """
    band_name: str = Field(description="Cool band name")
    members: list[dict[str, str]] = Field(
        description="List of band members with their roles"
    )
    origin_story: str = Field(description="How the band formed", min_length=100)
    signature_sound: str = Field(description="What makes their sound unique")

@flock_type
class Album(BaseModel):
    """
    STEP 3 OUTPUT → STEP 4 INPUT

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
    production_notes: str = Field(description="Special production techniques")

@flock_type
class MarketingCopy(BaseModel):
    """FINAL OUTPUT: Ready-to-publish promotional material"""
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
```

## Step 2: Create the Agent Chain (NO GRAPH EDGES!)

```python
flock = Flock("openai/gpt-4.1")

# 🕵️ Agent 1: The Talent Scout
# Watches for: BandConcept
# Produces: BandLineup
talent_scout = (
    flock.agent("talent_scout")
    .description("A legendary talent scout who assembles perfect band lineups")
    .consumes(BandConcept)
    .publishes(BandLineup)
)

# 🎵 Agent 2: The Music Producer
# Watches for: BandLineup ← AUTOMATICALLY CHAINS after talent_scout!
# Produces: Album
music_producer = (
    flock.agent("music_producer")
    .description("A visionary music producer who creates debut album concepts")
    .consumes(BandLineup)  # ← This creates the chain!
    .publishes(Album)
)

# 📢 Agent 3: The Marketing Guru
# Watches for: Album ← AUTOMATICALLY CHAINS after music_producer!
# Produces: MarketingCopy
marketing_guru = (
    flock.agent("marketing_guru")
    .description("A marketing genius who writes compelling promotional copy")
    .consumes(Album)  # ← This extends the chain!
    .publishes(MarketingCopy)
)
```

**💡 What Just Happened?**

We created a 3-agent pipeline WITHOUT any graph edges!

The chain emerges from type subscriptions:

```
BandConcept → [talent_scout] → BandLineup
BandLineup → [music_producer] → Album
Album → [marketing_guru] → MarketingCopy
```

## Step 3: Run the Pipeline

```python
async def main():
    print("🎸 Starting the Band Formation Pipeline...\n")

    # 🎯 Create the initial concept (our seed data)
    concept = BandConcept(
        genre="cyberpunk synthwave",
        vibe="dystopian future meets 80s nostalgia",
        target_audience="gamers, sci-fi fans, and retro-futurists",
    )

    print("📤 Publishing concept to blackboard...")
    await flock.publish(concept)

    # ⏳ Wait for the cascade to complete
    # This will execute: talent_scout → music_producer → marketing_guru
    print("⏳ Agents are working...\n")
    await flock.run_until_idle()

    print("✅ Pipeline complete!")
```

## Execution Flow

When you run this:

1. **publish(BandConcept)** → appears on blackboard
2. `talent_scout` sees BandConcept → executes → publishes BandLineup
3. `music_producer` sees BandLineup → executes → publishes Album
4. `marketing_guru` sees Album → executes → publishes MarketingCopy
5. **run_until_idle()** returns when all agents finish

All automatic! Zero coordination code needed.

## Retrieving Results

Get artifacts from the blackboard by type:

```python
# Get the band lineup
lineups = await flock.store.get_artifacts_by_type("BandLineup")
if lineups:
    lineup = lineups[-1].obj
    print(f"🎸 Band: {lineup.band_name}")
    print(f"🎵 Sound: {lineup.signature_sound}")

# Get the album
albums = await flock.store.get_artifacts_by_type("Album")
if albums:
    album = albums[-1].obj
    print(f"💿 Album: {album.title}")
    print(f"⭐ Hit: {album.standout_track}")

# Get marketing copy
marketing = await flock.store.get_artifacts_by_type("MarketingCopy")
if marketing:
    copy = marketing[-1].obj
    print(f"🔥 Tagline: {copy.billboard_tagline}")
```

## Key Takeaways

### 1. Emergent Workflows

- No `add_edge()` calls needed
- Agents chain automatically through type subscriptions
- The blackboard handles all routing

### 2. Type-Driven Composition

- `talent_scout` publishes BandLineup
- `music_producer` consumes BandLineup
- They auto-connect through the blackboard!

### 3. Sequential Execution

- `publish(BandConcept)` triggers talent_scout
- talent_scout publishes BandLineup, which triggers music_producer
- music_producer publishes Album, which triggers marketing_guru
- All automatic!

### 4. Decoupled Agents

- Agents don't know about each other
- They only know data types
- Adding a new agent? Just subscribe to a type!

## Try It Yourself

**Challenge 1: Add a Quality Checker**

Insert a validation agent between music_producer and marketing_guru:

```python
@flock_type
class ApprovedAlbum(BaseModel):
    album: Album
    quality_score: float
    approval_notes: str

quality_checker = (
    flock.agent("quality_checker")
    .consumes(Album)
    .publishes(ApprovedAlbum)
)

# Update marketing_guru to consume ApprovedAlbum
marketing_guru.consumes(ApprovedAlbum)  # Change one line!
```

No graph rewiring needed!

**Challenge 2: Create a Parallel Branch**

Add a `radio_promoter` that also consumes Album:

```python
@flock_type
class RadioPitch(BaseModel):
    target_stations: list[str]
    pitch_angle: str

radio_promoter = (
    flock.agent("radio_promoter")
    .consumes(Album)  # Same type as marketing_guru!
    .publishes(RadioPitch)
)
```

Watch both marketing_guru and radio_promoter run in parallel!

**Challenge 3: Enable Tracing**

See the execution order:

```bash
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
uv run python your_script.py

# Query traces
python -c "
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)
spans = conn.execute('''
    SELECT service, name, duration_ms
    FROM spans
    WHERE name LIKE '%agent.execute'
    ORDER BY start_time
''').fetchall()
for span in spans:
    print(f'{span[0]}: {span[2]:.2f}ms')
"
```

## Why This Matters

**Imagine you want to add a "quality_checker" agent between music_producer and marketing_guru:**

❌ **Graph way:**

```python
# Remove existing edge
graph.remove_edge("music_producer", "marketing_guru")
# Add new edges
graph.add_edge("music_producer", "quality_checker")
graph.add_edge("quality_checker", "marketing_guru")
# Recompile entire graph
```

✅ **Flock way:**

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

## Next Steps

Now that you understand agent chaining, let's add web browsing capabilities!

[Continue to Conditional Routing →](conditional-routing.md){ .md-button .md-button--primary }

## Reference Links

- [Blackboard Guide](../guides/blackboard.md) - Deep dive into blackboard architecture
- [Patterns Guide](../guides/patterns.md) - Common workflow patterns
- [API Reference](../reference/api/agent.md) - Complete agent builder API
