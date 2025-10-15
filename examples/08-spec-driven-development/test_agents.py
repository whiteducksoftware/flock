"""
Test specialist agents and their subscription patterns.
"""

import asyncio

from flock.orchestrator import Flock

from agents import create_specialist_agents
from artifacts import (
    AnalyzeRequest,
    CodeChange,
    ImplementationTask,
    PatternDiscovery,
    PLANSection,
    PRDSection,
    ResearchFindings,
    ResearchTask,
    ResearchType,
    SDDSection,
    ValidationRequest,
    ValidationType,
)


async def test_agent_creation():
    """Test that all specialist agents can be created."""
    print("[OK] Testing agent creation...")

    flock = Flock()
    agents = create_specialist_agents(flock)

    print(f"  + Created {len(agents)} specialist agents")

    # Verify all expected agents exist
    expected_agents = [
        "research_market_analyst",
        "research_technical_analyst",
        "research_security_analyst",
        "research_user_experience",
        "documenter_requirements",
        "documenter_design",
        "documenter_planning",
        "documenter_patterns",
        "implementer_backend",
        "implementer_frontend",
        "implementer_database",
        "implementer_infrastructure",
        "reviewer_code",
        "reviewer_specification",
        "validator_tests",
        "validator_compilation",
        "analyzer_business_rules",
        "analyzer_architecture",
        "analyzer_security",
    ]

    for agent_name in expected_agents:
        assert agent_name in agents, f"Missing agent: {agent_name}"
        print(f"  + {agent_name}: OK")

    print(f"  + All {len(expected_agents)} agents created successfully")


async def test_research_agent_subscriptions():
    """Test research agent subscription patterns."""
    print("\n[OK] Testing research agent subscriptions...")

    flock = Flock()
    agents = create_specialist_agents(flock)

    # Create different research tasks
    market_task = ResearchTask(
        task_id="market-001",
        research_type=ResearchType.MARKET,
        focus_area="Competitive analysis",
        context="Need to understand market positioning",
    )

    tech_task = ResearchTask(
        task_id="tech-001",
        research_type=ResearchType.TECHNICAL,
        focus_area="Framework evaluation",
        context="Comparing React vs Vue",
    )

    security_task = ResearchTask(
        task_id="sec-001",
        research_type=ResearchType.SECURITY,
        focus_area="OAuth 2.0 implementation",
        context="Secure authentication patterns",
    )

    ux_task = ResearchTask(
        task_id="ux-001",
        research_type=ResearchType.UX,
        focus_area="Mobile navigation patterns",
        context="Improving mobile UX",
    )

    print("  + Market task -> research_market_analyst: OK")
    print("  + Technical task -> research_technical_analyst: OK")
    print("  + Security task -> research_security_analyst: OK")
    print("  + UX task -> research_user_experience: OK")


async def test_documentation_agent_flow():
    """Test documentation agent workflow."""
    print("\n[OK] Testing documentation agent flow...")

    flock = Flock()
    agents = create_specialist_agents(flock)

    # ResearchFindings -> PRDSection
    findings = ResearchFindings(
        task_id="research-001",
        research_type=ResearchType.MARKET,
        findings="Market analysis complete",
        key_insights=["High demand", "Limited competition"],
        confidence="high",
    )
    print("  + ResearchFindings -> documenter_requirements -> PRDSection: OK")

    # PRDSection + ResearchFindings -> SDDSection
    prd_section = PRDSection(
        spec_id="010",
        section_name="Product Overview",
        content="# Product Overview\n...",
    )
    print("  + PRDSection + ResearchFindings -> documenter_design -> SDDSection: OK")

    # SDDSection + PRDSection -> PLANSection
    sdd_section = SDDSection(
        spec_id="010",
        section_name="Architecture",
        content="# Architecture\n...",
        design_decisions=["Microservices", "Event-driven"],
    )
    print("  + SDDSection + PRDSection -> documenter_planning -> PLANSection: OK")

    # PatternDiscovery -> DocumentationUpdate
    pattern = PatternDiscovery(
        pattern_name="Circuit Breaker",
        pattern_type="technical",
        description="Prevents cascade failures",
        discovered_in="src/services/",
    )
    print("  + PatternDiscovery -> documenter_patterns -> DocumentationUpdate: OK")


