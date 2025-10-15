"""
Refactor Workflow Example - Improve Code Quality

This example demonstrates the refactoring workflow:
1. Analyze code for refactoring opportunities (smells, duplication)
2. Prioritize refactorings by safety and impact
3. Apply changes incrementally with validation after each
4. Ensure ALL tests pass after every change
5. Revert immediately if tests fail

This shows how the blackboard enables safe, incremental refactoring
with strict quality gates.
"""

import asyncio
from pathlib import Path

from flock.orchestrator import Flock

from agents import create_specialist_agents
from artifacts import (
    BlockedState,
    CodeChange,
    RefactorRequest,
    ReviewRequest,
    ReviewResult,
    ValidationRequest,
    ValidationResult,
    ValidationType,
)
from mcp_config import configure_mcps


async def refactor_codebase():
    """
    Refactor code with safety checks and validation.

    Flow:
    1. Analyze code for refactoring opportunities
    2. Identify code smells: duplication, long methods, complex conditions
    3. For each refactoring:
       a. Apply code change
       b. Run full test suite (MUST PASS)
       c. If pass: Request review
       d. If fail: Revert and report BlockedState
    4. Continue until no more safe refactorings
    """
    print("\n" + "=" * 70)
    print("REFACTOR WORKFLOW - INCREMENTAL CODE IMPROVEMENT")
    print("=" * 70)

    # Target: Refactor our spec_tools.py (it could use some improvements!)
    target_path = str(Path(__file__).parent / "spec_tools.py")
    target_description = "Improve spec_tools.py: extract common patterns, add error handling"

    print(f"\n[TARGET] {target_path}")
    print(f"[GOAL] {target_description}")

    # ===========================================================================
    # SETUP
    # ===========================================================================

    print("\n[Step 1] Setting up Flock with MCP tools...")
    flock = Flock()

    # Configure MCP servers
    mcp_status = configure_mcps(flock)
    print(f"  + MCP Status: {sum(mcp_status.values())}/{len(mcp_status)} configured")

    if not mcp_status.get("filesystem"):
        print("\n[ERROR] Filesystem MCP required for refactoring!")
        print("  Please install: npm install -g @modelcontextprotocol/server-filesystem")
        return

    # Create specialist agents
    print("\n[Step 2] Creating specialist agents...")
    agents = create_specialist_agents(flock)
    print(f"  + Created {len(agents)} specialist agents")

    # ===========================================================================
    # PHASE 1: ANALYZE CODE FOR REFACTORING OPPORTUNITIES
    # ===========================================================================

    print("\n[Phase 1] Analyzing code for refactoring opportunities...")
    print("  (Looking for: code smells, duplication, complexity)")

    # Publish RefactorRequest
    refactor_request = RefactorRequest(
        target_path=target_path,
        target_description=target_description,
        refactoring_goals=[
            "Extract common file path validation into helper",
            "Add consistent error handling across all functions",
            "Reduce code duplication in document operations",
            "Improve function documentation",
        ],
        constraints=[
            "ALL tests must pass after every change",
            "No behavior changes (refactoring only)",
            "Incremental changes (one at a time)",
        ],
    )
    await flock.publish(refactor_request)
    print("  + Published RefactorRequest")

    # The refactor_orchestrator should analyze and create refactoring tasks
    # For this demo, we'll simulate the analysis by creating specific tasks

    print("\n[Analyzing] Simulating refactoring analysis...")
    print("  (In real system, refactor_orchestrator would analyze code)")

    # Simulated refactoring opportunities
    refactorings = [
        {
            "description": "Extract path validation into _validate_path() helper function",
            "area": "backend",
            "reason": "Reduce duplication across read_document, append_to_document, etc.",
            "risk": "low",
        },
        {
            "description": "Add docstring examples to all @flock_tool functions",
            "area": "backend",
            "reason": "Improve code documentation and usability",
            "risk": "low",
        },
        {
            "description": "Add consistent UTF-8 encoding specification in all file operations",
            "area": "backend",
            "reason": "Prevent encoding issues on Windows",
            "risk": "low",
        },
    ]

    print(f"\n  + Found {len(refactorings)} refactoring opportunities:")
    for i, r in enumerate(refactorings, 1):
        print(f"    {i}. {r['description']}")
        print(f"       Risk: {r['risk']}, Reason: {r['reason'][:60]}...")

    # ===========================================================================
    # PHASE 2: APPLY REFACTORINGS INCREMENTALLY
    # ===========================================================================

    print("\n[Phase 2] Applying refactorings incrementally...")
    print("  NOTE: Each refactoring requires test validation")
    print("  Press Ctrl+C to skip to results\n")

    # For demo, we'll apply just the first refactoring
    demo_refactoring = refactorings[0]

    print(f"\n{'=' * 70}")
    print(f"REFACTORING: {demo_refactoring['description']}")
    print(f"{'=' * 70}")

    # In a real system, the refactor_orchestrator would:
    # 1. Publish ImplementationTask for the refactoring
    # 2. implementer_backend would apply the change
    # 3. CodeChange artifact would be created
    # 4. ValidationRequest would be published
    # 5. validator_tests would run tests
    # 6. If tests pass: continue
    # 7. If tests fail: BlockedState + revert

    # For this demo, we'll simulate the validation cycle
    print("\n  [Step 1] Applying code change...")
    print(f"    Target: {target_path}")
    print(f"    Change: {demo_refactoring['description']}")

    # Simulate a CodeChange (in real system, agent would create this)
    print("\n  [Step 2] Running test suite...")
    print("    This is a CRITICAL safety check!")

    # Publish validation request
    validation = ValidationRequest(
        validation_id="refactor-001-tests",
        validation_type=ValidationType.TESTS,
        target="examples/08-spec-driven-development/",
        criteria=[
            "All existing tests pass",
            "No regressions",
            "Behavior unchanged",
        ],
    )
    await flock.publish(validation)
    print("  + Published validation request")

    # Wait for validation
    try:
        await asyncio.wait_for(flock.run_until_idle(), timeout=120.0)
    except asyncio.TimeoutError:
        print("  [TIMEOUT] Validation still running...")

    # Check validation results
    validation_results = await flock.store.get_by_type(ValidationResult)

    if validation_results:
        result = validation_results[0]
        if result.passed:
            print("\n  [SUCCESS] All tests passed!")
            print("    + Refactoring is SAFE")
            print("    + Can proceed to next refactoring")

            # Request review
            review = ReviewRequest(
                review_id="refactor-001-review",
                target_type="code",
                content="Refactored spec_tools.py: extracted path validation",
                review_focus=[
                    "Code quality improvement",
                    "Behavior preservation",
                    "Test coverage maintained",
                ],
            )
            await flock.publish(review)
            print("\n  [Step 3] Requesting code review...")

        else:
            print("\n  [FAIL] Tests failed!")
            print("    + Refactoring broke behavior")
            print("    + REVERTING changes immediately")

            # Publish BlockedState
            blocked = BlockedState(
                reason="Tests failed after refactoring",
                blocking_issue="Test validation failed",
                options=["Revert changes", "Fix tests", "Skip this refactoring"],
            )
            await flock.publish(blocked)
            print("  + Published BlockedState")

    # ===========================================================================
    # PHASE 3: CHECK REVIEWS
    # ===========================================================================

    print("\n[Phase 3] Checking code reviews...")

    # Wait for reviews
    try:
        await asyncio.wait_for(flock.run_until_idle(), timeout=60.0)
    except asyncio.TimeoutError:
        print("  [TIMEOUT] Review still in progress...")

    reviews = await flock.store.get_by_type(ReviewResult)
    if reviews:
        review = reviews[0]
        approval_icon = "[OK]" if review.approved else "[BLOCKED]"
        print(f"\n  {approval_icon} Code Review")
        print(f"    Approved: {review.approved}")
        if review.feedback:
            print(f"    Feedback: {review.feedback[:100]}...")

    # ===========================================================================
    # SUMMARY
    # ===========================================================================

    print("\n" + "=" * 70)
    print("[SUMMARY]")
    print("=" * 70)
    print(f"\nTarget: {target_path}")
    print(f"Refactoring Goal: {target_description}")
    print(f"Opportunities Found: {len(refactorings)}")
    print(f"Refactorings Applied: 1 (demo)")

    print("\n[REFACTORING PATTERN]")
    print("  1. Analyze code → Find opportunities")
    print("  2. Prioritize by safety → Low risk first")
    print("  3. Apply change → Single refactoring")
    print("  4. Validate → ALL tests MUST pass")
    print("  5. Review → Check quality improvement")
    print("  6. If pass: Continue")
    print("  7. If fail: REVERT immediately")

    print("\n[KEY PRINCIPLES]")
    print("  + Incremental: One refactoring at a time")
    print("  + Safe: Tests must pass after every change")
    print("  + Reversible: Can revert immediately")
    print("  + Quality-focused: Improve code without changing behavior")

    print("\n[BLOCKED STATE HANDLING]")
    print("  + If tests fail: BlockedState artifact published")
    print("  + Orchestrator halts execution")
    print("  + User decides: revert, fix, or skip")
    print("  + Safety is paramount")

    # Check for blocked states
    blocked_states = await flock.store.get_by_type(BlockedState)
    if blocked_states:
        print("\n[WARNING] Workflow blocked!")
        for blocked in blocked_states:
            print(f"  Reason: {blocked.reason}")
            print(f"  Issue: {blocked.blocking_issue}")
            print(f"  Options: {', '.join(blocked.options)}")

    print("\n" + "=" * 70)
    print("[COMPLETE] Refactor workflow finished!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Review code changes")
    print("  2. Apply remaining refactorings")
    print("  3. Maintain test coverage")
    print("  4. Monitor for regressions")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(refactor_codebase())
