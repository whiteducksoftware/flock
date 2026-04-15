# Retro: Surface-First Development vs Spec-Driven Development

## The Experiment (Unintentional)

The same feature — external agent integration for Flock — was built twice by two instances of Claude Opus, working with the same human, on the same codebase, three days apart. Neither instance knew about the other's work.

**Approach A: Spec-Driven (ce:ideate + ce:brainstorm + ce:plan + ce:work)**
- April 7-12, 2026
- ~6 hours of research, ideation, brainstorming, requirements, planning
- ~6 hours of implementation + code review + bug fixing
- Produced: 129-line ideation doc (48 raw ideas, 7 survivors), 182-line requirements doc, 754-line implementation plan (10 units across 4 phases), ~1,700 LOC of implementation, ~1,600 LOC of tests

**Approach B: Surface-First Development (SFD)**
- April 15, 2026
- ~10 minutes
- Produced: A converged API surface, 9 backend contracts, acceptance criteria

Both approaches targeted the same user story: *"As a Flock user, I want to use Claude Code and Codex as external agents in my blackboard pipelines."*

## What Each Approach Produced

### Spec-Driven: The Documents

**Ideation** (2026-04-07): Six parallel sub-agents generated 48 raw ideas from different angles (pain/friction, unmet needs, inversion, assumption-breaking, leverage, edge cases). After dedup: 25 unique. After adversarial filtering: 7 survivors + 3 honorable mentions. Grounded in web research (60+ competing projects), QMD memory search (4 prior art hits), and full codebase scan.

The 7 survivors became a layered architecture vision:
1. Changelog Stream (push infrastructure)
2. External Agent Runtime (lifecycle management)
3. Capability Manifests (self-describing agents)
4. Artifact Lineage (causal provenance)
5. Flock-as-MCP-Server (universal protocol bridge)
6. Subscription-as-Discovery (kill A2A dependency)
7. Human-as-Agent (HITL via existing primitives)

**Requirements** (2026-04-07): 17 requirements (R1-R17), 6 success criteria, scope boundaries, 5 key decisions, 5 deferred questions. 182 lines.

**Plan** (2026-04-08): 10 implementation units across 4 phases. Each unit: goal, requirements trace, dependencies, files, approach, patterns to follow, test scenarios, verification criteria. 28 key technical decisions with alternatives-rejected rationale. Risk matrix. System-wide impact analysis. 754 lines.

### Surface-First: The Contract

Started from: *"What does the user type?"*

```python
flock.external_agent("claude-code")
    .command("claude", "--print", "--output-format", "json")
    .consumes(FeatureSpec)
    .publishes(Implementation)
```

Worked backward from that surface to discover:
- External agents are just agents with a different engine (`EngineComponent`, not `DSPyEngine`)
- No separate scheduler needed — the existing evaluation pipeline handles it
- 6 contracts: AgentBuilder methods, adapter registry, ExternalEngineComponent base, two concrete adapters, domain rules
- 9 acceptance criteria

## The Divergence Point

Both approaches agreed on the surface: `.consumes(Type).publishes(Type)` with adapter selection. The user-facing API is nearly identical.

They diverged on the internal architecture:

| Decision | Spec-Driven | Surface-First |
|----------|------------|---------------|
| **What is an external agent?** | A new scheduling concern | A different engine |
| **Triggering mechanism** | Changelog events via StreamDispatcher | Normal subscription/schedule path |
| **Core abstraction** | `ExternalAgentScheduler` (OrchestratorComponent) | `ExternalEngineComponent` (EngineComponent) |
| **Event routing** | Parallel system: per-agent queues, worker tasks, changelog subscription | Existing system: artifact published → subscription match → agent evaluate |
| **Result publishing** | External agent POSTs back via REST with bearer token | `evaluate()` returns objects, normal pipeline publishes |
| **Auth requirement** | Yes — tokens for REST return path | No — results come through the engine, not HTTP |
| **New infrastructure** | StreamDispatcher, ChangelogStreamComponent, TokenStore, AuthenticationHandler, ExternalAgentScheduler | One base class extending an existing abstraction |

The spec-driven approach built a **parallel execution system** alongside the existing one. The surface-first approach **reused the existing execution system** with a different engine.

