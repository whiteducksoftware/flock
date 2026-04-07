---
date: 2026-04-07
topic: meta-orchestrator
---

# Flock Meta-Orchestrator: Vision & Changelog Stream Spec

## Vision Manifest — The Red String

Flock extends from orchestrating internal LLM-call agents to orchestrating **external autonomous coding agents** (Claude Code, Codex, GitHub Copilot, Gemini CLI, Aider) using the same blackboard pattern. External agents become first-class blackboard participants: they subscribe to typed artifacts, get woken up when matching artifacts appear, do their work, and publish results back.

### The 7 Pieces (Build Order)

```
┌─────────────────────────────────────────────────────────┐
│  1. CHANGELOG STREAM            ◄── THIS SPEC           │
│     Persistent event log + push subscriptions           │
│     Foundation for everything else                      │
├─────────────────────────────────────────────────────────┤
│  2. EXTERNAL AGENT RUNTIME      ◄── THIS SPEC           │
│     Protocol for spawning/resuming external agents      │
│     Adapters: Claude Code, Codex, Copilot               │
├─────────────────────────────────────────────────────────┤
│  3. CAPABILITY MANIFESTS                                │
│     Machine-readable agent contracts + hot-plug         │
│     Enables self-organizing agent ecosystems            │
├─────────────────────────────────────────────────────────┤
│  4. ARTIFACT LINEAGE                                    │
│     derived_from: list[UUID] on every artifact          │
│     Enables debugging, rollback, cost attribution       │
├─────────────────────────────────────────────────────────┤
│  5. FLOCK-AS-MCP-SERVER                                 │
│     Blackboard exposed as MCP tools                     │
│     Native integration for MCP-capable agents           │
├─────────────────────────────────────────────────────────┤
│  6. SUBSCRIPTION-AS-DISCOVERY                           │
│     Type contracts as the agent capability protocol     │
│     Eliminates need for external discovery protocols    │
├─────────────────────────────────────────────────────────┤
│  7. HUMAN-AS-AGENT                                      │
│     Humans modeled as slow, scheduled agents            │
│     HITL via existing primitives, no special machinery  │
└─────────────────────────────────────────────────────────┘
```

**Dependency graph:** 1 → 2 → 3. Items 4-7 are independently buildable after 1. Item 2 needs 1 for push-based agent wake-up.

### Validation Workflows

**Primary — OpenClaw on Blackboard:** Move Claude + Codie PR review coordination from Discord chat to typed blackboard artifacts. Discord adapter writes to blackboard, agents subscribe, review results flow back through the blackboard. Proves: adapters, subscriptions, external agent wake-up, security boundaries.

**Secondary — CORAL-style Research Loop:** Multiple agents competing on a graded task. Grader publishes `EvalResult`, agents subscribe and publish `Attempt` artifacts, cascade continues. Proves: competitive/collaborative multi-agent coordination.

---

## Problem Frame

Flock's blackboard currently triggers internal agents via an in-process scheduler. External autonomous coding agents (Claude Code, Codex, GitHub Copilot) cannot participate because:

1. **No push mechanism** — The blackboard is pull-based. External agents have no way to learn about new artifacts without polling.
2. **No agent lifecycle management** — Flock cannot spawn, resume, or communicate with external agent processes.
3. **No return path** — External agents have no authenticated way to publish artifacts back to the blackboard.

This spec addresses all three by adding a **changelog stream** (push infrastructure) and an **external agent runtime** (lifecycle + return path).

### End-to-End Flow

```
 Human / Adapter / Internal Agent
          │
          ▼
 ┌─────────────────┐
 │   BLACKBOARD     │──── publish() ────┐
 │   (typed store)  │                   │
 └─────────────────┘                   ▼
                              ┌─────────────────┐
                              │ CHANGELOG STREAM │
                              │ (ordered events  │
                              │  with seq nums)  │
                              └────────┬────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
            │ SSE/WebSocket│  │ Internal      │  │ Pull cursor  │
            │ push stream  │  │ scheduler     │  │ API          │
            │ (filtered)   │  │ (existing)    │  │ (catch-up)   │
            └──────┬───────┘  └──────────────┘  └──────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │ EXTERNAL AGENT   │
         │ RUNTIME          │
         │ ┌──────────────┐ │
         │ │ Claude Code  │ │    session mode:
         │ │ Codex        │ │    new / resume / append
         │ │ Copilot      │ │
         │ └──────────────┘ │
         └────────┬─────────┘
                  │
                  ▼  publishes result via REST API
         ┌─────────────────┐
         │   BLACKBOARD     │──── triggers next cascade
         └─────────────────┘
```

