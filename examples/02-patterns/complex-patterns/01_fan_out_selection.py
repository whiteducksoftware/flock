"""
Fan-Out Selection Patterns: React to the "Best" from Multiple Outputs

This example demonstrates THREE different patterns for selecting specific
artifacts from fan-out outputs. When an agent generates N variations,
how do you react to just ONE (the best)?

🎓 LEARNING OBJECTIVE:
Understand different strategies for downstream agents to select or filter
fan-out outputs, each with distinct tradeoffs.

KEY CONCEPTS:
- Pattern 1: Threshold Filter (where=) - Simple but imprecise
- Pattern 2: Two-Stage Selector - Explicit but adds latency
- Pattern 3: LLM Self-Selection - Elegant but requires LLM compliance

🎛️  CONFIGURATION: Set PATTERN to switch between patterns (1, 2, or 3)
                   Set USE_DASHBOARD for interactive mode

Run:
    uv run python examples/02-patterns/complex-patterns/01_fan_out_selection.py
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.core.subscription import BatchSpec
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
PATTERN = 3  # Which pattern to demonstrate: 1, 2, or 3
# ============================================================================


# ============================================================================
# SHARED TYPES: Used by all patterns
# ============================================================================


@flock_type
class ResearchTopic(BaseModel):
    """A topic to research and generate hypotheses for."""

    question: str = Field(description="The research question to explore")
    context: str = Field(description="Background context for the research")


@flock_type
class FinalAnalysis(BaseModel):
    """The final analysis based on the selected hypothesis."""

    selected_hypothesis: str = Field(description="The hypothesis that was selected")
    analysis: str = Field(description="Detailed analysis of the hypothesis")
    implications: list[str] = Field(description="Key implications of this finding")


# ============================================================================
# PATTERN 1: Threshold Filter
# ============================================================================
# Pros: Simple, no extra agents
# Cons: Not guaranteed "THE best", could match 0 or many
#
# Use when: You need "good enough" not "the absolute best"
# ============================================================================


@flock_type
class HypothesisP1(BaseModel):
    """Hypothesis for Pattern 1 (threshold filter)."""

    content: str = Field(description="The hypothesis statement")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Why this hypothesis is plausible")


def create_pattern_1(flock: Flock) -> None:
    """Pattern 1: Threshold Filter - use where= to filter high-confidence only."""

    # Generator produces 5 hypotheses
    flock.agent("hypothesis_generator_p1").description(
        "Generate multiple research hypotheses with varying confidence levels. "
        "Be honest about confidence - not all hypotheses should be high confidence."
    ).consumes(ResearchTopic).publishes(HypothesisP1, fan_out=5)

    # Analyst only sees hypotheses above threshold
    # May trigger 0, 1, or multiple times!
    flock.agent("analyst_p1").description(
        "Analyze a high-confidence hypothesis and explain its implications."
    ).consumes(
        HypothesisP1,
        where=lambda h: h.confidence >= 0.85,  # Only high-confidence!
    ).publishes(FinalAnalysis)


# ============================================================================
# PATTERN 2: Two-Stage Selector
# ============================================================================
# Pros: Guaranteed single best, explicit selection logic
# Cons: Extra agent = extra LLM call = cost/latency
#
# Use when: You need deterministic "pick exactly one" behavior
# ============================================================================


@flock_type
class HypothesisP2(BaseModel):
    """Hypothesis for Pattern 2 (two-stage selector)."""

    content: str = Field(description="The hypothesis statement")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Why this hypothesis is plausible")


@flock_type
class SelectedHypothesis(BaseModel):
    """The single best hypothesis, selected by the selector agent."""

    content: str = Field(description="The selected hypothesis statement")
    confidence: float = Field(description="Confidence of the selected hypothesis")
    selection_reason: str = Field(description="Why this one was chosen as best")


def create_pattern_2(flock: Flock) -> None:
    """Pattern 2: Two-Stage Selector - batch all, then pick the best."""

    # Generator produces 5 hypotheses
    flock.agent("hypothesis_generator_p2").description(
        "Generate multiple research hypotheses with varying confidence levels."
    ).consumes(ResearchTopic).publishes(HypothesisP2, fan_out=5)

    # Selector batches all 5, picks the single best
    flock.agent("hypothesis_selector").description(
        "Review all hypotheses and select the single BEST one. "
        "Consider confidence, clarity, and testability. "
        "Output exactly one SelectedHypothesis."
    ).consumes(
        HypothesisP2,
        batch=BatchSpec(size=5),  # Wait for all 5 before processing
    ).publishes(SelectedHypothesis)

    # Analyst only sees the winner
    flock.agent("analyst_p2").description(
        "Analyze the selected best hypothesis and explain its implications."
    ).consumes(SelectedHypothesis).publishes(FinalAnalysis)


# ============================================================================
# PATTERN 3: LLM Self-Selection
# ============================================================================
# Pros: Single LLM call, LLM has full context to judge
# Cons: Relies on LLM following instructions correctly
#
# Use when: LLM compliance is reliable, want minimal overhead
# ============================================================================


@flock_type
class HypothesisP3(BaseModel):
    """Hypothesis for Pattern 3 (self-selection)."""

    content: str = Field(description="The hypothesis statement")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Why this hypothesis is plausible")
    is_recommended: bool = Field(
        description="Set to True for EXACTLY ONE hypothesis - the best one",
        default=False,
    )


def create_pattern_3(flock: Flock) -> None:
    """Pattern 3: LLM Self-Selection - LLM marks the best one itself."""

    # Generator produces 5 hypotheses, marking ONE as recommended
    flock.agent("hypothesis_generator_p3").description(
        "Generate 5 research hypotheses with varying confidence levels. "
        "IMPORTANT: Set is_recommended=True for EXACTLY ONE hypothesis - "
        "the one you consider the strongest and most defensible. "
        "All others should have is_recommended=False."
    ).consumes(ResearchTopic).publishes(HypothesisP3, fan_out=5)

    # Analyst only sees the self-selected recommendation
    flock.agent("analyst_p3").description(
        "Analyze the recommended hypothesis and explain its implications."
    ).consumes(
        HypothesisP3,
        where=lambda h: h.is_recommended,  # Only the marked one!
    ).publishes(FinalAnalysis)


# ============================================================================
# MAIN EXECUTION
# ============================================================================


async def main_cli():
    """CLI mode: Run selected pattern and display results."""
    pattern_names = {
        1: "Threshold Filter (where=)",
        2: "Two-Stage Selector (batch + select)",
        3: "LLM Self-Selection (is_recommended)",
    }

    print("=" * 70)
    print(f"🎯 FAN-OUT SELECTION PATTERNS - Pattern {PATTERN}")
    print(f"   {pattern_names[PATTERN]}")
    print("=" * 70)
    print()

    # Create Flock and set up selected pattern
    flock = Flock()

    if PATTERN == 1:
        create_pattern_1(flock)
        print("📋 Pattern 1: Threshold Filter")
        print("   - Generator creates 5 hypotheses with fan_out=5")
        print("   - Analyst uses where=lambda h: h.confidence >= 0.85")
        print("   - May trigger 0, 1, or multiple times!")
        print()
    elif PATTERN == 2:
        create_pattern_2(flock)
        print("📋 Pattern 2: Two-Stage Selector")
        print("   - Generator creates 5 hypotheses with fan_out=5")
        print("   - Selector batches all 5, picks single best")
        print("   - Analyst receives exactly 1 SelectedHypothesis")
        print()
    else:  # PATTERN == 3
        create_pattern_3(flock)
        print("📋 Pattern 3: LLM Self-Selection")
        print("   - Generator creates 5 hypotheses with fan_out=5")
        print("   - Generator marks ONE as is_recommended=True")
        print("   - Analyst filters with where=lambda h: h.is_recommended")
        print()

    # Create research topic
    topic = ResearchTopic(
        question="Why do some programming languages become popular while others fade away?",
        context="Consider factors like ecosystem, timing, corporate backing, and developer experience.",
    )

    print(f"🔬 Research Topic: {topic.question}")
    print(f"   Context: {topic.context[:60]}...")
    print()
    print("⏳ Running workflow...")
    print()

    # Run the workflow
    await flock.publish(topic)
    await flock.run_until_idle()

    # Display results
    print("=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print()

    # Get all hypotheses
    all_artifacts = await flock.store.list()

    if PATTERN == 1:
        hypotheses = await flock.store.get_by_type(HypothesisP1)
        print(f"Generated {len(hypotheses)} hypotheses:")
        high_conf_count = 0
        for i, h in enumerate(hypotheses, 1):
            marker = "✅" if h.confidence >= 0.85 else "  "
            print(f"   {marker} {i}. confidence={h.confidence:.2f}: {h.content[:50]}...")
            if h.confidence >= 0.85:
                high_conf_count += 1
        print()
        print(f"   → {high_conf_count} hypotheses passed the threshold (≥0.85)")
        print(f"   → Analyst triggered {high_conf_count} time(s)")

    elif PATTERN == 2:
        hypotheses = await flock.store.get_by_type(HypothesisP2)
        selected = await flock.store.get_by_type(SelectedHypothesis)
        print(f"Generated {len(hypotheses)} hypotheses:")
        for i, h in enumerate(hypotheses, 1):
            print(f"   {i}. confidence={h.confidence:.2f}: {h.content[:50]}...")
        print()
        if selected:
            s = selected[0]
            print(f"   → Selector chose: {s.content[:60]}...")
            print(f"   → Reason: {s.selection_reason[:60]}...")
        print(f"   → Analyst triggered exactly 1 time")

    else:  # PATTERN == 3
        hypotheses = await flock.store.get_by_type(HypothesisP3)
        print(f"Generated {len(hypotheses)} hypotheses:")
        recommended_count = 0
        for i, h in enumerate(hypotheses, 1):
            marker = "⭐" if h.is_recommended else "  "
            print(f"   {marker} {i}. confidence={h.confidence:.2f}: {h.content[:50]}...")
            if h.is_recommended:
                recommended_count += 1
        print()
        print(f"   → {recommended_count} hypothesis marked as is_recommended=True")
        print(f"   → Analyst triggered {recommended_count} time(s)")

    # Show final analyses
    analyses = await flock.store.get_by_type(FinalAnalysis)
    print()
    print(f"📝 Final Analyses Generated: {len(analyses)}")
    for i, a in enumerate(analyses, 1):
        print(f"   {i}. Based on: {a.selected_hypothesis[:50]}...")
        print(f"      Implications: {len(a.implications)} points")

    print()
    print("=" * 70)
    print("💡 PATTERN COMPARISON")
    print("=" * 70)
    print("""
    Pattern 1 (Threshold):
      ✅ Simple, no extra agents
      ❌ Not guaranteed "THE best"
      ❌ Could match 0 or many
      🎯 Use when: "good enough" is acceptable

    Pattern 2 (Two-Stage):
      ✅ Guaranteed single best
      ✅ Explicit selection logic
      ❌ Extra LLM call (cost/latency)
      🎯 Use when: need deterministic selection

    Pattern 3 (Self-Selection):
      ✅ Single LLM call
      ✅ LLM has full context
      ❌ Relies on LLM compliance
      🎯 Use when: LLM is reliable, want minimal overhead
    """)


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface."""
    flock = Flock()

    # Set up all patterns for exploration
    create_pattern_1(flock)
    create_pattern_2(flock)
    create_pattern_3(flock)

    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to explore selection patterns!")
    print()
    print("💡 Try publishing a ResearchTopic and watch the different patterns!")
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
# EXPERIMENT 1: Change the Pattern
# ---------------------------------
# Set PATTERN = 1, 2, or 3 at the top and run each one.
# Questions to consider:
#   - How many times does the analyst trigger?
#   - Which pattern gives you most control?
#   - Which is most cost-effective?
#
#
# EXPERIMENT 2: Adjust the Threshold (Pattern 1)
# -----------------------------------------------
# Try different thresholds:
#   where=lambda h: h.confidence >= 0.95  # Very strict
#   where=lambda h: h.confidence >= 0.70  # More lenient
#   where=lambda h: h.confidence >= 0.50  # Half or more
#
# How does this affect how many hypotheses pass through?
#
#
# EXPERIMENT 3: Multiple Selection Criteria (Pattern 3)
# ------------------------------------------------------
# Add more fields for LLM to mark:
#   @flock_type
#   class HypothesisEnhanced(BaseModel):
#       content: str
#       confidence: float
#       is_recommended: bool = False
#       is_most_novel: bool = False  # Mark the most creative one
#       is_most_testable: bool = False  # Mark the easiest to test
#
# Then have different downstream agents react to different markers!
#
#
# EXPERIMENT 4: Combine Patterns
# -------------------------------
# Use Pattern 3 with a Pattern 1 fallback:
#   .consumes(
#       HypothesisP3,
#       where=lambda h: h.is_recommended or h.confidence >= 0.95
#   )
#
# This catches the recommended one OR any exceptionally high confidence ones.
#
#
# EXPERIMENT 5: Add Validation
# -----------------------------
# Ensure LLM compliance in Pattern 3:
#   .publishes(
#       HypothesisP3,
#       fan_out=5,
#       validate=lambda results: sum(h.is_recommended for h in results) == 1
#   )
#
# This fails if LLM doesn't mark exactly one!
#
#
# CHALLENGE: Build a "Best of N" Tournament
# ------------------------------------------
# Create a multi-round selection system:
#   1. Generate 10 hypotheses (fan_out=10)
#   2. Batch into groups of 5
#   3. Each group selects its best (2 winners)
#   4. Final selector picks from the 2 winners
#
# This is like a tournament bracket for ideas!
#
# ============================================================================
