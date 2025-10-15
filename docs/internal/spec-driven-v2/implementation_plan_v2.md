# Spec-Driven Development V2: The CORRECT Blackboard Orchestration

**Learning from V1 mistakes to build TRUE emergent coordination**

---

## 🎯 What Went Wrong in V1

### Critical Mistakes Made

1. **❌ Multiple `.publishes()` per agent**
   ```python
   # WRONG - V1 orchestrator
   specify_orchestrator = (
       flock.agent("specify_orchestrator")
       .consumes(SpecifyRequest)
       .publishes(SpecificationMetadata, ResearchTask, PRDSection, ...)  # TOO MANY!
   )
   ```
   **Problem**: Agents should have ONE job, ONE output type

2. **❌ Manual `flock.publish()` calls in workflows**
   ```python
   # WRONG - V1 workflow script
   await flock.publish(ResearchTask(...))
   await flock.publish(ResearchTask(...))
   await flock.publish(ResearchTask(...))
   ```
   **Problem**: We're orchestrating manually instead of letting it emerge!

3. **❌ "Orchestrator" agents trying to control everything**
   ```python
   # WRONG - V1 thinking
   class SpecifyOrchestrator:
       def run(self):
           # Manually publish multiple artifacts
           # Control the flow
           # Act like a command center
   ```
   **Problem**: This defeats the purpose of blackboard architecture!

### What V1 Looked Like

```
User → Manual Script → publish() → publish() → publish()
                         ↓           ↓           ↓
                    Orchestrator tells agents what to do
```

**Result**: We just recreated command-based orchestration with extra steps!

---

## ✅ The CORRECT Blackboard Pattern

### Core Principle: EMERGENT ORCHESTRATION

```
User publishes ONE artifact → Agent reacts → Publishes ONE artifact →
    Another agent reacts → Publishes ONE artifact → ...
```

**The workflow EMERGES from agent subscriptions, not from manual control!**

### Example: News Agency (From examples/02-dashboard/10_news_agency.py)

```python
# Step 1: Define artifact types
@flock_type
class NewsEvent(BaseModel):
    headline: str
    location: str

@flock_type
class NewsArticle(BaseModel):
    title: str
    body: str

@flock_type
class EditorialDecision(BaseModel):
    article_approved: bool

@flock_type
class PublishedStory(BaseModel):
    final_headline: str

# Step 2: Define agents (each with ONE publishes!)
reporter = (
    flock.agent("reporter")
    .consumes(NewsEvent)
    .publishes(NewsArticle)  # ONLY ONE!
)

editor = (
    flock.agent("editor")
    .consumes(NewsArticle)
    .publishes(EditorialDecision)  # ONLY ONE!
)

publisher = (
    flock.agent("publisher")
    .consumes(EditorialDecision)
    .consumes(NewsArticle)  # Can consume multiple, but...
    .publishes(PublishedStory)  # ...publishes ONLY ONE!
)

# Step 3: Start dashboard
asyncio.run(flock.serve(dashboard=True))
```

**What happens:**
1. User publishes `NewsEvent` in dashboard
2. `reporter` agent automatically reacts → publishes `NewsArticle`
3. `editor` agent automatically reacts → publishes `EditorialDecision`
4. `publisher` agent automatically reacts (needs both) → publishes `PublishedStory`
5. **DONE!** No manual orchestration needed!

---

## 📋 Agent Design Rules

### Rule #1: ONE Job, ONE Output

Each agent should:
- Have a single, clear responsibility
- Consume one or more artifact types
- **Publish EXACTLY ONE artifact type**

```python
# ✅ CORRECT
research_market = (
    flock.agent("research_market")
    .consumes(ResearchTask, where=lambda t: t.research_type == "market")
    .publishes(ResearchFindings)  # ONLY ONE!
)

# ❌ WRONG
research_orchestrator = (
    flock.agent("research_orchestrator")
    .consumes(SpecifyRequest)
    .publishes(ResearchTask, ResearchFindings, PRDSection)  # TOO MANY!
)
```

### Rule #2: No Manual Publishing in Workflows

```python
# ❌ WRONG - Manual orchestration
async def workflow():
    await flock.publish(TaskA(...))
    await flock.publish(TaskB(...))
    await flock.run_until_idle()

# ✅ CORRECT - Let it emerge
async def main():
    flock = Flock()
    # Define agents
    agent_a = flock.agent("a").consumes(Input).publishes(Output)
    # Start dashboard
    await flock.serve(dashboard=True)
    # User publishes in dashboard, workflow emerges!
```