## Why They Diverged

The spec-driven process started from the *problem space*:

> "The blackboard is pull-based. External agents have no way to learn about new artifacts."

This framing is correct for agents that are *independent processes running elsewhere*. It leads naturally to: push mechanism → changelog stream → stream subscriptions → separate scheduler → REST return path → auth tokens.

The surface-first process started from the *user's code*:

> "The user types `.adapter('claude_code')`. What's the minimum internal change to make that work?"

This framing sees that agents already get triggered by subscriptions and evaluated by engines. An external agent is just an engine that spawns a subprocess instead of calling an LLM. No new triggering mechanism needed.

**The spec-driven approach solved a harder problem than existed.** The "no push mechanism" premise assumed external agents needed to be notified externally. But Flock already has an internal notification mechanism (subscription matching + scheduling). If the external agent is just an engine, it doesn't need external notification — it gets triggered the same way every other agent does.

The surface-first approach couldn't make this mistake because it started from the integration point (the engine), not the communication problem (push vs pull).

## What Spec-Driven Got That SFD Didn't

The spec-driven approach wasn't wrong — it was solving a *larger* problem. Several things it produced are genuinely valuable and absent from the SFD output:

**The Changelog Stream itself.** Independent of external agents, a persistent event log with SSE/WebSocket delivery is valuable infrastructure. Dashboard monitoring, debugging, time-travel replay, cursor-based catch-up — none of this requires external agents. It's useful for any Flock deployment. SFD didn't produce this because it wasn't on the surface it was converging.

**The 7-piece vision.** Capability Manifests, Artifact Lineage, MCP Server, Subscription-as-Discovery, Human-as-Agent — these are real architectural ideas that compound. SFD didn't reach for them because they're beyond the immediate feature.

**Security analysis.** Stdin-based prompt passing (prevents flag injection), environment variable allowlisting (prevents secret leakage), cascade depth counters (prevents infinite loops), token scoping with per-agent identity, guard integration. SFD's contract mentioned none of this. These aren't nice-to-haves — they're production requirements.

**Session management.** Resume mode, per-subscription session policy, session store persistence. The SFD contract doesn't address conversational agents at all.

**Edge case catalog.** The plan's test scenarios enumerate 60+ specific edge cases across 10 units. SFD's 9 acceptance criteria are happy-path focused.

## What SFD Got That Spec-Driven Didn't

**The correct abstraction.** One thing, but the one thing that matters most. The engine-based approach eliminates ~700 LOC of scheduler, removes the StreamDispatcher dependency for triggering, removes the REST return path (and thus the auth requirement for basic operation), and makes external agents participate in all existing blackboard features naturally — because they're just agents.

**Time efficiency.** 10 minutes vs 12+ hours. Even accounting for the security/session/edge-case work that SFD deferred, the architectural decision was made in a fraction of the time.

**Simplicity as a forcing function.** By starting from "what does the user type?", SFD was structurally unable to introduce unnecessary infrastructure. The spec-driven approach had no such constraint — every well-reasoned requirement compounded into more infrastructure.

## The Hybrid Insight

Neither approach is complete alone:

- **SFD alone** produces the right architecture but misses security analysis, edge cases, session management, and the broader vision. It's a skeleton without muscle.
- **Spec-driven alone** produces comprehensive analysis but can lock in the wrong abstraction before anyone writes `.adapter("claude_code")` and asks "wait, why do we need a separate scheduler?"

The ideal workflow appears to be:

```
1. SFD first (10-30 min)
   → Converge on the API surface
   → Discover the minimum internal model
   → Produce contracts and acceptance criteria

2. Spec-driven review (1-2 hours)
   → Security analysis against the SFD contracts
   → Edge case enumeration
   → Session/lifecycle concerns
   → System-wide impact assessment
   → Vision-level features the surface doesn't demand

3. Implementation
   → Build the SFD architecture
   → With the spec-driven hardening
```

This inverts the traditional order. Instead of research → requirements → plan → surface, it's surface → architecture → hardening → plan. The surface constrains the architecture. The research hardens it.

## Metrics

