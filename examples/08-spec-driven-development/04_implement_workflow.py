"""
Implement Workflow Example - Execute Implementation Plan

This example demonstrates the implementation workflow:
1. Load a PLAN.md from a spec directory
2. Parse phases and tasks
3. Execute phase-by-phase with validation checkpoints
4. Implementation specialists handle tasks based on activity_area
5. Validators ensure quality (tests pass, build succeeds)

This shows how the blackboard enables phase-by-phase execution with
parallel task processing and validation gates.
"""

import asyncio
from pathlib import Path

from flock.orchestrator import Flock

from agents import create_specialist_agents
from artifacts import (
    CodeChange,
    ImplementationTask,
    ImplementRequest,
    PhaseComplete,
    PhaseStart,
    ValidationRequest,
    ValidationResult,
    ValidationType,
)
from mcp_config import configure_mcps
from spec_tools import parse_plan_phases


async def implement_from_plan():
    """
    Execute an implementation plan phase-by-phase.

    Flow:
    1. Load PLAN.md and parse phases
    2. For each phase:
       a. Publish PhaseStart artifact
       b. Publish ImplementationTasks for parallel execution
       c. Implementation specialists react based on activity_area
       d. Collect CodeChange artifacts
       e. Publish ValidationRequest
       f. Validators run tests/build
       g. Publish PhaseComplete
    3. Continue to next phase
    """
    print("\n" + "=" * 70)
    print("IMPLEMENT WORKFLOW - PHASE-BY-PHASE EXECUTION")
    print("=" * 70)

    # For this demo, we'll create a mock PLAN.md
    # In real usage, this would come from 02_specify_workflow.py output
    spec_id = "S001"
    spec_dir = Path(".flock/specs") / spec_id
    plan_path = spec_dir / "PLAN.md"

    print(f"\n[TARGET] Spec ID: {spec_id}")
    print(f"[PLAN] {plan_path}")

    # ===========================================================================
    # SETUP
    # ===========================================================================

    print("\n[Step 1] Setting up Flock with MCP tools...")
    flock = Flock()

    # Configure MCP servers
    mcp_status = configure_mcps(flock)
    print(f"  + MCP Status: {sum(mcp_status.values())}/{len(mcp_status)} configured")

    # Create specialist agents
    print("\n[Step 2] Creating specialist agents...")
    agents = create_specialist_agents(flock)
    print(f"  + Created {len(agents)} specialist agents")

    # ===========================================================================
    # CREATE MOCK PLAN (if it doesn't exist)
    # ===========================================================================

    if not plan_path.exists():
        print("\n[Setup] Creating mock PLAN.md for demo...")
        spec_dir.mkdir(parents=True, exist_ok=True)

        mock_plan = """# Implementation Plan

**Spec ID:** S001
**Feature:** Add user authentication with OAuth 2.0 and JWT tokens
**Status:** Ready for Implementation

---

## Phase 1: Database Schema

Set up the database foundation for user authentication.

- Create users table with email, password_hash, created_at fields (database)
- Create oauth_tokens table with provider, access_token, refresh_token (database)
- Create sessions table with user_id, token, expires_at (database)
- Add database migration script (infrastructure)

## Phase 2: Backend API

Implement the authentication API endpoints.

- Create /auth/signup endpoint with validation (backend)
- Create /auth/login endpoint with JWT generation (backend)
- Create /auth/oauth/google endpoint for OAuth flow (backend)
- Create /auth/refresh endpoint for token refresh (backend)
- Add authentication middleware for protected routes (backend)

## Phase 3: Frontend Components

Build the user-facing authentication UI.

- Create LoginForm component with email/password fields (frontend)
- Create SignupForm component with validation (frontend)
- Create SocialLoginButton component for OAuth (frontend)
- Add authentication state management (frontend)
- Create ProtectedRoute component (frontend)

## Phase 4: Security & Testing

Ensure security and quality standards.

- Add rate limiting for auth endpoints (backend)
- Implement CSRF protection (backend)
- Write unit tests for auth endpoints (backend)
- Write integration tests for OAuth flow (backend)
- Add end-to-end tests for login flow (frontend)
"""
        plan_path.write_text(mock_plan, encoding="utf-8")
        print(f"  + Created: {plan_path}")

    # ===========================================================================
    # PHASE 1: LOAD AND PARSE PLAN
    # ===========================================================================

    print("\n[Phase 1] Loading and parsing PLAN.md...")
    phases = parse_plan_phases(str(plan_path))
    print(f"  + Found {len(phases)} phases")

    for phase in phases:
        print(f"\n  Phase {phase['phase_number']}: {phase['description']}")
        print(f"    Tasks: {len(phase['tasks'])}")

    # ===========================================================================
    # PHASE 2: EXECUTE EACH PHASE
    # ===========================================================================

    print("\n[Phase 2] Executing implementation phases...")
    print("  NOTE: This will take several minutes per phase as LLM agents work!")
    print("  Press Ctrl+C to stop early and see partial results\n")

    # We'll execute just the first phase for demo purposes
    # In a real system, this would loop through all phases with user confirmation
    demo_phase = phases[0]  # Phase 1: Database Schema

    print(f"\n{'=' * 70}")
    print(f"EXECUTING PHASE {demo_phase['phase_number']}: {demo_phase['description']}")
    print(f"{'=' * 70}")

    # Publish PhaseStart
    phase_start = PhaseStart(
        spec_id=spec_id,
        phase_number=demo_phase["phase_number"],
        phase_description=demo_phase["description"],
        task_count=len(demo_phase["tasks"]),
    )
    await flock.publish(phase_start)
    print(f"\n  + Published PhaseStart for Phase {demo_phase['phase_number']}")

    # Publish ImplementationTasks
    print(f"\n  + Publishing {len(demo_phase['tasks'])} implementation tasks...")

    for i, task_description in enumerate(demo_phase["tasks"], 1):
        # Determine activity_area from task description
        # Simple heuristic: look for keywords in parentheses
        activity_area = "backend"  # default
        if "(frontend)" in task_description:
            activity_area = "frontend"
        elif "(database)" in task_description:
            activity_area = "database"
        elif "(infrastructure)" in task_description:
            activity_area = "infrastructure"

        # Remove the area hint from description
        clean_description = (
            task_description.replace("(frontend)", "")
            .replace("(backend)", "")
            .replace("(database)", "")
            .replace("(infrastructure)", "")
            .strip()
        )

        task = ImplementationTask(
            task_id=f"{spec_id}-p{demo_phase['phase_number']}-t{i}",
            spec_id=spec_id,
            phase_number=demo_phase["phase_number"],
            description=clean_description,
            activity_area=activity_area,
            complexity="medium",
            sdd_references=[],
        )
        await flock.publish(task)
        print(f"    {i}. [{activity_area}] {clean_description[:60]}...")

    # Execute implementation
    print("\n  [Executing] Running implementation specialists...")
    print("    (Specialists will pick tasks based on activity_area)")

    try:
        # Run agents with timeout
        await asyncio.wait_for(flock.run_until_idle(), timeout=300.0)
        print("\n  [SUCCESS] All tasks completed!")
    except asyncio.TimeoutError:
        print("\n  [TIMEOUT] Implementation took longer than expected")
        print("    Some tasks may still be processing...")
    except KeyboardInterrupt:
        print("\n  [INTERRUPTED] Stopping early to show partial results...")

    # ===========================================================================
    # PHASE 3: COLLECT CODE CHANGES
    # ===========================================================================

    print("\n[Phase 3] Collecting code changes...")
    code_changes = await flock.store.get_by_type(CodeChange)
    print(f"  + Found {len(code_changes)} code changes")

    if code_changes:
        for change in code_changes:
            print(f"\n  [CHANGE] Task: {change.task_id}")
            print(f"    Type: {change.change_type}")
            print(f"    Files: {len(change.files_modified)}")
            print(f"    Tests added: {change.tests_added}")
            if change.files_modified:
                for file in change.files_modified[:3]:  # Show first 3
                    print(f"      - {file}")

    # ===========================================================================
    # PHASE 4: VALIDATION
    # ===========================================================================

    print("\n[Phase 4] Running validation...")

    # Publish validation requests
    test_validation = ValidationRequest(
        validation_id=f"{spec_id}-p{demo_phase['phase_number']}-tests",
        spec_id=spec_id,
        phase_number=demo_phase["phase_number"],
        validation_type=ValidationType.TESTS,
        target="tests/",
        criteria=["All tests pass", "Coverage >= 80%"],
    )
    await flock.publish(test_validation)
    print("  + Published test validation request")

    build_validation = ValidationRequest(
        validation_id=f"{spec_id}-p{demo_phase['phase_number']}-build",
        spec_id=spec_id,
        phase_number=demo_phase["phase_number"],
        validation_type=ValidationType.BUILD,
        target="src/",
        criteria=["No type errors", "No lint errors"],
    )
    await flock.publish(build_validation)
    print("  + Published build validation request")

    # Wait for validators
    print("\n  [Executing] Running validators...")
    try:
        await asyncio.wait_for(flock.run_until_idle(), timeout=120.0)
    except asyncio.TimeoutError:
        print("  [TIMEOUT] Validation still running...")

    # Collect validation results
    validation_results = await flock.store.get_by_type(ValidationResult)
    print(f"\n  + Found {len(validation_results)} validation results")

    all_passed = True
    if validation_results:
        for result in validation_results:
            status_icon = "[OK]" if result.passed else "[FAIL]"
            print(f"\n  {status_icon} {result.validation_type.value}")
            print(f"    Passed: {result.passed}")
            if result.issues:
                print(f"    Issues: {len(result.issues)}")
                for issue in result.issues[:3]:  # Show first 3
                    print(f"      - {issue}")
            if not result.passed:
                all_passed = False

    # ===========================================================================
    # PHASE 5: PHASE COMPLETION
    # ===========================================================================

    print("\n[Phase 5] Finalizing phase...")

    if all_passed:
        phase_complete = PhaseComplete(
            spec_id=spec_id,
            phase_number=demo_phase["phase_number"],
            summary=f"Completed Phase {demo_phase['phase_number']}: {demo_phase['description']}",
            tasks_completed=len(demo_phase["tasks"]),
            next_phase=demo_phase["phase_number"] + 1,
        )
        await flock.publish(phase_complete)
        print(f"  + Phase {demo_phase['phase_number']} COMPLETE!")
        print(f"  + Ready for Phase {demo_phase['phase_number'] + 1}")
    else:
        print(f"  + Phase {demo_phase['phase_number']} BLOCKED (validation failed)")
        print("  + Fix issues before continuing")

    # ===========================================================================
    # SUMMARY
    # ===========================================================================

    print("\n" + "=" * 70)
    print("[SUMMARY]")
    print("=" * 70)
    print(f"\nSpec ID: {spec_id}")
    print(f"Phase Executed: {demo_phase['phase_number']} - {demo_phase['description']}")
    print(f"Tasks Published: {len(demo_phase['tasks'])}")
    print(f"Code Changes: {len(code_changes)}")
    print(f"Validation Results: {len(validation_results)}")
    print(f"Phase Status: {'COMPLETE' if all_passed else 'BLOCKED'}")

    print("\n[KEY INSIGHTS]")
    print("  + Implementation tasks routed by activity_area")
    print("  + Specialists executed in parallel (database + infrastructure)")
    print("  + Validation gates ensure quality before proceeding")
    print("  + BatchSpec could aggregate phase completion")

    print("\n" + "=" * 70)
    print("[COMPLETE] Implement workflow finished!")
    print("=" * 70)
    print("\nNext steps:")
    print(f"  1. Review code changes")
    print(f"  2. Fix any validation issues")
    print(f"  3. Execute Phase {demo_phase['phase_number'] + 1}")
    print(f"  4. Continue until all {len(phases)} phases complete")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(implement_from_plan())
