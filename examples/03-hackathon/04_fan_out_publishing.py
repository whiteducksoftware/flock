"""
Hackathon Track 04: Fan-Out Publishing

🎓 LEARNING OBJECTIVE:
Learn how agents can produce MULTIPLE artifacts from a single execution.
This is powerful for generating variations, exploring options, and optimizing costs.

KEY CONCEPTS:
- Fan-out publishing (fan_out parameter)
- Generating multiple outputs in one LLM call
- Cost optimization (1 call vs N calls)
- Filtering and validating fan-out outputs

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
# STEP 1: Define Types
# ============================================================================

@flock_type
class ProductBrief(BaseModel):
    """A brief description of a product to market."""
    product_name: str = Field(description="Name of the product")
    target_market: str = Field(description="Who is this product for?")
    key_features: list[str] = Field(description="Main features of the product")


@flock_type
class MarketingSlogan(BaseModel):
    """A catchy marketing slogan for the product."""
    slogan: str = Field(description="The marketing slogan")
    tone: str = Field(description="Tone: professional, playful, serious, inspiring")
    target_emotion: str = Field(description="What emotion should this evoke?")
    length: int = Field(description="Character count")


# ============================================================================
# STEP 2: Create the Orchestrator
# ============================================================================

flock = Flock()


# ============================================================================
# STEP 3: Define Agent with Fan-Out
# ============================================================================
# Fan-out means generating MULTIPLE artifacts from ONE agent execution.
#
# Without fan-out:
#   Input → Agent → 1 Output (1 LLM call)
#
# With fan_out=5:
#   Input → Agent → 5 Outputs (1 LLM call, not 5!)
#
# This is MUCH cheaper and faster than running the agent 5 times!
# ============================================================================

# Generate 5 different slogans in one execution
slogan_generator = (
    flock.agent("slogan_generator")
    .description(
        "Creates catchy marketing slogans for products. "
        "Generate diverse slogans with different tones and emotions."
    )
    .consumes(ProductBrief)
    .publishes(
        MarketingSlogan,
        fan_out=5  # Generate 5 slogans per execution!
    )
)


# ============================================================================
# STEP 4: Run and See Multiple Outputs
# ============================================================================

async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("=" * 70)
    print("🚀 FAN-OUT PUBLISHING EXAMPLE - Marketing Slogan Generator")
    print("=" * 70)
    print()
    
    # Create a product brief
    brief = ProductBrief(
        product_name="EcoClean Water Filter",
        target_market="Environmentally conscious homeowners",
        key_features=["Removes 99% contaminants", "Zero plastic waste", "Easy installation"]
    )
    
    print(f"📦 Product Brief:")
    print(f"   Product: {brief.product_name}")
    print(f"   Target: {brief.target_market}")
    print(f"   Features: {', '.join(brief.key_features)}")
    print()
    print("⏳ Generating 5 marketing slogans (fan_out=5)...")
    print("   (This happens in ONE LLM call, not five!)")
    print()
    
    # Publish the brief
    await flock.publish(brief)
    
    # Run until completion
    await flock.run_until_idle()
    
    # Retrieve all generated slogans
    slogans = await flock.store.get_by_type(MarketingSlogan)
    
    print("=" * 70)
    print(f"✅ Generated {len(slogans)} Marketing Slogans")
    print("=" * 70)
    print()
    
    for i, slogan in enumerate(slogans, 1):
        print(f"{i}. {slogan.slogan}")
        print(f"   Tone: {slogan.tone} | Emotion: {slogan.target_emotion} | Length: {slogan.length} chars")
        print()
    
    print("=" * 70)
    print("💡 Key Benefits of Fan-Out:")
    print("   ✅ Cost: 1 LLM call instead of 5")
    print("   ✅ Speed: Faster than sequential calls")
    print("   ✅ Context: All outputs share the same input context")
    print("   ✅ Diversity: LLM generates varied outputs naturally")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to see fan-out in action!")
    print()
    print("💡 Watch how ONE input produces MULTIPLE outputs!")
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
# EXPERIMENT 1: Change Fan-Out Count
# -----------------------------------
# Try different fan_out values:
#   .publishes(MarketingSlogan, fan_out=3)   # Generate 3 slogans
#   .publishes(MarketingSlogan, fan_out=10)  # Generate 10 slogans
#   .publishes(MarketingSlogan, fan_out=1)   # Same as no fan-out
#
# How does the output change? What's the optimal number?
#
#
# EXPERIMENT 2: Filter Fan-Out Outputs
# -------------------------------------
# Add a `where` clause to filter outputs:
#   slogan_generator = (
#       flock.agent("slogan_generator")
#       .consumes(ProductBrief)
#       .publishes(
#           MarketingSlogan,
#           fan_out=10,
#           where=lambda s: s.length <= 50  # Only short slogans!
#       )
#   )
#
# How many slogans pass the filter? What if you generate 10 but only 3 pass?
#
#
# EXPERIMENT 3: Validate Fan-Out Outputs
# ---------------------------------------
# Add validation to ensure quality:
#   slogan_generator = (
#       flock.agent("slogan_generator")
#       .consumes(ProductBrief)
#       .publishes(
#           MarketingSlogan,
#           fan_out=10,
#           validate=lambda s: s.length >= 20 and s.length <= 60
#       )
#   )
#
# What happens if validation fails? Check the logs!
#
#
# EXPERIMENT 4: Dynamic Fan-Out Range
# ------------------------------------
# Use a RANGE instead of fixed count:
#   from flock.core import FanOutRange
#
#   slogan_generator = (
#       flock.agent("slogan_generator")
#       .consumes(ProductBrief)
#       .publishes(
#           MarketingSlogan,
#           fan_out=(3, 8)  # Generate 3-8 slogans (engine decides!)
#       )
#   )
#
# How many does it generate? Does it vary based on product complexity?
#
#
# EXPERIMENT 5: Multi-Type Fan-Out
# ---------------------------------
# Generate MULTIPLE types in one call:
#   @flock_type
#   class SocialMediaPost(BaseModel):
#       platform: str
#       content: str
#       hashtags: list[str]
#
#   content_creator = (
#       flock.agent("content_creator")
#       .consumes(ProductBrief)
#       .publishes(
#           MarketingSlogan, fan_out=3,
#           SocialMediaPost, fan_out=2
#       )
#   )
#
# This generates 3 slogans + 2 social posts = 5 artifacts in ONE call!
# How much does this save vs separate calls?
#
#
# EXPERIMENT 6: Fan-Out with Conditional Consumption
# ----------------------------------------------------
# Combine fan-out with conditional consumption downstream:
#   brief_agent = (
#       flock.agent("brief_agent")
#       .consumes(ProductBrief)
#       .publishes(MarketingSlogan, fan_out=10)
#   )
#
#   short_slogan_agent = (
#       flock.agent("short_slogan_agent")
#       .consumes(MarketingSlogan, where=lambda s: s.length <= 30)
#       .publishes(MarketingSlogan)  # Process short ones
#   )
#
#   long_slogan_agent = (
#       flock.agent("long_slogan_agent")
#       .consumes(MarketingSlogan, where=lambda s: s.length > 50)
#       .publishes(MarketingSlogan)  # Process long ones
#   )
#
# How many slogans does each downstream agent process?
#
#
# CHALLENGE: Build a Content Variation System
# ---------------------------------------------
# Create a system that:
#   1. Takes a blog topic
#   2. Generates 5 different blog titles (fan-out)
#   3. Filters to keep only titles with certain keywords (where)
#   4. Validates titles are 40-60 characters (validate)
#   5. For each valid title, generates 3 social media posts (another fan-out)
#
# How many artifacts total? How many LLM calls?
# Calculate the cost savings vs sequential generation!
#
# ============================================================================

