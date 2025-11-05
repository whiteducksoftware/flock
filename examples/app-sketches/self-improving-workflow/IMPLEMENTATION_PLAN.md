# Self-Improving Workflow Engine - Implementation Plan

**Complete, self-contained guide to building a Self-Improving Workflow Engine with Flock.**

## Table of Contents

1. [Understanding Self-Improving Workflows](#understanding-self-improving-workflows)
2. [Core Concepts](#core-concepts)
3. [Architecture Design](#architecture-design)
4. [Implementation Phases](#implementation-phases)
5. [Testing Strategy](#testing-strategy)
6. [Production Considerations](#production-considerations)
7. [Extension Points](#extension-points)

---

## Understanding Self-Improving Workflows

### The Problem with Traditional Workflows

Traditional AI agent workflows follow a **rigid pipeline**:

```
Input → Step 1 → Step 2 → Step 3 → Output
```

**Limitations:**
- ❌ Must predict every scenario upfront
- ❌ Breaks when reality diverges from plan
- ❌ Can't adapt to discoveries during execution
- ❌ Requires manual intervention for unexpected paths

### The Self-Improving Solution

Self-Improving Workflows use **semi-structured phases**:

```
┌─────────────────────────────────────────────┐
│  Phase 1: Analysis                          │
│  - Understand problems                      │
│  - Create plans                             │
│  - Can spawn work in ANY phase              │
└─────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────┐
│  Phase 2: Implementation                    │
│  - Build solutions                          │
│  - Can discover optimizations → Phase 1     │
│  - Can discover bugs → Phase 2 (fix)        │
└─────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────┐
│  Phase 3: Validation                        │
│  - Test solutions                           │
│  - Can discover issues → Phase 1 (investigate)│
│  - Can discover optimizations → Phase 1      │
└─────────────────────────────────────────────┘
```

**Key Insight:** Agents work in **phase types**, not predefined sequences. They can spawn work in **any phase** based on discoveries.

### Real-World Example

**Scenario:** Building authentication system

1. **Analysis Agent** reads requirements → spawns 3 implementation tasks
2. **Implementation Agents** build in parallel
3. **Validation Agent** tests one component, discovers:
   - ✅ Works correctly
   - 💡 **Optimization opportunity**: Caching pattern could speed up all API routes
4. **Validation Agent** spawns **Phase 1 analysis task**: "Investigate caching optimization"
5. **New Analysis Agent** investigates → spawns **Phase 2 implementation**: "Apply caching"
6. **New Implementation Agent** implements → spawns **Phase 3 validation**: "Test optimization"
7. **Workflow branched itself!** No one planned for this optimization.

---

## Core Concepts

### 1. Phases

**Phases** are work categories, not execution steps. They define:
- **What type of work** happens here
- **Who does the work** (specialized agents)
- **What success looks like** (done definitions)
- **What gets produced** (outputs)

**Example Phase Definitions:**

```python
PHASES = {
    "analysis": {
        "description": "Understand problems and create plans",
        "done_definitions": [
            "Problem understood",
            "Plan documented",
            "Next phase tasks created"
        ],
        "expected_outputs": ["Analysis document", "Implementation plan"]
    },
    "implementation": {
        "description": "Build solutions based on plans",
        "done_definitions": [
            "Code implemented",
            "Tests written",
            "Validation task created"
        ],
        "expected_outputs": ["Code files", "Test files"]
    },
    "validation": {
        "description": "Test and verify solutions",
        "done_definitions": [
            "Tests passing",
            "Validation complete",
            "Issues documented"
        ],
        "expected_outputs": ["Test results", "Validation report"]
    }
}
```

### 2. Work Discoveries

**Work Discoveries** are artifacts that represent work that needs doing. Agents publish them when they discover something.

```python
class WorkDiscovery(BaseModel):
    """Represents work that needs to be done."""
    description: str
    phase: str  # Which phase should handle this?
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    done_definition: str  # What constitutes completion?
    discovered_by: str  # Which agent discovered this?
    parent_work_id: Optional[str] = None  # Related to what work?
    blocking_work_ids: List[str] = []  # What must complete first?
```

### 3. Phase-Aware Agents

Agents subscribe to work from specific phases:

```python
# Analysis phase agent
analyzer = (
    flock.agent("analyzer")
    .description("Analyzes problems and creates implementation plans")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
    .publishes(AnalysisResult)
)

# Implementation phase agent
implementer = (
    flock.agent("implementer")
    .description("Implements solutions based on analysis")
    .consumes(AnalysisResult, where=lambda a: a.approved)
    .publishes(Implementation)
)
```

### 4. Cross-Phase Discovery

Agents can discover work in **any phase**, not just the next one:

```python
async def validation_handler(ctx: AgentContext) -> list[Artifact]:
    """Validation agent that can discover optimizations."""
    implementation = ctx.artifacts[0]
    
    # Validate
    validation_result = validate(implementation)
    
    # Discover optimization (spawns Phase 1 work!)
    if optimization_found:
        discovery = WorkDiscovery(
            description="Caching pattern could optimize all API routes",
            phase="analysis",  # ✨ Spawns Phase 1 work!
            priority="high",
            done_definition="Analysis complete with implementation plan",
            discovered_by=ctx.agent_name
        )
        return [validation_result, discovery]  # Fan-out!
    
    return [validation_result]
```

### 5. Emergent Cascades

Workflows build themselves through Flock's artifact subscription system:

```
1. Agent publishes WorkDiscovery(phase="analysis")
2. Analysis agent consumes it → publishes AnalysisResult
3. Implementation agent consumes AnalysisResult → publishes Implementation
4. Validation agent consumes Implementation → publishes ValidationResult + WorkDiscovery(phase="analysis")
5. New analysis agent consumes discovery → cycle continues
```

**No explicit workflow definition needed!** The structure emerges from artifact subscriptions.

---

## Architecture Design

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Flock Blackboard                       │
│  (Phase-Aware Artifacts: WorkDiscovery, Results, etc.)   │
└─────────────────────────────────────────────────────────┘
                          ↑
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
│ Phase 1      │  │ Phase 2      │  │ Phase 3      │
│ Agents       │  │ Agents       │  │ Agents       │
│ (Analysis)   │  │ (Implement)  │  │ (Validate)   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                 ┌────────▼────────┐
                 │ Phase Context    │
                 │ Provider         │
                 │ (Injects phase   │
                 │  instructions)   │
                 └──────────────────┘
```

### Artifact Types

#### 1. WorkDiscovery
**Purpose:** Represents work that needs doing

```python
class WorkDiscovery(BaseModel):
    """Work that needs to be done in a specific phase."""
    description: str
    phase: str
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    done_definition: str
    discovered_by: str
    parent_work_id: Optional[str] = None
    blocking_work_ids: List[str] = []
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
```

#### 2. Phase Results
**Purpose:** Outputs from each phase

```python
class AnalysisResult(BaseModel):
    """Result from analysis phase."""
    plan: str
    approved: bool
    next_phase_work: List[WorkDiscovery] = []  # Can spawn new work!
    metadata: Dict[str, Any] = {}

class Implementation(BaseModel):
    """Result from implementation phase."""
    code_files: List[str]
    test_files: List[str]
    summary: str
    discovered_issues: List[WorkDiscovery] = []  # Can spawn new work!
    metadata: Dict[str, Any] = {}

class ValidationResult(BaseModel):
    """Result from validation phase."""
    passed: bool
    issues: List[str]
    optimizations_discovered: List[WorkDiscovery] = []  # Can spawn new work!
    metadata: Dict[str, Any] = {}
```

### Phase Context Provider

**Purpose:** Injects phase instructions into agent context

```python
class PhaseContextProvider(BaseContextProvider):
    """Provides phase instructions to agents."""
    
    def __init__(self, phase_definitions: Dict[str, PhaseDefinition]):
        self.phase_definitions = phase_definitions
    
    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        artifacts, _ = await request.store.query_artifacts(limit=1000)
        
        # Determine agent's phase from their subscriptions
        agent_phase = self._get_agent_phase(request.agent_name)
        
        if agent_phase and agent_phase in self.phase_definitions:
            # Inject phase instructions
            phase_def = self.phase_definitions[agent_phase]
            instructions = PhaseInstructions(
                phase_name=agent_phase,
                description=phase_def.description,
                done_definitions=phase_def.done_definitions,
                additional_notes=phase_def.additional_notes
            )
            artifacts.insert(0, instructions)
        
        return artifacts
```

---

## Implementation Phases

### Phase 1: MVP - Core Phase System (Week 1-2)

**Goal:** Basic 3-phase workflow with work discovery

#### Step 1.1: Define Core Artifacts

**File:** `artifacts.py`

```python
from pydantic import BaseModel
from typing import Literal, Optional, List, Dict, Any

class WorkDiscovery(BaseModel):
    """Work that needs to be done."""
    description: str
    phase: Literal["analysis", "implementation", "validation"]
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    done_definition: str
    discovered_by: str
    parent_work_id: Optional[str] = None
    blocking_work_ids: List[str] = []
    tags: List[str] = []

class AnalysisResult(BaseModel):
    """Result from analysis phase."""
    plan: str
    approved: bool
    next_phase_work: List[WorkDiscovery] = []

class Implementation(BaseModel):
    """Result from implementation phase."""
    code_summary: str
    files_created: List[str]
    discovered_issues: List[WorkDiscovery] = []

class ValidationResult(BaseModel):
    """Result from validation phase."""
    passed: bool
    issues: List[str]
    optimizations_discovered: List[WorkDiscovery] = []
```

#### Step 1.2: Create Phase-Aware Agents

**File:** `01_basic_workflow.py`

```python
from flock import Flock
from artifacts import WorkDiscovery, AnalysisResult, Implementation, ValidationResult

flock = Flock("openai/gpt-4.1")

# Phase 1: Analysis
analyzer = (
    flock.agent("analyzer")
    .description("Analyzes work discoveries and creates implementation plans")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
    .publishes(AnalysisResult)
)

# Phase 2: Implementation
implementer = (
    flock.agent("implementer")
    .description("Implements solutions based on analysis")
    .consumes(AnalysisResult, where=lambda a: a.approved)
    .publishes(Implementation)
)

# Phase 3: Validation
validator = (
    flock.agent("validator")
    .description("Validates implementations and discovers optimizations")
    .consumes(Implementation)
    .publishes(ValidationResult, WorkDiscovery)  # Can discover new work!
)

# Start workflow
await flock.publish(WorkDiscovery(
    description="Build authentication system with OAuth and JWT",
    phase="analysis",
    done_definition="Analysis complete with implementation plan",
    discovered_by="user"
))

await flock.run_until_idle()
```

#### Step 1.3: Handle Fan-Out Publishing

Agents need to publish multiple artifacts (results + discoveries):

```python
async def validation_handler(ctx: AgentContext) -> list[Artifact]:
    """Handler that publishes both results and discoveries."""
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

**✅ MVP Complete:** Basic 3-phase workflow with cross-phase discovery

---

### Phase 2: Phase Instructions & Context (Week 3-4)

**Goal:** Agents receive phase-specific instructions

#### Step 2.1: Define Phase Configurations

**File:** `phase_config.py`

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
        expected_outputs=["Analysis document", "Implementation plan", "Work discoveries"]
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
        expected_outputs=["Code files", "Test files", "Validation work discovery"]
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
        expected_outputs=["Test results", "Validation report", "Work discoveries"]
    )
}
```

#### Step 2.2: Create Phase Context Provider

**File:** `phase_context_provider.py`

```python
from flock.core.context_provider import BaseContextProvider, ContextRequest
from flock.core.artifacts import Artifact
from phase_config import PHASES, PhaseDefinition

class PhaseInstructions(BaseModel):
    """Phase instructions artifact."""
    phase_name: str
    description: str
    done_definitions: List[str]
    additional_notes: str
    expected_outputs: List[str]

class PhaseContextProvider(BaseContextProvider):
    """Injects phase instructions into agent context."""
    
    def __init__(self, phase_definitions: Dict[str, PhaseDefinition]):
        self.phase_definitions = phase_definitions
    
    def _get_agent_phase(self, agent_name: str) -> Optional[str]:
        """Determine agent's phase from name or configuration."""
        # Simple heuristic: check agent name
        if "analyzer" in agent_name.lower() or "analysis" in agent_name.lower():
            return "analysis"
        elif "implementer" in agent_name.lower() or "implementation" in agent_name.lower():
            return "implementation"
        elif "validator" in agent_name.lower() or "validation" in agent_name.lower():
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
                phase_name=agent_def.name,
                description=phase_def.description,
                done_definitions=phase_def.done_definitions,
                additional_notes=phase_def.additional_notes,
                expected_outputs=phase_def.expected_outputs
            )
            # Inject at the beginning for priority
            artifacts.insert(0, instructions)
        
        return artifacts
```

#### Step 2.3: Integrate Context Provider

**File:** `02_phase_instructions.py`

```python
from flock import Flock
from phase_context_provider import PhaseContextProvider
from phase_config import PHASES

# Create flock with phase context provider
phase_provider = PhaseContextProvider(PHASES)
flock = Flock("openai/gpt-4.1", context_provider=phase_provider)

# Agents automatically receive phase instructions!
analyzer = (
    flock.agent("analyzer")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
    .publishes(AnalysisResult)
)
```

**✅ Phase 2 Complete:** Agents receive phase-specific instructions

---

### Phase 3: Advanced Features (Week 5-6)

**Goal:** Workflow orchestration, completion detection, semantic routing

#### Step 3.1: Phase Orchestrator Component

**File:** `phase_orchestrator.py`

```python
from flock.core.orchestrator import OrchestratorComponent
from artifacts import ValidationResult, WorkDiscovery

class PhaseOrchestratorComponent(OrchestratorComponent):
    """Monitors phase progress and manages workflow state."""
    
    def __init__(self, phase_definitions: Dict[str, PhaseDefinition]):
        self.phase_definitions = phase_definitions
        self.phase_stats = {
            phase: {"completed": 0, "active": 0, "pending": 0}
            for phase in phase_definitions
        }
    
    async def on_post_publish(self, ctx, artifacts):
        """Track phase progress after artifacts published."""
        for artifact in artifacts:
            if isinstance(artifact, ValidationResult):
                self.phase_stats["validation"]["completed"] += 1
                
                # Check if workflow should complete
                if self._all_phases_complete():
                    await self._signal_workflow_complete(ctx)
    
    def _all_phases_complete(self) -> bool:
        """Check if all phases have completed work."""
        # Implementation: check if all phases have completed tasks
        # and no pending work discoveries
        return all(
            stats["completed"] > 0 and stats["pending"] == 0
            for stats in self.phase_stats.values()
        )
    
    async def _signal_workflow_complete(self, ctx):
        """Signal that workflow is complete."""
        # Publish workflow completion artifact
        await ctx.orchestrator.publish(WorkflowComplete(
            phases_completed=list(self.phase_stats.keys()),
            total_work_items=sum(s["completed"] for s in self.phase_stats.values())
        ))
```

#### Step 3.2: Semantic Phase Routing

**File:** `semantic_phase_routing.py`

```python
# Use Flock's semantic subscriptions for intelligent routing

discovery_agent = (
    flock.agent("discoverer")
    .description("Discovers work and routes to appropriate phase")
    .consumes(Implementation, ValidationResult)
    .publishes(
        WorkDiscovery,
        semantic_match={
            "optimization opportunity": "analysis",
            "performance improvement": "analysis",
            "bug fix needed": "implementation",
            "security issue": "analysis",
            "test failure": "validation"
        }
    )
)
```

#### Step 3.3: Work Deduplication

**File:** `work_deduplication.py`

```python
from flock.core.artifacts import Artifact

class DeduplicationComponent(AgentComponent):
    """Prevents duplicate work discoveries."""
    
    async def on_pre_evaluate(self, ctx, artifacts):
        """Check for duplicate work before agent runs."""
        for artifact in artifacts:
            if isinstance(artifact, WorkDiscovery):
                # Check if similar work already exists
                existing = await self._find_similar_work(artifact)
                if existing:
                    # Mark as duplicate
                    artifact.duplicate_of = existing.id
                    raise SkipExecution("Duplicate work discovery")
    
    async def _find_similar_work(self, discovery: WorkDiscovery) -> Optional[WorkDiscovery]:
        """Find similar work discoveries using semantic search."""
        # Use Flock's artifact query with semantic matching
        similar = await ctx.store.query_artifacts(
            type_name="WorkDiscovery",
            semantic_match=discovery.description,
            threshold=0.8
        )
        return similar[0] if similar else None
```

**✅ Phase 3 Complete:** Advanced orchestration and routing

---

### Phase 4: Production Features (Week 7-8)

**Goal:** Monitoring, validation, error handling, persistence

#### Step 4.1: Workflow Monitoring

**File:** `workflow_monitor.py`

```python
class WorkflowMonitorComponent(OrchestratorComponent):
    """Monitors workflow health and progress."""
    
    async def on_post_publish(self, ctx, artifacts):
        """Track workflow metrics."""
        metrics = {
            "total_discoveries": await self._count_artifacts(WorkDiscovery),
            "completed_work": await self._count_artifacts(ValidationResult),
            "active_phases": await self._get_active_phases(),
            "blocked_work": await self._count_blocked_work()
        }
        
        # Publish metrics
        await ctx.orchestrator.publish(WorkflowMetrics(**metrics))
    
    async def _get_active_phases(self) -> List[str]:
        """Get phases with active work."""
        # Query for WorkDiscovery artifacts by phase
        phases = set()
        discoveries, _ = await ctx.store.query_artifacts(
            type_name="WorkDiscovery",
            limit=1000
        )
        for disc in discoveries:
            phases.add(disc.phase)
        return list(phases)
```

#### Step 4.2: Validation System

**File:** `workflow_validation.py`

```python
class WorkValidationComponent(AgentComponent):
    """Validates work before marking complete."""
    
    async def on_post_evaluate(self, ctx, outputs):
        """Validate agent outputs."""
        for output in outputs:
            if isinstance(output, AnalysisResult):
                if not output.plan:
                    raise ValidationError("Analysis result must include plan")
                if not output.next_phase_work:
                    raise ValidationError("Analysis must spawn Phase 2 work")
            
            elif isinstance(output, Implementation):
                if not output.files_created:
                    raise ValidationError("Implementation must create files")
```

#### Step 4.3: Error Recovery

**File:** `error_recovery.py`

```python
class ErrorRecoveryComponent(OrchestratorComponent):
    """Handles workflow errors and recovery."""
    
    async def on_error(self, ctx, error, artifacts):
        """Recover from errors."""
        # Create recovery work discovery
        recovery = WorkDiscovery(
            description=f"Recover from error: {str(error)}",
            phase="analysis",  # Start with analysis
            priority="critical",
            done_definition="Error analyzed and recovery plan created",
            discovered_by="error_recovery_component"
        )
        
        await ctx.orchestrator.publish(recovery)
```

**✅ Phase 4 Complete:** Production-ready features

---

## Testing Strategy

### Unit Tests

**Test artifact definitions:**
```python
def test_work_discovery_creation():
    discovery = WorkDiscovery(
        description="Test",
        phase="analysis",
        done_definition="Done"
    )
    assert discovery.phase == "analysis"
```

**Test phase subscriptions:**
```python
def test_phase_filtering():
    analyzer = flock.agent("analyzer").consumes(
        WorkDiscovery, 
        where=lambda w: w.phase == "analysis"
    )
    # Test that agent only consumes analysis work
```

### Integration Tests

**Test workflow cascade:**
```python
async def test_workflow_cascade():
    await flock.publish(WorkDiscovery(phase="analysis", ...))
    await flock.run_until_idle()
    
    # Verify: Analysis → Implementation → Validation
    results = await flock.store.query_artifacts(type_name="ValidationResult")
    assert len(results) > 0
```

**Test cross-phase discovery:**
```python
async def test_cross_phase_discovery():
    # Validation agent discovers optimization
    await flock.publish(Implementation(...))
    await flock.run_until_idle()
    
    # Verify: New analysis work discovered
    discoveries = await flock.store.query_artifacts(
        type_name="WorkDiscovery",
        where=lambda w: w.phase == "analysis"
    )
    assert len(discoveries) > 0
```

### End-to-End Tests

**Test complete workflow:**
```python
async def test_complete_workflow():
    # Start with one discovery
    await flock.publish(WorkDiscovery(
        description="Build auth system",
        phase="analysis"
    ))
    
    await flock.run_until_idle()
    
    # Verify workflow branched and completed
    # - Analysis created implementation work
    # - Implementation created validation work
    # - Validation discovered optimizations
    # - New analysis branches created
```

---

## Production Considerations

### 1. Scalability

- **Parallel Execution**: Flock's `publish() + run_until_idle()` enables parallel agent execution
- **Artifact Limits**: Use context providers to limit artifact history
- **Rate Limiting**: Implement rate limits for LLM calls

### 2. Monitoring

- **Workflow Metrics**: Track discoveries, completions, phase transitions
- **Agent Performance**: Monitor agent execution times
- **Error Rates**: Track validation failures and recovery actions

### 3. Persistence

- **Artifact Storage**: Use Flock's SQLiteBlackboardStore for persistence
- **Workflow State**: Save workflow state for recovery
- **History**: Maintain artifact history for debugging

### 4. Security

- **Visibility Controls**: Use Flock's visibility system for phase isolation
- **Input Validation**: Validate all work discoveries
- **Resource Limits**: Limit agent execution time and resource usage

---

## Extension Points

### Custom Phase Types

Add new phases beyond Analysis/Implementation/Validation:

```python
PHASES["deployment"] = PhaseDefinition(
    name="deployment",
    description="Deploy solutions to production",
    ...
)
```

### External Integrations

Integrate with external systems:

```python
class GitHubIntegrationComponent(AgentComponent):
    """Creates GitHub issues from work discoveries."""
    async def on_post_publish(self, ctx, artifacts):
        for artifact in artifacts:
            if isinstance(artifact, WorkDiscovery):
                await self._create_github_issue(artifact)
```

### Advanced Routing

Use ML for intelligent phase routing:

```python
class MLPhaseRouter:
    """Uses ML to route work to optimal phase."""
    def route(self, discovery: WorkDiscovery) -> str:
        # ML model predicts best phase
        return self.model.predict(discovery.description)
```

---

## Next Steps

1. **Start with MVP** (Phase 1): Get basic 3-phase workflow working
2. **Add Instructions** (Phase 2): Inject phase context into agents
3. **Enhance Features** (Phase 3): Add orchestration and semantic routing
4. **Production Ready** (Phase 4): Add monitoring, validation, error handling
5. **Customize**: Adapt for your specific use cases

See [CODE_SNIPPETS.md](CODE_SNIPPETS.md) for reusable code patterns.



