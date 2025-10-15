# Spec-Driven Development with Flock

**A complete reimagination of devflow as a blackboard orchestration system.**

## 🎯 What Is This?

This example demonstrates how to implement a full spec-driven development workflow using Flock's blackboard architecture. Instead of rigid command-based orchestration, agents collaborate emergently through typed artifacts on the blackboard.

## 📊 Current Status: **36% Complete** (2.5/7 phases)

### ✅ What's Working

**Phase 1: Artifact Types (COMPLETE)**
- 26 artifact types across 6 categories
- All types validated with Pydantic + `@flock_type`
- See: `artifacts.py`

**Phase 2: Specialist Agents (COMPLETE)**
- 19 specialist agents that react to specific artifact types
- 4 Research specialists (market, technical, security, UX)
- 4 Documentation specialists (PRD, SDD, PLAN, patterns)
- 4 Implementation specialists (backend, frontend, database, infrastructure)
- 4 Review & Validation specialists
- 3 Analysis specialists
- See: `agents.py`

**Phase 3: Orchestrators (STRUCTURE COMPLETE)**
- 4 main orchestrators (specify, implement, analyze, refactor)
- 4 helper coordinators (research_aggregator, phase_validator, etc.)
- Uses JoinSpec for research batching
- Uses BatchSpec for phase execution
- See: `orchestrators.py`

### 🚧 What's In Progress

- Orchestrator implementation logic (needs MCP tools for file I/O)
- MCP tool integration (filesystem + web search)
- End-to-end workflow examples

## 🏃 Quick Start - Test the Specialists!

Run the specialist validation example:

```bash
cd examples/08-spec-driven-development
uv run python 00_test_specialists.py
```

**Note:** This will take several minutes as the LLM agents actually execute!

### What You'll See

1. **Research Specialists in Parallel**
   - 4 research tasks published
   - All 4 specialists react simultaneously
   - 4 ResearchFindings artifacts created

2. **Documentation Flow**
   - ResearchFindings → PRDSection
   - PRDSection + ResearchFindings → SDDSection
   - Sequential building

3. **Implementation Routing**
   - Tasks routed by `activity_area` predicate
   - Backend, Frontend, Database, Infrastructure specialists
   - All execute in parallel

4. **Analysis Pattern Discovery**
   - AnalyzeRequest routed by `analysis_area`
   - PatternDiscovery artifacts created

## 🎨 Architecture

### The Blackboard Pattern

```
┌────────────────────── BLACKBOARD ──────────────────────┐
│                                                          │
│  SpecifyRequest → ResearchTask → ResearchFindings →     │
│  PRDSection → SDDSection → PLANSection →                │
│  SpecificationComplete                                   │
│                                                          │
│  ImplementRequest → PhaseStart → ImplementationTask →   │
│  CodeChange → ValidationResult → PhaseComplete          │
│                                                          │
└──────────────────────────────────────────────────────────┘
     ↑           ↑            ↑           ↑
  Orchestrator Researcher  Implementer  Validator
  (coordinates) (discover) (build)      (verify)
```

### Key Design Decisions

**Why Hybrid Approach?**
- Orchestrators coordinate high-level workflow
- Specialists handle focused tasks
- Blackboard enables emergent collaboration

**Why JoinSpec for Research?**
- Multiple research tasks fire in parallel
- Orchestrator waits for ALL findings before documenting
- Mirrors devflow's "wait for all agents" pattern

**Why BatchSpec for Implementation?**
- Tasks within a phase can run in parallel
- Size threshold = all tasks in phase
- Timeout = safety valve for long-running tasks

## 📁 File Structure

```
examples/08-spec-driven-development/
├── README.md                    # This file
├── artifacts.py                 # 26 artifact type definitions
├── agents.py                    # 19 specialist agent definitions
├── orchestrators.py             # 4 orchestrator + 4 helper agents
├── test_artifacts.py            # Artifact validation tests
├── test_agents.py               # Agent creation tests
└── 00_test_specialists.py       # Live specialist demo
```

## 🔄 Workflow Comparison

### Original DevFlow

```
User → /s:specify → Command Orchestrator → Task Agents (via prompts)
                     ↓
                  Uses natural language delegation
                  Agents read prompt files
                  Coordination via cycles
```

### Flock Implementation

```
User → SpecifyRequest → specify_orchestrator → ResearchTask (artifacts)
                         ↓                        ↓
                    Blackboard          research_* agents (subscriptions)
                         ↓                        ↓
                  PRDSection ← documenter_requirements
```

**Key Differences:**
- ❌ DevFlow: Natural language prompts, explicit delegation
- ✅ Flock: Typed artifacts, emergent subscriptions
- ❌ DevFlow: Command-based coordination
- ✅ Flock: Event-driven blackboard
- ❌ DevFlow: ~40 text files defining agents
- ✅ Flock: 19 declarative agent definitions

## 🎯 Next Steps

1. **Phase 4: MCP Tool Integration** - Add file I/O and web search
2. **Phase 5: Complete Examples** - Full specify/implement/analyze/refactor workflows
3. **Phase 6: Testing** - Validate against real features
4. **Phase 7: Documentation** - Polish and compare with devflow

## 📚 Learn More

- **Flock Docs**: [../../docs/](../../docs/)
- **Implementation Plan**: [../../docs/internal/spec-driven-example/implementation_plan.md](../../docs/internal/spec-driven-example/implementation_plan.md)
- **Blackboard Architecture**: [../../docs/guides/blackboard.md](../../docs/guides/blackboard.md)

---

**Status:** Under active development
**Progress:** 2.5/7 phases complete (36%)
**Last Updated:** 2025-10-15