### Rule #3: Use Conditional Subscriptions for Routing

```python
# ✅ CORRECT - Routing via predicates
implementer_backend = (
    flock.agent("implementer_backend")
    .consumes(ImplementationTask, where=lambda t: t.area == "backend")
    .publishes(CodeChange)
)

implementer_frontend = (
    flock.agent("implementer_frontend")
    .consumes(ImplementationTask, where=lambda t: t.area == "frontend")
    .publishes(CodeChange)
)
```

**Result**: Same artifact type routes to different agents automatically!

### Rule #4: Use JoinSpec for Parallel Aggregation

```python
# ✅ CORRECT - Wait for multiple artifacts
aggregator = (
    flock.agent("aggregator")
    .consumes(
        ResearchFindings,
        join=JoinSpec(
            by=lambda f: f.request_id,  # Group by request
            within=timedelta(minutes=5)
        )
    )
    .publishes(AggregatedFindings)  # Still only ONE output!
)
```

### Rule #5: Use BatchSpec for Batching

```python
# ✅ CORRECT - Batch multiple artifacts
documenter = (
    flock.agent("documenter")
    .consumes(
        PatternDiscovery,
        batch=BatchSpec(size=5, timeout=timedelta(minutes=2))
    )
    .publishes(DocumentationUpdate)  # Still only ONE output!
)
```

---

## 🔄 Designing Emergent Workflows

### Pattern 1: Linear Chain

```
Request → AgentA → ArtifactA → AgentB → ArtifactB → AgentC → Result
```

**Example: Simple Specification**
```python
# Artifact chain
SpecifyRequest → SpecMetadata → ResearchRequest → ResearchFindings → PRDSection

# Agents
metadata_creator = (
    flock.agent("metadata_creator")
    .consumes(SpecifyRequest)
    .publishes(SpecMetadata)
)

research_dispatcher = (
    flock.agent("research_dispatcher")
    .consumes(SpecMetadata)
    .publishes(ResearchRequest)
)

researcher = (
    flock.agent("researcher")
    .consumes(ResearchRequest)
    .publishes(ResearchFindings)
)

documenter = (
    flock.agent("documenter")
    .consumes(ResearchFindings)
    .publishes(PRDSection)
)
```

**Flow:**
1. User publishes `SpecifyRequest`
2. `metadata_creator` reacts → publishes `SpecMetadata`
3. `research_dispatcher` reacts → publishes `ResearchRequest`
4. `researcher` reacts → publishes `ResearchFindings`
5. `documenter` reacts → publishes `PRDSection`
6. **DONE!** All emergent, no manual control!

### Pattern 2: Parallel Fan-Out with JoinSpec

```
                    ┌─ AgentA1 ─┐
Request → Dispatcher├─ AgentA2 ─┤ → Aggregator → Result
                    └─ AgentA3 ─┘
```

**Example: Parallel Research**
```python
# Artifacts
SpecifyRequest → ResearchTask (4x) → ResearchFindings (4x) → AggregatedFindings

# Agents
task_creator = (
    flock.agent("task_creator")
    .consumes(SpecifyRequest)
    .publishes(ResearchTask)  # Creates 4 tasks via LLM logic
)

research_market = (
    flock.agent("research_market")
    .consumes(ResearchTask, where=lambda t: t.type == "market")
    .publishes(ResearchFindings)
)

research_tech = (
    flock.agent("research_tech")
    .consumes(ResearchTask, where=lambda t: t.type == "tech")
    .publishes(ResearchFindings)
)

research_security = (
    flock.agent("research_security")
    .consumes(ResearchTask, where=lambda t: t.type == "security")
    .publishes(ResearchFindings)
)

research_ux = (
    flock.agent("research_ux")
    .consumes(ResearchTask, where=lambda t: t.type == "ux")
    .publishes(ResearchFindings)
)

aggregator = (
    flock.agent("aggregator")
    .consumes(
        ResearchFindings,
        join=JoinSpec(by=lambda f: f.spec_id, within=timedelta(minutes=10))
    )
    .publishes(AggregatedFindings)  # Waits for ALL 4!
)
```

**Key Insight**: The `task_creator` agent's LLM prompt tells it to create 4 tasks!

```python
# task_creator agent prompt
"""
You are a research task decomposer.
Given a SpecifyRequest, create 4 ResearchTask artifacts:
1. market analysis (type="market")
2. technical evaluation (type="tech")
3. security assessment (type="security")
4. UX research (type="ux")

For each task, publish a separate ResearchTask artifact.
"""
```

