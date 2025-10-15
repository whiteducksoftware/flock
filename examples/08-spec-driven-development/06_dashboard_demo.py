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
from orchestrators import create_orchestrator_agents


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
    orchestrators = create_orchestrator_agents(flock)
    print(f"  + Created {len(orchestrators)} orchestrator agents")

    total_agents = len(specialists) + len(orchestrators)
    print(f"\n  [TOTAL] {total_agents} agents ready to collaborate!")

    # ===========================================================================
    # WORKFLOW EXECUTION
    # ===========================================================================
    await flock.serve(dashboard=True)
    print("\n" + "=" * 70)
    print("[EXECUTION] Starting workflow...")
    print("=" * 70)


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
