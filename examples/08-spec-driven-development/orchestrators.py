"""
Orchestrator Agents for Spec-Driven Development

These are the master coordinators that manage workflow execution by
publishing work items, collecting results, and coordinating specialist agents.
"""

from datetime import timedelta

from flock.orchestrator import Flock
from flock.subscription import BatchSpec, JoinSpec

from artifacts import (
    AnalyzeRequest,
    BlockedState,
    CodeChange,
    ContinueSignal,
    CycleComplete,
    DocumentationUpdate,
    ImplementationTask,
    ImplementRequest,
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
)
from mcp_config import format_mcp_config_for_agent


def create_orchestrator_agents(flock: Flock):
    """
    Create and register orchestrator agents with the Flock.

    Returns a dictionary of orchestrator agent references.
    """

    # ==============================================================================
    # 3.1 SPECIFY ORCHESTRATOR
    # ==============================================================================

    specify_orchestrator = (
        flock.agent("specify_orchestrator")
        .description(
            """
            Master specification orchestrator that coordinates the creation of
            complete PRD/SDD/PLAN documents through iterative research cycles.

            Workflow:
            1. Initialize: Create spec directory and metadata
            2. PRD Phase: Research → Document → Review cycles
            3. SDD Phase: Technical research → Design → Review cycles
            4. PLAN Phase: Planning research → Tasks → Review cycles
            5. Finalize: Generate SpecificationComplete with confidence score

            Uses JoinSpec to wait for all research findings before documenting.
            Waits for ContinueSignal between phases for user validation.
            """
        )
        .consumes(SpecifyRequest)
        .with_mcps(format_mcp_config_for_agent("orchestrator"))
        .publishes(
            SpecificationMetadata,
            ResearchTask,
            PRDSection,
            SDDSection,
            PLANSection,
            SpecificationComplete,
            CycleComplete,
        )
    )

    # Helper agent: Research Aggregator
    # This agent waits for ALL research findings before triggering documentation
    research_aggregator = (
        flock.agent("research_aggregator")
        .description(
            """
            Aggregates multiple ResearchFindings and signals when complete.
            Uses JoinSpec to wait for all parallel research tasks.
            """
        )
        .consumes(
            ResearchFindings,
            join=JoinSpec(
                by=lambda finding: finding.task_id.split("-")[
                    1
                ],  # Group by research batch
                within=timedelta(minutes=10),  # Wait up to 10 minutes
            ),
        )
        .publishes(CycleComplete)
    )

    # ==============================================================================
    # 3.2 IMPLEMENT ORCHESTRATOR
    # ==============================================================================

    implement_orchestrator = (
        flock.agent("implement_orchestrator")
        .description(
            """
            Implementation orchestrator that executes PLAN.md phase-by-phase.

            Workflow:
            1. Load PLAN.md and parse phases
            2. For each phase:
               - Publish PhaseStart
               - Publish ImplementationTasks (parallel with BatchSpec)
               - Collect CodeChanges
               - Request validation
               - Wait for ValidationResults
               - Publish PhaseComplete
            3. Wait for ContinueSignal before starting next phase

            Uses BatchSpec to execute parallel tasks within a phase.
            """
        )
        .consumes(ImplementRequest)
        .with_mcps(format_mcp_config_for_agent("orchestrator"))
        .publishes(
            PhaseStart,
            ImplementationTask,
            ValidationRequest,
            PhaseComplete,
            BlockedState,
        )
    )

    # Helper agent: Phase Validator
    # Aggregates all CodeChanges and ValidationResults for a phase
    phase_validator = (
        flock.agent("phase_validator")
        .description(
            """
            Validates that all tasks in a phase completed successfully.
            Waits for all CodeChanges and ValidationResults before signaling complete.
            """
        )
        .consumes(
            CodeChange,
            ValidationResult,
            batch=BatchSpec(
                size=10,  # Batch up to 10 changes
                timeout=timedelta(minutes=5),  # Or wait 5 minutes
            ),
        )
        .publishes(PhaseComplete)
    )

    # ==============================================================================
    # 3.3 ANALYZE ORCHESTRATOR
    # ==============================================================================

    analyze_orchestrator = (
        flock.agent("analyze_orchestrator")
        .description(
            """
            Analysis orchestrator that discovers and documents patterns/rules.

            Workflow:
            1. Scan target path for code to analyze
            2. Publish ResearchTasks for different analysis specialists
            3. Collect PatternDiscovery artifacts
            4. Publish DocumentationUpdate for each pattern
            5. Publish CycleComplete with summary
            6. Wait for ContinueSignal to start next cycle

            Runs iteratively until user stops or no more patterns found.
            """
        )
        .consumes(AnalyzeRequest)
        .with_mcps(format_mcp_config_for_agent("orchestrator"))
        .publishes(
            ResearchTask,
            DocumentationUpdate,
            CycleComplete,
        )
    )

    # Helper agent: Pattern Documenter
    # Aggregates patterns and creates documentation
    pattern_documenter = (
        flock.agent("pattern_documenter")
        .description(
            """
            Collects discovered patterns and creates structured documentation.
            Groups patterns by type (business, technical, architectural, security).
            """
        )
        .consumes(
            PatternDiscovery,
            batch=BatchSpec(
                size=5,  # Batch 5 patterns
                timeout=timedelta(minutes=3),
            ),
        )
        .with_mcps(format_mcp_config_for_agent("documenter"))
        .publishes(DocumentationUpdate)
    )

    # ==============================================================================
    # 3.4 REFACTOR ORCHESTRATOR
    # ==============================================================================

    refactor_orchestrator = (
        flock.agent("refactor_orchestrator")
        .description(
            """
            Refactoring orchestrator that improves code quality incrementally.

            Workflow:
            1. Analyze code for refactoring opportunities (code smells, duplication)
            2. Prioritize refactorings by safety and impact
            3. For each refactoring:
               - Apply code change
               - Run validation (tests must pass)
               - Request review
               - If approved: continue, if rejected: revert
            4. Publish CycleComplete after each refactoring

            Strict constraint: ALL tests must pass after every change.
            If tests fail, immediately revert and report BlockedState.
            """
        )
        .consumes(RefactorRequest)
        .with_mcps(format_mcp_config_for_agent("orchestrator"))
        .publishes(
            ImplementationTask,  # Reuse implementation tasks for refactoring
            ValidationRequest,
            ReviewRequest,
            CycleComplete,
            BlockedState,
        )
    )

    # Helper agent: Refactor Validator
    # Ensures behavior preservation after each refactoring
    refactor_validator = (
        flock.agent("refactor_validator")
        .description(
            """
            Validates refactoring safety by running full test suite.
            CRITICAL: Must verify that external behavior is preserved.
            If any test fails, immediately signals BlockedState.
            """
        )
        .consumes(CodeChange, ValidationResult)
        .publishes(ReviewRequest, BlockedState)
    )

    return {
        # Main orchestrators
        "specify_orchestrator": specify_orchestrator,
        "implement_orchestrator": implement_orchestrator,
        "analyze_orchestrator": analyze_orchestrator,
        "refactor_orchestrator": refactor_orchestrator,
        # Helper coordinators
        "research_aggregator": research_aggregator,
        "phase_validator": phase_validator,
        "pattern_documenter": pattern_documenter,
        "refactor_validator": refactor_validator,
    }


