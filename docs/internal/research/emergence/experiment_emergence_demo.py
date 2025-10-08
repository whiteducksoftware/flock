"""
Emergence Demonstration Experiment

This script creates a complex multi-agent system that exhibits multiple
emergent phenomena, then analyzes them using the emergence toolkit.

Phenomena demonstrated:
1. Cascade patterns (sequential chaining)
2. Parallel emergence (concurrent execution)
3. Conditional routing (filter-based branching)
4. Feedback loops (iterative refinement)
5. Stigmergic coordination (context-based decisions)

Run with:
    python research/experiment_emergence_demo.py
"""

import asyncio
import os
from pydantic import BaseModel, Field
from typing import Literal

# Set up tracing BEFORE importing Flock
os.environ['FLOCK_AUTO_TRACE'] = 'true'
os.environ['FLOCK_TRACE_FILE'] = 'true'
os.environ['FLOCK_TRACE_SERVICES'] = '["flock", "agent"]'

from flock.orchestrator import Flock
from flock.registry import flock_type


# ============================================================================
# ARTIFACT DEFINITIONS
# ============================================================================

@flock_type
class ResearchIdea(BaseModel):
    """Seed input: A research topic to explore"""
    topic: str = Field(description="Research topic or question")
    domain: Literal["AI", "biology", "physics", "mathematics"]
    priority: int = Field(ge=1, le=10, description="Priority level")


@flock_type
class Literature(BaseModel):
    """Output from literature search"""
    topic: str
    papers: list[str] = Field(description="Relevant papers found", min_length=3)
    key_findings: list[str] = Field(description="Key insights from literature")
    domain: str


@flock_type
class Hypothesis(BaseModel):
    """Research hypothesis generated from literature"""
    statement: str = Field(description="Clear hypothesis statement")
    rationale: str = Field(description="Why this hypothesis is worth testing")
    domain: str
    novelty_score: int = Field(ge=1, le=10, description="How novel this hypothesis is")


@flock_type
class ExperimentDesign(BaseModel):
    """Experimental methodology"""
    hypothesis: str
    method: str = Field(description="Experimental approach")
    expected_outcome: str
    feasibility_score: int = Field(ge=1, le=10)
    domain: str


@flock_type
class Critique(BaseModel):
    """Critical review of experiment design"""
    score: int = Field(ge=1, le=10, description="Quality score")
    strengths: list[str] = Field(min_length=1)
    weaknesses: list[str] = Field(min_length=1)
    suggestions: list[str] = Field(min_length=1, description="Specific improvements")


@flock_type
class RevisedDesign(BaseModel):
    """Improved experiment design after critique"""
    original_hypothesis: str
    revised_method: str
    improvements_made: list[str]
    iteration: int = Field(default=1)
    quality_score: int = Field(ge=1, le=10)


@flock_type
class ResearchPaper(BaseModel):
    """Final research output"""
    title: str
    abstract: str = Field(min_length=200)
    methodology: str
    expected_results: str
    domain: str


# ============================================================================
# AGENT DEFINITIONS (EMERGENT COORDINATION)
# ============================================================================