### Pattern 3: Batching with BatchSpec

```
Event1 ┐
Event2 ├─ (batch) → BatchProcessor → BatchResult
Event3 ┘
```

**Example: Pattern Documentation**
```python
# Artifacts
AnalyzeRequest → PatternDiscovery (many) → DocumentationBatch → FinalDocs

analyzer = (
    flock.agent("analyzer")
    .consumes(AnalyzeRequest)
    .publishes(PatternDiscovery)  # Finds many patterns
)

batch_documenter = (
    flock.agent("batch_documenter")
    .consumes(
        PatternDiscovery,
        batch=BatchSpec(size=5, timeout=timedelta(minutes=2))
    )
    .publishes(DocumentationBatch)  # Batches 5 at a time
)
```

---

## 🎯 V2 Workflow Designs

### Workflow 1: Specify (PRD Generation)

**Artifact Flow:**
```
SpecifyRequest
  ↓
SpecMetadata (spec_id, directory created)
  ↓
ResearchTaskBatch (creates 4 ResearchTask artifacts)
  ↓
ResearchTask (market) → ResearchFindings (market) ┐
ResearchTask (tech)   → ResearchFindings (tech)   ├─ JoinSpec
ResearchTask (security) → ResearchFindings (security) │
ResearchTask (ux)     → ResearchFindings (ux)     ┘
  ↓
AggregatedFindings
  ↓
PRDDraft
  ↓
PRDReview
  ↓
SDDRequest
  ↓
SDDDraft
  ↓
SDDReview
  ↓
PLANRequest
  ↓
PLANDraft
  ↓
PLANReview
  ↓
SpecificationComplete
```

**Agents (each publishes ONLY ONE type):**
1. `spec_initializer` - Consumes: SpecifyRequest → Publishes: SpecMetadata
2. `research_planner` - Consumes: SpecMetadata → Publishes: ResearchTaskBatch
3. `task_dispatcher` - Consumes: ResearchTaskBatch → Publishes: ResearchTask (4x via LLM)
4. `research_market` - Consumes: ResearchTask (market) → Publishes: ResearchFindings
5. `research_tech` - Consumes: ResearchTask (tech) → Publishes: ResearchFindings
6. `research_security` - Consumes: ResearchTask (security) → Publishes: ResearchFindings
7. `research_ux` - Consumes: ResearchTask (ux) → Publishes: ResearchFindings
8. `research_aggregator` - Consumes: ResearchFindings (JoinSpec) → Publishes: AggregatedFindings
9. `prd_writer` - Consumes: AggregatedFindings → Publishes: PRDDraft
10. `prd_reviewer` - Consumes: PRDDraft → Publishes: PRDReview
11. `sdd_requester` - Consumes: PRDReview → Publishes: SDDRequest
12. `sdd_writer` - Consumes: SDDRequest + AggregatedFindings → Publishes: SDDDraft
13. `sdd_reviewer` - Consumes: SDDDraft → Publishes: SDDReview
14. `plan_requester` - Consumes: SDDReview → Publishes: PLANRequest
15. `plan_writer` - Consumes: PLANRequest + SDDDraft → Publishes: PLANDraft
16. `plan_reviewer` - Consumes: PLANDraft → Publishes: PLANReview
17. `spec_finalizer` - Consumes: PLANReview → Publishes: SpecificationComplete

**Total: 17 simple agents, each with ONE job!**

### Workflow 2: Analyze (Pattern Discovery)

**Artifact Flow:**
```
AnalyzeRequest
  ↓
AnalysisTaskBatch (creates 3 AnalysisTask artifacts)
  ↓
AnalysisTask (business) → PatternDiscovery ┐
AnalysisTask (technical) → PatternDiscovery ├─ BatchSpec
AnalysisTask (security) → PatternDiscovery  ┘
  ↓
DocumentationBatch
  ↓
AnalysisComplete
```

**Agents:**
1. `analysis_planner` - Consumes: AnalyzeRequest → Publishes: AnalysisTaskBatch
2. `task_dispatcher` - Consumes: AnalysisTaskBatch → Publishes: AnalysisTask (3x)
3. `business_analyzer` - Consumes: AnalysisTask (business) → Publishes: PatternDiscovery
4. `technical_analyzer` - Consumes: AnalysisTask (technical) → Publishes: PatternDiscovery
5. `security_analyzer` - Consumes: AnalysisTask (security) → Publishes: PatternDiscovery
6. `batch_documenter` - Consumes: PatternDiscovery (BatchSpec) → Publishes: DocumentationBatch
7. `analysis_finalizer` - Consumes: DocumentationBatch → Publishes: AnalysisComplete

