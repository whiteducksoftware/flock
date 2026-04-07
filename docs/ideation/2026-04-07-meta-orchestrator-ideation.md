---
date: 2026-04-07
topic: flock-meta-orchestrator
focus: Extending Flock from internal LLM-call agents to orchestrating external autonomous coding agents (Claude Code, Codex, Gemini CLI, Aider) using the blackboard pattern
---

# Ideation: Flock as Meta-Orchestrator for Autonomous Agents

## Codebase Context

**Project:** Flock — blackboard-based AI agent orchestration framework. Python 3.12+, 2300+ tests, 77% coverage. Current version v0.5.310 ("Raven").

**Architecture:** Agents declare `.consumes(Type)` and `.publishes(Type)` using Pydantic models. The blackboard handles routing, triggering, lifecycle. No direct agent coupling. Five visibility types (Public, Private, Tenant, Labelled, After). Components system (orchestrator/agent/server). Fan-out publishing, BatchSpec/JoinSpec, Until DSL, scheduling, webhook delivery, idempotency, OpenTelemetry tracing.

**Key Prior Art Already in Knowledge Base:**
- **ClawBoard concept** — fully designed coordination layer for external agents. 14 typed artifact types (WorkItem/WorkClaimed/WorkResult + Lock types + Baton-Pass types), lock arbiter, worker loop, identity mapping. Separates Coordination Plane (Flock) from Actuator Plane (external agents).
- **MAF comparison** — identifies checkpointing as P0 gap, agent-as-tool pattern missing, A2A protocol support absent.
- **Communication stack research** — 4-layer model: Protocol → Discovery → Shared State → Workflow Optimization. Current protocols handle shared state poorly. memX pattern as reference implementation.
- **Agent separation framework** — external coding agents score "yes" on all 4 axes (expertise, parallelism, context, reusability) — definitively separate agents, not skills.

**Landscape (April 2026):** 60+ orchestration projects. Tier 1 (actual external agent orchestration): Overstory (1.2k stars, hierarchical SQLite mail), ComposioHQ Agent Orchestrator (5.9k stars, git worktrees + CI fix loops), MCO (consensus scoring), Claude Code Agent Teams (experimental peer-to-peer), GitHub Squad (decisions.md proto-blackboard). Nobody has typed blackboard, zero-trust visibility, or declarative subscriptions that auto-wake agents.

**Grounding from Learnings Search:**
- Blackboard is pull-based — external agents need push
- Agent-specific output contamination requires normalization at write boundary
- Scratch space conventions apply to workspace isolation
- Six architectural patterns for agent teams: Pipeline, Fan-out/Fan-in, Expert Pool, Producer-Reviewer, Supervisor, Hierarchical Delegation
- "Pub/sub alone moves race conditions, doesn't remove them" — lock arbiter needed

## Ranked Ideas

### 1. Blackboard Changelog Stream (Push-Based Event Feed)
**Description:** Add a persistent, replayable changelog to the blackboard store — every publish, consumption, and state transition emits an ordered event with a sequence number. Expose as SSE/WebSocket stream AND pull-based cursor API. External agents subscribe to the stream rather than polling. The WebSocket infrastructure and SQLite WAL already exist.
**Rationale:** The single addition that makes 10 other things possible. Checkpointing = resume from sequence N. Push notifications = filtered stream subscriptions. Cross-instance replication = changelog shipping. Time-travel debugging = replay. Every future feature builds on this rather than being bespoke.
**Downsides:** Storage overhead. Retention policy needed. Stream backpressure for slow consumers.
**Confidence:** 90%
**Complexity:** Medium
**Status:** Unexplored

### 2. Flock-as-MCP-Server (Bidirectional MCP Bridge)
**Description:** Expose the Flock blackboard as an MCP server so any MCP-capable agent (Claude Code, Cursor, Windsurf, Gemini CLI) can natively `publish_artifact`, `subscribe`, and `query_blackboard` via standard MCP tool calls. Flock already has deep MCP client support — this adds the server side. The REST API already exposes the operations; MCP server is a thin protocol translation.
**Rationale:** MCP is becoming the universal agent integration protocol (~97M monthly SDK downloads). Instead of building per-agent integrations, build one MCP server and get every MCP-capable agent for free. Each new MCP agent in the ecosystem = free Flock distribution.
**Downsides:** MCP protocol still evolving. Server-side less mature than client-side. Subscription semantics may not map 1:1 to request/response.
**Confidence:** 85%
**Complexity:** Medium
**Status:** Unexplored