## Requirements

**Changelog Stream**

- R1. Every blackboard state change (artifact published, artifact consumed, agent snapshot updated) emits an ordered event with a monotonically increasing sequence number. Sequence numbers may have gaps (e.g., on transaction rollback); consumers must be gap-tolerant.
- R2. Events are persisted durably alongside the blackboard store (SQLite for the default store).
- R3. Events are exposed via two stream endpoints: SSE (primary, simpler for external agents, auto-reconnects) and WebSocket (for dashboard and interactive consumers). Both are filterable by artifact type, agent, correlation ID, and visibility — each subscriber only receives events for artifacts their `AgentIdentity` is permitted to see. Same event source, two delivery mechanisms.
- R4. Events are exposed as a pull-based cursor API (`GET /events?after=<seq>&limit=N`) for catch-up and batch consumption.
- R5. A configurable retention policy controls event storage (by age, by count, or by storage size). Default: 7 days.
- R6. The changelog stream is the unified foundation for ALL agent triggering — internal agents use the existing in-process path (fast, no change), external agents use stream subscriptions (async). Same event source, two delivery mechanisms.

**External Agent Runtime**

- R7. An `ExternalAgentRuntime` protocol (Python Protocol class) defines the interface for spawning, resuming, and communicating with external agent processes. Runtime adapters MUST NOT interpolate artifact payloads into shell commands — payloads are passed via stdin, temporary files, or structured IPC to prevent command injection.
- R8. Three session modes are supported per subscription: `new` (fresh session every trigger), `resume` (continue same session with agent-specific resume mechanism), `append` (inject artifact into a running session).
- R9. Session mode is configurable per subscription, not per agent — the same agent can have different session policies for different artifact types.
- R10. Three runtime adapters ship with this spec: Claude Code, Codex, GitHub Copilot. Each adapter implements the `ExternalAgentRuntime` protocol and knows its agent's CLI semantics, instruction file format, and session persistence model.

**Return Path & Authentication**

- R11. External agents publish artifacts back to the blackboard via Flock's REST API using typed Pydantic-validated payloads.
- R12. Each external agent is issued a scoped API token tied to its `AgentIdentity`. The token determines which artifact types the agent can read and publish. Tokens are generated with cryptographic randomness, stored as salted hashes (never plaintext), and support TTL expiration.
- R13. Flock's existing visibility system (Public, Private, Tenant, Labelled, After) applies to external agents identically to internal agents — no separate security model. Token scoping (type-level ACL) is evaluated first, then visibility filtering. Scope violations return HTTP 403.
- R14. Token management (create, revoke, list) is available programmatically. Tokens are injected into spawned agent processes via environment variables. The token list endpoint does not expose raw token values.
- R14a. Auth is a distinct sub-deliverable: the current REST API has no authentication. This requires building token-based middleware (Bearer header extraction, token-to-AgentIdentity resolution, per-route enforcement) as a FastAPI dependency. The existing `AuthenticationComponent` server component provides the extension point.

**Integration with Existing Flock**

- R15. External agents are a distinct agent type — they do NOT use `EngineComponent.evaluate()`. Instead, an `ExternalAgentScheduler` matches changelog events to external subscriptions and uses `ExternalAgentRuntime` adapters (R7/R10) to spawn agent processes (fire-and-forget). Results come back via the REST return path (R11), which publishes to the blackboard and emits changelog events (R1), triggering the next cascade. External agents are registered with `.consumes()` / `.publishes()` like internal agents, but their execution model is fundamentally async: spawn → agent works → publishes back via REST → changelog event → cascade continues.
- R16. Existing Flock features (fan-out, BatchSpec, JoinSpec, semantic subscriptions, Until DSL, scheduling) work with external agents at the artifact protocol level. Time-windowed features (JoinSpec `within`, BatchSpec `timeout`) may need adjusted defaults for external agents due to their longer execution times (minutes vs. sub-second).
- R17. The real-time dashboard shows external agent status (spawned, running, idle, failed) alongside internal agents.

