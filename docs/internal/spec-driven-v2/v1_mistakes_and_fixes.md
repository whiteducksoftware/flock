# V1 Mistakes and How to Fix Them

**A detailed analysis of what went wrong and how V2 will be different**

---

## 🔴 Mistake #1: Multiple `.publishes()` per Agent

### What We Did Wrong (V1)

```python
# From V1: orchestrators.py
specify_orchestrator = (
    flock.agent("specify_orchestrator")
    .description("Master specification orchestrator...")
    .consumes(SpecifyRequest)
    .with_mcps(format_mcp_config_for_agent("orchestrator"))
    .publishes(
        SpecificationMetadata,    # ❌ TOO MANY!
        ResearchTask,             # ❌
        PRDSection,               # ❌
        SDDSection,               # ❌
        PLANSection,              # ❌
        SpecificationComplete,    # ❌
        CycleComplete             # ❌
    )
)
```

**Problem:** This agent tries to do 7 different things! It's not a specialist, it's trying to be a conductor.

### How to Fix It (V2)

Break into multiple simple agents, each publishing ONE type:

```python
# Agent 1: Initialize specification
spec_initializer = (
    flock.agent("spec_initializer")
    .consumes(SpecifyRequest)
    .publishes(SpecMetadata)  # ✅ ONLY ONE!
)

# Agent 2: Plan research
research_planner = (
    flock.agent("research_planner")
    .consumes(SpecMetadata)
    .publishes(ResearchTaskBatch)  # ✅ ONLY ONE!
)

# Agent 3: Dispatch tasks
task_dispatcher = (
    flock.agent("task_dispatcher")
    .consumes(ResearchTaskBatch)
    .publishes(ResearchTask)  # ✅ ONLY ONE! (creates 4 via LLM)
)

# ... and so on
```

**Result:** Instead of 1 complex agent, we have many simple agents chained together!

---

## 🔴 Mistake #2: Manual `flock.publish()` in Workflows

### What We Did Wrong (V1)

```python
# From V1: 02_specify_workflow.py
async def simplified_specify_workflow():
    flock = Flock()
    configure_mcps(flock)
    create_specialist_agents(flock)

    # ❌ WRONG - We're manually orchestrating!
    spec_info = create_spec_directory(feature_description)

    # ❌ WRONG - Publishing multiple artifacts manually
    for research_type in [MARKET, TECHNICAL, SECURITY, UX]:
        task = ResearchTask(
            task_id=f"{spec_id}-research-{type}",
            research_type=research_type,
            focus_area="...",
        )
        await flock.publish(task)  # ❌ MANUAL ORCHESTRATION!

    await flock.run_until_idle()

    # ❌ WRONG - Manually collecting results
    findings = await flock.store.get_by_type(ResearchFindings)
    for finding in findings:
        append_to_document(prd_path, ...)  # ❌ MANUAL WORK!
```

**Problem:** We're doing the orchestration ourselves! The agents are just workers we're commanding.

### How to Fix It (V2)

Let the agents do everything through emergence:

```python
# V2: 06_dashboard_specify.py
import asyncio
from flock.orchestrator import Flock
from artifacts_v2 import *
from agents_v2 import create_specify_agents

async def main():
    flock = Flock()

    # Create all agents (they handle everything!)
    create_specify_agents(flock)

    # ✅ CORRECT - Just start the dashboard!
    await flock.serve(dashboard=True)
    # That's it! User publishes SpecifyRequest in dashboard,
    # the entire workflow emerges from agent subscriptions!

if __name__ == "__main__":
    asyncio.run(main())
```

**What happens when user publishes `SpecifyRequest`:**
1. `spec_initializer` sees it → creates spec directory → publishes `SpecMetadata`
2. `research_planner` sees `SpecMetadata` → publishes `ResearchTaskBatch`
3. `task_dispatcher` sees `ResearchTaskBatch` → publishes 4 `ResearchTask` artifacts
4. Research specialists see their tasks → publish `ResearchFindings`
5. `research_aggregator` collects all findings (JoinSpec) → publishes `AggregatedFindings`
6. `prd_writer` sees findings → writes PRD → publishes `PRDDraft`
7. ... and so on!

