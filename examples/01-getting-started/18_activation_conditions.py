"""
Example 18: Activation Conditions with When

This example demonstrates Flock's activation condition DSL for controlling
WHEN an agent starts processing. Instead of triggering immediately on any
matching artifact, agents can wait for specific conditions to be met.

Key concepts:
    - When helper for activation conditions
    - Deferring agent execution until conditions are met
    - Condition composition with &, |, ~
    - Combining activation with fan_out patterns

Comparison with Example 17 (workflow_conditions.py):
    - Until = WHEN TO STOP the workflow (termination)
    - When = WHEN TO START an agent (activation)

Run:
    uv run python examples/01-getting-started/18_activation_conditions.py
"""

import asyncio
import uuid

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.core.conditions import When


# ============================================================================
# Types for our code review workflow
# ============================================================================


@flock_type
class CodeSubmission(BaseModel):
    """A code submission to be reviewed."""

    filename: str = Field(description="Name of the file being reviewed")
    code: str = Field(description="The code content to review")
    language: str = Field(description="Programming language")


@flock_type
class SecurityReport(BaseModel):
    """Security analysis report."""

    filename: str = Field(description="File that was analyzed")
    vulnerabilities: list[str] = Field(description="List of vulnerabilities found")
    severity: str = Field(description="Overall severity: low, medium, high, critical")
    passed: bool = Field(description="True if no critical issues found")


@flock_type
class PerformanceReport(BaseModel):
    """Performance analysis report."""

    filename: str = Field(description="File that was analyzed")
    issues: list[str] = Field(description="Performance issues found")
    complexity_score: float = Field(description="Code complexity score 0-10")
    passed: bool = Field(description="True if performance is acceptable")


@flock_type
class StyleReport(BaseModel):
    """Code style analysis report."""

    filename: str = Field(description="File that was analyzed")
    violations: list[str] = Field(description="Style violations found")
    readability_score: float = Field(description="Readability score 0-10")
    passed: bool = Field(description="True if style is acceptable")


@flock_type
class FinalReview(BaseModel):
    """Final consolidated review decision."""

    filename: str = Field(description="File that was reviewed")
    approved: bool = Field(description="Whether the code is approved")
    summary: str = Field(description="Summary of all findings")
    recommendations: list[str] = Field(description="Improvement recommendations")


# ============================================================================
# Example Setup
# ============================================================================


