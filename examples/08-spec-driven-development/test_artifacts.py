"""
Quick test to verify all artifact types are properly defined and can be instantiated.
"""

import asyncio

from artifacts import (
    AnalyzeRequest,
    BlockedState,
    CodeChange,
    ContinueSignal,
    CycleComplete,
    DocumentationComplete,
    DocumentationUpdate,
    ImplementationTask,
    ImplementRequest,
    InterfaceDiscovery,
    PatternDiscovery,
    PhaseComplete,
    PhaseStart,
    PLANSection,
    PRDSection,
    RefactorRequest,
    ResearchFindings,
    ResearchTask,
    ResearchType,
    ReviewRequest,
    ReviewResult,
    SDDSection,
    SpecificationComplete,
    SpecificationMetadata,
    SpecifyRequest,
    ValidationRequest,
    ValidationResult,
    ValidationType,
)


async def test_core_requests():
    """Test core request artifact types."""
    print("[OK] Testing core request types...")

    specify = SpecifyRequest(
        feature_description="Add user authentication with OAuth 2.0"
    )
    print(f"  + SpecifyRequest: {specify.feature_description}")

    analyze = AnalyzeRequest(
        analysis_area="security", target_path="src/auth"
    )
    print(f"  + AnalyzeRequest: {analyze.analysis_area}")

    implement = ImplementRequest(spec_id="010")
    print(f"  + ImplementRequest: {implement.spec_id}")

    refactor = RefactorRequest(
        target_description="Refactor authentication module for better testability"
    )
    print(f"  + RefactorRequest: {refactor.target_description}")


async def test_specification_types():
    """Test specification artifact types."""
    print("\n[OK] Testing specification types...")

    metadata = SpecificationMetadata(
        spec_id="010",
        feature_name="user-auth",
        directory="docs/specs/010-user-auth",
        current_phase="prd",
    )
    print(f"  + SpecificationMetadata: {metadata.spec_id}-{metadata.feature_name}")

    prd_section = PRDSection(
        spec_id="010",
        section_name="Product Overview",
        content="# Product Overview\nOAuth 2.0 authentication...",
    )
    print(f"  + PRDSection: {prd_section.section_name}")

    sdd_section = SDDSection(
        spec_id="010",
        section_name="Architecture",
        content="# Architecture\nToken-based authentication...",
        design_decisions=["Use JWT tokens", "Refresh token rotation"],
    )
    print(f"  + SDDSection: {sdd_section.section_name}")

    plan_section = PLANSection(
        spec_id="010",
        section_name="Phase 1: Database Setup",
        content="## Phase 1\nSetup user tables...",
        task_count=5,
        estimated_complexity="medium",
    )
    print(f"  + PLANSection: {plan_section.section_name}")

    spec_complete = SpecificationComplete(
        spec_id="010",
        directory="docs/specs/010-user-auth",
        confidence_score=85,
        summary="Complete specification for OAuth authentication",
        next_steps="Run /s:implement 010",
    )
    print(f"  + SpecificationComplete: {spec_complete.confidence_score}% confidence")


async def test_research_types():
    """Test research and discovery artifact types."""
    print("\n[OK] Testing research & discovery types...")

    research_task = ResearchTask(
        task_id="research-001",
        research_type=ResearchType.SECURITY,
        focus_area="OAuth 2.0 best practices",
        context="Need to understand secure token storage",
        spec_id="010",
    )
    print(f"  + ResearchTask: {research_task.focus_area}")

    findings = ResearchFindings(
        task_id="research-001",
        research_type=ResearchType.SECURITY,
        findings="OAuth 2.0 requires secure token storage...",
        key_insights=["Use httpOnly cookies", "Implement token rotation"],
        confidence="high",
    )
    print(f"  + ResearchFindings: {len(findings.key_insights)} insights")

    pattern = PatternDiscovery(
        pattern_name="Repository Pattern",
        pattern_type="technical",
        description="Data access abstraction layer",
        use_cases=["Database operations", "Data mocking"],
        discovered_in="src/repositories/",
    )
    print(f"  + PatternDiscovery: {pattern.pattern_name}")

    interface = InterfaceDiscovery(
        interface_name="Auth0 API",
        interface_type="rest_api",
        contract_details="POST /oauth/token, GET /userinfo",
        discovered_in="src/integrations/auth0.py",
    )
    print(f"  + InterfaceDiscovery: {interface.interface_name}")