**All automatic! No manual orchestration!**

---

## 🔴 Mistake #3: "Orchestrator" Classes with Control Logic

### What We Did Wrong (V1)

```python
# From V1: orchestrators.py (NOT in the actual code, but the intention was there)
class SpecifyOrchestrator:
    """
    Orchestrator that coordinates the entire specification workflow.
    """

    def __init__(self, flock: Flock):
        self.flock = flock

    async def run(self, request: SpecifyRequest):
        # ❌ WRONG - Control logic in a class

        # Step 1: Create metadata
        metadata = await self.create_metadata(request)
        await self.flock.publish(metadata)

        # Step 2: Create research tasks
        tasks = await self.create_research_tasks(metadata)
        for task in tasks:
            await self.flock.publish(task)

        # Step 3: Wait for all findings
        findings = await self.wait_for_findings(tasks)

        # Step 4: Create PRD
        prd = await self.create_prd(findings)
        await self.flock.publish(prd)

        # ... and so on
```

**Problem:** This is just command-based orchestration with extra steps! We're recreating the original devflow pattern instead of using blackboard architecture.

### How to Fix It (V2)

**NO ORCHESTRATOR CLASSES!** Just simple agent definitions:

```python
# V2: agents_v2.py
def create_specify_agents(flock: Flock):
    """
    Creates all agents for the specify workflow.
    Each agent is simple and declarative - no control logic!
    """

    # Agent 1
    spec_initializer = (
        flock.agent("spec_initializer")
        .description(
            "Creates spec directory and metadata when user requests specification. "
            "Uses create_spec_directory tool to generate unique spec ID and folder structure."
        )
        .consumes(SpecifyRequest)
        .with_mcps({"filesystem": ["read", "write"]})
        .publishes(SpecMetadata)
    )

    # Agent 2
    research_planner = (
        flock.agent("research_planner")
        .description(
            "Plans research activities based on feature description. "
            "Determines what research is needed (market, technical, security, UX). "
            "Creates a ResearchTaskBatch artifact."
        )
        .consumes(SpecMetadata)
        .publishes(ResearchTaskBatch)
    )

    # Agent 3
    task_dispatcher = (
        flock.agent("task_dispatcher")
        .description(
            "Creates individual ResearchTask artifacts from a batch. "
            "Generates 4 separate tasks: market, technical, security, and UX. "
            "Each task becomes a separate artifact on the blackboard."
        )
        .consumes(ResearchTaskBatch)
        .publishes(ResearchTask)
    )

    # ... more agents

    return {
        "spec_initializer": spec_initializer,
        "research_planner": research_planner,
        "task_dispatcher": task_dispatcher,
        # ... rest
    }
```

**Key difference:** Agents are just declarations! No classes, no methods, no control flow!

---

## 🔴 Mistake #4: Complex Dashboard Example with Manual Steps

### What We Did Wrong (V1)

```python
# From V1: 06_dashboard_demo.py (the one I created incorrectly)
async def run_dashboard_demo():
    # ... setup code ...

    # ❌ WRONG - User chooses workflow in code
    choice = input("Enter workflow number (1-4): ")

    if choice == "1":
        # ❌ WRONG - We manually create the request
        request = SpecifyRequest(feature_description=feature)
        await flock.publish(request)  # ❌ MANUAL!

        # ❌ WRONG - We wait and check results
        await flock.run_until_idle()
        findings = await flock.store.get_by_type(ResearchFindings)
        # ... manual result processing

    # More manual orchestration for other workflows...
```

**Problem:**
- The script is doing the orchestration
- User interaction is in Python code (should be in dashboard UI!)
- We're manually publishing and checking results

### How to Fix It (V2)

