# Spec-Driven Development: Agent Architecture

**A deep dive into the 27-agent system that powers spec-driven development with Flock**

---

## 🎯 Overview

The spec-driven development system consists of **27 agents** collaborating through **26 artifact types** on a **blackboard architecture**. This document explains how agents are organized, how they communicate, and how workflows emerge from their interactions.

---

## 📊 Agent Taxonomy

### By Category (19 Specialists + 8 Orchestrators)

```
Specialists (19 agents):
├── Research (4)
│   ├── research_market_analyst
│   ├── research_technical_analyst
│   ├── research_security_analyst
│   └── research_user_experience
├── Documentation (4)
│   ├── documenter_requirements
│   ├── documenter_design
│   ├── documenter_planning
│   └── documenter_patterns
├── Implementation (4)
│   ├── implementer_backend
│   ├── implementer_frontend
│   ├── implementer_database
│   └── implementer_infrastructure
├── Review & Validation (4)
│   ├── reviewer_code
│   ├── reviewer_specification
│   ├── validator_tests
│   └── validator_compilation
└── Analysis (3)
    ├── analyzer_business_rules
    ├── analyzer_architecture
    └── analyzer_security

Orchestrators (8 agents):
├── Main (4)
│   ├── specify_orchestrator
│   ├── implement_orchestrator
│   ├── analyze_orchestrator
│   └── refactor_orchestrator
└── Helpers (4)
    ├── research_aggregator
    ├── phase_validator
    ├── pattern_documenter
    └── refactor_validator
```

---

## 🔄 Artifact Flow Diagrams

### 1. Specify Workflow

```
SpecifyRequest
    ↓
[specify_orchestrator]
    ↓
ResearchTask (4x in parallel) ──────┐
    ↓                                │
[research_market_analyst]            │
[research_technical_analyst]         │ JoinSpec
[research_security_analyst]          │ (wait for all)
[research_user_experience]           │
    ↓                                │
ResearchFindings (4x) ───────────────┘
    ↓
[research_aggregator]
    ↓
CycleComplete
    ↓
[documenter_requirements]
    ↓
PRDSection
    ↓
[documenter_design]
    ↓
SDDSection
    ↓
[documenter_planning]
    ↓
PLANSection
    ↓
SpecificationComplete
```

### 2. Implement Workflow

```
ImplementRequest
    ↓
[implement_orchestrator]
    ↓
PhaseStart
    ↓
ImplementationTask (Nx) ──────────────┐
    ↓                                  │
[implementer_backend]                  │ BatchSpec
[implementer_frontend]                 │ (collect all)
[implementer_database]                 │
[implementer_infrastructure]           │
    ↓                                  │
CodeChange (Nx) ──────────────────────┘
    ↓
ValidationRequest
    ↓
[validator_tests]
[validator_compilation]
    ↓
ValidationResult
    ↓
[phase_validator]
    ↓
PhaseComplete
```

### 3. Analyze Workflow

```
AnalyzeRequest (3x) ──────────────────┐
    ↓                                  │
[analyzer_business_rules]              │
[analyzer_architecture]                │ Parallel
[analyzer_security]                    │ execution
    ↓                                  │
PatternDiscovery (Nx) ────────────────┘
    ↓
[pattern_documenter] (BatchSpec)
    ↓
DocumentationUpdate
    ↓
CycleComplete
```

### 4. Refactor Workflow

```
RefactorRequest
    ↓
[refactor_orchestrator]
    ↓
ImplementationTask
    ↓
[implementer_backend]
    ↓
CodeChange
    ↓
ValidationRequest
    ↓
[validator_tests]
    ↓
ValidationResult ───┬─ [passed] ──→ ReviewRequest ──→ [reviewer_code]
                    │
                    └─ [failed] ──→ BlockedState
```

---

## 🧩 Artifact Types Reference

### Category 1: Core Requests (4 types)

