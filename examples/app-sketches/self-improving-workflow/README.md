# Self-Improving Workflow Engine

A powerful Flock-based system where AI agents discover, plan, implement, and validate work—with workflows that **build themselves** as agents discover what needs to be done.

## 🎯 What is a Self-Improving Workflow?

Traditional AI workflows are **rigid pipelines**: you define every step upfront, and if reality doesn't match your plan, the workflow breaks.

**Self-Improving Workflows** are different. They're **semi-structured**:

- ✅ **Structure where it matters**: Phase types define work categories (Analysis → Implementation → Validation)
- ✅ **Flexibility where you need it**: Agents discover work and spawn new tasks dynamically
- ✅ **Emergent intelligence**: Workflows branch and adapt based on what agents actually find

### Example: Building Software

You start with one task: "Build authentication system."

1. **Analysis Agent** reads requirements, identifies 5 components → spawns 5 implementation tasks
2. **Implementation Agents** work in parallel, each building one component
3. **Validation Agent** tests one component, discovers optimization opportunity → spawns new analysis task
4. **New Analysis Agent** investigates → spawns implementation → spawns validation
5. **Workflow branches itself** - no one planned for this optimization!

The workflow structure **emerges** from the problem itself, not from a predefined plan.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              Blackboard (Phase-Aware Artifacts)          │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │Analysis  │→ │Implement │→ │Validate  │             │
│  │ Discovery│  │   Task   │  │  Result  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│       ↑                              ↓                  │
│       └────────── Discovers ──────────┘                 │
│                  (Self-Building!)                        │
└─────────────────────────────────────────────────────────┘
      ↑              ↑              ↑
  Phase 1        Phase 2        Phase 3
  Agents         Agents         Agents
```

**Key Concepts:**

1. **Phases**: Work categories (Analysis, Implementation, Validation)
2. **Work Discoveries**: Agents publish discoveries that need work
3. **Phase-Aware Subscriptions**: Agents consume only work from their phase
4. **Cross-Phase Discovery**: Agents can spawn work in ANY phase
5. **Emergent Cascades**: Workflows build themselves through artifact subscriptions

## 🚀 Quick Start

```python
from flock import Flock
from examples.full_projects.self_improving_workflow.artifacts import (
    WorkDiscovery, AnalysisResult, Implementation, ValidationResult
)

# Create workflow
flock = Flock("openai/gpt-4.1")

# Define phase-aware agents
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
    .publishes(ValidationResult, WorkDiscovery)  # Can discover new work!
)

# Start workflow
await flock.publish(WorkDiscovery(
    description="Build authentication system",
    phase="analysis"
))

await flock.run_until_idle()
# ✨ Workflow builds itself as agents discover work!
```

## 📚 Documentation

- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Complete step-by-step implementation guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed architecture and design decisions
- **[CODE_SNIPPETS.md](CODE_SNIPPETS.md)** - Reusable code patterns and examples
- **[examples/](examples/)** - Working examples at different stages

## 🎓 Learning Path

1. **Start Here**: Read [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the complete roadmap
2. **Understand Design**: Review [ARCHITECTURE.md](ARCHITECTURE.md) for design decisions
3. **Build MVP**: Follow Phase 1 of the implementation plan
4. **Iterate**: Add features incrementally (Phase 2, 3, 4...)
5. **Customize**: Adapt patterns from [CODE_SNIPPETS.md](CODE_SNIPPETS.md) for your use case

## ✨ Key Features

- **Phase-Based Work Organization**: Clear work categories with specialized agents
- **Dynamic Work Discovery**: Agents spawn new work based on discoveries
- **Cross-Phase Branching**: Workflows adapt by spawning work in any phase
- **Automatic Parallelization**: Flock's blackboard enables parallel execution
- **Real-Time Visualization**: Dashboard shows workflow structure emerging
- **No Predefined Paths**: Workflows build themselves from discoveries

## 🤝 Contributing

This is a reference implementation. Feel free to:
- Adapt patterns for your use cases
- Extend with new phase types
- Add validation and monitoring
- Integrate with external systems

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for extension points.