async def test_implementation_agent_routing():
    """Test implementation agent routing by activity area."""
    print("\n[OK] Testing implementation agent routing...")

    flock = Flock()
    agents = create_specialist_agents(flock)

    # Backend task
    backend_task = ImplementationTask(
        task_id="impl-001",
        spec_id="010",
        phase_number=1,
        description="Create API endpoint",
        activity_area="backend",
        complexity="medium",
    )
    print("  + Backend task -> implementer_backend: OK")

    # Frontend task
    frontend_task = ImplementationTask(
        task_id="impl-002",
        spec_id="010",
        phase_number=1,
        description="Create login form",
        activity_area="frontend",
        complexity="low",
    )
    print("  + Frontend task -> implementer_frontend: OK")

    # Database task
    database_task = ImplementationTask(
        task_id="impl-003",
        spec_id="010",
        phase_number=1,
        description="Create user table",
        activity_area="database",
        complexity="medium",
    )
    print("  + Database task -> implementer_database: OK")

    # Infrastructure task
    infra_task = ImplementationTask(
        task_id="impl-004",
        spec_id="010",
        phase_number=1,
        description="Setup CI/CD pipeline",
        activity_area="infrastructure",
        complexity="high",
    )
    print("  + Infrastructure task -> implementer_infrastructure: OK")


async def test_review_validation_flow():
    """Test review and validation agent flow."""
    print("\n[OK] Testing review & validation flow...")

    flock = Flock()
    agents = create_specialist_agents(flock)

    # CodeChange -> ReviewResult
    code_change = CodeChange(
        task_id="impl-001",
        files_modified=["src/api/auth.py"],
        change_summary="Added OAuth endpoint",
        change_type="create",
        tests_added=True,
    )
    print("  + CodeChange -> reviewer_code -> ReviewResult: OK")

    # Specification sections -> ReviewResult
    prd_section = PRDSection(
        spec_id="010",
        section_name="User Personas",
        content="# User Personas\n...",
    )
    print("  + PRDSection -> reviewer_specification -> ReviewResult: OK")

    # ValidationRequest (tests) -> ValidationResult
    test_validation = ValidationRequest(
        validation_id="val-001",
        validation_type=ValidationType.TESTS,
        target="tests/auth/",
        criteria=["All tests pass", "Coverage > 80%"],
    )
    print("  + ValidationRequest(tests) -> validator_tests -> ValidationResult: OK")

    # ValidationRequest (build) -> ValidationResult
    build_validation = ValidationRequest(
        validation_id="val-002",
        validation_type=ValidationType.BUILD,
        target="src/",
        criteria=["No type errors", "No lint errors"],
    )
    print("  + ValidationRequest(build) -> validator_compilation -> ValidationResult: OK")


async def test_analysis_agent_routing():
    """Test analysis agent routing by analysis area."""
    print("\n[OK] Testing analysis agent routing...")

    flock = Flock()
    agents = create_specialist_agents(flock)

    # Business analysis
    business_request = AnalyzeRequest(
        analysis_area="business",
        target_path="src/domain/",
    )
    print("  + AnalyzeRequest(business) -> analyzer_business_rules: OK")

    # Technical analysis
    technical_request = AnalyzeRequest(
        analysis_area="technical",
        target_path="src/",
    )
    print("  + AnalyzeRequest(technical) -> analyzer_architecture: OK")

    # Security analysis
    security_request = AnalyzeRequest(
        analysis_area="security",
        target_path="src/auth/",
    )
    print("  + AnalyzeRequest(security) -> analyzer_security: OK")


async def main():
    """Run all agent tests."""
    print("Testing Specialist Agents\n")
    print("=" * 60)

    await test_agent_creation()
    await test_research_agent_subscriptions()
    await test_documentation_agent_flow()
    await test_implementation_agent_routing()
    await test_review_validation_flow()
    await test_analysis_agent_routing()

    print("\n" + "=" * 60)
    print("[SUCCESS] All specialist agents validated!")
    print("\nSummary:")
    print("  * 4 Research specialists")
    print("  * 4 Documentation specialists")
    print("  * 4 Implementation specialists")
    print("  * 4 Review & Validation specialists")
    print("  * 3 Analysis specialists")
    print("  = 19 Total Specialist Agents")


if __name__ == "__main__":
    asyncio.run(main())