**Total: 7 simple agents!**

### Workflow 3: Implement (Phase Execution)

**Artifact Flow:**
```
ImplementRequest
  ↓
ImplementationPlan (parsed PLAN.md)
  ↓
PhaseStart
  ↓
ImplementationTask (backend) → CodeChange ┐
ImplementationTask (frontend) → CodeChange ├─ (collect all)
ImplementationTask (database) → CodeChange │
ImplementationTask (infra) → CodeChange    ┘
  ↓
ValidationRequest
  ↓
ValidationResult (tests)
  ↓
ValidationResult (build)
  ↓
PhaseComplete
  ↓
(repeat for next phase OR)
  ↓
ImplementationComplete
```

**Agents:**
1. `plan_loader` - Consumes: ImplementRequest → Publishes: ImplementationPlan
2. `phase_starter` - Consumes: ImplementationPlan → Publishes: PhaseStart
3. `task_dispatcher` - Consumes: PhaseStart → Publishes: ImplementationTask (Nx)
4. `implementer_backend` - Consumes: ImplementationTask (backend) → Publishes: CodeChange
5. `implementer_frontend` - Consumes: ImplementationTask (frontend) → Publishes: CodeChange
6. `implementer_database` - Consumes: ImplementationTask (database) → Publishes: CodeChange
7. `implementer_infra` - Consumes: ImplementationTask (infra) → Publishes: CodeChange
8. `validation_dispatcher` - Consumes: CodeChange (after all) → Publishes: ValidationRequest
9. `test_validator` - Consumes: ValidationRequest (tests) → Publishes: ValidationResult
10. `build_validator` - Consumes: ValidationRequest (build) → Publishes: ValidationResult
11. `phase_completer` - Consumes: ValidationResult (all) → Publishes: PhaseComplete
12. `next_phase_starter` - Consumes: PhaseComplete → Publishes: PhaseStart OR ImplementationComplete

**Total: 12 simple agents!**

### Workflow 4: Refactor (Incremental Improvement)

**Artifact Flow:**
```
RefactorRequest
  ↓
RefactorAnalysis
  ↓
RefactorTask (single task)
  ↓
CodeChange
  ↓
ValidationRequest
  ↓
ValidationResult
  ↓ (if passed)
ReviewRequest
  ↓
ReviewResult
  ↓ (if approved)
NextRefactorTask OR RefactorComplete
  ↓ (if failed)
RefactorBlocked
```

**Agents:**
1. `refactor_analyzer` - Consumes: RefactorRequest → Publishes: RefactorAnalysis
2. `task_prioritizer` - Consumes: RefactorAnalysis → Publishes: RefactorTask (ONE at a time!)
3. `code_refactorer` - Consumes: RefactorTask → Publishes: CodeChange
4. `test_validator` - Consumes: CodeChange → Publishes: ValidationResult
5. `success_router` - Consumes: ValidationResult (passed) → Publishes: ReviewRequest
6. `failure_router` - Consumes: ValidationResult (failed) → Publishes: RefactorBlocked
7. `code_reviewer` - Consumes: ReviewRequest → Publishes: ReviewResult
8. `completion_decider` - Consumes: ReviewResult → Publishes: NextRefactorTask OR RefactorComplete

**Total: 8 simple agents!**

---

## 🚀 Implementation Strategy

### Phase 1: Artifact Types V2

Define ALL artifact types for emergent flows:

**Specify Workflow:**
- SpecifyRequest
- SpecMetadata
- ResearchTaskBatch
- ResearchTask
- ResearchFindings
- AggregatedFindings
- PRDDraft
- PRDReview
- SDDRequest
- SDDDraft
- SDDReview
- PLANRequest
- PLANDraft
- PLANReview
- SpecificationComplete

**Analyze Workflow:**
- AnalyzeRequest
- AnalysisTaskBatch
- AnalysisTask
- PatternDiscovery
- DocumentationBatch
- AnalysisComplete

**Implement Workflow:**
- ImplementRequest
- ImplementationPlan
- PhaseStart
- ImplementationTask
- CodeChange
- ValidationRequest
- ValidationResult
- PhaseComplete
- ImplementationComplete

**Refactor Workflow:**
- RefactorRequest
- RefactorAnalysis
- RefactorTask
- CodeChange (reused)
- ValidationResult (reused)
- ReviewRequest
- ReviewResult
- RefactorBlocked
- RefactorComplete

