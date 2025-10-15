"""
Specialist Agent Pool for Spec-Driven Development

This module defines all specialist agents that work together through the blackboard
to accomplish specification, analysis, implementation, and refactoring tasks.
"""

from flock.orchestrator import Flock

from artifacts import (
    AnalyzeRequest,
    CodeChange,
    DocumentationUpdate,
    ImplementationTask,
    PatternDiscovery,
    PLANSection,
    PRDSection,
    ResearchFindings,
    ResearchTask,
    ResearchType,
    ReviewRequest,
    ReviewResult,
    SDDSection,
    ValidationRequest,
    ValidationResult,
)
from mcp_config import format_mcp_config_for_agent


def create_specialist_agents(flock: Flock):
    """
    Create and register all specialist agents with the Flock orchestrator.

    Returns a dictionary of agent references for orchestrator use.
    """

    # ==============================================================================
    # 2.1 RESEARCH SPECIALISTS
    # ==============================================================================

    research_market_analyst = (
        flock.agent("research_market_analyst")
        .description(
            "Market research specialist who analyzes competitive landscape, "
            "market trends, user needs, and industry best practices. "
            "Provides data-driven insights for product decisions."
        )
        .consumes(
            ResearchTask,
            where=lambda task: task.research_type == ResearchType.MARKET,
        )
        .with_mcps(format_mcp_config_for_agent("research"))
        .publishes(ResearchFindings)
    )

    research_technical_analyst = (
        flock.agent("research_technical_analyst")
        .description(
            "Technical research specialist who investigates technologies, frameworks, "
            "architectural patterns, and technical feasibility. "
            "Evaluates trade-offs and provides implementation recommendations."
        )
        .consumes(
            ResearchTask,
            where=lambda task: task.research_type == ResearchType.TECHNICAL,
        )
        .with_mcps(format_mcp_config_for_agent("research"))
        .publishes(ResearchFindings)
    )

    research_security_analyst = (
        flock.agent("research_security_analyst")
        .description(
            "Security research specialist who analyzes security implications, "
            "vulnerabilities, compliance requirements, and best practices. "
            "Provides security recommendations and threat assessments."
        )
        .consumes(
            ResearchTask,
            where=lambda task: task.research_type == ResearchType.SECURITY,
        )
        .with_mcps(format_mcp_config_for_agent("research"))
        .publishes(ResearchFindings)
    )

    research_user_experience = (
        flock.agent("research_user_experience")
        .description(
            "User experience research specialist who studies user behavior, "
            "usability patterns, accessibility requirements, and design best practices. "
            "Provides user-centric design recommendations."
        )
        .consumes(
            ResearchTask,
            where=lambda task: task.research_type == ResearchType.UX,
        )
        .with_mcps(format_mcp_config_for_agent("research"))
        .publishes(ResearchFindings)
    )

    # ==============================================================================
    # 2.2 DOCUMENTATION SPECIALISTS
    # ==============================================================================

    documenter_requirements = (
        flock.agent("documenter_requirements")
        .description(
            "Requirements documentation specialist who synthesizes research findings "
            "into clear, actionable Product Requirements Documents (PRD). "
            "Focuses on WHAT to build and WHY, avoiding implementation details."
        )
        .consumes(ResearchFindings)
        .with_mcps(format_mcp_config_for_agent("documenter"))
        .publishes(PRDSection)
    )

    documenter_design = (
        flock.agent("documenter_design")
        .description(
            "Design documentation specialist who creates Solution Design Documents (SDD) "
            "based on requirements and technical research. "
            "Focuses on HOW to build it with architecture, data models, and APIs."
        )
        .consumes(PRDSection, ResearchFindings)
        .with_mcps(format_mcp_config_for_agent("documenter"))
        .publishes(SDDSection)
    )

    documenter_planning = (
        flock.agent("documenter_planning")
        .description(
            "Implementation planning specialist who breaks down technical designs "
            "into actionable implementation plans with tasks, phases, and dependencies. "
            "Creates executable roadmaps from specifications."
        )
        .consumes(SDDSection, PRDSection)
        .with_mcps(format_mcp_config_for_agent("documenter"))
        .publishes(PLANSection)
    )

    documenter_patterns = (
        flock.agent("documenter_patterns")
        .description(
            "Pattern documentation specialist who captures discovered patterns "
            "as reusable documentation for future reference. "
            "Creates clear, searchable pattern guides."
        )
        .consumes(PatternDiscovery)
        .with_mcps(format_mcp_config_for_agent("documenter"))
        .publishes(DocumentationUpdate)
    )

    # ==============================================================================
    # 2.3 IMPLEMENTATION SPECIALISTS
    # ==============================================================================

    implementer_backend = (
        flock.agent("implementer_backend")
        .description(
            "Backend implementation specialist who creates server-side code, "
            "APIs, business logic, and data processing. "
            "Follows SDD specifications and writes production-quality code."
        )
        .consumes(
            ImplementationTask,
            where=lambda task: task.activity_area == "backend",
        )
        .with_mcps(format_mcp_config_for_agent("implementer"))
        .publishes(CodeChange)
    )

    implementer_frontend = (
        flock.agent("implementer_frontend")
        .description(
            "Frontend implementation specialist who creates user interfaces, "
            "client-side logic, and interactive components. "
            "Builds accessible, responsive UIs following design specifications."
        )
        .consumes(
            ImplementationTask,
            where=lambda task: task.activity_area == "frontend",
        )
        .with_mcps(format_mcp_config_for_agent("implementer"))
        .publishes(CodeChange)
    )

    implementer_database = (
        flock.agent("implementer_database")
        .description(
            "Database implementation specialist who creates schemas, migrations, "
            "queries, and data access layers. "
            "Ensures data integrity and optimal performance."
        )
        .consumes(
            ImplementationTask,
            where=lambda task: task.activity_area == "database",
        )
        .with_mcps(format_mcp_config_for_agent("implementer"))
        .publishes(CodeChange)
    )

    implementer_infrastructure = (
        flock.agent("implementer_infrastructure")
        .description(
            "Infrastructure implementation specialist who creates deployment configs, "
            "CI/CD pipelines, containerization, and infrastructure as code. "
            "Builds reliable, scalable infrastructure."
        )
        .consumes(
            ImplementationTask,
            where=lambda task: task.activity_area == "infrastructure",
        )
        .with_mcps(format_mcp_config_for_agent("implementer"))
        .publishes(CodeChange)
    )

    # ==============================================================================
    # 2.4 REVIEW & VALIDATION SPECIALISTS
    # ==============================================================================

    reviewer_code = (
        flock.agent("reviewer_code")
        .description(
            "Code review specialist who examines code changes for quality, "
            "security, maintainability, and specification compliance. "
            "Provides constructive feedback and catches issues early."
        )
        .consumes(CodeChange)
        .with_mcps(format_mcp_config_for_agent("reviewer"))
        .publishes(ReviewResult)
    )

    reviewer_specification = (
        flock.agent("reviewer_specification")
        .description(
            "Specification review specialist who validates PRD, SDD, and PLAN documents "
            "for completeness, clarity, feasibility, and consistency. "
            "Ensures specifications are ready for implementation."
        )
        .consumes(PRDSection, SDDSection, PLANSection)
        .with_mcps(format_mcp_config_for_agent("reviewer"))
        .publishes(ReviewResult)
    )

    validator_tests = (
        flock.agent("validator_tests")
        .description(
            "Test validation specialist who runs test suites, analyzes coverage, "
            "and verifies that all tests pass. "
            "Ensures code changes maintain quality and don't introduce regressions."
        )
        .consumes(
            ValidationRequest,
            where=lambda req: req.validation_type.value == "tests",
        )
        .with_mcps(format_mcp_config_for_agent("validator"))
        .publishes(ValidationResult)
    )

    validator_compilation = (
        flock.agent("validator_compilation")
        .description(
            "Build validation specialist who runs compilation, type checking, "
            "and linting to verify code quality. "
            "Catches syntax errors and type issues before deployment."
        )
        .consumes(
            ValidationRequest,
            where=lambda req: req.validation_type.value == "build",
        )
        .with_mcps(format_mcp_config_for_agent("validator"))
        .publishes(ValidationResult)
    )

    # ==============================================================================
    # 2.5 ANALYSIS SPECIALISTS
    # ==============================================================================

    analyzer_business_rules = (
        flock.agent("analyzer_business_rules")
        .description(
            "Business rules analysis specialist who discovers domain logic, "
            "business workflows, validation rules, and business patterns. "
            "Documents how the business operates through code."
        )
        .consumes(
            AnalyzeRequest,
            where=lambda req: req.analysis_area == "business",
        )
        .with_mcps(format_mcp_config_for_agent("analyzer"))
        .publishes(PatternDiscovery)
    )

    analyzer_architecture = (
        flock.agent("analyzer_architecture")
        .description(
            "Architecture analysis specialist who identifies architectural patterns, "
            "design decisions, component relationships, and system structure. "
            "Maps out how the system is organized."
        )
        .consumes(
            AnalyzeRequest,
            where=lambda req: req.analysis_area == "technical",
        )
        .with_mcps(format_mcp_config_for_agent("analyzer"))
        .publishes(PatternDiscovery)
    )

    analyzer_security = (
        flock.agent("analyzer_security")
        .description(
            "Security analysis specialist who discovers security patterns, "
            "authentication mechanisms, authorization logic, and vulnerabilities. "
            "Identifies how security is implemented and potential risks."
        )
        .consumes(
            AnalyzeRequest,
            where=lambda req: req.analysis_area == "security",
        )
        .with_mcps(format_mcp_config_for_agent("analyzer"))
        .publishes(PatternDiscovery)
    )

    # Return agent references for orchestrator use
    return {
        # Research specialists
        "research_market_analyst": research_market_analyst,
        "research_technical_analyst": research_technical_analyst,
        "research_security_analyst": research_security_analyst,
        "research_user_experience": research_user_experience,
        # Documentation specialists
        "documenter_requirements": documenter_requirements,
        "documenter_design": documenter_design,
        "documenter_planning": documenter_planning,
        "documenter_patterns": documenter_patterns,
        # Implementation specialists
        "implementer_backend": implementer_backend,
        "implementer_frontend": implementer_frontend,
        "implementer_database": implementer_database,
        "implementer_infrastructure": implementer_infrastructure,
        # Review & validation specialists
        "reviewer_code": reviewer_code,
        "reviewer_specification": reviewer_specification,
        "validator_tests": validator_tests,
        "validator_compilation": validator_compilation,
        # Analysis specialists
        "analyzer_business_rules": analyzer_business_rules,
        "analyzer_architecture": analyzer_architecture,
        "analyzer_security": analyzer_security,
    }