| Metric | Spec-Driven | Surface-First |
|--------|------------|---------------|
| Time to architectural decision | ~6 hours | ~10 minutes |
| Documents produced | 3 (1,065 lines total) | 1 contract (~60 lines) |
| Correct core abstraction? | No (separate scheduler) | Yes (engine component) |
| Security coverage | Comprehensive | None |
| Edge case coverage | 60+ test scenarios | 9 acceptance criteria |
| Vision-level thinking | 7-piece architecture | Single feature |
| Implementation LOC | ~1,700 + ~1,600 tests | Not yet implemented |
| LOC that survives the correct architecture | ~750 (adapters, parsing, subprocess lifecycle) | All (by definition) |
| Wasted LOC | ~950 (scheduler, token auth for return path, changelog routing for triggering) | 0 |

## Skill Mechanics: Why SFD Succeeds Where CE Ideate/Brainstorm/Plan Doesn't

Reading the actual skill definitions reveals structural differences that explain the divergence. This isn't about one being "better" — it's about what each methodology's mechanics *force* the agent to do.

### CE Pipeline: Problem-Space Expansion

The CE pipeline (ideate → brainstorm → plan) is designed to be **thorough**. Each skill explicitly expands the problem space before narrowing it:

**ce:ideate** dispatches 3-4 parallel sub-agents, each with a different "ideation frame" (pain/friction, inversion, assumption-breaking, leverage). They generate ~30 raw ideas, dedupe to ~25, adversarially filter to 5-7. The skill literally says: *"Generate many → critique all → explain survivors only."*

**ce:brainstorm** then takes one survivor and explores it through collaborative dialogue. It runs a "Product Pressure Test" that asks: *"Is this the right problem? What happens if we do nothing? What durable capability should this create in 6-12 months?"* It produces a requirements document.

**ce:plan** takes the requirements and produces implementation units. It dispatches research agents (learnings search, best practices, framework docs). It requires: requirements trace, file paths, test scenarios, decisions with rationale, risk analysis, system-wide impact.

The pipeline's strength is **comprehensive coverage**. Its weakness is that **every step reinforces premises from the previous step**. Once ce:ideate frames the problem as "external agents need push notifications" and ce:brainstorm encodes that as requirement R15 ("External agents do NOT use EngineComponent.evaluate()"), ce:plan has no mechanism to question that framing. It faithfully plans implementation units for a separate scheduler because the requirements say so.

The pipeline amplifies: good premises produce excellent plans; wrong premises produce excellent plans for the wrong thing.

### SFD: Surface-Space Constraint

SFD works in the opposite direction. Its core mechanic is a **constraint function**:

> *"Identify the primary interaction surface. Build the smallest believable prototype that covers the critical path. Put it in front of the user quickly."*

The skill explicitly forbids:
- Starting with database schemas, backend architecture, or API design
- Asking for specs before building
- Building backend before the surface is converged

Phase 4 (Derive Contracts) only runs *after* convergence:
> *"Before writing any backend/internal code, extract what the converged surface demands."*

This means the internal architecture is **derived from the surface**, not designed from the problem space. When the surface is `.adapter("claude_code").consumes(A).publishes(B)`, the derived contract asks: "What's the minimum internal change to support this?" The answer is an engine swap — because that's what the surface demands, and the skill won't let you build more than the surface demands.

### The Structural Difference

| Mechanic | CE Pipeline | SFD |
|----------|------------|-----|
| **Starting point** | Problem space (what's broken, what's needed) | User's code (what do they type) |
| **Direction** | Outward expansion → narrowing → planning | Surface → convergence → inward derivation |
| **Architecture source** | Requirements (authored) | Contracts (derived from surface) |
| **Premise challenging** | Only within each phase (pressure test), not across pipeline stages | The surface itself challenges premises — if the surface is simple, the architecture must be simple |
| **Complexity bias** | Expansive — thorough analysis discovers real concerns that accumulate into infrastructure | Reductive — can't add infrastructure the surface doesn't demand |
| **Risk of over-engineering** | High — every well-reasoned requirement compounds | Low — the surface constrains what exists |
| **Risk of under-engineering** | Low — the pipeline catches edge cases, security, and lifecycle concerns | High — security, sessions, edge cases aren't on the surface |

