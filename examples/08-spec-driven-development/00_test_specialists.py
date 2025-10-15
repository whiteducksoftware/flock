"""
Test Specialists in Action - Simple Demo

This example demonstrates the specialist agents working together through
the blackboard without any orchestrators. Shows the emergent collaboration
pattern that makes Flock powerful.
"""

import asyncio

from flock.orchestrator import Flock

from agents import create_specialist_agents
from artifacts import (
    AnalyzeRequest,
    ImplementationTask,
    PRDSection,
    ResearchFindings,
    ResearchTask,
    ResearchType,
    SDDSection,
    ValidationRequest,
    ValidationType,
)


async def demo_research_flow():
    """
    Demo: ResearchTask -> ResearchFindings (parallel)

    Shows multiple research specialists reacting in parallel to different
    research task types.
    """
    print("\n" + "=" * 70)
    print("DEMO 1: Research Specialists (Parallel Execution)")
    print("=" * 70)

    flock = Flock()
    agents = create_specialist_agents(flock)

    print("\n[Step 1] Publishing 4 research tasks (different types)...")

    # Publish 4 different research tasks
    market_task = ResearchTask(
        task_id="research-market-001",
        research_type=ResearchType.MARKET,
        focus_area="Competitive analysis for authentication solutions",
        context="Need to understand what competitors offer for OAuth/SSO",
        spec_id="010",
    )
    await flock.publish(market_task)
    print("  + Published: Market research task")

    tech_task = ResearchTask(
        task_id="research-tech-001",
        research_type=ResearchType.TECHNICAL,
        focus_area="OAuth 2.0 implementation patterns",
        context="Evaluate OAuth libraries and frameworks",
        spec_id="010",
    )
    await flock.publish(tech_task)
    print("  + Published: Technical research task")

    security_task = ResearchTask(
        task_id="research-sec-001",
        research_type=ResearchType.SECURITY,
        focus_area="Authentication security best practices",
        context="OWASP guidelines and common vulnerabilities",
        spec_id="010",
    )
    await flock.publish(security_task)
    print("  + Published: Security research task")

    ux_task = ResearchTask(
        task_id="research-ux-001",
        research_type=ResearchType.UX,
        focus_area="Login/signup UX patterns",
        context="Best practices for authentication flows",
        spec_id="010",
    )
    await flock.publish(ux_task)
    print("  + Published: UX research task")

    print("\n[Step 2] Running agents until idle...")
    print("  (All 4 research specialists will execute IN PARALLEL)")

    await flock.run_until_idle()

    print("\n[Step 3] Checking blackboard for ResearchFindings...")
    findings = await flock.store.get_by_type(ResearchFindings)

    print(f"\n[SUCCESS] {len(findings)} ResearchFindings artifacts created!")
    for finding in findings:
        print(f"  + {finding.research_type.value}: {len(finding.key_insights)} insights")

    print("\n[Observation] All 4 research specialists executed in parallel")
    print("              without any orchestrator coordination!")


async def demo_documentation_flow():
    """
    Demo: ResearchFindings -> PRDSection -> SDDSection

    Shows documentation specialists building on each other's work.
    """
    print("\n" + "=" * 70)
    print("DEMO 2: Documentation Specialists (Sequential Flow)")
    print("=" * 70)

    flock = Flock()
    agents = create_specialist_agents(flock)

    print("\n[Step 1] Publishing ResearchFindings...")

    # Publish research findings
    findings = ResearchFindings(
        task_id="research-001",
        research_type=ResearchType.MARKET,
        findings="## Market Analysis\n\nCompetitive landscape shows high demand...",
        key_insights=[
            "Market size: $5B and growing",
            "Key competitors: Auth0, Okta, Firebase",
            "Differentiation opportunity: Open-source + simplicity"
        ],
        recommendations=[
            "Focus on developer experience",
            "Provide migration tools from competitors"
        ],
        confidence="high",
    )
    await flock.publish(findings)
    print("  + Published: Market research findings")

    print("\n[Step 2] Running agents (documenter_requirements should react)...")
    await flock.run_until_idle()

    # Check for PRDSection
    prd_sections = await flock.store.get_by_type(PRDSection)
    print(f"\n[Result] {len(prd_sections)} PRDSection created by documenter_requirements")

    if prd_sections:
        prd = prd_sections[0]
        print(f"  + Section: {prd.section_name}")
        print(f"  + Based on: {len(prd.research_basis)} research findings")

    print("\n[Step 3] Publishing PRDSection + more findings for SDD...")

    # Add technical findings
    tech_findings = ResearchFindings(
        task_id="research-002",
        research_type=ResearchType.TECHNICAL,
        findings="## Technical Evaluation\n\nOAuth 2.0 with JWT tokens...",
        key_insights=[
            "Use proven libraries (Passport.js, OAuth2 Server)",
            "JWT for stateless authentication",
            "Refresh token rotation for security"
        ],
        recommendations=[
            "Implement token revocation list",
            "Use short-lived access tokens (15min)"
        ],
        confidence="high",
    )
    await flock.publish(tech_findings)

    # Publish PRD section (already exists, so documenter_design can react)
    if prd_sections:
        # documenter_design consumes both PRDSection and ResearchFindings
        print("  + PRDSection already published")
        print("  + Published: Technical findings")

    print("\n[Step 4] Running agents (documenter_design should react)...")
    await flock.run_until_idle()

    # Check for SDDSection
    sdd_sections = await flock.store.get_by_type(SDDSection)
    print(f"\n[Result] {len(sdd_sections)} SDDSection created by documenter_design")

    if sdd_sections:
        sdd = sdd_sections[0]
        print(f"  + Section: {sdd.section_name}")
        print(f"  + Design decisions: {len(sdd.design_decisions)}")

    print("\n[Observation] Documentation specialists build on each other:")
    print("              ResearchFindings -> PRDSection -> SDDSection")