# ==============================================================================
# ORCHESTRATOR LOGIC (Custom implementations for complex workflows)
# ==============================================================================

# NOTE: The orchestrators above are declarative agent definitions.
# For complex logic like parsing PLAN.md, managing cycles, and file I/O,
# we'll need custom orchestrator classes that wrap these agents.
# This will be implemented in Phase 4 with MCP tool integration.


class SpecifyOrchestrator:
    """
    Custom orchestrator that implements the specify workflow logic.

    This wraps the declarative specify_orchestrator agent with imperative
    logic for:
    - Creating spec directories via spec.go helper
    - Managing PRD/SDD/PLAN cycles
    - Coordinating research batches
    - Handling user confirmations
    """

    def __init__(self, flock: Flock, agent):
        self.flock = flock
        self.agent = agent

    async def execute(self, request: SpecifyRequest):
        """Execute the specification workflow."""
        # Phase 1: Initialize specification
        spec_metadata = await self._initialize_spec(request)

        # Phase 2: PRD cycles
        await self._prd_cycles(spec_metadata)

        # Phase 3: SDD cycles
        await self._sdd_cycles(spec_metadata)

        # Phase 4: PLAN cycles
        await self._plan_cycles(spec_metadata)

        # Phase 5: Finalize
        completion = await self._finalize_spec(spec_metadata)

        return completion

    async def _initialize_spec(self, request: SpecifyRequest):
        """Create spec directory and metadata."""
        # TODO: Call spec.go helper to create directory
        # TODO: Generate spec ID
        # TODO: Create PRD.md from template
        pass

    async def _prd_cycles(self, spec_metadata: SpecificationMetadata):
        """Execute PRD research and documentation cycles."""
        # TODO: Implement cycle pattern:
        # 1. Publish ResearchTasks
        # 2. Wait for ResearchFindings (JoinSpec)
        # 3. Trigger documenter_requirements
        # 4. Wait for PRDSection
        # 5. Publish ReviewRequest
        # 6. Wait for ReviewResult
        # 7. If approved: CycleComplete, else: revise
        # 8. Wait for ContinueSignal before next cycle
        pass

    async def _sdd_cycles(self, spec_metadata: SpecificationMetadata):
        """Execute SDD research and documentation cycles."""
        pass

    async def _plan_cycles(self, spec_metadata: SpecificationMetadata):
        """Execute PLAN research and documentation cycles."""
        pass

    async def _finalize_spec(self, spec_metadata: SpecificationMetadata):
        """Generate final specification complete artifact."""
        pass


