# Quick Start Guide

**Get started with Self-Improving Workflows in 5 minutes.**

## What You'll Build

A workflow where AI agents discover, plan, implement, and validate work—with workflows that **build themselves** as agents discover what needs to be done.

## Step 1: Understand the Concept (2 minutes)

**Traditional workflow:** Rigid pipeline that breaks when reality diverges from plan.

**Self-Improving workflow:** Semi-structured phases where agents discover work and spawn new tasks dynamically.

```
Analysis → Implementation → Validation
    ↑                           ↓
    └─── Discovers work ───────┘
         (Workflow branches itself!)
```

## Step 2: Install Dependencies (1 minute)

```bash
# Ensure Flock is installed
poe install

# Set API key
export OPENAI_API_KEY="sk-..."
```

## Step 3: Run Basic Example (2 minutes)

```bash
uv run python examples/10-full-projects/self-improving-workflow/examples/01_basic_workflow.py
```

**What happens:**
1. User publishes initial work discovery (Phase 1: Analysis)
2. Analysis agent consumes it → creates implementation plan
3. Implementation agent consumes plan → builds solution
4. Validation agent consumes implementation → validates + may discover optimizations
5. If optimization found → new analysis work spawned → workflow branches!

## Step 4: Understand the Code

### Core Pattern

```python
from flock import Flock
from artifacts import WorkDiscovery, AnalysisResult, Implementation, ValidationResult

flock = Flock("openai/gpt-4.1")

# Phase 1: Analysis
analyzer = (
    flock.agent("analyzer")
    .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
    .publishes(AnalysisResult)
)

# Phase 2: Implementation
implementer = (
    flock.agent("implementer")
    .consumes(AnalysisResult, where=lambda a: a.approved)
    .publishes(Implementation)
)

# Phase 3: Validation (can discover new work!)
validator = (
    flock.agent("validator")
    .consumes(Implementation)
    .publishes(ValidationResult, WorkDiscovery)  # Fan-out!
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

### Key Concepts

1. **WorkDiscovery**: Represents work that needs doing in a specific phase
2. **Phase-aware subscriptions**: Agents consume only work from their phase
3. **Fan-out publishing**: Agents can publish results AND discoveries
4. **Emergent cascades**: Workflows build themselves through subscriptions

## Step 5: Customize for Your Use Case

### Change Phase Types

```python
# Add new phase
PHASES["deployment"] = PhaseDefinition(
    name="deployment",
    description="Deploy solutions to production",
    ...
)

# Create deployment agent
deployer = (
    flock.agent("deployer")
    .consumes(ValidationResult, where=lambda v: v.passed)
    .publishes(DeploymentResult)
)
```

### Add Discovery Logic

```python
async def validation_handler(ctx: AgentContext) -> list[Artifact]:
    implementation = ctx.artifacts[0]
    
    # Validate
    result = ValidationResult(passed=True, ...)
    
    # Discover optimization
    if optimization_found:
        discovery = WorkDiscovery(
            description="Caching pattern could optimize API routes",
            phase="analysis",  # Spawns Phase 1 work!
            priority="high",
            done_definition="Analysis complete",
            discovered_by=ctx.agent_name
        )
        result.optimizations_discovered.append(discovery)
    
    return [result, discovery]  # Fan-out!
```

## Next Steps

1. **Read [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Complete implementation guide
2. **Review [ARCHITECTURE.md](ARCHITECTURE.md)** - Design decisions and rationale
3. **Check [CODE_SNIPPETS.md](CODE_SNIPPETS.md)** - Reusable patterns
4. **Build your workflow!** - Adapt examples to your needs

## Common Patterns

### Pattern 1: Basic 3-Phase Workflow
See `examples/01_basic_workflow.py`

### Pattern 2: Phase Instructions
Add `PhaseContextProvider` to inject phase instructions

### Pattern 3: Cross-Phase Discovery
Agents publish `WorkDiscovery` in any phase

### Pattern 4: Work Orchestration
Add `PhaseOrchestratorComponent` for monitoring

## Troubleshooting

**Q: Agents not consuming work?**
- Check phase matching in subscriptions (`where=lambda w: w.phase == "analysis"`)
- Verify artifact types match

**Q: Workflow not branching?**
- Ensure agents publish `WorkDiscovery` artifacts
- Check that discovery phase matches agent subscriptions

**Q: Phase instructions not appearing?**
- Add `PhaseContextProvider` to flock
- Verify phase definitions are configured

## Resources

- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Complete guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Architecture details
- **[CODE_SNIPPETS.md](CODE_SNIPPETS.md)** - Code patterns
- **[examples/](examples/)** - Working examples

---

**Ready to build?** Start with `01_basic_workflow.py` and iterate from there!