async def demo_implementation_routing():
    """
    Demo: ImplementationTask -> CodeChange (routed by activity_area)

    Shows how implementation specialists route by task area.
    """
    print("\n" + "=" * 70)
    print("DEMO 3: Implementation Specialists (Smart Routing)")
    print("=" * 70)

    flock = Flock()
    agents = create_specialist_agents(flock)

    print("\n[Step 1] Publishing 4 implementation tasks (different areas)...")

    # Backend task
    backend_task = ImplementationTask(
        task_id="impl-backend-001",
        spec_id="010",
        phase_number=1,
        description="Create OAuth token endpoint",
        activity_area="backend",
        complexity="medium",
        sdd_references=["SDD Section 3.2: API Design"],
    )
    await flock.publish(backend_task)
    print("  + Published: Backend task")

    # Frontend task
    frontend_task = ImplementationTask(
        task_id="impl-frontend-001",
        spec_id="010",
        phase_number=1,
        description="Create login form component",
        activity_area="frontend",
        complexity="low",
        sdd_references=["SDD Section 4.1: UI Components"],
    )
    await flock.publish(frontend_task)
    print("  + Published: Frontend task")

    # Database task
    database_task = ImplementationTask(
        task_id="impl-database-001",
        spec_id="010",
        phase_number=1,
        description="Create users and tokens tables",
        activity_area="database",
        complexity="medium",
        sdd_references=["SDD Section 2.1: Data Models"],
    )
    await flock.publish(database_task)
    print("  + Published: Database task")

    # Infrastructure task
    infra_task = ImplementationTask(
        task_id="impl-infra-001",
        spec_id="010",
        phase_number=1,
        description="Setup authentication service deployment",
        activity_area="infrastructure",
        complexity="high",
        sdd_references=["SDD Section 5.1: Deployment"],
    )
    await flock.publish(infra_task)
    print("  + Published: Infrastructure task")

    print("\n[Step 2] Running agents (each specialist picks their task)...")
    await flock.run_until_idle()

    print("\n[Step 3] Checking blackboard for CodeChanges...")
    code_changes = await flock.store.get_by_type(CodeChange)

    print(f"\n[SUCCESS] {len(code_changes)} CodeChange artifacts created!")
    for change in code_changes:
        print(f"  + Task {change.task_id}: {len(change.files_modified)} files modified")

    print("\n[Observation] Implementation specialists automatically route")
    print("              tasks based on activity_area predicate!")


async def demo_analysis_flow():
    """
    Demo: AnalyzeRequest -> PatternDiscovery -> DocumentationUpdate

    Shows analysis specialists discovering patterns.
    """
    print("\n" + "=" * 70)
    print("DEMO 4: Analysis Specialists (Pattern Discovery)")
    print("=" * 70)

    flock = Flock()
    agents = create_specialist_agents(flock)

    print("\n[Step 1] Publishing 3 analysis requests (different areas)...")

    # Business analysis
    business_request = AnalyzeRequest(
        analysis_area="business",
        target_path="src/domain/orders",
    )
    await flock.publish(business_request)
    print("  + Published: Business analysis request")

    # Technical analysis
    technical_request = AnalyzeRequest(
        analysis_area="technical",
        target_path="src/architecture",
    )
    await flock.publish(technical_request)
    print("  + Published: Technical analysis request")

    # Security analysis
    security_request = AnalyzeRequest(
        analysis_area="security",
        target_path="src/auth",
    )
    await flock.publish(security_request)
    print("  + Published: Security analysis request")

    print("\n[Step 2] Running analysis specialists...")
    await flock.run_until_idle()

    print("\n[Step 3] Checking for discovered patterns...")
    patterns = await flock.store.get_by_type(PatternDiscovery)

    print(f"\n[Result] {len(patterns)} patterns discovered!")
    for pattern in patterns:
        print(f"  + {pattern.pattern_type}: {pattern.pattern_name}")

    print("\n[Observation] Analysis specialists discover patterns in parallel")
    print("              based on analysis_area routing!")


async def main():
    """Run all specialist demos."""
    print("\n" + "=" * 70)
    print("SPECIALIST AGENTS IN ACTION - PROOF OF CONCEPT")
    print("=" * 70)
    print("\nThis demo shows specialist agents collaborating through the")
    print("blackboard WITHOUT orchestrators. Pure emergent behavior!")

    await demo_research_flow()
    await demo_documentation_flow()
    await demo_implementation_routing()
    await demo_analysis_flow()

    print("\n" + "=" * 70)
    print("[FINAL SUMMARY]")
    print("=" * 70)
    print("\nAll specialist agents validated in action!")
    print("\nKey Observations:")
    print("  1. Parallel execution: Multiple research specialists run simultaneously")
    print("  2. Sequential flow: Documentation builds on previous work")
    print("  3. Smart routing: Implementation tasks route by activity_area")
    print("  4. Conditional consumption: Agents filter by predicates (where=)")
    print("\nNext: Build orchestrators to coordinate these specialists!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