async def main():
    """Demonstrate activation conditions for agent orchestration."""
    print("=" * 70)
    print("Flock Activation Conditions - Code Review System")
    print("=" * 70)
    print()
    print("This example shows how agents can WAIT for conditions before activating.")
    print("Unlike 'where=' which filters artifacts, 'activation=' defers execution")
    print("until the condition is satisfied.")
    print()

    # Create Flock instance
    flock = Flock()

    # =========================================================================
    # Define Analyzer Agents (run in parallel)
    # =========================================================================
    # These three agents run independently when code is submitted

    flock.agent("security_analyzer").description(
        "Analyzes code for security vulnerabilities. "
        "Check for injection risks, authentication issues, and data exposure."
    ).consumes(CodeSubmission).publishes(SecurityReport)

    flock.agent("performance_analyzer").description(
        "Analyzes code for performance issues. "
        "Check for inefficient algorithms, memory leaks, and bottlenecks."
    ).consumes(CodeSubmission).publishes(PerformanceReport)

    flock.agent("style_analyzer").description(
        "Analyzes code for style and readability. "
        "Check for naming conventions, documentation, and code organization."
    ).consumes(CodeSubmission).publishes(StyleReport)

    # =========================================================================
    # Example 1: Wait for ALL reports before final review
    # =========================================================================
    # The final_reviewer waits until all 3 analysis reports exist
    # before synthesizing the final review decision.

    print("=" * 70)
    print("Example 1: Final reviewer waits for ALL 3 reports")
    print("=" * 70)
    print()
    print("  Activation condition:")
    print("    When.correlation(SecurityReport).exists()")
    print("    & When.correlation(PerformanceReport).exists()")
    print("    & When.correlation(StyleReport).exists()")
    print()

    # Final reviewer with composite activation condition
    # Only activates when ALL three report types exist in the correlation
    flock.agent("final_reviewer").description(
        "Synthesizes all analysis reports into a final review decision. "
        "Consider security, performance, and style findings together."
    ).consumes(
        SecurityReport,  # Triggers on SecurityReport arrival...
        activation=(
            # ...but WAITS until all three report types exist
            When.correlation(SecurityReport).exists()
            & When.correlation(PerformanceReport).exists()
            & When.correlation(StyleReport).exists()
        ),
    ).publishes(FinalReview)

    # Generate correlation ID to track this workflow
    correlation_id = str(uuid.uuid4())

    # Submit code for review
    code = CodeSubmission(
        filename="auth_handler.py",
        code="""
def authenticate(username, password):
    query = f"SELECT * FROM users WHERE name='{username}'"  # SQL injection!
    result = db.execute(query)
    if result:
        return create_session(result[0])
    return None
""",
        language="python",
    )

    print(f"📝 Submitting code: {code.filename}")
    print(f"   Language: {code.language}")
    print(f"   Correlation ID: {correlation_id[:8]}...")
    print()

    await flock.publish(code, correlation_id=correlation_id)

    print("⏳ Running workflow...")
    print("   - Security, Performance, Style analyzers run in parallel")
    print("   - Final reviewer waits for ALL THREE before activating")
    print()

    await flock.run_until_idle()

    # Check results
    security_reports = await flock.store.get_by_type(
        SecurityReport, correlation_id=correlation_id
    )
    performance_reports = await flock.store.get_by_type(
        PerformanceReport, correlation_id=correlation_id
    )
    style_reports = await flock.store.get_by_type(
        StyleReport, correlation_id=correlation_id
    )
    final_reviews = await flock.store.get_by_type(
        FinalReview, correlation_id=correlation_id
    )

    print("=" * 70)
    print("📊 Results")
    print("=" * 70)
    print()
    print(f"Security Reports: {len(security_reports)}")
    if security_reports:
        r = security_reports[0]
        print(f"  - Severity: {r.severity}")
        print(f"  - Passed: {r.passed}")
        print(f"  - Vulnerabilities: {len(r.vulnerabilities)}")

    print(f"\nPerformance Reports: {len(performance_reports)}")
    if performance_reports:
        r = performance_reports[0]
        print(f"  - Complexity: {r.complexity_score:.1f}/10")
        print(f"  - Passed: {r.passed}")

    print(f"\nStyle Reports: {len(style_reports)}")
    if style_reports:
        r = style_reports[0]
        print(f"  - Readability: {r.readability_score:.1f}/10")
        print(f"  - Passed: {r.passed}")

    print(f"\nFinal Reviews: {len(final_reviews)}")
    if final_reviews:
        r = final_reviews[0]
        print(f"  - Approved: {'✅ Yes' if r.approved else '❌ No'}")
        print(f"  - Summary: {r.summary[:80]}...")

    # =========================================================================
    # Summary: When vs Until vs Where
    # =========================================================================
    print()
    print("=" * 70)
    print("📚 Summary: When vs Until vs Where")
    print("=" * 70)
    print(
        """
    WHERE (filtering):
        .consumes(Report, where=lambda r: r.severity == "critical")
        → Only process artifacts matching the predicate
        → Triggers immediately for each matching artifact

    WHEN (activation):
        .consumes(Report, activation=When.correlation(Report).count_at_least(3))
        → Defer processing until condition is met
        → Then process the triggering artifact

    UNTIL (termination):
        await flock.run_until(Until.artifact_count(Report).at_least(3))
        → Control when the workflow STOPS
        → Applied to run_until(), not to agent subscriptions

    Key difference:
        - WHERE: "Which artifacts should I process?"
        - WHEN: "Should I start processing NOW?"
        - UNTIL: "Should the workflow STOP now?"
    """
    )

    # =========================================================================
    # Available When Conditions
    # =========================================================================
    print("=" * 70)
    print("📖 Available When Conditions")
    print("=" * 70)
    print(
        """
    When.correlation(Model).exists()         - Any artifact of type exists
    When.correlation(Model).count_at_least(N) - At least N artifacts exist
    When.correlation(Model).any_field(        - Field matches predicate
        field="name",
        predicate=lambda v: v > threshold
    )

    Composition:
        condition1 & condition2         - Both must be True (AND)
        condition1 | condition2         - Either must be True (OR)
        ~condition                      - Inverts condition (NOT)

    Examples:
        # Wait for 5 results OR any critical finding
        activation=(
            When.correlation(Report).count_at_least(5)
            | When.correlation(Report).any_field("critical", lambda v: v)
        )

        # Wait for all required types
        activation=(
            When.correlation(TypeA).exists()
            & When.correlation(TypeB).exists()
            & When.correlation(TypeC).exists()
        )
    """
    )


if __name__ == "__main__":
    asyncio.run(main())
