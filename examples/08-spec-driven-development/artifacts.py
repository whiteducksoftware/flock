"""
Artifact Types for Spec-Driven Development with Flock

This module defines all artifact types used in the spec-driven development workflow,
including requests, research, documentation, implementation, and validation artifacts.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from flock.registry import flock_type


# ==============================================================================
# 1.1 CORE ARTIFACT DEFINITIONS (User Requests)
# ==============================================================================


@flock_type
class SpecifyRequest(BaseModel):
    """User request to create a comprehensive specification (PRD/SDD/PLAN)."""

    feature_description: str = Field(
        description="Brief description of the feature to specify"
    )
    spec_id: str | None = Field(
        default=None,
        description="Optional existing spec ID to continue (e.g., '010' or '010-user-auth')",
    )
    start_from: Literal["prd", "sdd", "plan"] | None = Field(
        default=None,
        description="Which document to start from if continuing existing spec",
    )


@flock_type
class AnalyzeRequest(BaseModel):
    """User request to analyze codebase and discover patterns/rules."""

    analysis_area: str = Field(
        description="Area to analyze: business, technical, security, performance, integration, or specific domain"
    )
    target_path: str | None = Field(
        default=None, description="Optional specific path to analyze"
    )


@flock_type
class ImplementRequest(BaseModel):
    """User request to execute an implementation plan."""

    spec_id: str = Field(
        description="Specification ID to implement (e.g., '010' or '010-user-auth')"
    )
    start_from_phase: int | None = Field(
        default=None, description="Optional phase number to start from (1-based)"
    )


@flock_type
class RefactorRequest(BaseModel):
    """User request to refactor code for improved maintainability."""

    target_description: str = Field(
        description="Description of code to refactor and why"
    )
    target_path: str | None = Field(
        default=None, description="Optional specific path to refactor"
    )
    preserve_behavior: bool = Field(
        default=True, description="Whether to strictly preserve external behavior"
    )


# ==============================================================================
# 1.2 SPECIFICATION ARTIFACT TYPES
# ==============================================================================


@flock_type
class SpecificationMetadata(BaseModel):
    """Metadata about a specification including ID, directory, and phase."""

    spec_id: str = Field(description="Unique 3-digit specification ID (e.g., '010')")
    feature_name: str = Field(description="Short feature name (e.g., 'user-auth')")
    directory: str = Field(description="Full path to specification directory")
    current_phase: Literal["prd", "sdd", "plan", "complete"] = Field(
        description="Current phase of specification"
    )
    prd_path: str | None = Field(default=None, description="Path to PRD.md if exists")
    sdd_path: str | None = Field(default=None, description="Path to SDD.md if exists")
    plan_path: str | None = Field(
        default=None, description="Path to PLAN.md if exists"
    )


@flock_type
class PRDSection(BaseModel):
    """A completed section of the Product Requirements Document."""

    spec_id: str = Field(description="Specification ID this section belongs to")
    section_name: str = Field(
        description="Name of the PRD section (e.g., 'Product Overview', 'User Personas')"
    )
    content: str = Field(description="Markdown content for this section")
    research_basis: list[str] = Field(
        default_factory=list, description="Research findings this section is based on"
    )


@flock_type
class SDDSection(BaseModel):
    """A completed section of the Solution Design Document."""

    spec_id: str = Field(description="Specification ID this section belongs to")
    section_name: str = Field(
        description="Name of the SDD section (e.g., 'Architecture', 'Data Models')"
    )
    content: str = Field(description="Markdown content for this section")
    design_decisions: list[str] = Field(
        default_factory=list,
        description="Key design decisions documented in this section",
    )


@flock_type
class PLANSection(BaseModel):
    """A completed section of the Implementation Plan."""

    spec_id: str = Field(description="Specification ID this section belongs to")
    section_name: str = Field(
        description="Name of the PLAN section (e.g., 'Phase 1: Database Setup')"
    )
    content: str = Field(description="Markdown content for this section")
    task_count: int = Field(description="Number of implementation tasks in this phase")
    estimated_complexity: Literal["low", "medium", "high"] = Field(
        description="Overall complexity of this phase"
    )


@flock_type
class SpecificationComplete(BaseModel):
    """Signals that a specification is complete and ready for implementation."""

    spec_id: str = Field(description="Completed specification ID")
    directory: str = Field(description="Path to specification directory")
    confidence_score: int = Field(
        ge=0, le=100, description="Confidence in implementation readiness (0-100)"
    )
    summary: str = Field(description="Summary of what was specified")
    next_steps: str = Field(
        description="Recommended next steps (e.g., '/s:implement 010')"
    )


# ==============================================================================
# 1.3 RESEARCH & DISCOVERY ARTIFACTS
# ==============================================================================


class ResearchType(str, Enum):
    """Types of research that can be performed."""

    MARKET = "market"
    TECHNICAL = "technical"
    SECURITY = "security"
    UX = "user_experience"
    COMPETITIVE = "competitive"
    DOMAIN = "domain"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"


@flock_type
class ResearchTask(BaseModel):
    """A decomposed research activity for specialist agents."""

    task_id: str = Field(description="Unique identifier for this research task")
    research_type: ResearchType = Field(description="Type of research to perform")
    focus_area: str = Field(
        description="Specific area to research (e.g., 'OAuth 2.0 best practices')"
    )
    context: str = Field(
        description="Context about why this research is needed and what to look for"
    )
    spec_id: str | None = Field(
        default=None, description="Specification ID if related to a spec"
    )
    for_section: str | None = Field(
        default=None, description="Which document section this research supports"
    )


@flock_type
class ResearchFindings(BaseModel):
    """Results from specialist research including data and recommendations."""

    task_id: str = Field(description="ID of the ResearchTask this responds to")
    research_type: ResearchType = Field(description="Type of research performed")
    findings: str = Field(
        description="Detailed findings from the research (markdown format)"
    )
    key_insights: list[str] = Field(
        description="List of key insights or takeaways"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Actionable recommendations based on findings"
    )
    sources: list[str] = Field(
        default_factory=list, description="Sources consulted (URLs, file paths, etc.)"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level in these findings"
    )


@flock_type
class PatternDiscovery(BaseModel):
    """A discovered reusable pattern during analysis."""

    pattern_name: str = Field(description="Name of the discovered pattern")
    pattern_type: Literal["business", "technical", "architectural", "security"] = Field(
        description="Type of pattern discovered"
    )
    description: str = Field(description="What this pattern does and when to use it")
    examples: list[str] = Field(
        default_factory=list,
        description="Examples of where this pattern is used in the codebase",
    )
    use_cases: list[str] = Field(
        default_factory=list, description="Scenarios where this pattern applies"
    )
    discovered_in: str = Field(
        description="Where this pattern was discovered (file paths, modules)"
    )


@flock_type
class InterfaceDiscovery(BaseModel):
    """A discovered external integration or API contract."""

    interface_name: str = Field(
        description="Name of the external interface or API"
    )
    interface_type: Literal["rest_api", "graphql", "grpc", "webhook", "sdk"] = Field(
        description="Type of interface"
    )
    contract_details: str = Field(
        description="Details of the interface contract (endpoints, schemas, etc.)"
    )
    authentication: str | None = Field(
        default=None, description="Authentication mechanism used"
    )
    discovered_in: str = Field(
        description="Where this interface was discovered (file paths)"
    )
    documentation_url: str | None = Field(
        default=None, description="URL to external documentation if available"
    )


# ==============================================================================
# 1.4 IMPLEMENTATION ARTIFACTS
# ==============================================================================


@flock_type
class PhaseStart(BaseModel):
    """Signals the start of an implementation phase."""

    spec_id: str = Field(description="Specification being implemented")
    phase_number: int = Field(ge=1, description="Phase number (1-based)")
    phase_name: str = Field(description="Name of this phase")
    task_count: int = Field(description="Number of tasks in this phase")
    tasks_overview: list[str] = Field(
        description="Brief overview of tasks in this phase"
    )
    required_reading: list[str] = Field(
        default_factory=list,
        description="SDD sections that must be understood before starting",
    )


@flock_type
class ImplementationTask(BaseModel):
    """An individual implementation task within a phase."""

    task_id: str = Field(description="Unique task identifier")
    spec_id: str = Field(description="Specification being implemented")
    phase_number: int = Field(description="Phase this task belongs to")
    description: str = Field(description="What needs to be implemented")
    activity_area: Literal[
        "backend", "frontend", "database", "infrastructure", "testing", "documentation"
    ] = Field(description="Area of implementation")
    complexity: Literal["low", "medium", "high"] = Field(
        description="Implementation complexity"
    )
    can_run_parallel: bool = Field(
        default=False, description="Whether this task can run in parallel with others"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Task IDs that must complete before this one"
    )
    sdd_references: list[str] = Field(
        default_factory=list,
        description="SDD sections/line numbers this task must follow",
    )


@flock_type
class CodeChange(BaseModel):
    """Result of a code modification during implementation."""

    task_id: str = Field(description="Task ID this change belongs to")
    files_modified: list[str] = Field(description="Files that were created or modified")
    change_summary: str = Field(
        description="Summary of what was changed and why"
    )
    change_type: Literal[
        "create", "modify", "delete", "refactor"
    ] = Field(description="Type of change made")
    diff_summary: str | None = Field(
        default=None, description="Summary of the diff if modifying existing files"
    )
    tests_added: bool = Field(
        default=False, description="Whether tests were added for this change"
    )
    follows_spec: bool = Field(
        default=True, description="Whether this change follows the SDD specification"
    )


@flock_type
class PhaseComplete(BaseModel):
    """Signals completion of an implementation phase."""

    spec_id: str = Field(description="Specification being implemented")
    phase_number: int = Field(description="Completed phase number")
    phase_name: str = Field(description="Name of completed phase")
    tasks_completed: int = Field(description="Number of tasks completed")
    tasks_total: int = Field(description="Total number of tasks in phase")
    validation_passed: bool = Field(
        description="Whether all validations passed for this phase"
    )
    summary: str = Field(description="Summary of what was accomplished in this phase")
    next_phase: int | None = Field(
        default=None, description="Next phase number if more phases remain"
    )


# ==============================================================================
# 1.5 VALIDATION & CONTROL FLOW ARTIFACTS
# ==============================================================================


class ValidationType(str, Enum):
    """Types of validation that can be performed."""

    TESTS = "tests"
    BUILD = "build"
    LINT = "lint"
    TYPE_CHECK = "type_check"
    SECURITY = "security"
    SPEC_COMPLIANCE = "spec_compliance"


@flock_type
class ValidationRequest(BaseModel):
    """Request for validation of code, tests, or specifications."""

    validation_id: str = Field(description="Unique validation identifier")
    validation_type: ValidationType = Field(description="Type of validation to perform")
    target: str = Field(
        description="What to validate (file path, spec section, etc.)"
    )
    criteria: list[str] = Field(description="Specific criteria that must be met")
    spec_id: str | None = Field(
        default=None, description="Specification ID if validating against a spec"
    )
    blocking: bool = Field(
        default=True,
        description="Whether to block progress if validation fails",
    )


@flock_type
class ValidationResult(BaseModel):
    """Outcome of a validation request."""

    validation_id: str = Field(
        description="ID of the ValidationRequest this responds to"
    )
    validation_type: ValidationType = Field(description="Type of validation performed")
    status: Literal["passed", "failed", "warning"] = Field(
        description="Validation outcome"
    )
    issues: list[str] = Field(
        default_factory=list, description="Issues found during validation"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Suggestions for fixing issues"
    )
    details: str | None = Field(
        default=None, description="Detailed validation output"
    )


@flock_type
class ReviewRequest(BaseModel):
    """Request for review of code, documentation, or specifications."""

    review_id: str = Field(description="Unique review identifier")
    review_type: Literal["code", "specification", "documentation", "architecture"] = (
        Field(description="Type of review to perform")
    )
    target: str = Field(description="What to review (file path, spec section, etc.)")
    focus: str = Field(
        description="What to focus on during review (e.g., 'security', 'maintainability')"
    )
    spec_id: str | None = Field(
        default=None, description="Specification ID if reviewing against a spec"
    )


@flock_type
class ReviewResult(BaseModel):
    """Outcome of a review request."""

    review_id: str = Field(description="ID of the ReviewRequest this responds to")
    review_type: str = Field(description="Type of review performed")
    status: Literal["approved", "needs_revision", "rejected"] = Field(
        description="Review decision"
    )
    feedback: str = Field(description="Detailed feedback from the review")
    issues_found: list[str] = Field(
        default_factory=list, description="Issues that need to be addressed"
    )
    improvements: list[str] = Field(
        default_factory=list, description="Suggested improvements"
    )
    spec_deviations: list[str] = Field(
        default_factory=list,
        description="Deviations from specification if reviewing against spec",
    )


@flock_type
class CycleComplete(BaseModel):
    """Signals completion of a discovery-documentation-review cycle."""

    cycle_type: Literal["specify", "analyze", "refactor"] = Field(
        description="Type of cycle that completed"
    )
    cycle_number: int = Field(ge=1, description="Cycle number")
    summary: str = Field(description="Summary of what was accomplished in this cycle")
    artifacts_created: list[str] = Field(
        description="Artifacts created during this cycle (file paths)"
    )
    next_action: str = Field(
        description="Recommended next action or question for user"
    )


@flock_type
class ContinueSignal(BaseModel):
    """User confirmation to proceed to next phase or cycle."""

    signal_type: Literal["continue", "skip", "abort"] = Field(
        description="User's decision"
    )
    target: str = Field(
        description="What to continue to (e.g., 'next_phase', 'next_cycle', 'sdd')"
    )
    message: str | None = Field(
        default=None, description="Optional message or instructions from user"
    )


@flock_type
class BlockedState(BaseModel):
    """Signals that an agent is blocked and needs user assistance."""

    blocked_by: str = Field(description="What is causing the blockage")
    context: str = Field(description="Context about what was being attempted")
    reason: str = Field(description="Detailed explanation of why progress is blocked")
    options: list[str] = Field(
        description="Possible ways to resolve the blockage"
    )
    spec_id: str | None = Field(
        default=None, description="Specification ID if related to a spec"
    )


# ==============================================================================
# 1.6 DOCUMENTATION ARTIFACTS
# ==============================================================================


@flock_type
class DocumentationUpdate(BaseModel):
    """An update to any documentation file."""

    file_path: str = Field(description="Path to the documentation file")
    update_type: Literal["create", "append", "replace", "delete"] = Field(
        description="Type of update being made"
    )
    content: str = Field(description="Content to add or replace (markdown format)")
    section: str | None = Field(
        default=None, description="Specific section being updated if applicable"
    )
    reason: str = Field(description="Why this documentation update is needed")


@flock_type
class DocumentationComplete(BaseModel):
    """Signals that a documentation file is complete."""

    file_path: str = Field(description="Path to the completed documentation")
    document_type: Literal["prd", "sdd", "plan", "pattern", "interface", "domain"] = (
        Field(description="Type of document completed")
    )
    summary: str = Field(description="Summary of the completed documentation")
    word_count: int | None = Field(
        default=None, description="Approximate word count"
    )
    sections_complete: list[str] = Field(
        description="List of sections that are complete"
    )
