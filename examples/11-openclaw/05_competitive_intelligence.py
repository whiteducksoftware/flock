"""
OpenClaw Integration: Competitive Intelligence Pipeline

Complex orchestration example showcasing Flock's full power with OpenClaw.
Eight agents, nine artifact types, six pipeline stages — from product brief
to executive report.

Pipeline Architecture:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  CompetitorBrief (input)                                                │
│         │                                                               │
│  [OpenClaw: MarketScout] ── web search to discover competitors          │
│         │ fan_out=(3, 8)                                                │
│         ▼                                                               │
│  CompetitorProfile (one per competitor)                                  │
│         │                                                               │
│         ├─── [OpenClaw: PricingAnalyst] → PricingData                   │
│         ├─── [OpenClaw: TechAnalyst]    → TechStack                     │
│         └─── [Native:   SentimentAnalyst] → SentimentReport             │
│                        │                                                │
│              JoinSpec(by=competitor_name, within=120s)                   │
│                        │                                                │
│              [Native: CompetitorProfiler] → CompetitorDossier            │
│                        │                                                │
│              BatchSpec(size=3, timeout=180s)                             │
│                        │                                                │
│              [Native: MarketAnalyst] → MarketLandscape                  │
│                        │                                                │
│              When(MarketLandscape exists)                                │
│                        │                                                │
│              [Native: StrategyAdvisor] → StrategicRecommendation        │
│                        │                                                │
│              When(StrategicRecommendation AND MarketLandscape exist)     │
│                        │                                                │
│              [OpenClaw: ReportCompiler] → ExecutiveReport                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

Patterns Showcased:
    1. Dynamic fan-out     — MarketScout discovers 3-8 competitors
    2. Parallel processing — 3 analyzers run concurrently per competitor
    3. JoinSpec            — 3-way correlation by competitor_name (120s window)
    4. BatchSpec           — Accumulate CompetitorDossiers (size=3 OR timeout=180s)
    5. Activation (When)   — StrategyAdvisor and ReportCompiler wait for deps
    6. Mixed agents        — 4 OpenClaw (web research) + 4 native LLM (analysis)

🔧 SETUP:
    1) Enable gateway.http.endpoints.responses.enabled=true in OpenClaw config
    2) export OPENCLAW_CODEX_URL=http://localhost:19789
    3) export OPENCLAW_CODEX_TOKEN=your-token
    4) export DEFAULT_MODEL=openai/gpt-4.1  (for native LLM agents)

Run (CLI):
    uv run python examples/11-openclaw/05_competitive_intelligence.py

Run (Dashboard):
    Set USE_DASHBOARD = True below, then:
    uv run python examples/11-openclaw/05_competitive_intelligence.py

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
import uuid
from datetime import timedelta

from pydantic import BaseModel, Field

from flock import Flock, OpenClawConfig
from flock.core.conditions import When
from flock.core.subscription import BatchSpec, JoinSpec
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# STAGE 1: Artifact Types (9 types across 6 pipeline stages)
# ============================================================================


@flock_type
class CompetitorBrief(BaseModel):
    """Input: describes your product and market for competitive analysis."""

    product_name: str = Field(default="Flock", description="Your product's name")
    product_description: str = Field(
        default="An open-source blackboard-architecture framework for building "
        "multi-agent AI systems with typed artifacts and declarative pipelines.",
        description="What your product does (1-2 sentences)",
    )
    target_market: str = Field(
        default="AI/ML engineers and teams building production agent systems",
        description="Who your product is for",
    )
    key_differentiators: list[str] = Field(
        default_factory=lambda: [
            "Blackboard architecture with typed artifacts",
            "Declarative agent pipelines (no imperative glue code)",
            "Fan-out, JoinSpec, BatchSpec orchestration primitives",
            "Mixed compute backends (OpenClaw + native LLM)",
            "Built-in real-time dashboard",
        ],
        description="What makes your product unique (2-5 points)",
    )
    known_competitors: list[str] = Field(
        default_factory=lambda: ["CrewAI", "LangGraph", "AutoGen"],
        description="Competitors you already know about (optional, helps seed the search)",
    )


@flock_type
class CompetitorProfile(BaseModel):
    """One profile per discovered competitor — feeds the 3 parallel analyzers."""

    competitor_name: str = Field(description="Name of the competitor company/product")
    website_url: str = Field(description="Primary website URL")
    one_liner: str = Field(description="What they do in one sentence")
    target_audience: str = Field(description="Who they serve")
    estimated_size: str = Field(
        description="Company size estimate: startup, scaleup, enterprise"
    )


@flock_type
class PricingData(BaseModel):
    """Pricing intelligence for a single competitor."""

    competitor_name: str = Field(description="Which competitor this pricing is for")
    pricing_model: str = Field(
        description="Pricing model: freemium, subscription, usage-based, enterprise, etc."
    )
    price_range: str = Field(description="Price range or tiers (e.g. '$10-$99/mo')")
    free_tier: bool = Field(description="Whether a free tier exists")
    enterprise_pricing: bool = Field(
        description="Whether custom enterprise pricing exists"
    )
    pricing_notes: str = Field(
        description="Key observations about the pricing strategy"
    )


@flock_type
class TechStack(BaseModel):
    """Technical intelligence for a single competitor."""

    competitor_name: str = Field(description="Which competitor this analysis is for")
    primary_language: str = Field(description="Main programming language or framework")
    infrastructure: str = Field(description="Cloud provider, hosting approach")
    key_integrations: list[str] = Field(
        description="Notable integrations and partnerships"
    )
    api_available: bool = Field(description="Whether a public API is available")
    tech_differentiators: list[str] = Field(
        description="Technical features that stand out"
    )


@flock_type
class SentimentReport(BaseModel):
    """Market sentiment analysis for a single competitor."""

    competitor_name: str = Field(description="Which competitor this sentiment is for")
    overall_sentiment: str = Field(
        description="Overall market sentiment: very_positive, positive, mixed, negative"
    )
    strengths_mentioned: list[str] = Field(
        description="Top strengths cited by users/reviewers"
    )
    weaknesses_mentioned: list[str] = Field(
        description="Top weaknesses cited by users/reviewers"
    )
    market_perception: str = Field(
        description="How the market perceives this competitor (1-2 sentences)"
    )


@flock_type
class CompetitorDossier(BaseModel):
    """Correlated dossier combining pricing, tech, and sentiment for one competitor."""

    competitor_name: str = Field(description="Competitor this dossier covers")
    executive_summary: str = Field(
        description="2-3 sentence summary of this competitor's position"
    )
    threat_level: str = Field(description="Threat level: low, moderate, high, critical")
    pricing_summary: str = Field(description="Key pricing findings")
    tech_summary: str = Field(description="Key technical findings")
    sentiment_summary: str = Field(description="Key sentiment findings")
    competitive_advantages: list[str] = Field(
        description="Their advantages over our product"
    )
    competitive_weaknesses: list[str] = Field(
        description="Their weaknesses relative to our product"
    )


@flock_type
class MarketLandscape(BaseModel):
    """Holistic view of the competitive landscape synthesized from all dossiers."""

    market_summary: str = Field(
        description="Executive summary of the competitive landscape (3-5 sentences)"
    )
    total_competitors_analyzed: int = Field(
        description="Number of competitors analyzed"
    )
    market_segments: list[str] = Field(
        description="Distinct market segments identified"
    )
    pricing_trends: list[str] = Field(
        description="Key pricing trends across the market"
    )
    technology_trends: list[str] = Field(
        description="Key technology trends across competitors"
    )
    market_gaps: list[str] = Field(
        description="Underserved needs or gaps in the market"
    )
    top_threats: list[str] = Field(
        description="Top 3 competitive threats, ranked by severity"
    )


@flock_type
class StrategicRecommendation(BaseModel):
    """Strategic recommendations based on competitive analysis."""

    positioning_statement: str = Field(
        description="Recommended market positioning (2-3 sentences)"
    )
    pricing_recommendations: list[str] = Field(
        description="Pricing strategy recommendations"
    )
    feature_priorities: list[str] = Field(
        description="Features to prioritize based on competitive gaps"
    )
    go_to_market_tactics: list[str] = Field(
        description="GTM tactics to differentiate from competitors"
    )
    risks_to_monitor: list[str] = Field(
        description="Competitive risks that need ongoing monitoring"
    )


@flock_type
class ExecutiveReport(BaseModel):
    """Final deliverable: comprehensive competitive intelligence report."""

    report_title: str = Field(
        description="Title of the competitive intelligence report"
    )
    date_generated: str = Field(description="Date the report was generated")
    executive_summary: str = Field(
        description="High-level executive summary (3-5 sentences)"
    )
    market_overview: str = Field(description="Overview of the competitive landscape")
    competitor_profiles: list[str] = Field(
        description="One-paragraph summary per competitor"
    )
    strategic_recommendations: list[str] = Field(
        description="Top 5-7 strategic recommendations"
    )
    action_items: list[str] = Field(description="Immediate action items for the team")
    appendix_notes: str = Field(
        description="Methodology notes and data freshness caveats"
    )


# ============================================================================
# STAGE 2: Flock Instance + OpenClaw Configuration
# ============================================================================

flock = Flock(openclaw=OpenClawConfig.from_env())


# ============================================================================
# STAGE 3: Agent Definitions (8 agents, mixed OpenClaw + native LLM)
# ============================================================================

# --- Agent 1: MarketScout (OpenClaw) ---
# Discovers competitors via web search, produces 3-8 CompetitorProfiles.
market_scout = (
    flock.openclaw_agent("codex", name="market_scout")
    .description(
        "Competitive intelligence scout. Given a product brief, use web search "
        "to discover direct and indirect competitors. For each competitor found, "
        "produce a CompetitorProfile with their name, website, one-liner description, "
        "target audience, and estimated company size. Discover between 3 and 8 "
        "competitors — prioritize the most relevant ones."
    )
    .consumes(CompetitorBrief)
    .publishes(CompetitorProfile, fan_out=(3, 8))
)


# --- Agent 2: PricingAnalyst (OpenClaw) ---
# Visits competitor websites to extract pricing intelligence.
pricing_analyst = (
    flock.openclaw_agent("codex", name="pricing_analyst")
    .description(
        "Pricing intelligence specialist. Given a competitor profile, search for "
        "and analyze their pricing page. Determine their pricing model, price range, "
        "whether they offer a free tier, enterprise pricing, and any notable pricing "
        "strategy observations. Use web search and fetch to find current pricing data."
    )
    .consumes(CompetitorProfile)
    .publishes(PricingData)
)


# --- Agent 3: TechAnalyst (OpenClaw) ---
# Researches competitor tech stack via web search.
tech_analyst = (
    flock.openclaw_agent("codex", name="tech_analyst")
    .description(
        "Technical intelligence specialist. Given a competitor profile, research their "
        "technology stack. Use web search to find their primary language/framework, "
        "infrastructure choices, key integrations, whether they have a public API, and "
        "any technical differentiators. Check sources like StackShare, GitHub, job "
        "postings, and tech blog posts."
    )
    .consumes(CompetitorProfile)
    .publishes(TechStack)
)


# --- Agent 4: SentimentAnalyst (Native LLM) ---
# Pure text analysis — no tools needed, just reasoning about the profile.
sentiment_analyst = (
    flock.agent("sentiment_analyst")
    .description(
        "Market sentiment analyst. Given a competitor profile, analyze the likely "
        "market sentiment based on the competitor's positioning, target audience, "
        "and market presence. Assess overall sentiment (very_positive, positive, "
        "mixed, negative), identify likely strengths and weaknesses as perceived "
        "by their users, and summarize the market perception. Base your analysis "
        "on the profile information and your knowledge of the market."
    )
    .consumes(CompetitorProfile)
    .publishes(SentimentReport)
)


# --- Agent 5: CompetitorProfiler (Native LLM, JoinSpec) ---
# Waits for all 3 per-competitor analyses, then synthesizes a dossier.
competitor_profiler = (
    flock.agent("competitor_profiler")
    .description(
        "Competitive profiler who synthesizes pricing, technical, and sentiment data "
        "into a comprehensive dossier. Combine all three analyses into an executive "
        "summary, assess the threat level (low/moderate/high/critical), summarize "
        "each dimension, and identify the competitor's advantages and weaknesses "
        "relative to our product."
    )
    .consumes(
        PricingData,
        TechStack,
        SentimentReport,
        join=JoinSpec(
            by=lambda artifact: artifact.competitor_name,
            within=timedelta(seconds=120),
        ),
    )
    .publishes(CompetitorDossier)
)


# --- Agent 6: MarketAnalyst (Native LLM, BatchSpec) ---
# Accumulates dossiers and synthesizes the full market landscape.
market_analyst = (
    flock.agent("market_analyst")
    .description(
        "Market landscape analyst. Given a batch of competitor dossiers, synthesize "
        "a holistic view of the competitive landscape. Identify market segments, "
        "pricing trends, technology trends, market gaps, and the top 3 competitive "
        "threats. Provide the total count of competitors analyzed."
    )
    .consumes(
        CompetitorDossier,
        batch=BatchSpec(
            size=3,
            timeout=timedelta(seconds=180),
        ),
    )
    .publishes(MarketLandscape)
)


# --- Agent 7: StrategyAdvisor (Native LLM, When activation) ---
# Activates only after the MarketLandscape is available.
strategy_advisor = (
    flock.agent("strategy_advisor")
    .description(
        "Strategic advisor who converts market analysis into actionable strategy. "
        "Based on the market landscape, formulate a positioning statement, pricing "
        "recommendations, feature priorities, go-to-market tactics, and risks to "
        "monitor. Be specific and actionable — this goes to the leadership team."
    )
    .consumes(
        MarketLandscape,
        activation=When.correlation(MarketLandscape).exists(),
    )
    .publishes(StrategicRecommendation)
)


# --- Agent 8: ReportCompiler (OpenClaw, When activation) ---
# Activates when BOTH MarketLandscape and StrategicRecommendation exist.
report_compiler = (
    flock.openclaw_agent("codex", name="report_compiler")
    .description(
        "Executive report compiler. Given the market landscape and strategic "
        "recommendations, produce a polished executive report. Include a clear title, "
        "today's date, executive summary, market overview, per-competitor profiles, "
        "strategic recommendations, action items, and methodology notes. This is the "
        "final deliverable for leadership — make it clear, concise, and actionable."
    )
    .consumes(
        MarketLandscape,
        activation=(
            When.correlation(MarketLandscape).exists()
            & When.correlation(StrategicRecommendation).exists()
        ),
    )
    .publishes(ExecutiveReport)
)


# ============================================================================
# STAGE 4: Execution — CLI Mode
# ============================================================================


async def main_cli():
    """CLI mode: run the full pipeline and display results in the terminal."""
    print("=" * 70)
    print("🎯 COMPETITIVE INTELLIGENCE PIPELINE")
    print("=" * 70)
    print()
    print("Pipeline Architecture:")
    print("  CompetitorBrief")
    print("       │")
    print("  [MarketScout] ── web search ── fan_out=(3,8)")
    print("       │")
    print("  CompetitorProfile (×N)")
    print("       ├── [PricingAnalyst]  → PricingData")
    print("       ├── [TechAnalyst]     → TechStack")
    print("       └── [SentimentAnalyst] → SentimentReport")
    print("              │")
    print("       JoinSpec(by=competitor_name)")
    print("              │")
    print("       [CompetitorProfiler] → CompetitorDossier")
    print("              │")
    print("       BatchSpec(size=3, timeout=180s)")
    print("              │")
    print("       [MarketAnalyst] → MarketLandscape")
    print("              │")
    print("       [StrategyAdvisor] → StrategicRecommendation")
    print("              │")
    print("       [ReportCompiler] → ExecutiveReport")
    print()

    # Create the input brief
    brief = CompetitorBrief(
        product_name="Flock",
        product_description=(
            "An open-source blackboard-architecture framework for building "
            "multi-agent AI systems with typed artifacts and declarative pipelines."
        ),
        target_market="AI/ML engineers and teams building production agent systems",
        key_differentiators=[
            "Blackboard architecture with typed artifacts",
            "Declarative agent pipelines (no imperative glue code)",
            "Fan-out, JoinSpec, BatchSpec orchestration primitives",
            "Mixed compute backends (OpenClaw + native LLM)",
            "Built-in real-time dashboard",
        ],
        known_competitors=["CrewAI", "LangGraph", "AutoGen"],
    )

    # Track the workflow with a correlation ID
    correlation_id = str(uuid.uuid4())

    print(f"📋 Product: {brief.product_name}")
    print(f"   Market: {brief.target_market}")
    print(f"   Known competitors: {', '.join(brief.known_competitors)}")
    print(f"   Correlation ID: {correlation_id[:8]}...")
    print()

    # Launch the pipeline
    print("🚀 Launching pipeline...")
    print("   Stage 1: MarketScout discovers competitors (OpenClaw + web search)")
    print("   Stage 2: 3 analyzers run in parallel per competitor")
    print("   Stage 3: JoinSpec correlates results per competitor")
    print("   Stage 4: BatchSpec accumulates dossiers")
    print("   Stage 5: MarketAnalyst + StrategyAdvisor synthesize")
    print("   Stage 6: ReportCompiler produces final deliverable")
    print()

    await flock.publish(brief, correlation_id=correlation_id)
    await flock.run_until_idle()

    # ---- Display Results ----
    print()
    print("=" * 70)
    print("📊 PIPELINE RESULTS")
    print("=" * 70)

    # Competitor Profiles
    profiles = await flock.store.get_by_type(
        CompetitorProfile, correlation_id=correlation_id
    )
    print(f"\n🔍 Competitors Discovered: {len(profiles)}")
    for p in profiles:
        print(f"   • {p.competitor_name} — {p.one_liner[:60]}...")

    # Dossiers
    dossiers = await flock.store.get_by_type(
        CompetitorDossier, correlation_id=correlation_id
    )
    print(f"\n📁 Dossiers Compiled: {len(dossiers)}")
    for d in dossiers:
        print(f"   • {d.competitor_name} — Threat: {d.threat_level}")
        print(f"     {d.executive_summary[:80]}...")

    # Market Landscape
    landscapes = await flock.store.get_by_type(
        MarketLandscape, correlation_id=correlation_id
    )
    if landscapes:
        ml = landscapes[0]
        print(f"\n🗺️  Market Landscape:")
        print(f"   Competitors analyzed: {ml.total_competitors_analyzed}")
        print(f"   Segments: {', '.join(ml.market_segments[:4])}")
        print(f"   Top threats:")
        for t in ml.top_threats[:3]:
            print(f"     ⚠️  {t}")
        print(f"   Market gaps:")
        for g in ml.market_gaps[:3]:
            print(f"     💡 {g}")

    # Strategic Recommendations
    strategies = await flock.store.get_by_type(
        StrategicRecommendation, correlation_id=correlation_id
    )
    if strategies:
        sr = strategies[0]
        print(f"\n🎯 Strategic Recommendations:")
        print(f"   Positioning: {sr.positioning_statement[:80]}...")
        print(f"   Feature priorities:")
        for fp in sr.feature_priorities[:3]:
            print(f"     → {fp}")
        print(f"   GTM tactics:")
        for tactic in sr.go_to_market_tactics[:3]:
            print(f"     → {tactic}")

    # Executive Report
    reports = await flock.store.get_by_type(
        ExecutiveReport, correlation_id=correlation_id
    )
    if reports:
        er = reports[0]
        print(f"\n📄 Executive Report: {er.report_title}")
        print(f"   Date: {er.date_generated}")
        print(f"   Summary: {er.executive_summary[:120]}...")
        print(f"   Action items: {len(er.action_items)}")
        for item in er.action_items[:3]:
            print(f"     ✅ {item}")

    # Pipeline Summary
    print()
    print("=" * 70)
    print("📈 PIPELINE SUMMARY")
    print("=" * 70)
    print(f"   Competitors discovered:    {len(profiles)}")
    print(f"   Dossiers compiled:         {len(dossiers)}")
    print(f"   Market landscapes:         {len(landscapes)}")
    print(f"   Strategic recommendations: {len(strategies)}")
    print(f"   Executive reports:         {len(reports)}")
    print()
    print("✅ Competitive intelligence pipeline complete!")
    print()
    print("💡 Patterns Used:")
    print("   1. fan_out=(3,8)  — Dynamic competitor discovery")
    print("   2. Parallel agents — PricingAnalyst ∥ TechAnalyst ∥ SentimentAnalyst")
    print("   3. JoinSpec       — Correlate 3 analyses by competitor_name")
    print("   4. BatchSpec      — Accumulate dossiers before market synthesis")
    print("   5. When activation — StrategyAdvisor waits for MarketLandscape")
    print("   6. When composite — ReportCompiler waits for Landscape + Strategy")
    print("   7. Mixed agents   — 4 OpenClaw (web research) + 4 native (analysis)")


# ============================================================================
# STAGE 5: Execution — Dashboard Mode
# ============================================================================


async def main_dashboard():
    """Dashboard mode: serve with the real-time web interface.

    Open http://localhost:8344 to watch the pipeline execute live.
    You'll see artifacts flowing through all 6 stages in real time.
    """
    print("🌐 Starting Flock Dashboard for Competitive Intelligence Pipeline...")
    print("   Open http://localhost:8344 to watch the pipeline live!")
    print()
    print("💡 What to watch for:")
    print("   • MarketScout fan-out: 3-8 CompetitorProfiles appear")
    print("   • Parallel analyzers: 3 agents fire per competitor simultaneously")
    print("   • JoinSpec correlation: Dossiers appear after all 3 analyses complete")
    print("   • BatchSpec accumulation: MarketLandscape appears after dossiers batch")
    print(
        "   • When activations: StrategyAdvisor and ReportCompiler trigger in sequence"
    )
    print()
    await flock.serve(dashboard=True)


# ============================================================================
# STAGE 6: Entry Point
# ============================================================================


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