async def test_implementation_types():
    """Test implementation artifact types."""
    print("\n[OK] Testing implementation types...")

    phase_start = PhaseStart(
        spec_id="010",
        phase_number=1,
        phase_name="Database Setup",
        task_count=5,
        tasks_overview=["Create user table", "Add auth columns", "Create migrations"],
    )
    print(f"  + PhaseStart: Phase {phase_start.phase_number}")

    task = ImplementationTask(
        task_id="task-001",
        spec_id="010",
        phase_number=1,
        description="Create user authentication table",
        activity_area="database",
        complexity="medium",
    )
    print(f"  + ImplementationTask: {task.description}")

    code_change = CodeChange(
        task_id="task-001",
        files_modified=["migrations/001_create_users.sql", "models/user.py"],
        change_summary="Added user authentication table with OAuth fields",
        change_type="create",
        tests_added=True,
    )
    print(f"  + CodeChange: {len(code_change.files_modified)} files modified")

    phase_complete = PhaseComplete(
        spec_id="010",
        phase_number=1,
        phase_name="Database Setup",
        tasks_completed=5,
        tasks_total=5,
        validation_passed=True,
        summary="Database schema created and migrated successfully",
        next_phase=2,
    )
    print(f"  + PhaseComplete: {phase_complete.tasks_completed}/{phase_complete.tasks_total} tasks")


async def test_validation_types():
    """Test validation and control flow artifact types."""
    print("\n[OK] Testing validation & control flow types...")

    val_request = ValidationRequest(
        validation_id="val-001",
        validation_type=ValidationType.TESTS,
        target="tests/auth/",
        criteria=["All tests pass", "Coverage > 80%"],
    )
    print(f"  + ValidationRequest: {val_request.validation_type}")

    val_result = ValidationResult(
        validation_id="val-001",
        validation_type=ValidationType.TESTS,
        status="passed",
        issues=[],
    )
    print(f"  + ValidationResult: {val_result.status}")

    review_req = ReviewRequest(
        review_id="review-001",
        review_type="code",
        target="src/auth/oauth.py",
        focus="security and error handling",
    )
    print(f"  + ReviewRequest: {review_req.focus}")

    review_res = ReviewResult(
        review_id="review-001",
        review_type="code",
        status="approved",
        feedback="Good implementation, follows security best practices",
    )
    print(f"  + ReviewResult: {review_res.status}")

    cycle_complete = CycleComplete(
        cycle_type="specify",
        cycle_number=1,
        summary="PRD Product Overview section complete",
        artifacts_created=["docs/specs/010-user-auth/PRD.md"],
        next_action="Continue to User Personas section?",
    )
    print(f"  + CycleComplete: Cycle {cycle_complete.cycle_number}")

    continue_sig = ContinueSignal(signal_type="continue", target="next_cycle")
    print(f"  + ContinueSignal: {continue_sig.signal_type}")

    blocked = BlockedState(
        blocked_by="missing_specification",
        context="Attempting to implement Phase 2",
        reason="SDD section 3.2 has unresolved [NEEDS CLARIFICATION] markers",
        options=["Return to specify", "Skip this task", "Manual resolution"],
    )
    print(f"  + BlockedState: {blocked.blocked_by}")


async def test_documentation_types():
    """Test documentation artifact types."""
    print("\n[OK] Testing documentation types...")

    doc_update = DocumentationUpdate(
        file_path="docs/patterns/oauth-pattern.md",
        update_type="create",
        content="# OAuth Pattern\nHow to implement OAuth 2.0...",
        reason="Discovered OAuth pattern during analysis",
    )
    print(f"  + DocumentationUpdate: {doc_update.file_path}")

    doc_complete = DocumentationComplete(
        file_path="docs/specs/010-user-auth/PRD.md",
        document_type="prd",
        summary="Product requirements for user authentication",
        sections_complete=["Product Overview", "User Personas", "Feature Requirements"],
    )
    print(f"  + DocumentationComplete: {len(doc_complete.sections_complete)} sections")


async def main():
    """Run all artifact tests."""
    print("Testing Spec-Driven Development Artifacts\n")
    print("=" * 60)

    await test_core_requests()
    await test_specification_types()
    await test_research_types()
    await test_implementation_types()
    await test_validation_types()
    await test_documentation_types()

    print("\n" + "=" * 60)
    print("[SUCCESS] All artifact types validated successfully!")
    print(f"\nSummary:")
    print(f"  * 4 Core Request types")
    print(f"  * 5 Specification types")
    print(f"  * 4 Research & Discovery types")
    print(f"  * 4 Implementation types")
    print(f"  * 7 Validation & Control Flow types")
    print(f"  * 2 Documentation types")
    print(f"  = 26 Total Artifact Types")


if __name__ == "__main__":
    asyncio.run(main())