| Artifact | Purpose | Published By | Consumed By |
|----------|---------|--------------|-------------|
| `SpecifyRequest` | User wants to create specification | User/CLI | specify_orchestrator |
| `AnalyzeRequest` | User wants to analyze codebase | User/CLI | analyze_orchestrator, analyzer_* |
| `ImplementRequest` | User wants to execute plan | User/CLI | implement_orchestrator |
| `RefactorRequest` | User wants to refactor code | User/CLI | refactor_orchestrator |

### Category 2: Specification (5 types)

| Artifact | Purpose | Published By | Consumed By |
|----------|---------|--------------|-------------|
| `PRDSection` | Section of Product Requirements Doc | documenter_requirements | documenter_design, reviewer_specification |
| `SDDSection` | Section of Solution Design Doc | documenter_design | documenter_planning, reviewer_specification |
| `PLANSection` | Section of Implementation Plan | documenter_planning | reviewer_specification |
| `SpecificationComplete` | Spec is ready for implementation | specify_orchestrator | implement_orchestrator |
| `SpecificationMetadata` | Tracks spec ID, directory, phase | specify_orchestrator | All documenters |

### Category 3: Research & Discovery (4 types)

| Artifact | Purpose | Published By | Consumed By |
|----------|---------|--------------|-------------|
| `ResearchTask` | Decomposed research activity | Orchestrators | research_* agents |
| `ResearchFindings` | Results from specialist research | research_* agents | Documenters, research_aggregator |
| `PatternDiscovery` | Discovered reusable pattern | analyzer_* agents | pattern_documenter |
| `InterfaceDiscovery` | Discovered external integration | analyzer_* agents | documenter_patterns |

### Category 4: Implementation (4 types)

| Artifact | Purpose | Published By | Consumed By |
|----------|---------|--------------|-------------|
| `PhaseStart` | Signals start of implementation phase | implement_orchestrator | (tracking) |
| `ImplementationTask` | Individual implementation task | Orchestrators | implementer_* agents |
| `CodeChange` | Code modification result | implementer_* agents | reviewer_code, phase_validator |
| `PhaseComplete` | Signals phase completion | phase_validator | implement_orchestrator |

### Category 5: Validation & Control (7 types)

| Artifact | Purpose | Published By | Consumed By |
|----------|---------|--------------|-------------|
| `ValidationRequest` | Request for validation | Orchestrators | validator_* agents |
| `ValidationResult` | Validation outcome | validator_* agents | Orchestrators, phase_validator |
| `ReviewRequest` | Request for review | Orchestrators | reviewer_* agents |
| `ReviewResult` | Review outcome | reviewer_* agents | Orchestrators |
| `CycleComplete` | Signals iteration cycle complete | Orchestrators, aggregators | (tracking) |
| `ContinueSignal` | User confirmation to proceed | User/CLI | Orchestrators |
| `BlockedState` | Agent is blocked and needs help | Any agent | Orchestrators, User |

### Category 6: Documentation (2 types)

| Artifact | Purpose | Published By | Consumed By |
|----------|---------|--------------|-------------|
| `DocumentationUpdate` | Update to any document | Documenters | (file system) |
| `DocumentationComplete` | Document is finalized | Documenters | Orchestrators |

---

## 🎯 Subscription Patterns

### Pattern 1: Type-Based Subscription

**Example**: Research specialists subscribe to ResearchTask by type

```python
research_market_analyst = (
    flock.agent("research_market_analyst")
    .consumes(
        ResearchTask,
        where=lambda task: task.research_type == ResearchType.MARKET,
    )
    .publishes(ResearchFindings)
)
```

**Key Points**:
- Agent only reacts to tasks matching its specialty
- Predicate function (`where=`) provides filtering
- Multiple agents can subscribe to same artifact type
- Automatic parallel execution

### Pattern 2: Multi-Artifact Subscription

**Example**: Documenter consumes multiple artifact types

```python
documenter_design = (
    flock.agent("documenter_design")
    .consumes(PRDSection, ResearchFindings)
    .publishes(SDDSection)
)
```