### 3. Typed Filesystem Bridge
**Description:** Materialize blackboard artifacts as validated JSON files in agent-specific workspace directories, and watch for new files to ingest back as artifacts. External coding agents write a file → Flock validates against Pydantic schema → publishes to blackboard. Visibility maps to per-agent directory scoping. No SDK, no HTTP client, no protocol — the filesystem IS the API.
**Rationale:** Every external coding agent already speaks filesystem. CORAL validates this pattern works in the wild. Zero-integration onboarding for any new agent. Combined with MCP Server (#2), this gives Flock two universal interfaces covering the entire agent landscape.
**Downsides:** File watching adds latency vs direct API. FUSE is complex (simpler watcher is more pragmatic). Filesystem semantics don't naturally express subscriptions.
**Confidence:** 75%
**Complexity:** High
**Status:** Unexplored

### 4. Agent Capability Manifests with Hot-Plug Registration
**Description:** Formalize each agent's behavioral contract as a machine-readable manifest: consumes, publishes, conditions, latency/cost expectations, engine type. Manifests are publishable to the blackboard, so agents discover and reason about each other at runtime. External agents register via REST endpoint or `AgentRegistration` artifact. `AgentSnapshotRecord` is already 70% of this.
**Rationale:** Makes "add a new agent without rewiring anything" real. Claude Code spins up, registers as CodeReviewer, works, departs — no config changes. Mostly elevating existing metadata from observability side-channel to first-class queryable primitive.
**Downsides:** Schema versioning for manifests. Stale registrations from crashed agents. Capability matching heuristics can be brittle.
**Confidence:** 85%
**Complexity:** Low-Medium
**Status:** Unexplored

### 5. Artifact Lineage Graph (Causal Provenance)
**Description:** Add `derived_from: list[UUID]` to `Artifact`. When an agent consumes artifact A and produces artifact B, automatically record derivation. Expose as queryable DAG through existing graph endpoint. Enables: root cause analysis, impact analysis, rollback, cost attribution per workflow path.
**Rationale:** Literally one field + a join table. `ConsumptionRecord` already tracks what was consumed. The orchestrator already knows which artifacts an agent consumed and produced. 90% built. Foundation for replay, rollback, debugging, and cost attribution. Every agent run enriches the graph.
**Downsides:** DAG queries expensive at scale. Lineage bloat for high-fan-out. Needs GC policy.
**Confidence:** 90%
**Complexity:** Low
**Status:** Unexplored

### 6. Subscription-as-Discovery Protocol (Kill A2A Dependency)
**Description:** Use Flock's `.consumes()/.publishes()` declarations as the universal agent capability description. An agent's subscription IS its capability contract. A schema registry exposes these as queryable discovery surface. External agents publish Pydantic schemas to the blackboard; the blackboard matches them to work automatically. No separate agent cards, no A2A protocol needed.
**Rationale:** A2A has spec traction but zero adoption in coding agents. Flock's subscriptions are already more expressive (predicates, semantic matching, batch/join specs, schedules). The subscription IS the registration. The type match IS the discovery. This is how you claim the protocol layer.
**Downsides:** Tightly couples discovery to Flock's type system. Less interoperable with non-Flock ecosystems. A2A could accelerate and make this a dead end.
**Confidence:** 80%
**Complexity:** Low-Medium
**Status:** Unexplored

### 7. Human-as-Agent (Unify HITL with Timer Scheduling)
**Description:** Model humans as agents with `ScheduleSpec(interval=timedelta(hours=8))`. Their "engine" is a notification system that renders pending artifacts. Approval/rejection is a typed `HumanDecision` artifact. No special HITL machinery — existing scheduling, subscriptions, and conditions handle it. A human can subscribe with `where=lambda x: x.confidence < 0.8` — they only see what needs review.
**Rationale:** Every orchestration framework treats HITL as a special case. If humans are slow scheduled agents, ALL of Flock's patterns apply automatically. Eliminates an entire category of special-case code using only existing primitives. The Hearsay-II architecture explicitly included human knowledge sources with different operating tempos.
**Downsides:** Humans are interrupt-driven, not polling. Notification system still needs building. "Human as agent" framing may confuse users.
**Confidence:** 80%
**Complexity:** Low
**Status:** Unexplored

## Honorable Mentions

**Speculative Execution / Try-Branches** — Race multiple agents on the same task, judge picks winner. Maps to CORAL's competitive model. Uses existing `partition_key` + `TenantVisibility`. Bold (5/5) but complex.

**Disagreement Resolution / Quorum Artifacts** — `QuorumSubscription` collects N artifacts from different agents, detects disagreement via comparator, routes to arbiter. Real problem when multiple agents review the same PR. Extends JoinSpec.

**Cost Accounting & Budget Enforcement** — Per-agent, per-correlation budget with `BudgetGuard` orchestrator component. Composes with existing `When` activation conditions. Operational necessity at scale.

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Checkpoint/WAL | Subsumed by Changelog Stream — checkpointing is a feature of the event log |
| 2 | Agent Heartbeat Protocol | Operational component, not vision-level architecture |
| 3 | Artifact Translation/Normalization | Covered by Schema-as-Contract within Capability Manifests |
| 4 | Kill Agent Sessions (stateless only) | Too extreme — `--resume` is genuinely valuable |
| 5 | Pull-Only / Claim-Based | Changelog with push+pull is strictly better |
| 6 | Cryptographic Envelopes | Over-engineered — visibility system works, crypto is additive later |
| 7 | Natural Language Auto-Wiring | "Use LLMs to configure LLM coordination" is circular |
| 8 | Orchestrator as pyproject.toml | Premature — Python API is still the right level |
| 9 | Git Branches as Artifact Partitions | Conflates versioning with coordination |
| 10 | LLM Broker (centralize all LLM calls) | Bottleneck for agents with built-in LLM access |
| 11 | Contamination Firewall / Namespaces | Covered by TenantVisibility + Capability Manifests |
| 12 | Adversarial Sandbox / Capability Tokens | Important for enterprise, premature for vision |
| 13 | Federated Blackboards / Gossip | Too ambitious — single-instance first |
| 14 | Temporal Replay / What-If Branching | Subsumed by Changelog + Lineage |
| 15 | Semantic Subscription Mesh at Scale | Optimization, not vision |
| 16 | Deterministic Workflow Replay | Subsumed by Changelog + Lineage |
| 17 | Cross-Workflow Artifact Referencing | Subsumed by Federation (deferred) |
| 18 | Observability-Driven Self-Healing | Premature — need basic checkpointing first |
| 19 | Workflow Templates | DX improvement, not architectural direction |
| 20 | Agents Work on Schemas Not Code | Too radical — agents need to touch code |
| 21 | Merge Semantics for Concurrent Artifacts | Covered by Disagreement Resolution pattern |
| 22 | Cost/Budget Enforcement | Real but operational, not vision-level |
| 23 | Visibility Information Gradients | Novel but heavy — reworks core return type |
| 24 | Distributed Blackboard Sharding | Scale problem for later |
| 25 | Blackboard-as-FUSE-Mount | FUSE is a liability — simpler watcher approach captured in Filesystem Bridge |
| 26 | Embedded Orchestrator Config | Premature abstraction |

## Session Log
- 2026-04-07: Initial ideation — 48 raw ideas from 6 parallel sub-agents (pain/friction, unmet needs, inversion/removal, assumption-breaking, leverage/compounding, edge cases/power-user), ~25 unique after dedup, 4 cross-cutting combinations identified, 7 survivors + 3 honorable mentions after adversarial filtering. Grounded in web research (60+ competing projects analyzed), QMD memory search (ClawBoard concept, MAF comparison, communication stack, agent separation framework), and codebase scan.