```python
# V2: 06_dashboard_specify.py
"""
Dashboard visualization for Specify workflow.

User publishes a SpecifyRequest artifact in the dashboard UI.
Watch 17 agents collaborate to produce PRD → SDD → PLAN!

No code needed - just watch the emergence!
"""

import asyncio
from flock.orchestrator import Flock
from artifacts_v2 import *
from agents_v2 import create_specify_agents

async def main():
    flock = Flock()

    # Configure MCP tools
    configure_mcps(flock)

    # Create all 17 agents for specify workflow
    create_specify_agents(flock)

    # ✅ CORRECT - Just serve the dashboard!
    await flock.serve(dashboard=True)

if __name__ == "__main__":
    asyncio.run(main())
```

**Usage:**
1. Run: `uv run python 06_dashboard_specify.py`
2. Dashboard opens in browser
3. Click "Publish Artifact"
4. Choose `SpecifyRequest`
5. Enter: `{"feature_description": "Add user authentication"}`
6. Click "Publish"
7. **WATCH THE MAGIC!** 17 agents react in a chain!

**That's it! < 20 lines, zero manual orchestration!**

---

## 🔴 Mistake #5: Agents with Multiple Responsibilities

### What We Did Wrong (V1)

```python
# From V1: agents.py
documenter_requirements = (
    flock.agent("documenter_requirements")
    .description(
        "Requirements documenter who creates PRD sections from research findings. "
        "Also synthesizes findings and validates completeness."  # ❌ Multiple jobs!
    )
    .consumes(PRDSection, ResearchFindings)  # ❌ Mixed concerns
    .publishes(PRDSection)
)
```

**Problem:** Agent description says it does multiple things. This leads to confused LLM behavior and unclear responsibilities.

### How to Fix It (V2)

One agent, one job, one output:

```python
# V2: agents_v2.py

# Agent 1: Just aggregate findings
findings_aggregator = (
    flock.agent("findings_aggregator")
    .description(
        "Aggregates multiple ResearchFindings into a single AggregatedFindings artifact. "
        "Waits for all research to complete using JoinSpec. "
        "Combines market, technical, security, and UX research into one cohesive summary."
    )
    .consumes(
        ResearchFindings,
        join=JoinSpec(by=lambda f: f.spec_id, within=timedelta(minutes=10))
    )
    .publishes(AggregatedFindings)  # ✅ One job, one output!
)

# Agent 2: Just write PRD
prd_writer = (
    flock.agent("prd_writer")
    .description(
        "Writes Product Requirements Document based on aggregated research. "
        "Creates structured PRD with sections: Overview, Goals, Requirements, Constraints. "
        "Follows PRD template structure and writes to spec directory."
    )
    .consumes(AggregatedFindings)
    .with_mcps({"filesystem": ["write"]})
    .publishes(PRDDraft)  # ✅ One job, one output!
)

# Agent 3: Just review PRD
prd_reviewer = (
    flock.agent("prd_reviewer")
    .description(
        "Reviews PRD for completeness, clarity, and consistency. "
        "Checks that all requirements are testable and unambiguous. "
        "Provides review feedback and approval status."
    )
    .consumes(PRDDraft)
    .publishes(PRDReview)  # ✅ One job, one output!
)
```

**Result:** Three simple agents instead of one confused agent!

---

## 🔴 Mistake #6: Conditional Logic in Artifact Types

### What We Did Wrong (V1)

```python
# From V1: We had multiple artifact types for success/failure
@flock_type
class ValidationSuccess(BaseModel):
    test_results: str
    all_passed: bool = True

@flock_type
class ValidationFailure(BaseModel):
    test_results: str
    all_passed: bool = False
    errors: list[str]
```

**Problem:** Two types when we could use one with a field!

### How to Fix It (V2)

```python
# V2: One type with status
@flock_type
class ValidationResult(BaseModel):
    validation_id: str
    passed: bool  # ✅ Just a field!
    test_output: str
    errors: list[str] = Field(default_factory=list)
    timestamp: datetime

# Then route based on the field
success_router = (
    flock.agent("success_router")
    .consumes(ValidationResult, where=lambda r: r.passed)  # ✅ Conditional subscription
    .publishes(ReviewRequest)
)

failure_router = (
    flock.agent("failure_router")
    .consumes(ValidationResult, where=lambda r: not r.passed)  # ✅ Conditional subscription
    .publishes(BlockedState)
)
```