**Key Points**:
- Agent waits for ALL specified artifact types
- Enables sequential dependencies (PRD → SDD)
- Can also use conditional logic on multiple types

### Pattern 3: JoinSpec (Parallel Aggregation)

**Example**: Wait for all research findings before proceeding

```python
research_aggregator = (
    flock.agent("research_aggregator")
    .consumes(
        ResearchFindings,
        join=JoinSpec(
            by=lambda finding: finding.task_id.split("-")[1],
            within=timedelta(minutes=10),
        ),
    )
    .publishes(CycleComplete)
)
```

**Key Points**:
- `by=` groups related artifacts by correlation key
- `within=` specifies timeout window
- Agent fires when ALL related artifacts arrive
- Enables "wait for all parallel tasks" pattern

### Pattern 4: BatchSpec (Collect and Process)

**Example**: Batch multiple patterns for documentation

```python
pattern_documenter = (
    flock.agent("pattern_documenter")
    .consumes(
        PatternDiscovery,
        batch=BatchSpec(
            size=5,
            timeout=timedelta(minutes=3),
        ),
    )
    .publishes(DocumentationUpdate)
)
```

**Key Points**:
- Collects up to `size` artifacts OR waits for `timeout`
- Whichever comes first triggers the agent
- Enables efficient batch processing
- Reduces overhead from processing one-by-one

---

## 🔧 MCP Tool Access Matrix

| Agent Type | Filesystem | Web Search | Website Reader | Custom Tools |
|------------|-----------|------------|----------------|--------------|
| **Research** | Read-only | ✅ | ✅ | format_research_findings |
| **Documentation** | Read + Write (docs/) | ❌ | ❌ | append_to_document, create_spec_directory |
| **Implementation** | Full access | ❌ | ❌ | append_to_document |
| **Review** | Read-only | ❌ | ❌ | ❌ |
| **Validation** | Read + Execute | ❌ | ❌ | ❌ |
| **Analysis** | Read + Search | ❌ | ❌ | ❌ |
| **Orchestrators** | Full access | ✅ | ✅ | All custom tools |

**Design Principle**: Least privilege - agents only get tools they need.

---

## 🚀 Workflow Patterns

### Pattern A: Fan-Out / Fan-In (Research)

```
              ┌─── research_market ───┐
              ├─── research_technical ─┤
ResearchTask ─┤                        ├─ ResearchFindings → JoinSpec → CycleComplete
              ├─── research_security ──┤
              └─── research_ux ────────┘

       (Fan-Out: Parallel)         (Fan-In: Aggregate)
```

**Use Case**: Parallel information gathering with synchronization

### Pattern B: Pipeline (Documentation)

```
ResearchFindings → documenter_requirements → PRDSection
                                                ↓
                                        documenter_design → SDDSection
                                                              ↓
                                                    documenter_planning → PLANSection
```

**Use Case**: Sequential transformation with dependencies

### Pattern C: Router (Implementation)

```
                      ┌─ [backend] ──→ implementer_backend
ImplementationTask ───┼─ [frontend] ─→ implementer_frontend
                      ├─ [database] ─→ implementer_database
                      └─ [infrastructure] → implementer_infrastructure
```

**Use Case**: Task routing based on attributes

### Pattern D: Guard (Validation)

```
CodeChange ──→ ValidationRequest ──→ validator_tests ──→ ValidationResult
                                                              ↓
                                                    [passed] ─┬─→ Continue
                                                              │
                                                    [failed] ─┴─→ BlockedState
```

**Use Case**: Quality gates with conditional progression

---

## 💡 Design Principles

### 1. Loose Coupling

Agents only know about artifact types, not other agents:

```python
# Agent doesn't specify WHO will consume its output
implementer_backend.publishes(CodeChange)

# Other agents subscribe independently
reviewer_code.consumes(CodeChange)
phase_validator.consumes(CodeChange)
```

### 2. Type Safety

All communication is typed with Pydantic models:

```python
@flock_type
class ResearchTask(BaseModel):
    task_id: str
    research_type: ResearchType  # Enum
    focus_area: str
    context: str
```