class ImplementOrchestrator:
    """
    Custom orchestrator that implements the implement workflow logic.

    Wraps implement_orchestrator with imperative logic for:
    - Loading and parsing PLAN.md
    - Managing phase-by-phase execution
    - Batching parallel tasks
    - Validation checkpoints
    """

    def __init__(self, flock: Flock, agent):
        self.flock = flock
        self.agent = agent

    async def execute(self, request: ImplementRequest):
        """Execute the implementation workflow."""
        # TODO: Load PLAN.md
        # TODO: Parse phases and tasks
        # TODO: For each phase:
        #   - Publish PhaseStart
        #   - Publish ImplementationTasks (with can_run_parallel grouping)
        #   - Wait for CodeChanges
        #   - Publish ValidationRequest
        #   - Wait for ValidationResult
        #   - If pass: PhaseComplete, else: BlockedState
        #   - Wait for ContinueSignal before next phase
        pass


class AnalyzeOrchestrator:
    """
    Custom orchestrator that implements the analyze workflow logic.

    Wraps analyze_orchestrator with imperative logic for:
    - Scanning target paths
    - Iterative discovery cycles
    - Pattern documentation
    """

    def __init__(self, flock: Flock, agent):
        self.flock = flock
        self.agent = agent

    async def execute(self, request: AnalyzeRequest):
        """Execute the analysis workflow."""
        # TODO: Scan target_path for files
        # TODO: Publish AnalyzeRequest-derived research tasks
        # TODO: Collect PatternDiscovery
        # TODO: Create documentation in docs/patterns/, docs/domain/
        # TODO: CycleComplete with summary
        # TODO: Wait for ContinueSignal for next cycle
        pass


class RefactorOrchestrator:
    """
    Custom orchestrator that implements the refactor workflow logic.

    Wraps refactor_orchestrator with imperative logic for:
    - Code smell detection
    - Incremental refactoring
    - Test validation checkpoints
    """

    def __init__(self, flock: Flock, agent):
        self.flock = flock
        self.agent = agent

    async def execute(self, request: RefactorRequest):
        """Execute the refactoring workflow."""
        # TODO: Analyze code for refactoring opportunities
        # TODO: Prioritize refactorings
        # TODO: For each refactoring:
        #   - Apply change
        #   - Validate (tests must pass)
        #   - If fail: revert and BlockedState
        #   - Request review
        #   - CycleComplete
        pass
