"""
Hackathon Track 11: News Batching with Agent Components

🎓 LEARNING OBJECTIVE:
Combine MCP-powered news analysis with batch processing AND agent components.

This example builds on:
- MCP usage from the news examples (web search + website reader)
- Batch processing (BatchSpec) to create a daily digest
- Agent components to add cross-cutting behavior:
  - Per-category metrics and logging
  - Digest-level statistics

KEY CONCEPTS:
- MCP tools used by multiple agents
- BatchSpec for aggregating many analyses into one digest
- AgentComponent hooks (`on_post_evaluate`, `on_post_publish`)
- Using component state, logs, and metrics for observability

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.components import AgentComponent
from flock.core.subscription import BatchSpec
from flock.mcp import StdioServerParameters
from flock.registry import flock_type
from flock.runtime import EvalInputs, EvalResult


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# STEP 1: Define Types
# ============================================================================


@flock_type
class Trigger(BaseModel):
    """Trigger artifact that kicks off a daily news run."""

    today_date: str = Field(
        default_factory=lambda: datetime.now(tz=UTC).strftime("%Y-%m-%d"),
        description="Today's date in YYYY-MM-DD format",
    )


@flock_type
class NewsAnalysis(BaseModel):
    """Analysis for a single news category (e.g. tech, sports)."""

    category: str
    key_takeaways: list[str] = Field(
        description="3–7 bullet points summarizing important stories"
    )
    impact_assessment: str = Field(
        description="Short paragraph on why this category matters today"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.7,
        description="How confident the analyst is in this summary (0–1)",
    )


@flock_type
class NewsDigest(BaseModel):
    """Combined digest produced by the editor from all category analyses."""

    summary_title: str
    per_category_overview: list[str] = Field(
        description="One-line overview per category"
    )
    global_takeaways: list[str] = Field(
        description="3–10 overarching insights across all categories"
    )
    low_confidence_categories: list[str] = Field(
        description="Categories where analysts were uncertain (confidence < 0.6)"
    )


# ============================================================================
# STEP 2: Create the Orchestrator and Register MCP Servers
# ============================================================================
# We reuse the same MCP servers as the news batching example:
# - search_web: DuckDuckGo search via `uvx duckduckgo-mcp-server`
# - web_reader: website reader via `npx @just-every/mcp-read-website-fast`
#
# Both are key-free: no additional API keys are required.
# If they aren't installed, we log a warning and allow the agents to fall back
# to LLM-only behavior.
# ============================================================================

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
    print("✅ Added search MCP (search_web)")
except Exception as e:  # pragma: no cover - environment dependent
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
    print("✅ Added web reader MCP (web_reader)")
except Exception as e:  # pragma: no cover - environment dependent
    print(f"⚠️  Could not add web reader MCP: {e}")


# ============================================================================
# STEP 3: Define Agent Components
# ============================================================================
# We'll create two AgentComponents:
#
# 1) CategoryMetricsComponent
#    - Attached to each category analyst
#    - Tracks how many analyses they've produced
#    - Counts how often confidence < 0.6
#    - Writes metrics + logs for observability
#
# 2) DigestStatsComponent
#    - Attached to the editor
#    - Tracks how many global_takeaways were generated
#    - Logs digest stats after each run
# ============================================================================


class CategoryMetricsComponent(AgentComponent):
    """Tracks per-category analysis metrics and logs them.

    This component is stateless from the LLM's perspective but stateful from
    the orchestrator's perspective: it remembers how many analyses have been
    produced and how often the analyst was uncertain.
    """

    analyses_seen: int = Field(
        default=0,
        description="How many NewsAnalysis artifacts this agent has produced",
    )
    low_confidence_count: int = Field(
        default=0,
        description="How many analyses had confidence < 0.6",
    )

    async def on_post_evaluate(
        self, agent, ctx, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """Run after the agent generates its output, before publishing."""
        if not result.has_output:
            return result

        data = result.output_value
        # Extract confidence and category from the output (dict or BaseModel)
        if isinstance(data, dict):
            confidence = float(data.get("confidence", 0.7))
            category = str(data.get("category", agent.name.replace("_analyst", "")))
        else:
            confidence = float(getattr(data, "confidence", 0.7))
            category = str(getattr(data, "category", agent.name.replace("_analyst", "")))

        self.analyses_seen += 1
        if confidence < 0.6:
            self.low_confidence_count += 1

        # Record metrics for dashboard/monitoring
        result.metrics["analyses_seen"] = self.analyses_seen
        result.metrics["low_confidence_count"] = self.low_confidence_count
        result.metrics["latest_confidence"] = confidence

        # Add a human-readable log entry
        result.logs.append(
            f"[CategoryMetrics] {agent.name} produced analysis for '{category}' "
            f"with confidence={confidence:.2f} "
            f"(low={self.low_confidence_count}/{self.analyses_seen})"
        )
        return result

    async def on_post_publish(self, agent, ctx, artifact) -> None:
        """Run after the artifact is published to the blackboard."""
        category = artifact.payload.get("category", "unknown")
        confidence = artifact.payload.get("confidence", 0.7)
        print(
            f"🧮 [{agent.name}] Published analysis for {category!r} "
            f"(confidence={confidence:.2f})"
        )


class DigestStatsComponent(AgentComponent):
    """Tracks digest statistics like number of global takeaways."""

    last_digest_takeaway_count: int = Field(
        default=0, description="How many global_takeaways the last digest had"
    )

    async def on_post_evaluate(
        self, agent, ctx, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """Run after the editor assembles the digest."""
        if not result.has_output:
            return result

        data = result.output_value
        if isinstance(data, dict):
            takeaways = data.get("global_takeaways", [])
        else:
            takeaways = getattr(data, "global_takeaways", [])

        self.last_digest_takeaway_count = len(takeaways or [])
        result.metrics["global_takeaway_count"] = self.last_digest_takeaway_count
        result.logs.append(
            f"[DigestStats] Digest contains {self.last_digest_takeaway_count} global takeaways."
        )
        return result


# ============================================================================
# STEP 4: Define Agents (Category Analysts + Editor)
# ============================================================================

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

# One analyst per category, all using the same MCP servers + metrics component
for category in categories:
    (
        flock.agent(f"{category}_analyst")
        .description(
            f"Specialist {category} news analyst. Use web search and website reading "
            f"tools to gather today's most important {category} stories. "
            "Return 3–7 key_takeaways, a short impact_assessment, and a confidence "
            "score between 0.0 and 1.0 representing how sure you are."
        )
        .with_mcps(
            {
                "search_web": {"tool_whitelist": ["search"]},
                "web_reader": {"tool_whitelist": ["read_website", "read_url", "read"]},
            }
        )
        .with_utilities(CategoryMetricsComponent())
        .consumes(Trigger)
        .publishes(NewsAnalysis)
    )


editor = (
    flock.agent("editor")
    .description(
        "Daily news editor who waits for all category analyses, then produces a "
        "single NewsDigest. The digest should contain:\n"
        "1) A summary_title for the whole day.\n"
        "2) A one-line overview per category in per_category_overview.\n"
        "3) 3–10 global_takeaways combining patterns across categories.\n"
        "4) A list of low_confidence_categories where analysts reported "
        "confidence < 0.6."
    )
    .consumes(
        NewsAnalysis,
        batch=BatchSpec(
            size=len(categories),  # Wait for all categories if possible
            timeout=timedelta(seconds=60),  # But don't wait forever
        ),
    )
    .with_utilities(DigestStatsComponent())
    .publishes(NewsDigest)
)


# ============================================================================
# STEP 5: Run and Observe
# ============================================================================


async def main_cli() -> None:
    """CLI mode: Run agents and display the digest in the terminal."""
    print("📰 News Batching with Agent Components - Daily Digest")
    print("=" * 80)
    print("📡 Starting category analysts in parallel...")
    print()

    trigger = Trigger()
    print(f"📅 Date       : {trigger.today_date}")
    print(f"🔍 Categories : {', '.join(categories)}")
    print()
    print("⏳ Waiting for all analysts to complete and editor to batch results...")
    print()

    await flock.publish(trigger)
    await flock.run_until_idle()

    digests = await flock.store.get_by_type(NewsDigest)

    if not digests:
        print("❌ No NewsDigest artifacts were generated.")
        print("   - Check MCP installation messages above.")
        print("   - The editor may still be waiting for analyses.")
        return

    digest = digests[0]

    print("\n" + "=" * 80)
    print("📰 TODAY'S NEWS DIGEST")
    print("=" * 80)
    print()
    print(f"🏷️  Title: {digest.summary_title}")
    print()

    print("📂 Per-Category Overview")
    print("------------------------")
    for line in digest.per_category_overview:
        print(f"- {line}")

    print()
    print("🌍 Global Takeaways")
    print("-------------------")
    for i, takeaway in enumerate(digest.global_takeaways, start=1):
        print(f"{i:2d}. {takeaway}")

    print()
    print("⚠️  Low-Confidence Categories")
    print("-----------------------------")
    if digest.low_confidence_categories:
        print(", ".join(sorted(set(digest.low_confidence_categories))))
    else:
        print("None (all analysts were reasonably confident).")


async def main_dashboard() -> None:
    """Dashboard mode: Serve with interactive web interface."""
    print("🌐 Starting Flock Dashboard for News Batching with Components...")
    print("   Visit http://localhost:8344 to:")
    print("   - Publish Trigger artifacts")
    print("   - Watch category analysts and the editor run")
    print("   - Inspect metrics/logs from CategoryMetricsComponent and DigestStatsComponent")
    print()
    await flock.serve(dashboard=True)


async def main() -> None:
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
# EXPERIMENT 1: Change Categories
# -------------------------------
# Modify the `categories` list above:
#   categories = ["ai", "climate", "economy"]
#
# How does the digest change when you focus on just a few topics?
# Does the editor still wait for all categories before running?
#
#
# EXPERIMENT 2: Tune BatchSpec Behavior
# -------------------------------------
# Change the BatchSpec in the editor:
#   - Reduce size to 4
#   - Reduce timeout to 10 seconds
#
# This simulates a scenario where not all category analysts report in time.
# What happens when some NewsAnalysis artifacts are missing?
# How does that affect the digest?
#
#
# EXPERIMENT 3: Tighten Confidence Thresholds
# -------------------------------------------
# Update CategoryMetricsComponent to treat confidence < 0.7 as "low":
#   if confidence < 0.7:
#       self.low_confidence_count += 1
#
# Run the example a few times:
#   - Do you see more low-confidence categories?
#   - How might you use this to decide where to invest more analyst time?
#
#
# EXPERIMENT 4: Add a Quality Gate Component
# ------------------------------------------
# Create a new AgentComponent that enforces a minimum number of key_takeaways
# (e.g., at least 3). In `on_post_evaluate`, if the analysis has too few
# takeaways, you could:
#   - Add a log entry saying "insufficient detail"
#   - Or even return EvalResult.empty() to drop the output
#
# Attach it to one or more category analysts with .with_utilities(...).
# What happens to the digest when some analyses are dropped?
#
#
# EXPERIMENT 5: Digest-Level Alerts
# ---------------------------------
# Extend DigestStatsComponent to:
#   - Raise an alert (log + metric) if global_takeaway_count < 3
#   - Or if there are more than 3 low-confidence categories
#
# How would you surface this in a real dashboard (e.g., warning badges)?
#
#
# EXPERIMENT 6: Combine with Other MCP Servers
# --------------------------------------------
# Try adding another MCP server (like filesystem) and have the editor:
#   - Append the digest to a daily markdown file
#   - Or archive digests under a /news/ directory
#
# This would combine:
#   - MCP web tools (search + web_reader)
#   - MCP filesystem tools
#   - Batch processing
#   - Agent components for metrics and quality gates
#
# ============================================================================

