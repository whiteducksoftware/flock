"""
Specify Workflow Example - End-to-End PRD Generation

This example demonstrates the complete specification workflow:
1. User provides a feature description
2. System creates spec directory and metadata
3. Research specialists gather information in parallel
4. Documentation specialists synthesize findings into PRD sections
5. PRD is written to .flock/specs/SXXX/PRD.md

This is a simplified version showing the pattern. Full implementation
would include SDD and PLAN phases, review cycles, and user confirmations.
"""

import asyncio
from pathlib import Path

from flock.orchestrator import Flock

from agents import create_specialist_agents
from artifacts import (
    PRDSection,
    ResearchFindings,
    ResearchTask,
    ResearchType,
    SpecifyRequest,
)
from mcp_config import configure_mcps
from spec_tools import (
    append_to_document,
    create_spec_directory,
    finalize_spec,
    format_research_findings,
    get_current_date,
)


async def simplified_specify_workflow():
    """
    Simplified specify workflow that demonstrates the pattern.

    Flow:
    1. Create spec directory with custom tool
    2. Publish 4 research tasks (market, technical, security, UX)
    3. Research specialists execute in parallel
    4. Collect research findings
    5. Publish findings to trigger documenter_requirements
    6. Documenter creates PRDSection artifacts
    7. Write PRDSection content to PRD.md
    """
    print("\n" + "=" * 70)
    print("SPECIFY WORKFLOW - PRD GENERATION")
    print("=" * 70)

    # Feature we want to specify
    feature_description = "Add user authentication with OAuth 2.0 and JWT tokens"

    print(f"\n[FEATURE] {feature_description}")

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

    # Add custom tools to the orchestrator (we'll act as a simple orchestrator)
    print("\n[Step 3] Registering custom spec tools...")
    custom_tools = [
        create_spec_directory,
        append_to_document,
        format_research_findings,
        finalize_spec,
        get_current_date,
    ]
    print(f"  + Registered {len(custom_tools)} custom tools")

    # ===========================================================================
    # PHASE 1: INITIALIZE SPEC
    # ===========================================================================

    print("\n[Phase 1] Creating spec directory...")
    spec_info = create_spec_directory(feature_description)
    spec_id = spec_info["spec_id"]
    prd_path = spec_info["prd_path"]

    print(f"  + Spec ID: {spec_id}")
    print(f"  + Spec Dir: {spec_info['spec_dir']}")
    print(f"  + PRD Path: {prd_path}")

    # ===========================================================================
    # PHASE 2: RESEARCH (Parallel Execution)
    # ===========================================================================

    print("\n[Phase 2] Publishing research tasks...")
    print("  (4 research specialists will execute IN PARALLEL)")

    # Market research
    market_task = ResearchTask(
        task_id=f"{spec_id}-research-market",
        research_type=ResearchType.MARKET,
        focus_area="OAuth 2.0 authentication market analysis",
        context=(
            "Analyze competitive authentication solutions, market trends, "
            "and user expectations for OAuth 2.0 with JWT tokens"
        ),
        spec_id=spec_id,
    )
    await flock.publish(market_task)
    print("  + Published: Market research task")

    # Technical research
    tech_task = ResearchTask(
        task_id=f"{spec_id}-research-technical",
        research_type=ResearchType.TECHNICAL,
        focus_area="OAuth 2.0 and JWT implementation patterns",
        context=(
            "Research OAuth 2.0 flows, JWT token structure, "
            "refresh token strategies, and best practices"
        ),
        spec_id=spec_id,
    )
    await flock.publish(tech_task)
    print("  + Published: Technical research task")

    # Security research
    security_task = ResearchTask(
        task_id=f"{spec_id}-research-security",
        research_type=ResearchType.SECURITY,
        focus_area="OAuth 2.0 and JWT security considerations",
        context=(
            "Identify security vulnerabilities, OWASP guidelines, "
            "token security, PKCE requirements, and common attack vectors"
        ),
        spec_id=spec_id,
    )
    await flock.publish(security_task)
    print("  + Published: Security research task")

    # UX research
    ux_task = ResearchTask(
        task_id=f"{spec_id}-research-ux",
        research_type=ResearchType.UX,
        focus_area="Authentication user experience patterns",
        context=(
            "Research login/signup flows, social login UX, "
            "error messaging, and accessibility considerations"
        ),
        spec_id=spec_id,
    )
    await flock.publish(ux_task)
    print("  + Published: UX research task")

    # ===========================================================================
    # EXECUTE RESEARCH
    # ===========================================================================

    print("\n[Executing] Running research specialists...")
    print("  NOTE: This will take several minutes as LLM agents think!")
    print("  Press Ctrl+C to stop early and see partial results\n")

    try:
        # Run agents with a longer timeout since research takes time
        await asyncio.wait_for(flock.run_until_idle(), timeout=300.0)
        print("\n[SUCCESS] All research completed!")
    except asyncio.TimeoutError:
        print("\n[TIMEOUT] Research took longer than expected")
        print("  Some findings may still be processing...")
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Stopping early to show partial results...")

    # ===========================================================================
    # PHASE 3: COLLECT RESEARCH FINDINGS
    # ===========================================================================

    print("\n[Phase 3] Collecting research findings...")
    findings = await flock.store.get_by_type(ResearchFindings)
    print(f"  + Found {len(findings)} research findings")

    if findings:
        for finding in findings:
            print(f"\n  [{finding.research_type.value.upper()}]")
            print(f"    Insights: {len(finding.key_insights)}")
            print(f"    Recommendations: {len(finding.recommendations)}")
            print(f"    Confidence: {finding.confidence}")

            # Format and append to PRD
            formatted = format_research_findings(
                research_type=finding.research_type.value,
                findings=finding.findings,
                insights=finding.key_insights,
                recommendations=finding.recommendations,
            )
            append_to_document(prd_path, formatted, None)
            print(f"    -> Appended to PRD.md")

    # ===========================================================================
    # PHASE 4: TRIGGER DOCUMENTATION (PRD Sections)
    # ===========================================================================

    print("\n[Phase 4] Waiting for documenter_requirements...")
    print("  (Agent will synthesize research into PRD sections)")

    # The documenter_requirements agent should react to ResearchFindings
    # and create PRDSection artifacts. Let's wait a bit more.
    if findings:
        print("\n[Waiting] Giving documenter time to process findings...")
        try:
            await asyncio.wait_for(flock.run_until_idle(), timeout=120.0)
        except asyncio.TimeoutError:
            print("  [TIMEOUT] Documenter still processing...")

    # Collect PRD sections
    prd_sections = await flock.store.get_by_type(PRDSection)
    print(f"\n  + Found {len(prd_sections)} PRD sections")

    if prd_sections:
        for section in prd_sections:
            print(f"\n  [PRD SECTION] {section.section_name}")
            print(f"    Research basis: {len(section.research_basis)} findings")

            # Append to PRD
            append_to_document(prd_path, section.content, section.section_name)
            print(f"    -> Appended to PRD.md")

    # ===========================================================================
    # FINALIZE
    # ===========================================================================

    print("\n[Phase 5] Finalizing specification...")

    # Determine confidence based on findings
    if len(findings) >= 4:
        confidence = "high"
    elif len(findings) >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    finalize_spec(spec_id, confidence)
    print(f"  + Marked spec as complete ({confidence} confidence)")

    # ===========================================================================
    # SUMMARY
    # ===========================================================================

    print("\n" + "=" * 70)
    print("[SUMMARY]")
    print("=" * 70)
    print(f"\nSpec ID: {spec_id}")
    print(f"Feature: {feature_description}")
    print(f"PRD Location: {prd_path}")
    print(f"\nResearch Findings: {len(findings)}")
    print(f"PRD Sections: {len(prd_sections)}")
    print(f"Confidence: {confidence}")

    # Show PRD content
    prd_content = Path(prd_path).read_text(encoding="utf-8")
    print(f"\n--- PRD.md Content ({len(prd_content)} characters) ---")
    print(prd_content[:500])
    if len(prd_content) > 500:
        print(f"\n... (truncated, see {prd_path} for full content)")

    print("\n" + "=" * 70)
    print("[COMPLETE] Specify workflow finished!")
    print("=" * 70)
    print(f"\nNext steps:")
    print(f"  1. Review the PRD: {prd_path}")
    print(f"  2. Run SDD phase (coming soon)")
    print(f"  3. Run PLAN phase (coming soon)")
    print(f"  4. Run implement workflow with spec ID: {spec_id}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(simplified_specify_workflow())
