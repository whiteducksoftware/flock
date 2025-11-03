# Self-Improving Workflow Engine - Architecture

**Detailed architecture and design decisions for the Self-Improving Workflow Engine.**

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Components](#core-components)
3. [Data Flow](#data-flow)
4. [Design Decisions](#design-decisions)
5. [Extension Architecture](#extension-architecture)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Flock Blackboard                         │
│  (Persistent, Typed Artifacts with Phase Metadata)          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │WorkDiscovery │  │Phase Results │  │Instructions  │      │
│  │(Phase-aware)│  │(Analysis,     │  │(Phase defs)  │      │
│  │              │  │ Implement,   │  │              │      │
│  │              │  │ Validate)   │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                          ↑
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
│ Phase 1      │  │ Phase 2      │  │ Phase 3      │
│ Agents       │  │ Agents       │  │ Agents       │
│              │  │              │  │              │
│ - Analyzer   │  │ - Implementer│  │ - Validator  │
│ - Researcher │  │ - Builder    │  │ - Tester     │
│ - Planner    │  │ - Fixer      │  │ - Reviewer   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                 ┌────────▼────────┐
                 │ Phase Context   │
                 │ Provider        │
                 │ (Injects phase  │
                 │  instructions)  │
                 └─────────────────┘
                          │
                 ┌────────▼────────┐
                 │ Orchestrator    │
                 │ Components      │
                 │ - Monitor       │
                 │ - Validator     │
                 │ - Recovery      │
                 └─────────────────┘
```

### Key Architectural Principles

1. **Blackboard-Centric**: All coordination happens through the blackboard
2. **Phase-Aware**: Artifacts carry phase metadata for routing
3. **Subscription-Based**: Agents subscribe to phase-specific work
4. **Emergent Structure**: Workflows build themselves through cascades
5. **Decentralized**: No central workflow controller needed

---

## Core Components

### 1. Artifact Layer

**Purpose:** Define typed artifacts that carry phase information

**Components:**
- `WorkDiscovery`: Work that needs doing
- `AnalysisResult`: Output from analysis phase
- `Implementation`: Output from implementation phase
- `ValidationResult`: Output from validation phase
- `PhaseInstructions`: Phase definitions injected into context

**Design Decision:** Artifacts carry phase metadata, not separate phase system

**Rationale:**
- ✅ Keeps everything on blackboard
- ✅ Enables semantic search and filtering
- ✅ Natural fit for Flock's architecture
- ✅ No separate phase management needed

### 2. Agent Layer

**Purpose:** Specialized agents for each phase

**Components:**
- **Phase 1 Agents**: Analysis, research, planning
- **Phase 2 Agents**: Implementation, building, fixing
- **Phase 3 Agents**: Validation, testing, review

**Design Decision:** Agents subscribe to phase-specific artifacts

**Rationale:**
- ✅ Leverages Flock's subscription system
- ✅ Enables parallel execution
- ✅ Automatic routing via predicates
- ✅ No manual agent assignment needed

### 3. Context Layer

**Purpose:** Provide phase instructions to agents

**Components:**
- `PhaseContextProvider`: Injects phase instructions
- `PhaseDefinition`: Phase configuration
- `PhaseInstructions`: Instructions artifact

**Design Decision:** Instructions as artifacts + context provider injection

**Rationale:**
- ✅ Instructions versioned and evolvable
- ✅ Context provider ensures agents always see instructions
- ✅ Instructions searchable on blackboard
- ✅ Can be updated dynamically

### 4. Orchestration Layer

**Purpose:** Monitor and coordinate workflow

**Components:**
- `PhaseOrchestratorComponent`: Tracks phase progress
- `WorkflowMonitorComponent`: Monitors workflow health
- `ErrorRecoveryComponent`: Handles errors

**Design Decision:** Orchestrator components, not separate service

**Rationale:**
- ✅ Leverages Flock's component system
- ✅ Lifecycle hooks for monitoring
- ✅ Consistent with Flock patterns
- ✅ Easy to extend

---

## Data Flow

### Standard Workflow Flow

```
1. User/Agent publishes WorkDiscovery(phase="analysis")
   ↓
2. Blackboard stores artifact
   ↓
3. Analysis agent (subscribed to analysis work) consumes it
   ↓
4. PhaseContextProvider injects analysis phase instructions
   ↓
5. Analysis agent executes, publishes AnalysisResult
   ↓
6. Implementation agent (subscribed to AnalysisResult) consumes it
   ↓
7. Implementation agent executes, publishes Implementation
   ↓
8. Validation agent (subscribed to Implementation) consumes it
   ↓
9. Validation agent executes, publishes ValidationResult
   ↓
10. Workflow continues or completes
```

### Cross-Phase Discovery Flow

```
1. Validation agent executes
   ↓
2. Discovers optimization opportunity
   ↓
3. Publishes ValidationResult + WorkDiscovery(phase="analysis")
   ↓
4. Fan-out: Both artifacts published
   ↓
5. Analysis agent consumes WorkDiscovery (new branch!)
   ↓
6. New analysis → implementation → validation cascade
   ↓
7. Workflow branched itself!
```

### Phase Instruction Injection Flow

```
1. Agent triggered (e.g., analysis agent)
   ↓
2. ContextProvider.get_artifacts() called
   ↓
3. Query blackboard for relevant artifacts
   ↓
4. Determine agent's phase from name/subscriptions
   ↓
5. Look up PhaseDefinition for that phase
   ↓
6. Create PhaseInstructions artifact
   ↓
7. Inject at beginning of artifact list (priority)
   ↓
8. Agent receives phase instructions in context
```

---

## Design Decisions

### Decision 1: Phases as Artifact Metadata vs Separate System

**Choice:** Phases as artifact metadata

**Alternatives Considered:**
- Separate phase management system (like Hephaestus)
- Phase as agent property
- Phase as separate artifact type

**Rationale:**
- ✅ Natural fit for blackboard architecture
- ✅ Enables semantic search by phase
- ✅ Filters work via subscription predicates
- ✅ No separate phase system to maintain
- ✅ Phases are discoverable on blackboard

**Trade-offs:**
- Requires phase metadata on all artifacts
- Phase filtering happens at subscription level

### Decision 2: Phase Instructions as Artifacts vs Context Injection

**Choice:** Both! Instructions as artifacts + Context Provider injection

**Alternatives Considered:**
- Instructions only in context provider
- Instructions only as artifacts
- Instructions in agent prompts

**Rationale:**
- ✅ Instructions as artifacts: versionable, searchable, evolvable
- ✅ Context provider: ensures agents always see instructions
- ✅ Best of both worlds: persistence + guaranteed visibility

**Trade-offs:**
- Slight complexity overhead
- Requires coordination between systems

### Decision 3: Explicit Phase Routing vs Semantic Matching

**Choice:** Both! Explicit for deterministic workflows, semantic for adaptive discovery

**Alternatives Considered:**
- Only explicit phase assignment
- Only semantic routing
- Manual phase selection by agents

**Rationale:**
- ✅ Explicit: predictable, deterministic, testable
- ✅ Semantic: adaptive, handles edge cases, discovers patterns
- ✅ Agents can use both based on context

**Trade-offs:**
- Requires semantic matching infrastructure
- May route incorrectly (mitigated by thresholds)

### Decision 4: Fan-Out Publishing vs Sequential Discovery

**Choice:** Fan-out publishing (agents publish multiple artifacts)

**Alternatives Considered:**
- Sequential: agent publishes result, then separately publishes discoveries
- Single artifact with nested discoveries
- Separate discovery agent

**Rationale:**
- ✅ Leverages Flock's fan-out capability
- ✅ Atomic: discoveries published with results
- ✅ Efficient: single agent execution, multiple outputs
- ✅ Natural: agent discovers during execution

**Trade-offs:**
- Requires fan-out handling in agents
- More complex output structure

### Decision 5: Decentralized vs Centralized Orchestration

**Choice:** Decentralized (blackboard-based coordination)

**Alternatives Considered:**
- Centralized workflow controller
- Phase manager service
- Task queue system

**Rationale:**
- ✅ Matches Flock's blackboard architecture
- ✅ Scalable: no single point of failure
- ✅ Flexible: agents coordinate through artifacts
- ✅ Simple: no separate orchestration service

**Trade-offs:**
- Harder to enforce global workflow constraints
- Requires careful artifact design for coordination

---

## Extension Architecture

### Adding New Phase Types

```python
# 1. Define phase configuration
PHASES["deployment"] = PhaseDefinition(
    name="deployment",
    description="Deploy solutions to production",
    done_definitions=["Deployed", "Monitoring active"],
    additional_notes="...",
    expected_outputs=["Deployment logs", "Monitoring config"]
)

# 2. Create phase artifacts
class DeploymentResult(BaseModel):
    deployed: bool
    environment: str
    monitoring_url: str

# 3. Create phase-aware agents
deployer = (
    flock.agent("deployer")
    .consumes(ValidationResult, where=lambda v: v.passed)
    .publishes(DeploymentResult)
)

# 4. Update context provider
phase_provider.phase_definitions["deployment"] = PHASES["deployment"]
```

### Custom Discovery Patterns

```python
class CustomDiscoveryAgent:
    """Agent that discovers work using custom logic."""
    
    async def discover_work(self, context: AgentContext) -> List[WorkDiscovery]:
        """Custom discovery logic."""
        discoveries = []
        
        # Analyze context
        if optimization_opportunity:
            discoveries.append(WorkDiscovery(
                phase="analysis",
                description="...",
                ...
            ))
        
        return discoveries
```

### Integration with External Systems

```python
class ExternalIntegrationComponent(OrchestratorComponent):
    """Integrates with external systems."""
    
    async def on_post_publish(self, ctx, artifacts):
        """Sync artifacts with external system."""
        for artifact in artifacts:
            if isinstance(artifact, WorkDiscovery):
                # Create ticket in external system
                await self.external_api.create_ticket(artifact)
            
            elif isinstance(artifact, ValidationResult):
                # Update external system
                await self.external_api.update_status(artifact)
```

---

## Performance Considerations

### Artifact Volume

**Challenge:** Large workflows generate many artifacts

**Solutions:**
- Context providers limit artifact history (limit=1000)
- Archive old artifacts to separate store
- Use visibility controls to reduce context size

### Parallel Execution

**Challenge:** Coordinate parallel agent execution

**Solutions:**
- Flock's `run_until_idle()` handles parallelization automatically
- Use `publish()` to queue work, then `run_until_idle()` to execute
- Independent agents run in parallel naturally

### LLM Rate Limits

**Challenge:** Many agents calling LLMs simultaneously

**Solutions:**
- Implement rate limiting in agent components
- Use agent queues for sequential execution if needed
- Batch similar work when possible

---

## Security Considerations

### Phase Isolation

**Requirement:** Agents should only see work from their phase

**Implementation:**
- Use visibility controls on artifacts
- Filter by phase in subscription predicates
- Context providers enforce phase boundaries

### Input Validation

**Requirement:** Validate all work discoveries

**Implementation:**
- Pydantic models validate structure
- Agent components validate content
- Orchestrator components validate workflow rules

### Resource Limits

**Requirement:** Prevent runaway workflows

**Implementation:**
- Limit agent execution time
- Limit artifact generation per agent
- Monitor workflow metrics for anomalies

---

## Monitoring and Observability

### Workflow Metrics

Track:
- Discoveries per phase
- Completion rates
- Cross-phase branching frequency
- Agent execution times
- Error rates

### Phase Health

Monitor:
- Active work per phase
- Blocked work
- Phase transition times
- Completion criteria satisfaction

### Agent Performance

Track:
- Execution time per agent
- Success rates
- Discovery rates
- Output quality

---

## Future Enhancements

### 1. Machine Learning Phase Routing

Use ML to predict optimal phase for discoveries:

```python
class MLPhaseRouter:
    def route(self, discovery: WorkDiscovery) -> str:
        return self.model.predict(discovery.description)
```

### 2. Workflow Templates

Predefined workflow templates for common patterns:

```python
SOFTWARE_DEVELOPMENT_TEMPLATE = {
    "phases": ["requirements", "design", "implement", "test", "deploy"],
    "transitions": {...},
    "validation_rules": {...}
}
```

### 3. Workflow Versioning

Version workflow definitions and track evolution:

```python
class WorkflowVersion(BaseModel):
    version: str
    phase_definitions: Dict[str, PhaseDefinition]
    created_at: datetime
```

### 4. Collaborative Workflows

Multiple users/teams collaborating on workflows:

```python
class CollaborativeWorkflow:
    owners: List[str]
    contributors: List[str]
    visibility: VisibilitySettings
```

---

## Conclusion

The Self-Improving Workflow Engine leverages Flock's blackboard architecture to create workflows that build themselves. Key architectural principles:

1. **Blackboard-Centric**: All coordination through artifacts
2. **Phase-Aware**: Metadata-driven phase routing
3. **Subscription-Based**: Agents subscribe to work
4. **Emergent**: Structure emerges from discoveries
5. **Extensible**: Easy to add phases and features

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for step-by-step implementation guide.