### 3. Declarative Subscriptions

Agents declare what they consume/publish:

```python
agent
    .consumes(InputArtifact, where=predicate)
    .publishes(OutputArtifact)
```

### 4. Emergent Behavior

Complex workflows emerge from simple subscription rules:
- No central coordinator listing all agents
- No hard-coded workflow steps
- Agents self-organize based on artifacts

### 5. Observable

Blackboard provides full audit trail:
- Every artifact persisted
- Timestamp of creation
- Which agent produced it
- Which agents consumed it

---

## 📈 Scalability Patterns

### Adding New Agent Types

1. Define new artifact type (Pydantic model)
2. Create agent with subscription
3. Deploy - no changes to existing agents!

```python
@flock_type
class PerformanceAnalysisRequest(BaseModel):
    target_path: str
    metrics: list[str]

analyzer_performance = (
    flock.agent("analyzer_performance")
    .consumes(PerformanceAnalysisRequest)
    .publishes(PatternDiscovery)
)
```

### Adding New Workflows

1. Define workflow artifacts (Request, sections, etc.)
2. Create orchestrator agent
3. Reuse existing specialists!

```python
# New workflow reuses existing agents
security_review_orchestrator = (
    flock.agent("security_review_orchestrator")
    .consumes(SecurityReviewRequest)
    .publishes(ResearchTask)  # Reuses research_security_analyst!
)
```

---

## 🎯 Best Practices

### For Agent Design

1. **Single Responsibility**: Each agent has one clear purpose
2. **Conditional Subscriptions**: Use `where=` predicates for routing
3. **Type Safety**: Always use `@flock_type` for artifacts
4. **Tool Access**: Request only tools needed (least privilege)
5. **Error Handling**: Publish BlockedState when stuck

### For Workflow Design

1. **Use JoinSpec**: For parallel aggregation (fan-in)
2. **Use BatchSpec**: For efficient bulk processing
3. **Validation Gates**: Always validate before proceeding
4. **User Confirmation**: Wait for ContinueSignal between major phases
5. **Observable**: Publish artifacts for tracking

### For Testing

1. **Mock Blackboard**: Test agents with mocked artifact store
2. **Test Predicates**: Unit test `where=` functions
3. **Test Artifacts**: Validate Pydantic models
4. **Integration Tests**: Test artifact flows end-to-end

---

## 🔥 Key Insights

### Insight 1: Agents Are Just Subscriptions

An agent is fundamentally a subscription rule:
```
IF artifact_type matches
AND predicate returns true
THEN invoke agent
AND publish results
```

### Insight 2: Workflows Emerge

Complex workflows emerge from simple rules:
- No central controller
- No hard-coded sequences
- Just agents reacting to artifacts

### Insight 3: Blackboard Is The Truth

The blackboard is the single source of truth:
- All agent communication goes through it
- Full audit trail of what happened
- Replay workflows by examining artifacts

### Insight 4: Type Safety Enables Scale

Pydantic models enable:
- IDE autocomplete
- Refactoring with confidence
- Early error detection
- Clear contracts between agents

---

## 🎊 Summary

The spec-driven development system demonstrates how **27 agents** collaborating through **26 typed artifacts** can implement complex, multi-phase workflows without explicit orchestration.

**Key Architectural Patterns**:
- ✅ Blackboard for loose coupling
- ✅ Typed artifacts for safety
- ✅ Declarative subscriptions for clarity
- ✅ JoinSpec/BatchSpec for coordination
- ✅ MCP tools for real operations
- ✅ Emergent behavior from simple rules

**The Result**: A flexible, type-safe, testable, observable system that scales from simple tasks to complex workflows.

---

**Status**: Architecture documented
**Agents**: 27 (19 specialists + 8 orchestrators)
**Artifacts**: 26 typed Pydantic models
**Patterns**: Fan-out/fan-in, Pipeline, Router, Guard
**Scalability**: Add agents without changing existing system