## Success Criteria

- SC1. An external Claude Code agent can be woken by a blackboard artifact, perform work, and publish a result — triggering a downstream internal agent cascade.
- SC2. The OpenClaw PR review workflow (Claude + Codie) can run entirely through the blackboard, decomposed as: (a) an adapter publishes a typed artifact to the blackboard, (b) an external agent subscription matches and triggers a wake-up, (c) the external agent publishes a result back via REST, (d) the result triggers a downstream cascade. Discord acts as an adapter that only reads/writes artifacts.
- SC3. Three runtime adapters (Claude Code, Codex, Copilot) pass integration tests demonstrating all three session modes (new, resume, append). Claude Code is the primary adapter; Codex and Copilot validate protocol generality.
- SC4. The changelog stream handles 1000+ events/second on the default SQLite store without degrading blackboard publish latency by more than 10%.
- SC5. An unauthorized agent (wrong token, wrong scope) is rejected when attempting to read or publish artifacts outside its allowed types.
- SC6. Internal agent cascades emit changelog events visible via SSE and cursor API — validating the changelog stream independently of external agents.

## Scope Boundaries

- **In scope:** Changelog stream, ExternalAgentRuntime protocol, three adapters (Claude Code, Codex, Copilot), API token auth, REST return path, dashboard integration.
- **Out of scope:** Capability manifests (#3), artifact lineage (#4), MCP server (#5), subscription-as-discovery (#6), human-as-agent (#7), federated blackboards, Kafka backend, cost tracking, filesystem bridge.
- **Explicitly deferred:** Gemini CLI and Aider adapters (follow-up after the protocol stabilizes). Cross-machine agent coordination (requires network transport layer beyond local). Agent-to-agent direct messaging (agents communicate only through the blackboard).

## Key Decisions

- **Unified event source:** The changelog is the single source of truth for all triggering, not a parallel system. Internal agents get fast in-process delivery; external agents get async stream delivery. Same events, two paths.
- **REST for return path:** External agents publish results via REST, not MCP or filesystem. REST is universal, typed, and works from any language. MCP server comes in a later spec (#5).
- **Per-subscription session policy:** Session mode (new/resume/append) is on the subscription, not the agent. The same Claude Code agent can start fresh for `BugReport` artifacts but resume for `CodeReview` artifacts.
- **API tokens, not shared secrets:** Each agent gets its own scoped token. This maps cleanly to Flock's existing `AgentIdentity` and visibility system.
- **Three adapters in v1:** Claude Code (primary, most mature), Codex (validates heterogeneity), GitHub Copilot (validates breadth). More adapters follow the established protocol.

## Dependencies / Assumptions

- Flock's REST API and WebSocket infrastructure are stable and sufficient for the stream endpoint (verified: `src/flock/api/` exists with FastAPI + WebSocket).
- Claude Code supports `--resume` for session continuity (verified: CORAL uses this).
- Codex CLI supports non-interactive execution mode (verified: Claude and Codex can start each other programmatically in practice).
- GitHub Copilot CLI supports programmatic invocation (verified: confirmed by project maintainer to offer equivalent features).

## Outstanding Questions

### Deferred to Planning

- [Affects R2][Technical] What's the optimal SQLite schema for the event log — separate table with sequence index, or extension of existing artifact table?
- [Affects R8][Technical] What are the exact CLI flags and session resume semantics for Codex and Copilot? (Capabilities verified, but invocation details need research during planning.)
- [Affects R10][Technical] How should the runtime adapters handle agent crashes and timeouts? Should this be in the runtime protocol or an orchestrator component?
- [Affects R5][Technical] What retention policy granularity is needed? Per-type retention? Per-correlation retention?
- [Affects R6][Technical] How does the unified event source integrate with the existing `AgentScheduler._persist_and_schedule` flow without breaking the hot path? Recommended approach: batch artifact insert + event insert in a single SQLite transaction, or use an AFTER INSERT trigger on the artifacts table. The plan must resolve this — it is the most load-bearing technical decision.

## Next Steps

→ `/ce:plan` for structured implementation planning.
