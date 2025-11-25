"""
Hackathon Track 03: Conditional Consumption

🎓 LEARNING OBJECTIVE:
Learn how to filter which artifacts agents consume using `where` clauses.
This enables agents to only process relevant data, reducing costs and improving quality.

KEY CONCEPTS:
- Conditional consumption with `where` predicates
- Filtering artifacts before processing
- Multiple predicates (AND logic)
- Quality gates and routing decisions

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
# STEP 1: Define Types with Filterable Fields
# ============================================================================
# For conditional consumption, your types need fields that can be filtered.
# Common filterable fields: scores, status, priority, categories, etc.
# ============================================================================

@flock_type
class CodeReview(BaseModel):
    """A code review with quality metrics."""
    file_path: str
    reviewer: str
    score: int = Field(ge=1, le=10, description="Quality score from 1-10")
    comments: list[str] = Field(description="Review comments")
    language: str = Field(description="Programming language")
    complexity: str = Field(description="Complexity level: simple, moderate, complex")


@flock_type
class ApprovedReview(BaseModel):
    """High-quality review that passed quality gates."""
    file_path: str
    reviewer: str
    score: int
    approval_note: str = Field(description="Why this review was approved")


@flock_type
class RevisionRequest(BaseModel):
    """Review that needs improvement."""
    file_path: str
    reviewer: str
    score: int
    required_changes: list[str] = Field(description="What needs to be fixed")


# ============================================================================
# STEP 2: Create the Orchestrator
# ============================================================================

flock = Flock()


# ============================================================================
# STEP 3: Define Agents with Conditional Consumption
# ============================================================================
# The `where` parameter lets you filter artifacts before agents process them.
# 
# Syntax: .consumes(Type, where=lambda artifact: condition)
#
# The lambda receives the artifact as a Pydantic model instance.
# Only artifacts where the predicate returns True will trigger the agent.
# ============================================================================

# Agent 1: Only processes high-quality reviews (score >= 8)
approver_agent = (
    flock.agent("approver")
    .description(
        "Approves high-quality code reviews. Only processes reviews with score >= 8."
    )
    .consumes(
        CodeReview,
        where=lambda review: review.score >= 8  # Conditional filter!
    )
    .publishes(ApprovedReview)
)

# Agent 2: Only processes low-quality reviews (score < 6)
revision_agent = (
    flock.agent("revision_agent")
    .description(
        "Requests revisions for low-quality code reviews. Only processes reviews with score < 6."
    )
    .consumes(
        CodeReview,
        where=lambda review: review.score < 6  # Different condition!
    )
    .publishes(RevisionRequest)
)

# Agent 3: Processes ALL reviews (no filter)
# This agent will see every CodeReview, regardless of score
summary_agent = (
    flock.agent("summary_agent")
    .description("Creates a summary of all code reviews for reporting.")
    .consumes(CodeReview)  # No where clause = processes everything
    .publishes(ApprovedReview)  # Using same type for simplicity
)


# ============================================================================
# STEP 4: Run with Multiple Artifacts
# ============================================================================

async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("=" * 70)
    print("🔍 CONDITIONAL CONSUMPTION EXAMPLE - Code Review Filtering")
    print("=" * 70)
    print()
    
    # Create multiple reviews with different scores
    reviews = [
        CodeReview(
            file_path="src/auth.py",
            reviewer="Alice",
            score=9,
            comments=["Excellent code quality", "Well documented"],
            language="Python",
            complexity="moderate"
        ),
        CodeReview(
            file_path="src/db.py",
            reviewer="Bob",
            score=4,
            comments=["Needs better error handling", "Missing tests"],
            language="Python",
            complexity="complex"
        ),
        CodeReview(
            file_path="src/api.py",
            reviewer="Charlie",
            score=7,
            comments=["Good structure", "Minor improvements needed"],
            language="Python",
            complexity="simple"
        ),
        CodeReview(
            file_path="src/utils.py",
            reviewer="Diana",
            score=10,
            comments=["Perfect implementation", "Great documentation"],
            language="Python",
            complexity="moderate"
        ),
    ]
    
    print("📝 Publishing Code Reviews:")
    for review in reviews:
        print(f"   {review.file_path}: Score {review.score}/10 ({review.reviewer})")
    print()
    print("⏳ Processing reviews with conditional filters...")
    print()
    
    # Publish all reviews
    await flock.publish_many(reviews)
    
    # Run until all agents finish
    await flock.run_until_idle()
    
    # Check results
    approvals = await flock.store.get_by_type(ApprovedReview)
    revisions = await flock.store.get_by_type(RevisionRequest)
    
    print("=" * 70)
    print("📊 FILTERING RESULTS")
    print("=" * 70)
    
    print(f"\n✅ Approved Reviews (score >= 8): {len(approvals)}")
    for approval in approvals:
        print(f"   • {approval.file_path} (Score: {approval.score})")
        print(f"     Note: {approval.approval_note[:60]}...")
    
    print(f"\n❌ Revision Requests (score < 6): {len(revisions)}")
    for revision in revisions:
        print(f"   • {revision.file_path} (Score: {revision.score})")
        print(f"     Required: {', '.join(revision.required_changes[:2])}")
    
    print()
    print("=" * 70)
    print("💡 Key Insights:")
    print("   - approver_agent only saw reviews with score >= 8")
    print("   - revision_agent only saw reviews with score < 6")
    print("   - summary_agent saw ALL reviews (no filter)")
    print("   - Score 7 review was processed by summary_agent only!")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to see conditional consumption in action!")
    print()
    print("💡 Watch how different agents only process filtered artifacts!")
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
# EXPERIMENT 1: Multiple Conditions
# ----------------------------------
# Create an agent that filters by MULTIPLE conditions:
#   senior_reviewer = (
#       flock.agent("senior_reviewer")
#       .consumes(
#           CodeReview,
#           where=lambda r: r.score >= 8 and r.complexity == "complex"
#       )
#       .publishes(ApprovedReview)
#   )
#
# What reviews does this agent process? Try it!
#
#
# EXPERIMENT 2: Multiple Predicates (AND Logic)
# ---------------------------------------------
# Use a list of predicates - ALL must pass:
#   strict_approver = (
#       flock.agent("strict_approver")
#       .consumes(
#           CodeReview,
#           where=[
#               lambda r: r.score >= 9,           # High score
#               lambda r: len(r.comments) >= 3,   # Detailed comments
#               lambda r: r.language == "Python"   # Python only
#           ]
#       )
#       .publishes(ApprovedReview)
#   )
#
# How many reviews pass ALL three conditions?
#
#
# EXPERIMENT 3: Filter by List/Set Membership
# ---------------------------------------------
# Filter reviews by language:
#   python_reviewer = (
#       flock.agent("python_reviewer")
#       .consumes(CodeReview, where=lambda r: r.language == "Python")
#       .publishes(ApprovedReview)
#   )
#
#   javascript_reviewer = (
#       flock.agent("javascript_reviewer")
#       .consumes(CodeReview, where=lambda r: r.language == "JavaScript")
#       .publishes(ApprovedReview)
#   )
#
# Create reviews in different languages and see them route correctly!
#
#
# EXPERIMENT 4: Complex Filtering Logic
# --------------------------------------
# Create a "priority_reviewer" that processes:
#   - High scores (>= 9) OR
#   - Complex code (complexity == "complex") OR
#   - Critical files (file_path contains "auth" or "payment")
#
# Hint: Use `or` and `in` operators in your lambda!
#
#
# EXPERIMENT 5: Count-Based Filtering
# ------------------------------------
# What if you want to process only reviews with MANY comments?
#   detailed_reviewer = (
#       flock.agent("detailed_reviewer")
#       .consumes(CodeReview, where=lambda r: len(r.comments) >= 5)
#       .publishes(ApprovedReview)
#   )
#
# Or reviews with FEW comments (might need quick fixes)?
#   quick_fix_reviewer = (
#       flock.agent("quick_fix_reviewer")
#       .consumes(CodeReview, where=lambda r: len(r.comments) <= 2)
#       .publishes(RevisionRequest)
#   )
#
#
# CHALLENGE: Build a Quality Gate System
# ---------------------------------------
# Create a multi-stage quality gate:
#   1. Stage 1: Filter by score (>= 7)
#   2. Stage 2: Filter by complexity (simple or moderate)
#   3. Stage 3: Filter by language (Python or TypeScript)
#   4. Stage 4: Filter by comment count (>= 3)
#
# Each stage is a separate agent. Only reviews that pass ALL stages
# get approved. How do you chain these filters?
#
# Hint: Each agent publishes a "passed" artifact that the next agent consumes!
#
# ============================================================================