**Result:** Fewer artifact types, clearer routing!

---

## 🔴 Mistake #7: Tool Usage in Wrong Agents

### What We Did Wrong (V1)

We gave custom tools to orchestrators:

```python
# V1: mcp_config.py
"orchestrator": {
    "mcps": ["filesystem", "search_web", "read_website"],
    "filesystem_tools": ["read", "write", "edit", "list", ...],  # ❌ TOO MANY!
    "custom_tools": [  # ❌ Orchestrator shouldn't use custom tools!
        "create_spec_directory",
        "append_to_document",
        "read_document",
        # ... all tools
    ]
}
```

**Problem:** "Orchestrators" had access to everything because they were trying to do everything!

### How to Fix It (V2)

Give tools only to agents that need them:

```python
# V2: agents_v2.py

spec_initializer = (
    flock.agent("spec_initializer")
    .consumes(SpecifyRequest)
    .with_mcps({
        "filesystem": ["read", "write"],
        "custom_tools": ["create_spec_directory"]  # ✅ Only what it needs!
    })
    .publishes(SpecMetadata)
)

prd_writer = (
    flock.agent("prd_writer")
    .consumes(AggregatedFindings)
    .with_mcps({
        "filesystem": ["write"],
        "custom_tools": ["append_to_document"]  # ✅ Only what it needs!
    })
    .publishes(PRDDraft)
)

research_market = (
    flock.agent("research_market")
    .consumes(ResearchTask, where=lambda t: t.type == "market")
    .with_mcps({
        "search_web": ["search"],  # ✅ Only what it needs!
        "read_website": ["read"]
    })
    .publishes(ResearchFindings)
)
```

**Result:** Least privilege - agents only get tools they need!

---

## 📊 Summary: V1 vs V2 Side-by-Side

| Aspect | V1 (Wrong) | V2 (Correct) |
|--------|------------|--------------|
| **Agent publishes** | Multiple types | ONE type only |
| **Workflow scripts** | Manual `flock.publish()` calls | Just `flock.serve(dashboard=True)` |
| **Orchestrator classes** | Complex classes with control logic | Don't exist! |
| **Agent count** | 27 (8 trying to do everything) | ~44 (all doing one thing) |
| **Dashboard example** | 300+ lines with manual steps | < 20 lines, pure emergence |
| **Tool access** | Broad permissions | Least privilege |
| **Complexity** | High (control logic) | Low (pure declarations) |
| **Emergence** | Fake (we control it) | Real (natural chain reactions) |
| **Code in workflows** | ~200 lines orchestration | ~15 lines setup |

---

## ✅ V2 Checklist

Before implementing any agent, ask:

- [ ] Does this agent have EXACTLY ONE `.publishes()`?
- [ ] Is this agent's job simple and focused?
- [ ] Could I explain what this agent does in one sentence?
- [ ] Does this agent transform ONE input type to ONE output type?
- [ ] Is there NO control logic (if/else/loops) in my workflow script?
- [ ] Am I letting the blackboard orchestrate, not me?
- [ ] Could a user publish ONE artifact and see the whole workflow emerge?
- [ ] Is my dashboard example < 30 lines?

**If you answered NO to any of these, redesign!**

---

## 🎓 The Core Lesson

> **Blackboard orchestration is about EMERGENCE, not CONTROL!**

You don't tell agents what to do. You define:
1. What artifacts they react to
2. What artifact they produce
3. Let them self-organize!

**Think:** "I'm designing a chemical reaction, not conducting an orchestra"

```
Catalyst A + Reagent X → Product Y
Product Y + Catalyst B → Product Z
Product Z + Catalyst C → Final Product
```

You don't tell the molecules when to react - they just do when conditions are right!

**Same with Flock agents!**

---

**Ready for V2? Let's build it the RIGHT way!** 🚀
