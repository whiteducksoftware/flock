"""
Dashboard Demo - Visualize Spec-Driven Development

This example provides a live dashboard where you can:
1. Choose one of 4 workflows: Specify, Analyze, Implement, or Refactor
2. Publish the request artifact
3. Watch 27 agents collaborate in real-time on the blackboard
4. See artifact transformations and agent execution flow

Perfect for demonstrating the blackboard orchestration pattern!
"""

import asyncio
from pathlib import Path

from flock.orchestrator import Flock

from agents import create_specialist_agents
from artifacts import (
    AnalyzeRequest,
    ImplementRequest,
    RefactorRequest,
    SpecifyRequest,
)
from mcp_config import configure_mcps
from orchestrators import create_orchestrators


async def run_dashboard_demo():
    """
    Interactive dashboard demo for spec-driven development.

    Choose a workflow and watch the magic happen!
    """
    print("\n" + "=" * 70)
    print("SPEC-DRIVEN DEVELOPMENT - LIVE DASHBOARD")
    print("=" * 70)
    print("\nWatch 27 agents collaborate through typed artifacts!")
    print("Perfect for demonstrating blackboard orchestration.\n")

    # ===========================================================================
    # WORKFLOW SELECTION
    # ===========================================================================

    print("=" * 70)
    print("CHOOSE YOUR WORKFLOW:")
    print("=" * 70)
    print("\n[1] SPECIFY - Generate complete PRD/SDD/PLAN from feature description")
    print("    Example: 'Add user authentication with OAuth 2.0'")
    print("    Agents: 4 research specialists + 3 documenters + orchestrator")
    print("    Flow: Research (parallel) -> PRD -> SDD -> PLAN")
    print()
    print("[2] ANALYZE - Discover patterns and document system architecture")
    print("    Example: Analyze the Flock framework itself")
    print("    Agents: 3 analysis specialists + pattern documenter")
    print("    Flow: Business + Technical + Security analysis (parallel)")
    print()
    print("[3] IMPLEMENT - Execute implementation plan phase-by-phase")
    print("    Example: Implement spec S001 (requires existing PLAN.md)")
    print("    Agents: 4 implementers + 2 validators + orchestrator")
    print("    Flow: PhaseStart -> Tasks (parallel) -> Validation -> PhaseComplete")
    print()
    print("[4] REFACTOR - Improve code quality with safety checks")
    print("    Example: Refactor spec_tools.py for better structure")
    print("    Agents: Implementers + validators + reviewers")
    print("    Flow: Analyze -> Apply (incremental) -> Validate -> Review")
    print()

    choice = input("Enter workflow number (1-4): ").strip()

    if choice not in ["1", "2", "3", "4"]:
        print(f"\n[ERROR] Invalid choice: {choice}")
        print("Please run again and choose 1, 2, 3, or 4")
        return

    # ===========================================================================
    # SETUP FLOCK WITH DASHBOARD
    # ===========================================================================

    print("\n" + "=" * 70)
    print("[SETUP] Initializing Flock with dashboard...")
    print("=" * 70)

    flock = Flock()

    # Configure MCP servers
    print("\n[Step 1] Configuring MCP tools...")
    mcp_status = configure_mcps(flock)
    print(f"  + Filesystem MCP: {'[OK]' if mcp_status.get('filesystem') else '[SKIP]'}")
    print(f"  + DuckDuckGo MCP: {'[OK]' if mcp_status.get('search_web') else '[SKIP]'}")
    print(f"  + Website Reader MCP: {'[OK]' if mcp_status.get('read_website') else '[SKIP]'}")

    if not mcp_status.get("filesystem"):
        print("\n[WARNING] Filesystem MCP not available!")
        print("  Install: npm install -g @modelcontextprotocol/server-filesystem")
        print("  Some workflows may not work without file I/O.")

    # Create all agents
    print("\n[Step 2] Creating specialist agents...")
    specialists = create_specialist_agents(flock)
    print(f"  + Created {len(specialists)} specialist agents")

    print("\n[Step 3] Creating orchestrator agents...")
    orchestrators = create_orchestrators(flock)
    print(f"  + Created {len(orchestrators)} orchestrator agents")

    total_agents = len(specialists) + len(orchestrators)
    print(f"\n  [TOTAL] {total_agents} agents ready to collaborate!")

    # ===========================================================================
    # WORKFLOW EXECUTION
    # ===========================================================================

    print("\n" + "=" * 70)
    print("[EXECUTION] Starting workflow...")
    print("=" * 70)

    if choice == "1":
        # SPECIFY WORKFLOW
        print("\n[WORKFLOW] Specify - Generate comprehensive specification")
        feature = input("\nEnter feature description (or press Enter for demo): ").strip()
        if not feature:
            feature = "Add user authentication with OAuth 2.0 and JWT tokens, including social login options (Google, Microsoft), password reset flow, and session management with refresh tokens"

        print(f"\n[FEATURE] {feature}")
        print("\n[PUBLISHING] SpecifyRequest artifact...")

        request = SpecifyRequest(
            feature_description=feature,
            spec_id=None,  # Will be auto-generated
        )
        await flock.publish(request)
        print("  + Published to blackboard")

        print("\n[AGENTS] These agents will react:")
        print("  1. specify_orchestrator - Coordinates the workflow")
        print("  2. research_market_analyst - Analyzes market and competition")
        print("  3. research_technical_analyst - Evaluates technical approaches")
        print("  4. research_security_analyst - Identifies security requirements")
        print("  5. research_user_experience - Studies UX patterns")
        print("  6. research_aggregator - Collects all findings (JoinSpec)")
        print("  7. documenter_requirements - Creates PRD sections")
        print("  8. documenter_design - Creates SDD sections")
        print("  9. documenter_planning - Creates PLAN sections")
        print("  10. reviewer_specification - Reviews documentation quality")

        print("\n[FLOW] SpecifyRequest -> ResearchTask (4x parallel) ->")
        print("       ResearchFindings (JoinSpec) -> PRDSection ->")
        print("       SDDSection -> PLANSection -> SpecificationComplete")

    elif choice == "2":
        # ANALYZE WORKFLOW
        print("\n[WORKFLOW] Analyze - Discover patterns and document architecture")
        target = input("\nEnter path to analyze (or press Enter for demo): ").strip()
        if not target:
            target = "examples/08-spec-driven-development/"

        print(f"\n[TARGET] {target}")
        print("\n[PUBLISHING] AnalyzeRequest artifacts (3x parallel)...")

        # Publish 3 analysis requests in parallel
        for analysis_type in ["business", "technical", "security"]:
            request = AnalyzeRequest(
                analysis_area=analysis_type,
                target_path=target,
                focus_questions=[
                    f"What {analysis_type} patterns exist?",
                    f"What {analysis_type} rules are enforced?",
                    f"What {analysis_type} interfaces are exposed?",
                ],
            )
            await flock.publish(request)
            print(f"  + Published AnalyzeRequest (area={analysis_type})")

        print("\n[AGENTS] These agents will react:")
        print("  1. analyzer_business_rules - Discovers business logic patterns")
        print("  2. analyzer_architecture - Maps technical architecture")
        print("  3. analyzer_security - Identifies security patterns")
        print("  4. pattern_documenter - Creates pattern documentation (BatchSpec)")

        print("\n[FLOW] AnalyzeRequest (3x parallel) -> PatternDiscovery (Nx) ->")
        print("       DocumentationUpdate (BatchSpec) -> CycleComplete")

    elif choice == "3":
        # IMPLEMENT WORKFLOW
        print("\n[WORKFLOW] Implement - Execute implementation plan")
        spec_id = input("\nEnter spec ID (e.g., S001) or press Enter for demo: ").strip()
        if not spec_id:
            print("\n[DEMO MODE] Creating a sample implementation plan...")
            spec_id = "DEMO"

        print(f"\n[SPEC ID] {spec_id}")
        print("\n[PUBLISHING] ImplementRequest artifact...")

        request = ImplementRequest(
            spec_id=spec_id,
            plan_path=f".flock/specs/{spec_id}/PLAN.md" if spec_id != "DEMO" else None,
            start_from_phase=1,
        )
        await flock.publish(request)
        print("  + Published to blackboard")

        print("\n[AGENTS] These agents will react:")
        print("  1. implement_orchestrator - Coordinates phase execution")
        print("  2. implementer_backend - Handles backend tasks")
        print("  3. implementer_frontend - Handles frontend tasks")
        print("  4. implementer_database - Handles database tasks")
        print("  5. implementer_infrastructure - Handles infrastructure tasks")
        print("  6. validator_tests - Runs test suites")
        print("  7. validator_compilation - Checks build status")
        print("  8. phase_validator - Aggregates results (BatchSpec)")
        print("  9. reviewer_code - Reviews code quality")

        print("\n[FLOW] ImplementRequest -> PhaseStart -> ImplementationTask (Nx) ->")
        print("       CodeChange (parallel) -> ValidationRequest ->")
        print("       ValidationResult -> PhaseComplete")

    elif choice == "4":
        # REFACTOR WORKFLOW
        print("\n[WORKFLOW] Refactor - Improve code quality safely")
        target = input("\nEnter file to refactor (or press Enter for demo): ").strip()
        if not target:
            target = str(Path(__file__).parent / "spec_tools.py")

        print(f"\n[TARGET] {target}")
        print("\n[PUBLISHING] RefactorRequest artifact...")

        request = RefactorRequest(
            target_path=target,
            target_description="Improve code structure, add error handling, reduce duplication",
            refactoring_goals=[
                "Extract common patterns into helper functions",
                "Add comprehensive error handling",
                "Improve documentation",
                "Reduce code duplication",
            ],
            constraints=[
                "ALL tests must pass after every change",
                "No behavior changes (refactoring only)",
                "Incremental changes (one at a time)",
            ],
        )
        await flock.publish(request)
        print("  + Published to blackboard")

        print("\n[AGENTS] These agents will react:")
        print("  1. refactor_orchestrator - Coordinates refactoring")
        print("  2. implementer_backend - Applies code changes")
        print("  3. validator_tests - Validates after EVERY change")
        print("  4. reviewer_code - Reviews quality improvement")
        print("  5. refactor_validator - Ensures behavior preservation")

        print("\n[FLOW] RefactorRequest -> ImplementationTask ->")
        print("       CodeChange -> ValidationRequest -> ValidationResult ->")
        print("       (if pass) ReviewRequest | (if fail) BlockedState")

    # ===========================================================================
    # RUN WITH DASHBOARD
    # ===========================================================================

    print("\n" + "=" * 70)
    print("[DASHBOARD] Starting Flock dashboard...")
    print("=" * 70)
    print("\nThe dashboard will show:")
    print("  + Agent execution graph (who's working on what)")
    print("  + Blackboard artifacts (what data is flowing)")
    print("  + Real-time updates as agents collaborate")
    print("  + Artifact transformations and dependencies")
    print()
    print("Press Ctrl+C to stop the dashboard")
    print("=" * 70 + "\n")

    try:
        # Run the flock with dashboard
        await flock.run()
    except KeyboardInterrupt:
        print("\n\n[STOPPED] Dashboard stopped by user")

    # ===========================================================================
    # RESULTS SUMMARY
    # ===========================================================================

    print("\n" + "=" * 70)
    print("[SUMMARY] Workflow Results")
    print("=" * 70)

    # Show artifact counts
    from artifacts import (
        BlockedState,
        CodeChange,
        CycleComplete,
        DocumentationUpdate,
        PatternDiscovery,
        PhaseComplete,
        ResearchFindings,
        ReviewResult,
        SpecificationComplete,
        ValidationResult,
    )

    print("\n[ARTIFACTS CREATED]")
    research_findings = await flock.store.get_by_type(ResearchFindings)
    print(f"  + ResearchFindings: {len(research_findings)}")

    patterns = await flock.store.get_by_type(PatternDiscovery)
    print(f"  + PatternDiscovery: {len(patterns)}")

    code_changes = await flock.store.get_by_type(CodeChange)
    print(f"  + CodeChange: {len(code_changes)}")

    validations = await flock.store.get_by_type(ValidationResult)
    print(f"  + ValidationResult: {len(validations)}")

    reviews = await flock.store.get_by_type(ReviewResult)
    print(f"  + ReviewResult: {len(reviews)}")

    docs = await flock.store.get_by_type(DocumentationUpdate)
    print(f"  + DocumentationUpdate: {len(docs)}")

    cycles = await flock.store.get_by_type(CycleComplete)
    print(f"  + CycleComplete: {len(cycles)}")

    phases = await flock.store.get_by_type(PhaseComplete)
    print(f"  + PhaseComplete: {len(phases)}")

    specs = await flock.store.get_by_type(SpecificationComplete)
    print(f"  + SpecificationComplete: {len(specs)}")

    blocked = await flock.store.get_by_type(BlockedState)
    if blocked:
        print(f"\n  [WARNING] BlockedState: {len(blocked)}")
        for b in blocked:
            print(f"    - {b.reason}")

    print("\n" + "=" * 70)
    print("[COMPLETE] Dashboard demo finished!")
    print("=" * 70)
    print("\nWhat you just saw:")
    print("  + 27 agents collaborating through typed artifacts")
    print("  + Emergent coordination via blackboard pattern")
    print("  + Parallel execution with JoinSpec/BatchSpec")
    print("  + Real file I/O via MCP tools")
    print("  + Type-safe communication with Pydantic models")
    print()
    print("This is the power of blackboard orchestration! 🚀")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_dashboard_demo())
