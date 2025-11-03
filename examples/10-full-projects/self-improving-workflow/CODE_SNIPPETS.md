# Self-Improving Workflow Engine - Code Snippets

**Reusable code patterns and examples for building Self-Improving Workflows.**

## Table of Contents

1. [Core Artifacts](#core-artifacts)
2. [Agent Definitions](#agent-definitions)
3. [Phase Configuration](#phase-configuration)
4. [Context Providers](#context-providers)
5. [Orchestrator Components](#orchestrator-components)
6. [Workflow Patterns](#workflow-patterns)
7. [Testing Patterns](#testing-patterns)

---

## Core Artifacts

### Basic Work Discovery

```python
from pydantic import BaseModel
from typing import Literal, Optional, List

class WorkDiscovery(BaseModel):
    """Work that needs to be done in a specific phase."""
    description: str
    phase: Literal["analysis", "implementation", "validation"]
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    done_definition: str
    discovered_by: str
    parent_work_id: Optional[str] = None
    blocking_work_ids: List[str] = []
    tags: List[str] = []
    metadata: dict = {}
```

### Phase Results

```python
class AnalysisResult(BaseModel):
    """Result from analysis phase."""
    plan: str
    approved: bool
    next_phase_work: List[WorkDiscovery] = []
    confidence: float = 0.0
    risks: List[str] = []
    metadata: dict = {}

class Implementation(BaseModel):
    """Result from implementation phase."""
    code_summary: str
    files_created: List[str]
    tests_written: List[str]
    discovered_issues: List[WorkDiscovery] = []
    metadata: dict = {}

class ValidationResult(BaseModel):
    """Result from validation phase."""
    passed: bool
    issues: List[str] = []
    optimizations_discovered: List[WorkDiscovery] = []
    performance_metrics: dict = {}
    metadata: dict = {}
```

### Phase Instructions

```python
class PhaseInstructions(BaseModel):
    """Phase instructions injected into agent context."""
    phase_name: str
    description: str
    done_definitions: List[str]
    additional_notes: str
    expected_outputs: List[str]
```

---

## Agent Definitions

### Basic Phase-Aware Agent

```python
from flock import Flock

flock = Flock("openai/gpt-4.1")

# Analysis agent
analyzer = (
    flock.agent("analyzer")
    .description("Analyzes work discoveries and creates implementation plans")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
    .publishes(AnalysisResult)
)
```

### Multi-Phase Agent

```python
# Agent that can work in multiple phases
flexible_agent = (
    flock.agent("flexible_worker")
    .description("Can handle analysis or implementation work")
    .consumes(
        WorkDiscovery,
        where=lambda w: w.phase in ["analysis", "implementation"]
    )
    .publishes(AnalysisResult, Implementation)
)
```

### Discovery Agent (Fan-Out)

```python
# Agent that publishes results AND discoveries
validator = (
    flock.agent("validator")
    .description("Validates and discovers optimizations")
    .consumes(Implementation)
    .publishes(ValidationResult, WorkDiscovery)  # Fan-out!
)

# Handler implementation
async def validation_handler(ctx: AgentContext) -> list[Artifact]:
    implementation = ctx.artifacts[0]
    
    # Validate
    result = ValidationResult(
        passed=True,
        issues=[],
        optimizations_discovered=[]
    )
    
    # Discover optimization
    if optimization_found:
        discovery = WorkDiscovery(
            description="Caching pattern could optimize API routes",
            phase="analysis",
            priority="high",
            done_definition="Analysis complete",
            discovered_by=ctx.agent_name
        )
        result.optimizations_discovered.append(discovery)
    
    # Return both result and discoveries
    outputs = [result]
    if result.optimizations_discovered:
        outputs.extend(result.optimizations_discovered)
    
    return outputs
```

### Semantic Phase Routing

```python
# Use semantic subscriptions for intelligent routing
discovery_router = (
    flock.agent("discovery_router")
    .description("Routes discoveries to appropriate phase")
    .consumes(Implementation, ValidationResult)
    .publishes(
        WorkDiscovery,
        semantic_match={
            "optimization": "analysis",
            "performance": "analysis",
            "bug": "implementation",
            "security": "analysis",
            "test": "validation"
        }
    )
)
```

---

## Phase Configuration

### Phase Definition

```python
from pydantic import BaseModel
from typing import List

class PhaseDefinition(BaseModel):
    """Definition of a workflow phase."""
    name: str
    description: str
    done_definitions: List[str]
    additional_notes: str
    expected_outputs: List[str]
    next_phases: List[str] = []  # Optional: suggested next phases

PHASES = {
    "analysis": PhaseDefinition(
        name="analysis",
        description="Understand problems and create implementation plans",
        done_definitions=[
            "Problem understood and documented",
            "Implementation plan created",
            "Phase 2 work discoveries created"
        ],
        additional_notes="""
        YOU ARE AN ANALYSIS AGENT
        
        Your job:
        1. Understand the work discovery thoroughly
        2. Break it down into implementable components
        3. Create detailed implementation plans
        4. Spawn Phase 2 work discoveries for each component
        
        When you discover optimizations or issues, spawn Phase 1 work discoveries
        to investigate them further.
        """,
        expected_outputs=["Analysis document", "Implementation plan", "Work discoveries"],
        next_phases=["implementation"]
    ),
    "implementation": PhaseDefinition(
        name="implementation",
        description="Build solutions based on analysis",
        done_definitions=[
            "Code implemented",
            "Tests written and passing",
            "Phase 3 validation work discovery created"
        ],
        additional_notes="""
        YOU ARE AN IMPLEMENTATION AGENT
        
        Your job:
        1. Read the analysis result carefully
        2. Implement the solution according to the plan
        3. Write comprehensive tests
        4. Spawn Phase 3 validation work discovery
        
        If you discover issues during implementation, spawn Phase 1 work discoveries
        to investigate them.
        """,
        expected_outputs=["Code files", "Test files", "Validation work discovery"],
        next_phases=["validation"]
    ),
    "validation": PhaseDefinition(
        name="validation",
        description="Test and verify solutions",
        done_definitions=[
            "All tests passing",
            "Validation report complete",
            "Issues documented if any"
        ],
        additional_notes="""
        YOU ARE A VALIDATION AGENT
        
        Your job:
        1. Run comprehensive tests
        2. Verify the implementation meets requirements
        3. Document any issues found
        4. Discover optimizations and improvements
        
        When you discover optimizations, spawn Phase 1 work discoveries to
        investigate them. When you find bugs, spawn Phase 2 work discoveries
        to fix them.
        """,
        expected_outputs=["Test results", "Validation report", "Work discoveries"],
        next_phases=[]  # End of workflow or spawn new analysis
    )
}
```

---

## Context Providers

### Basic Phase Context Provider

```python
from flock.core.context_provider import BaseContextProvider, ContextRequest
from flock.core.artifacts import Artifact

class PhaseContextProvider(BaseContextProvider):
    """Injects phase instructions into agent context."""
    
    def __init__(self, phase_definitions: dict[str, PhaseDefinition]):
        self.phase_definitions = phase_definitions
    
    def _get_agent_phase(self, agent_name: str) -> Optional[str]:
        """Determine agent's phase from name."""
        name_lower = agent_name.lower()
        if "analyzer" in name_lower or "analysis" in name_lower:
            return "analysis"
        elif "implementer" in name_lower or "implementation" in name_lower:
            return "implementation"
        elif "validator" in name_lower or "validation" in name_lower:
            return "validation"
        return None
    
    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        artifacts, _ = await request.store.query_artifacts(limit=1000)
        
        # Determine agent's phase
        agent_phase = self._get_agent_phase(request.agent_name)
        
        if agent_phase and agent_phase in self.phase_definitions:
            # Create phase instructions artifact
            phase_def = self.phase_definitions[agent_phase]
            instructions = PhaseInstructions(
                phase_name=phase_def.name,
                description=phase_def.description,
                done_definitions=phase_def.done_definitions,
                additional_notes=phase_def.additional_notes,
                expected_outputs=phase_def.expected_outputs
            )
            # Inject at beginning for priority
            artifacts.insert(0, instructions)
        
        return artifacts
```

### Advanced Phase Context Provider with Subscription Analysis

```python
class AdvancedPhaseContextProvider(BaseContextProvider):
    """Determines phase from agent subscriptions."""
    
    def __init__(self, phase_definitions: dict, orchestrator):
        self.phase_definitions = phase_definitions
        self.orchestrator = orchestrator
    
    def _get_agent_phase_from_subscriptions(self, agent_name: str) -> Optional[str]:
        """Determine phase by analyzing agent subscriptions."""
        agent = self.orchestrator.get_agent(agent_name)
        if not agent:
            return None
        
        # Analyze subscriptions to determine phase
        for subscription in agent.subscriptions:
            # Check if subscribes to WorkDiscovery with phase filter
            if hasattr(subscription, 'artifact_type') and \
               subscription.artifact_type == WorkDiscovery:
                # Extract phase from predicate if possible
                # This is a simplified example - actual implementation would
                # need to parse the predicate lambda
                pass
        
        # Fallback to name-based detection
        return self._get_agent_phase_from_name(agent_name)
    
    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        # Similar to basic provider but uses subscription analysis
        artifacts, _ = await request.store.query_artifacts(limit=1000)
        
        agent_phase = self._get_agent_phase_from_subscriptions(request.agent_name)
        
        if agent_phase:
            # Inject phase instructions
            ...
        
        return artifacts
```

---

## Orchestrator Components

### Phase Progress Monitor

```python
from flock.core.orchestrator import OrchestratorComponent
from flock.core.artifacts import Artifact

class PhaseProgressMonitor(OrchestratorComponent):
    """Monitors phase progress and completion."""
    
    def __init__(self, phase_definitions: dict):
        self.phase_definitions = phase_definitions
        self.phase_stats = {
            phase: {"discoveries": 0, "completed": 0, "active": 0}
            for phase in phase_definitions
        }
    
    async def on_post_publish(self, ctx, artifacts: list[Artifact]):
        """Track artifacts published."""
        for artifact in artifacts:
            if isinstance(artifact, WorkDiscovery):
                phase = artifact.phase
                self.phase_stats[phase]["discoveries"] += 1
                self.phase_stats[phase]["active"] += 1
            
            elif isinstance(artifact, ValidationResult):
                self.phase_stats["validation"]["completed"] += 1
                self.phase_stats["validation"]["active"] -= 1
        
        # Check for phase completion
        await self._check_phase_completion(ctx)
    
    async def _check_phase_completion(self, ctx):
        """Check if phases have completed."""
        for phase_name, stats in self.phase_stats.items():
            if stats["active"] == 0 and stats["completed"] > 0:
                # Phase completed
                await ctx.orchestrator.publish(PhaseComplete(
                    phase=phase_name,
                    discoveries=stats["discoveries"],
                    completed=stats["completed"]
                ))
```

### Workflow Completion Detector

```python
class WorkflowCompletionDetector(OrchestratorComponent):
    """Detects when workflow is complete."""
    
    def __init__(self):
        self.workflow_started = False
        self.pending_discoveries = set()
        self.completed_work = set()
    
    async def on_post_publish(self, ctx, artifacts: list[Artifact]):
        """Track workflow state."""
        for artifact in artifacts:
            if isinstance(artifact, WorkDiscovery):
                self.pending_discoveries.add(artifact.id)
                self.workflow_started = True
            
            elif isinstance(artifact, ValidationResult):
                # Mark related discovery as completed
                if hasattr(artifact, 'related_discovery_id'):
                    self.completed_work.add(artifact.related_discovery_id)
                    self.pending_discoveries.discard(artifact.related_discovery_id)
        
        # Check completion
        if self.workflow_started and len(self.pending_discoveries) == 0:
            await ctx.orchestrator.publish(WorkflowComplete(
                total_work=len(self.completed_work),
                phases_completed=list(self.phase_stats.keys())
            ))
```

### Error Recovery Component

```python
class ErrorRecoveryComponent(OrchestratorComponent):
    """Handles errors and spawns recovery work."""
    
    async def on_error(self, ctx, error: Exception, artifacts: list[Artifact]):
        """Recover from errors by spawning analysis work."""
        # Create recovery discovery
        recovery = WorkDiscovery(
            description=f"Recover from error: {str(error)}",
            phase="analysis",
            priority="critical",
            done_definition="Error analyzed and recovery plan created",
            discovered_by="error_recovery_component",
            metadata={"error_type": type(error).__name__, "error_message": str(error)}
        )
        
        await ctx.orchestrator.publish(recovery)
        
        # Log error
        logger.error(f"Error in workflow, spawned recovery work: {recovery.id}")
```

---

## Workflow Patterns

### Basic 3-Phase Workflow

```python
from flock import Flock
from artifacts import WorkDiscovery, AnalysisResult, Implementation, ValidationResult

flock = Flock("openai/gpt-4.1")

# Define agents
analyzer = (
    flock.agent("analyzer")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
    .publishes(AnalysisResult)
)

implementer = (
    flock.agent("implementer")
    .consumes(AnalysisResult, where=lambda a: a.approved)
    .publishes(Implementation)
)

validator = (
    flock.agent("validator")
    .consumes(Implementation)
    .publishes(ValidationResult, WorkDiscovery)
)

# Start workflow
await flock.publish(WorkDiscovery(
    description="Build authentication system",
    phase="analysis",
    done_definition="Analysis complete",
    discovered_by="user"
))

await flock.run_until_idle()
```

### Workflow with Phase Instructions

```python
from phase_context_provider import PhaseContextProvider
from phase_config import PHASES

# Create flock with phase context provider
phase_provider = PhaseContextProvider(PHASES)
flock = Flock("openai/gpt-4.1", context_provider=phase_provider)

# Agents automatically receive phase instructions
analyzer = (
    flock.agent("analyzer")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
    .publishes(AnalysisResult)
)
```

### Workflow with Monitoring

```python
from orchestrator_components import PhaseProgressMonitor

# Add monitoring component
monitor = PhaseProgressMonitor(PHASES)
flock.add_orchestrator_component(monitor)

# Workflow now tracks progress automatically
await flock.publish(WorkDiscovery(...))
await flock.run_until_idle()
```

### Workflow with Error Recovery

```python
from orchestrator_components import ErrorRecoveryComponent

# Add error recovery
recovery = ErrorRecoveryComponent()
flock.add_orchestrator_component(recovery)

# Errors automatically spawn recovery work
```

---

## Testing Patterns

### Test Basic Workflow

```python
import pytest
from flock import Flock
from artifacts import WorkDiscovery, ValidationResult

@pytest.mark.asyncio
async def test_basic_workflow():
    flock = Flock("openai/gpt-4.1")
    
    # Setup agents
    analyzer = (
        flock.agent("analyzer")
        .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
        .publishes(AnalysisResult)
    )
    
    # Start workflow
    await flock.publish(WorkDiscovery(
        description="Test work",
        phase="analysis",
        done_definition="Done",
        discovered_by="test"
    ))
    
    await flock.run_until_idle()
    
    # Verify: Analysis result published
    results = await flock.store.query_artifacts(type_name="AnalysisResult")
    assert len(results) > 0
```

### Test Cross-Phase Discovery

```python
@pytest.mark.asyncio
async def test_cross_phase_discovery():
    flock = Flock("openai/gpt-4.1")
    
    # Setup agents
    validator = (
        flock.agent("validator")
        .consumes(Implementation)
        .publishes(ValidationResult, WorkDiscovery)
    )
    
    analyzer = (
        flock.agent("analyzer")
        .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
        .publishes(AnalysisResult)
    )
    
    # Start with implementation
    await flock.publish(Implementation(...))
    await flock.run_until_idle()
    
    # Verify: New analysis work discovered
    discoveries = await flock.store.query_artifacts(
        type_name="WorkDiscovery",
        where=lambda w: w.phase == "analysis"
    )
    assert len(discoveries) > 0
```

### Test Phase Instructions Injection

```python
@pytest.mark.asyncio
async def test_phase_instructions():
    phase_provider = PhaseContextProvider(PHASES)
    flock = Flock("openai/gpt-4.1", context_provider=phase_provider)
    
    analyzer = (
        flock.agent("analyzer")
        .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
        .publishes(AnalysisResult)
    )
    
    # Trigger agent
    await flock.publish(WorkDiscovery(...))
    
    # Verify: Phase instructions in context
    # (Check through tracing or context inspection)
```

---

## Advanced Patterns

### Conditional Phase Transitions

```python
# Agent that conditionally spawns work in different phases
smart_agent = (
    flock.agent("smart_worker")
    .consumes(AnalysisResult)
    .publishes(Implementation, WorkDiscovery)
)

async def smart_handler(ctx: AgentContext) -> list[Artifact]:
    analysis = ctx.artifacts[0]
    
    if analysis.complexity > 10:
        # Complex work: spawn additional analysis
        return [
            Implementation(...),
            WorkDiscovery(phase="analysis", description="Deep dive needed")
        ]
    else:
        # Simple work: just implement
        return [Implementation(...)]
```

### Parallel Phase Execution

```python
# Multiple agents in same phase work in parallel
analyzer1 = (
    flock.agent("analyzer_1")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis" and "auth" in w.tags)
    .publishes(AnalysisResult)
)

analyzer2 = (
    flock.agent("analyzer_2")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis" and "api" in w.tags)
    .publishes(AnalysisResult)
)

# Publish multiple discoveries - agents run in parallel!
await flock.publish(WorkDiscovery(phase="analysis", tags=["auth"], ...))
await flock.publish(WorkDiscovery(phase="analysis", tags=["api"], ...))
await flock.run_until_idle()  # Both run in parallel
```

### Work Blocking

```python
# Work that blocks other work
blocking_discovery = WorkDiscovery(
    description="Critical infrastructure work",
    phase="implementation",
    blocking_work_ids=["dependent_work_id"]
)

# Dependent work waits
dependent_discovery = WorkDiscovery(
    description="Dependent work",
    phase="implementation",
    parent_work_id="blocking_work_id"
)

# Component that enforces blocking
class WorkBlockingComponent(AgentComponent):
    async def on_pre_evaluate(self, ctx, artifacts):
        for artifact in artifacts:
            if isinstance(artifact, WorkDiscovery):
                if artifact.blocking_work_ids:
                    # Check if blocking work is complete
                    blocking_complete = await self._check_blocking_work(
                        artifact.blocking_work_ids
                    )
                    if not blocking_complete:
                        raise SkipExecution("Work is blocked")
```

---

## Best Practices

### 1. Always Include Done Definitions

```python
# ✅ Good
WorkDiscovery(
    description="Build auth system",
    done_definition="Authentication working with OAuth and JWT, tests passing"
)

# ❌ Bad
WorkDiscovery(
    description="Build auth system",
    done_definition="Done"  # Too vague
)
```

### 2. Use Meaningful Phase Names

```python
# ✅ Good
phase="analysis"
phase="implementation"
phase="validation"

# ❌ Bad
phase="step1"
phase="step2"
phase="step3"
```

### 3. Leverage Fan-Out for Discoveries

```python
# ✅ Good: Publish discoveries with results
async def handler(ctx):
    result = ValidationResult(...)
    discovery = WorkDiscovery(...)
    return [result, discovery]  # Fan-out

# ❌ Bad: Sequential publishing
async def handler(ctx):
    result = ValidationResult(...)
    await ctx.publish(result)
    discovery = WorkDiscovery(...)
    await ctx.publish(discovery)  # Less efficient
```

### 4. Use Tags for Organization

```python
WorkDiscovery(
    description="...",
    phase="analysis",
    tags=["auth", "security", "critical"]
)
```

### 5. Track Parent Work

```python
# Maintain work relationships
discovery = WorkDiscovery(
    description="Optimize caching",
    phase="analysis",
    parent_work_id=original_work.id  # Track relationship
)
```

---

## Conclusion

These code snippets provide reusable patterns for building Self-Improving Workflows. Adapt them to your specific use cases and extend as needed.

For complete implementation guide, see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).