**Total: ~35 artifact types** (vs V1's 26)

### Phase 2: Simple Agents

Each agent follows this pattern:

```python
agent_name = (
    flock.agent("agent_name")
    .description("Does ONE thing")
    .consumes(InputArtifact, where=optional_predicate)
    .with_mcps(mcp_config)  # If needed
    .publishes(OutputArtifact)  # ONLY ONE!
)
```

**No orchestrator classes!** Just simple, declarative agents.

### Phase 3: Dashboard Example

```python
# 06_dashboard_specify.py
import asyncio
from flock.orchestrator import Flock
from artifacts import *
from agents import *

flock = Flock()

# Create ALL agents (17 for specify workflow)
create_specify_agents(flock)

# Start dashboard
asyncio.run(flock.serve(dashboard=True))
```

**That's it!** User publishes `SpecifyRequest` in dashboard, workflow emerges!

---

## 📊 Comparison: V1 vs V2

| Aspect | V1 (Wrong) | V2 (Correct) |
|--------|-----------|--------------|
| **Agents** | 27 (8 complex orchestrators) | ~44 (all simple) |
| **Agent Design** | Multiple `.publishes()` | ONE `.publishes()` |
| **Workflow** | Manual `flock.publish()` | Emergent from subscriptions |
| **Orchestrators** | Control everything | Don't exist! |
| **Complexity** | High (classes, methods) | Low (declarative) |
| **Dashboard** | Script with manual steps | Just `flock.serve(dashboard=True)` |
| **Emergence** | Fake (we control it) | Real (agents react) |

---

## ⚠️ Common Pitfalls to Avoid

### Pitfall #1: "I need an orchestrator"

**Wrong thinking:** "This workflow is complex, I need an orchestrator to manage it"

**Correct thinking:** "This workflow has steps A → B → C, so I need 3 simple agents"

### Pitfall #2: "Agent should publish multiple types"

**Wrong:** Agent publishes success AND failure types

**Correct:** Agent publishes one output type, another agent routes based on content

```python
# ❌ WRONG
validator = (
    flock.agent("validator")
    .consumes(CodeChange)
    .publishes(ValidationSuccess, ValidationFailure)  # Two types!
)

# ✅ CORRECT
validator = (
    flock.agent("validator")
    .consumes(CodeChange)
    .publishes(ValidationResult)  # One type with status field!
)

# Then route based on status
success_router = (
    flock.agent("success_router")
    .consumes(ValidationResult, where=lambda r: r.passed)
    .publishes(ReviewRequest)
)

failure_router = (
    flock.agent("failure_router")
    .consumes(ValidationResult, where=lambda r: not r.passed)
    .publishes(BlockedState)
)
```

### Pitfall #3: "I'll manually publish in the workflow"

**Wrong:** Writing `await flock.publish(...)` in workflow script

**Correct:** Let agents publish! Your script just starts the dashboard.

### Pitfall #4: "Workflow won't work without control logic"

**Trust the emergence!** If you design the artifact chain correctly, the workflow WILL emerge.

```
A publishes X
B consumes X publishes Y
C consumes Y publishes Z
```

When you publish A's input, the chain reaction happens automatically!

---

## 🎯 Success Criteria for V2

- [ ] Each agent has EXACTLY ONE `.publishes()`
- [ ] No manual `flock.publish()` in workflow scripts
- [ ] Dashboard example is < 20 lines (just setup + serve)
- [ ] User publishes ONE artifact, entire workflow emerges
- [ ] No "orchestrator" classes with control logic
- [ ] All agents are simple, declarative definitions
- [ ] Workflows are documented as artifact chains
- [ ] JoinSpec used for parallel aggregation
- [ ] BatchSpec used for batching
- [ ] Conditional subscriptions used for routing

---

## 📚 Learning Resources

**Study these dashboard examples:**
- `01_declarative_pizza.py` - Simplest possible chain
- `10_news_agency.py` - Multi-step chain with 3 agents
- `13_medical_diagnostics_joinspec.py` - JoinSpec pattern
- `14_ecommerce_batch_processing.py` - BatchSpec pattern

**Key insight from these examples:**
They're all < 100 lines and have NO manual orchestration!

---

## 🚀 Next Steps

1. **Review this plan** - Make sure we understand the principles
2. **Design artifact chains** - Map out the flows
3. **Implement simple agents** - One job, one output each
4. **Create dashboard example** - Just setup + serve
5. **Test emergence** - Publish one artifact, watch magic!

---

**The Golden Rule:** If you're writing control logic, you're doing it wrong! Let the blackboard orchestrate! 🎯