### Why R15 Happened

The most load-bearing mistake in the CE pipeline was requirement R15:

> *"External agents are a distinct agent type — they do NOT use EngineComponent.evaluate(). Instead, an ExternalAgentScheduler matches changelog events to external subscriptions."*

This wasn't a careless error. It was a *well-reasoned* decision based on:
1. **ce:ideate** framed the problem as "the blackboard is pull-based, external agents need push" (correct observation)
2. **ce:brainstorm** encoded this as "changelog stream + external agent runtime" (reasonable architecture)
3. **ce:plan** faithfully designed the ExternalAgentScheduler as an OrchestratorComponent with its own queues and workers (correct implementation of the requirements)

Each step was internally consistent. The error was in step 1 — the framing assumed external agents need a *new* notification mechanism. But Flock already has one (subscription matching → scheduling → engine evaluation). The existing mechanism works if you treat external agents as a different engine.

SFD couldn't make this error because it doesn't start from "what notification mechanism do external agents need?" It starts from "the user types `.adapter('claude_code')`" and works backward to "what existing mechanism supports this?" The existing engine pipeline is the first thing you find.

### What CE Should Borrow From SFD

**A surface checkpoint before planning.** Between ce:brainstorm and ce:plan, there should be a gate: *"Write the user-facing API for this feature. Does the internal architecture you're about to plan match what the surface demands?"*

If the meta-orchestrator brainstorm had included this checkpoint, someone would have written:

```python
flock.agent("x").kind("external").adapter("claude_code").consumes(A).publishes(B)
```

...and then asked: "This looks like an agent with a different engine. Why are we building a separate scheduler?" R15 would have been challenged before 754 lines of plan were written.

### What SFD Should Borrow From CE

**Adversarial hardening after convergence.** SFD's Phase 4 (Derive Contracts) extracts what the surface demands, but it doesn't stress-test those contracts. CE's security analysis (stdin injection, env sanitization, cascade depth), edge case enumeration (60+ test scenarios), and vision-level thinking (7-piece architecture) are exactly what SFD's contracts need before implementation.

SFD's Phase 5 (Build Inward) should include a step: *"Before implementing the first slice, dispatch a security reviewer and edge case analyst against the derived contracts."*

### The Combined Methodology

```
SFD Phase 1-3: Surface → Converge → Contracts
    ↓
CE-style hardening: Security review + edge cases + lifecycle analysis
    ↓
CE-style planning: Implementation units + test scenarios + risk matrix
    ↓
CE-style execution: ce:work with review checkpoints
```

The surface prevents the wrong architecture. The CE pipeline hardens the right one.

## Takeaways

1. **Start from the surface.** Ten minutes of "what does the user type?" caught an architectural error that 6 hours of research didn't. The surface constrains the architecture more effectively than analysis does.

2. **Research amplifies the right architecture; it doesn't find it.** The spec-driven security analysis, edge case catalog, and vision thinking are valuable — but only when applied to the right foundation. Applied to the wrong abstraction, they produce well-documented unnecessary complexity.

3. **Problem framing determines architecture.** "External agents can't receive push notifications" leads to a push system. "External agents are agents with a different engine" leads to an engine swap. Same user story, same codebase, different framing, different architecture. The surface-first framing was correct because it started from the integration point, not the communication theory.

4. **Beware of well-reasoned requirements that create their own problems.** R15 said: "External agents do NOT use EngineComponent.evaluate()." This was stated as a design constraint, not discovered from the surface. It then required a parallel execution system (ExternalAgentScheduler), which required a push mechanism (StreamDispatcher), which required auth (TokenStore), which required token management (TokenManagementComponent). Each step was well-reasoned given the previous one. The chain was wrong from the first link.

5. **The spec-driven approach's strength is its weakness.** Thoroughness prevents you from questioning premises. When you've spent 6 hours building a requirements document, the requirements feel load-bearing. The 10-minute SFD output has no sunk cost — it's easy to throw away and redo.

6. **Neither approach is sufficient alone.** SFD finds the architecture. Spec-driven hardens it. The combination — SFD first, then targeted spec-driven analysis — appears to be strictly better than either alone.