async def main():
    # Create orchestrator with circuit breaker for feedback loops
    flock = Flock("openai/gpt-4o-mini", max_agent_iterations=30)

    print("=" * 80)
    print("EMERGENCE DEMONSTRATION EXPERIMENT")
    print("=" * 80)
    print()

    # ---------------------------------------------------------------------
    # PHENOMENON 1: CASCADE PATTERNS
    # Sequential chaining emerges from type subscriptions
    # ---------------------------------------------------------------------

    print("Setting up agents for CASCADE PATTERNS...")

    literature_agent = (
        flock.agent("literature_researcher")
        .description("Searches academic literature for relevant papers")
        .consumes(ResearchIdea)
        .publishes(Literature)
    )

    hypothesis_agent = (
        flock.agent("hypothesis_generator")
        .description("Generates testable hypotheses from literature review")
        .consumes(Literature)
        .publishes(Hypothesis)
    )

    # ---------------------------------------------------------------------
    # PHENOMENON 2: PARALLEL EMERGENCE
    # Multiple agents consume same type → parallel execution
    # ---------------------------------------------------------------------

    print("Setting up agents for PARALLEL EMERGENCE...")

    # 3 experiment designers work in parallel on different approaches
    for approach in ["computational", "empirical", "theoretical"]:
        (
            flock.agent(f"designer_{approach}")
            .description(f"Designs {approach} experiments")
            .consumes(Hypothesis)
            .publishes(ExperimentDesign)
        )

    # ---------------------------------------------------------------------
    # PHENOMENON 3: CONDITIONAL ROUTING
    # Filters create dynamic execution paths
    # ---------------------------------------------------------------------

    print("Setting up agents for CONDITIONAL ROUTING...")

    # High-priority hypotheses get extra scrutiny
    rigorous_critic = (
        flock.agent("rigorous_critic")
        .description("Harsh critic for high-novelty hypotheses")
        .consumes(ExperimentDesign, where=lambda e: e.feasibility_score <= 7)
        .publishes(Critique)
    )

    # Low-feasibility designs get auto-approval
    quick_approver = (
        flock.agent("quick_approver")
        .description("Quick approval for feasible designs")
        .consumes(ExperimentDesign, where=lambda e: e.feasibility_score >= 8)
        .publishes(ResearchPaper)
    )

    # ---------------------------------------------------------------------
    # PHENOMENON 4: FEEDBACK LOOPS
    # Iterative refinement with convergence condition
    # ---------------------------------------------------------------------

    print("Setting up agents for FEEDBACK LOOPS...")

    refiner = (
        flock.agent("design_refiner")
        .description("Improves experiment design based on critique")
        .consumes(Critique, where=lambda c: c.score < 9)  # Only if needs improvement
        .publishes(RevisedDesign)
        .prevent_self_trigger(False)  # Allow feedback loop
    )

    # Re-evaluate revised designs
    re_evaluator = (
        flock.agent("re_evaluator")
        .description("Re-evaluates revised designs")
        .consumes(RevisedDesign, where=lambda r: r.quality_score < 9)
        .publishes(Critique)
    )

    # Final publisher (exit condition for feedback loop)
    publisher = (
        flock.agent("paper_publisher")
        .description("Publishes approved research papers")
        .consumes(RevisedDesign, where=lambda r: r.quality_score >= 9)
        .publishes(ResearchPaper)
    )

    # ---------------------------------------------------------------------
    # PHENOMENON 5: STIGMERGIC COORDINATION
    # Agents reference historical context from blackboard
    # ---------------------------------------------------------------------

    print("Setting up agents for STIGMERGIC COORDINATION...")

    cross_domain_synthesizer = (
        flock.agent("cross_domain_synthesizer")
        .description(
            "Synthesizes insights across multiple domains by reading "
            "historical research papers from blackboard"
        )
        .consumes(ResearchPaper)
        # This agent will use context.fetch_conversation_context() to read
        # papers from other domains (stigmergic coordination)
    )

    print()
    print("=" * 80)
    print("RUNNING EXPERIMENT")
    print("=" * 80)
    print()

    # Run with different scenarios to generate diverse traces

    scenarios = [
        ResearchIdea(
            topic="Emergent intelligence in multi-agent AI systems",
            domain="AI",
            priority=9
        ),
        ResearchIdea(
            topic="Quantum entanglement in biological photosynthesis",
            domain="physics",
            priority=7
        ),
        ResearchIdea(
            topic="Graph theory applications to protein folding",
            domain="mathematics",
            priority=6
        ),
    ]

    for i, idea in enumerate(scenarios, 1):
        print(f"\nScenario {i}/{len(scenarios)}: {idea.topic}")
        print("-" * 60)

        # Publish idea and let cascade emerge
        await flock.publish(idea)
        await flock.run_until_idle()

        print(f"✓ Scenario {i} complete")

    print()
    print("=" * 80)
    print("ANALYZING EMERGENT BEHAVIOR")
    print("=" * 80)
    print()

    # Import and run emergence analysis
    from emergence_toolkit import EmergenceAnalyzer

    analyzer = EmergenceAnalyzer(".flock/traces.duckdb")
    report = analyzer.generate_comprehensive_report()
    print(report)

    # Export detailed results
    analyzer.export_to_json("emergence_analysis_results.json")

    print()
    print("=" * 80)
    print("EXPERIMENT COMPLETE")
    print("=" * 80)
    print()
    print("Results saved to:")
    print("  - Trace database: .flock/traces.duckdb")
    print("  - Analysis report: emergence_analysis_results.json")
    print()
    print("To explore traces interactively:")
    print("  1. Run: python -m flock.dashboard")
    print("  2. Navigate to Trace Viewer module")
    print("  3. Examine cascade patterns, parallel execution, and feedback loops")
    print()

    # Summary of expected emergent phenomena
    print("Expected Phenomena Observed:")
    print("  1. CASCADE PATTERNS: ResearchIdea → Literature → Hypothesis → ExperimentDesign")
    print("  2. PARALLEL EMERGENCE: 3 designers execute concurrently on same Hypothesis")
    print("  3. CONDITIONAL ROUTING: Different critics activate based on feasibility_score")
    print("  4. FEEDBACK LOOPS: Critique → RevisedDesign → Critique until quality >= 9")
    print("  5. STIGMERGIC COORDINATION: Synthesizer reads historical papers from blackboard")
    print()


if __name__ == "__main__":
    asyncio.run(main())
