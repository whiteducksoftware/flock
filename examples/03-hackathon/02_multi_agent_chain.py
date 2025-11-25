"""
Hackathon Track 02: Multi-Agent Chain

🎓 LEARNING OBJECTIVE:
Learn how agents can form pipelines where one agent's output becomes another's input.
This creates powerful workflows where specialized agents handle different stages.

KEY CONCEPTS:
- Agent pipelines (A → B → C)
- Data flow through the blackboard
- Multiple agents working together
- Automatic dependency resolution

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# STEP 1: Define the Data Flow
# ============================================================================
# In a multi-agent chain, each agent produces data that the next agent consumes.
# Think of it like an assembly line: each station adds value to the product.
# ============================================================================

@flock_type
class BlogTopic(BaseModel):
    """Initial blog topic idea."""
    topic: str = Field(description="The blog topic to write about")
    target_audience: str = Field(description="Who is this blog for?")


@flock_type
class BlogOutline(BaseModel):
    """Structured outline for a blog post."""
    title: str = Field(description="Catchy blog post title")
    introduction: str = Field(description="Engaging introduction paragraph")
    main_sections: list[dict[str, str]] = Field(
        description="List of sections, each with 'heading' and 'summary'"
    )
    conclusion: str = Field(description="Concluding thoughts")


@flock_type
class BlogPost(BaseModel):
    """Complete blog post with full content."""
    title: str
    introduction: str
    sections: list[dict[str, str]] = Field(
        description="List of sections, each with 'heading' and 'content'"
    )
    conclusion: str
    word_count: int = Field(description="Total word count of the post")
    reading_time_minutes: int = Field(description="Estimated reading time")


@flock_type
class BlogSEO(BaseModel):
    """SEO optimization for the blog post."""
    meta_title: str = Field(description="SEO-optimized meta title (50-60 chars)")
    meta_description: str = Field(description="SEO meta description (150-160 chars)")
    keywords: list[str] = Field(description="Relevant SEO keywords")
    readability_score: str = Field(description="Readability assessment")


# ============================================================================
# STEP 2: Create the Orchestrator
# ============================================================================

flock = Flock()


# ============================================================================
# STEP 3: Define the Agent Chain
# ============================================================================
# The magic of Flock: agents automatically connect through the blackboard!
# 
# Flow: BlogTopic → BlogOutline → BlogPost → BlogSEO
#
# How it works:
# 1. outline_agent consumes BlogTopic, produces BlogOutline
# 2. writer_agent consumes BlogOutline, produces BlogPost
# 3. seo_agent consumes BlogPost, produces BlogSEO
#
# The orchestrator automatically:
# - Triggers outline_agent when BlogTopic appears
# - Triggers writer_agent when BlogOutline appears
# - Triggers seo_agent when BlogPost appears
# ============================================================================

# Agent 1: Creates the outline
outline_agent = (
    flock.agent("outline_agent")
    .description(
        "A content strategist who creates structured outlines for blog posts. "
        "Focuses on logical flow and engaging structure."
    )
    .consumes(BlogTopic)
    .publishes(BlogOutline)
)

# Agent 2: Writes the full post
writer_agent = (
    flock.agent("writer_agent")
    .description(
        "A skilled blog writer who expands outlines into full blog posts. "
        "Writes engaging, informative content that matches the target audience."
    )
    .consumes(BlogOutline)  # Consumes what outline_agent produces!
    .publishes(BlogPost)
)

# Agent 3: Optimizes for SEO
seo_agent = (
    flock.agent("seo_agent")
    .description(
        "An SEO specialist who optimizes blog posts for search engines. "
        "Creates meta tags, keywords, and assesses readability."
    )
    .consumes(BlogPost)  # Consumes what writer_agent produces!
    .publishes(BlogSEO)
)


# ============================================================================
# STEP 4: Run the Chain
# ============================================================================

async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("=" * 70)
    print("📝 MULTI-AGENT CHAIN EXAMPLE - Blog Writing Pipeline")
    print("=" * 70)
    print()
    
    # Create the initial topic
    topic = BlogTopic(
        topic="Getting Started with Flock: A Beginner's Guide",
        target_audience="Developers new to AI agent frameworks"
    )
    
    print(f"💡 Blog Topic:")
    print(f"   Topic: {topic.topic}")
    print(f"   Audience: {topic.target_audience}")
    print()
    print("⏳ Publishing topic and watching the chain execute...")
    print("   (outline_agent → writer_agent → seo_agent)")
    print()
    
    # Publish the topic - this triggers the entire chain!
    await flock.publish(topic)
    
    # Run until all agents finish
    await flock.run_until_idle()
    
    # Retrieve results from each stage
    outlines = await flock.store.get_by_type(BlogOutline)
    posts = await flock.store.get_by_type(BlogPost)
    seo_data = await flock.store.get_by_type(BlogSEO)
    
    print("=" * 70)
    print("📊 PIPELINE RESULTS")
    print("=" * 70)
    
    if outlines:
        outline = outlines[0]
        print("\n📋 STAGE 1: Outline Generated")
        print(f"   Title: {outline.title}")
        print(f"   Sections: {len(outline.main_sections)}")
        for i, section in enumerate(outline.main_sections[:3], 1):  # Show first 3
            print(f"      {i}. {section.get('heading', 'N/A')}")
    
    if posts:
        post = posts[0]
        print("\n✍️  STAGE 2: Blog Post Written")
        print(f"   Title: {post.title}")
        print(f"   Word Count: {post.word_count:,}")
        print(f"   Reading Time: {post.reading_time_minutes} minutes")
        print(f"   Sections: {len(post.sections)}")
    
    if seo_data:
        seo = seo_data[0]
        print("\n🔍 STAGE 3: SEO Optimized")
        print(f"   Meta Title: {seo.meta_title}")
        print(f"   Keywords: {', '.join(seo.keywords[:5])}...")
        print(f"   Readability: {seo.readability_score}")
    
    print()
    print("=" * 70)
    print("✅ Complete pipeline executed successfully!")
    print()
    print("💡 Notice how:")
    print("   - Each agent consumed the previous agent's output")
    print("   - The orchestrator automatically triggered agents in sequence")
    print("   - No manual wiring needed - agents connect through types!")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to watch the agent chain execute!")
    print()
    print("💡 Watch how artifacts flow: BlogTopic → BlogOutline → BlogPost → BlogSEO")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# 🎓 NOW IT'S YOUR TURN!
# ============================================================================
# 
# EXPERIMENT 1: Add Another Stage
# --------------------------------
# Add a "reviewer_agent" that consumes BlogPost and produces ReviewedPost:
#   @flock_type
#   class ReviewedPost(BaseModel):
#       original_title: str
#       reviewed_content: str
#       suggestions: list[str]
#       quality_score: float
#
# Create the agent:
#   reviewer_agent = (
#       flock.agent("reviewer_agent")
#       .description("A critical editor who reviews blog posts")
#       .consumes(BlogPost)
#       .publishes(ReviewedPost)
#   )
#
# Where in the chain does this fit? Before or after seo_agent?
#
#
# EXPERIMENT 2: Parallel Processing
# ----------------------------------
# What if you want TWO agents to process BlogPost simultaneously?
# Create a "social_media_agent" that also consumes BlogPost:
#   social_agent = (
#       flock.agent("social_media_agent")
#       .description("Creates social media posts from blog content")
#       .consumes(BlogPost)
#       .publishes(SocialMediaPost)
#   )
#
# What happens when BlogPost is published? Do both agents run?
# Check the dashboard to see parallel execution!
#
#
# EXPERIMENT 3: Branching Chains
# -------------------------------
# Create a branching workflow:
#   BlogTopic → BlogOutline
#            ↓
#   BlogOutline → TechnicalPost (for technical topics)
#   BlogOutline → BeginnerPost (for beginner topics)
#
# Use conditional consumption (we'll learn this in example 03!):
#   technical_writer = (
#       flock.agent("technical_writer")
#       .consumes(BlogOutline, where=lambda o: "technical" in o.topic.lower())
#       .publishes(TechnicalPost)
#   )
#
# Or try semantic matching to route based on content meaning!
#
#
# EXPERIMENT 4: Reverse the Flow
# -------------------------------
# What if you want feedback loops? Create an agent that:
#   - Consumes BlogSEO
#   - Produces BlogTopic (suggestions for new topics based on SEO data)
#
# Does this create a loop? What happens?
#
#
# EXPERIMENT 5: Multiple Inputs
# ------------------------------
# Create an agent that needs BOTH BlogOutline AND BlogPost:
#   comparison_agent = (
#       flock.agent("comparison_agent")
#       .consumes(BlogOutline, BlogPost)  # Needs BOTH!
#       .publishes(ComparisonReport)
#   )
#
# When does this agent trigger? After BlogPost is created, right?
# What if BlogPost arrives before BlogOutline? (Hint: check JoinSpec in example 07)
#
#
# CHALLENGE: Build a Complete Content Pipeline
# ---------------------------------------------
# Design a full content creation system:
#   1. Topic → Outline
#   2. Outline → Draft
#   3. Draft → Reviewed Draft (parallel: SEO + Social Media)
#   4. Reviewed Draft → Published Post
#   5. Published Post → Analytics Report
#
# How many agents? What's the longest chain? Where can you parallelize?
#
# ============================================================================

