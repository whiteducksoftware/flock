"""
Getting Started: News Batching

This example demonstrates real-world batch processing with multiple agents.
Multiple category analysts process in parallel, then results are batched
together for a daily digest.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from flock.mcp import StdioServerParameters
from flock import Flock
from flock.registry import flock_type
from flock.core.subscription import BatchSpec

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class Trigger(BaseModel):
    today_date: str = Field(
        default=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        description="Today's date in YYYY-MM-DD format",
    )


@flock_type
class NewsAnalysis(BaseModel):
    category: str
    key_takeaways: list[str]
    impact_assessment: str


@flock_type
class NewsDigest(BaseModel):
    summary_title: str
    summary_of_all_news: list[str]
    key_takeaways: list[str]


flock = Flock()

try:
    flock.add_mcp(
        name="search_web",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="uvx",
            args=["duckduckgo-mcp-server"],
        ),
    )
    print("✅ Added search MCP")
except Exception as e:
    print(f"⚠️  Could not add search MCP: {e}")

try:
    flock.add_mcp(
        name="web_reader",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@just-every/mcp-read-website-fast"],
        ),
    )
    print("✅ Added web reader MCP")
except Exception as e:
    print(f"⚠️  Could not add web reader MCP: {e}")

categories = [
    "world",
    "tech",
    "business",
    "sports",
    "entertainment",
    "science",
    "politics",
    "health",
]

for category in categories:
    (
        flock.agent(f"{category}_analyst")
        .description(
            f"Searches the web for {category} news and provides key takeaways and impact assessment."
        )
        .with_mcps(["search_web", "web_reader"])
        .consumes(Trigger)
        .publishes(NewsAnalysis)
    )


editor = (
    flock.agent("editor")
    .consumes(NewsAnalysis, batch=BatchSpec(size=8, timeout=timedelta(seconds=60)))
    .publishes(NewsDigest)
)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("📰 News Batching - Daily Digest Generation")
    print("=" * 60)
    print("📡 Starting 8 news category analysts in parallel...\n")

    trigger = Trigger()
    print(f"📅 Date: {trigger.today_date}")
    print(f"🔍 Categories: {', '.join(categories)}\n")

    print("⏳ Waiting for all analysts to complete...")
    await flock.publish(trigger)
    await flock.run_until_idle()

    digests = await flock.store.get_by_type(NewsDigest)

    if digests:
        digest = digests[0]
        print("\n" + "=" * 60)
        print("📰 TODAY'S NEWS DIGEST")
        print("=" * 60)
        print(f"\n📌 {digest.summary_title}\n")
        print("📋 Summary:")
        for i, summary in enumerate(digest.summary_of_all_news, 1):
            print(f"   {i}. {summary}")
        print("\n🎯 Key Takeaways:")
        for takeaway in digest.key_takeaways:
            print(f"   • {takeaway}")
    else:
        print("❌ No digest was generated!")
        print("💡 Make sure MCPs are installed (duckduckgo-mcp-server and mcp-read-website-fast)")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
