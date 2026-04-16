---
title: "Meta-Orchestrator: Artifact + Implementation Review"
date: 2026-04-16
branch: feat/meta-orchestrator
reviewer: Claude (Opus 4.7)
artifacts:
  - docs/ideation/2026-04-07-meta-orchestrator-ideation.md
  - docs/brainstorms/2026-04-07-meta-orchestrator-requirements.md
  - docs/plans/2026-04-08-001-feat-meta-orchestrator-plan.md
prior_review: docs/reviews/2026-04-12-meta-orchestrator-review.md
status: implementation-complete-with-architectural-debt
---

# Meta-Orchestrator: Findings Report

## TL;DR

The 7-piece vision (changelog stream + external agent runtime + 5 deferred pieces) was researched, planned, implemented, code-reviewed, and hardened over April 7-15. **All 10 plan units are checked off, the prior review's 19 P0/P1/P2 findings have applied fixes, 233 tests pass.** The feature ships and the API works (`flock.agent("x").kind("external").adapter("claude_code")...`).

But the SFD retro on April 15 (`docs/retro-sfd-vs-spec-driven.md`) caught a load-bearing architectural mistake: **R15's premise — "external agents do NOT use `EngineComponent.evaluate()`" — was wrong.** The right abstraction is an `ExternalEngineComponent`, not an `ExternalAgentScheduler`. The current implementation is ~700 LOC of working-but-unnecessary infrastructure (scheduler + StreamDispatcher routing + REST return path + token auth for that path). The auto-wiring facade in commit `8d923970` papers over it (example 01 dropped from 171 → 101 LOC) but doesn't fix the underlying shape.

You're holding two completed features bolted together: a **genuinely useful changelog stream** (independent value: dashboards, replay, audit) and a **misshaped external-agent execution path** (works, but doesn't belong as a parallel system).

---

## 1. The Three Artifacts

### Ideation (`2026-04-07-meta-orchestrator-ideation.md`, 129 lines)
Quality: high. Six parallel sub-agents → 48 raw → 7 survivors after adversarial filtering. Grounded in 60+ competing-project landscape scan, 4 prior-art QMD hits (ClawBoard, MAF comparison, communication stack, agent separation framework), full codebase scan. Rejection log (26 entries) is excellent — shows premises were stress-tested. Confidence/complexity/status fields on each survivor.

The 7-piece dependency graph (1 → 2 → 3, 4-7 independent after 1) is sound.

### Brainstorm / Requirements (`2026-04-07-meta-orchestrator-requirements.md`, 182 lines)
Quality: high *for the framing it adopted*. 17 numbered requirements (R1-R17), 6 success criteria, 5 key decisions, scope boundaries with explicit deferrals. The end-to-end flow diagram is clear.

**Load-bearing mistake (R15):** "External agents are a distinct agent type — they do NOT use `EngineComponent.evaluate()`. Instead, an `ExternalAgentScheduler` matches changelog events to external subscriptions." This single sentence sealed in the parallel-system architecture. The retro identifies this as the chain's first wrong link; everything downstream (scheduler → StreamDispatcher coupling → REST return path → auth tokens for that path) is consistent with R15 but unnecessary if R15 is reversed.

### Plan (`2026-04-08-001-feat-meta-orchestrator-plan.md`, 753 lines)
Quality: very high *as faithful implementation of the requirements*. 10 units across 4 phases, each with goal, requirements trace, files, approach, patterns to follow, test scenarios (60+ total), verification, risk matrix. 28 key technical decisions with alternatives-rejected rationale. Mermaid sequence diagram. System-wide impact analysis.

This is what spec-driven development looks like at its best — and exactly the failure mode the retro identifies: **"the pipeline amplifies. Good premises produce excellent plans; wrong premises produce excellent plans for the wrong thing."** Every implementation unit is well-designed for solving R15's problem, but R15 was the wrong problem to solve.

---

## 2. Implementation State

### What's built (all units `[x]` in plan)

| Unit | Path | Status |
|------|------|--------|
| 1 — ChangelogEvent + store protocol | `src/flock/models/changelog.py`, `src/flock/core/store.py` | ✅ |
| 2 — Atomic persist (SQLite + memory) | `src/flock/storage/sqlite/schema_manager.py` (v4 migration), `src/flock/orchestrator/artifact_manager.py` | ✅ |
| 3 — SSE + WebSocket + cursor API | `src/flock/components/server/changelog/{changelog_component.py, stream_dispatcher.py}` | ✅ |
| 4 — Retention policy | `src/flock/components/orchestrator/retention.py` | ✅ |
| 5 — Token model + store + bearer handler | `src/flock/auth/{token_models.py, token_store.py}`, `auth_component.py` | ✅ |
| 6 — Token management API | `src/flock/components/server/auth/token_management_component.py` | ✅ |
| 7 — Runtime protocol + scheduler | `src/flock/integrations/external/{runtime.py, scheduler.py, models.py}` | ✅ |
| 8 — Claude Code adapter | `src/flock/integrations/external/adapters/claude_code.py` | ✅ |
| 9 — Codex adapter | `src/flock/integrations/external/adapters/codex.py` | ✅ |
| 10 — Dashboard events | `src/flock/components/server/models/events.py`, `event_emitter.py` | ✅ |

Diff against `main`: ~11,600 LOC across 55 files (~1,700 src + ~3,800 tests + ~1,200 docs/examples + lock file).

### Tests
233 tests passing in the prior review (April 12). New test files:
- `tests/test_changelog_event.py` (327L), `test_changelog_store.py` (336L), `test_changelog_retention.py` (289L)
- `tests/test_token_auth.py` (414L), `tests/api/test_token_api.py` (296L)
- `tests/test_external_runtime.py` (784L), `test_claude_adapter.py` (605L), `test_codex_adapter.py` (579L), `test_external_dashboard.py` (323L)
- `tests/api/test_changelog_api.py` (774L)
- `tests/integration/test_meta_orchestrator_e2e.py` (821L) — covers SC1-SC6

### Documentation & examples
- `docs/guides/meta-orchestrator.md` (301L) — user-facing guide
- `examples/12-external-agents/01_claude_code_query.py` (101 LOC, auto-wired)
- `examples/12-external-agents/02_multi_agent_code_review.py` (243 LOC, **manual-wired** — not migrated to auto-wiring yet)

### Auto-wiring facade
Added in commit `8d923970` (April 15). `Flock._run_initialize()` (orchestrator.py:1212-1263) auto-detects agents with `kind("external")` and registers `ExternalAgentScheduler` + `StreamDispatcher` + adapter instances on the fly. This is what dropped example 01 from 171 → 101 LOC.

It's a real DX win for the surface, but the session retro is correct that it's "a facade over the wrong abstraction." Wiring is hidden, not eliminated.

---

## 3. Gap Between Plan and Reality

### Items the prior review flagged that are still residual risks
The April 12 review applied fixes for 19 P0/P1/P2 findings but explicitly left these unresolved:

- **`ExternalSessionStore` persistence:** plan says SQLite-backed; review notes in-memory only. (Code now has `SQLiteExternalSessionStore` class — needs verification it's used by default.)
- **Adapter code deduplication:** ~50 LOC duplicated between `claude_code.py` and `codex.py`.
- **Retention chunked DELETE:** plan promised batches of 500 with event-loop yields. Implementation does single DELETE under `_write_lock`.
- **`_build_prompt` enrichment:** strips `correlation_id` and `artifact_id` — external agents have no traceback handle.
- **Guard component:** stubbed/commented-out in scheduler. Plan made guards a major design point; implementation defers.
- **No audit logging** for token lifecycle.
- **`--dangerously-skip-permissions` on all adapters:** sandboxing punted to deployment.
- **InMemoryTokenStore accumulates revoked/expired tokens** without GC.

### Bugs / inconsistencies I found in this pass

1. **`examples/12-external-agents/02_multi_agent_code_review.py:170` calls `.produces(ReviewSummary)`** — `AgentBuilder` has no `produces()` method. Will `AttributeError` at first run. The correct method is `.publishes()` (used correctly two lines above). Easy fix; example never executed end-to-end.

2. **Example 02 still wires infrastructure manually** (`InMemoryTokenStore`, `ChangelogStreamComponent`, `AuthenticationComponent`, `ExternalAgentScheduler.set_token_store()`, `flock.add_component(...)`, `flock.add_server_component(...)`). After the auto-wiring commit, this should be 100+ LOC shorter and look like example 01. Unfinished migration.

3. **Auto-wiring only triggers when `agents` already contains externals at `_run_initialize` time.** If an external agent is added after `Flock` boot, no scheduler is wired. Plan didn't promise hot-add, but the surface implies it. Worth a docstring caveat.

4. **`SC4 — < 5ms p99 latency` measured at 15ms on WSL2** (per April 12 review). Spec ratchet was already loosened from R3's 1000+ events/sec to 50 events/sec; the 15ms result still sits 3× over the success bar. No production-grade benchmark exists.

---

## 4. The Architectural Question (the real finding)

This is the substance the retro put on the table and the plan's `[x]` checkmarks hide.

### What R15 cost
The plan committed to "external agents are a parallel system." That decision created:

| Component | LOC | Reason it exists | Reason it shouldn't |
|-----------|-----|------------------|---------------------|
| `ExternalAgentScheduler` | 686 | Match changelog events → spawn adapters | Subscriptions already match artifacts → engines |
| `StreamDispatcher` (for triggering) | 121 | Push events to scheduler | Internal scheduling already pushes to engines |
| Token auth + management | ~620 | Authenticate REST return path | If results return through `evaluate()`, no REST return path needed |
| Token API tests + integration | ~700 | Cover the above | Same |

That's ~2,000 LOC of "infrastructure for the wrong abstraction" by retro's accounting.

### What survives an `ExternalEngineComponent` refactor
- `ChangelogEvent` model, store protocol, SQLite schema v4, retention policy — **independently useful** for dashboards, audit, replay (the retro's own carve-out)
- SSE/WebSocket/cursor changelog API — same, for external observers (not for triggering external agents)
- Adapter subprocess code (`ClaudeCodeRuntime`, `CodexRuntime`) — unchanged, just called from a different lifecycle point
- Builder API surface (`.kind()`, `.adapter()`, `.session_mode()`, `.working_dir()`, `.spawn_timeout()`) — unchanged
- Most tests for changelog model/store/retention/adapters — unchanged
- Some tests for scheduler/token-auth-for-return-path — deletable
- Auto-wiring facade — collapses; engine selection is just a builder field

The retro's estimate ("~750 LOC survives, ~950 LOC wasted") matches what I see in the diff.

### Why this is worth surfacing now
The session memory's "Next Step" already says: *"Do the actual engine-component refactor (revert scheduler, implement ExternalEngineComponent)."* This report concurs with that plan. The longer the scheduler ships in user-facing examples, the more code reaches into it; the right time to revert is before downstream consumers form.

---

## 5. Methodology Observations (cross-cutting)

The retro covers this in depth; here's the operational distillation for future planning sessions:

1. **Add a "user-types-this" checkpoint between brainstorm and plan.** If R15 had been preceded by writing `flock.agent("x").kind("external").adapter("claude_code").consumes(A).publishes(B)`, the question "why is this an agent with one feature different and not a separate scheduling system?" would have surfaced before 753 lines of plan.

2. **Spec-driven adversarial review of premises, not just decisions.** The plan has alternatives-rejected lists for individual decisions (e.g., AFTER INSERT trigger vs. single transaction). It has no alternatives-rejected list for the framing assumption ("external agents need a separate scheduler"). The rejection log lives in ideation but is structured by *feature* (rejected ideas), not by *premise* (rejected framings).

3. **The plan's `status: completed` is honest about implementation but silent about architecture.** Consider a second status field: `architecture_validated: pending | accepted | superseded`. R15 would currently be `superseded`.

---

## 6. Recommendations

In priority order — these are options for the user to choose from, not a decided path:

### High priority
1. **Fix `examples/12-external-agents/02_multi_agent_code_review.py:170`** — replace `.produces()` with `.publishes()`. Trivial; unblocks the example.
2. **Decide on the engine-component refactor.** Options: (a) ship as-is and refactor in v0.6, (b) refactor on this branch before merging, (c) merge changelog stream + auth + adapters but rip out scheduler in favor of `ExternalEngineComponent`. Recommendation: (c). Keeps the genuinely useful infra; eliminates the load-bearing wrong abstraction; matches the retro's "hybrid methodology" insight.
3. **Migrate example 02 to auto-wiring** to match example 01's surface — or, if (c) above, rewrite both examples against the new engine-component surface.

### Medium priority
4. **Verify `SQLiteExternalSessionStore` is the default**, not `ExternalSessionStore` (in-memory). Resume mode silently breaks across restarts otherwise.
5. **Make `ChangelogStreamComponent` a public, optional, recommended add-on** independent of external agents. The retro is right that it has standalone value; surface that explicitly so users adopt it for dashboards/audit even without external agents.
6. **Replace `_build_prompt` with structured payload** including `correlation_id` and `artifact_id` in agent context. External agents can't trace back today.
7. **Land a real SC4 benchmark**, not the WSL2 15ms one-off. If the system can't sustain even 50 events/sec under load, that should be a known limit, not a relaxed-without-measurement bar.

### Low priority
8. **Extract adapter base class** for shared subprocess lifecycle (~50 LOC dedup).
9. **Chunked retention DELETE** (plan promised this).
10. **InMemoryTokenStore GC** for revoked/expired entries.
11. **Audit log for token lifecycle.**
12. **Implement the guard hook** the plan made first-class, or remove the references and ship without it.

---

## 7. What Worked

To balance the architectural critique:

- **The ideation phase was textbook.** Six adversarial frames, rejection log, prior-art search, landscape scan. If R15 was the failure mode, ideation wasn't where it happened.
- **The plan's research depth caught real production concerns** that SFD missed: stdin-only payload passing, env var allowlisting, cascade-depth fail-safe, per-token salt, scoped tokens. These survive the architectural shift; they apply to *any* external-agent execution path.
- **The April 12 code review caught 4 P0s and 11 P1s including the dispatcher-never-called bug** (artifact_manager.py:173) that would have shipped a completely broken push path. Without that review the feature would be visibly broken in addition to architecturally wrong.
- **Test coverage is serious** (~3,800 LOC). The 821-line E2E suite exercises SC1-SC6 with real subprocess flow.
- **The retro itself is a genuine artifact.** Documenting "we built the wrong thing and here's why" while the work is still on a feature branch (not after merge) is the rare healthy outcome.

---

## Appendix: Files Touched (high signal)

```
src/flock/models/changelog.py                        81L  new
src/flock/core/store.py                            +321L  protocol + SQLite + memory store
src/flock/storage/sqlite/schema_manager.py          +69L  v4 migration
src/flock/orchestrator/artifact_manager.py          +64L  atomic persist + cascade depth
src/flock/components/server/changelog/              483L  new package (component + dispatcher)
src/flock/components/orchestrator/retention.py     130L  new
src/flock/auth/                                    211L  new package
src/flock/components/server/auth/token_management_component.py  245L  new
src/flock/components/server/auth/auth_component.py  +56L  bearer handler
src/flock/integrations/external/                  1,718L  new package (runtime + scheduler + adapters + models)
src/flock/core/agent.py                             +68L  builder additions (.kind, .adapter, etc.)
src/flock/core/orchestrator.py                    +118L  auto-wiring
src/flock/components/server/models/events.py        +72L  external agent lifecycle events
src/flock/orchestrator/event_emitter.py            +111L  emit_external_agent_*
```

Implementation checklist: complete. Architecture review: superseded by SFD retro. Ship-readiness: depends on whether the engine-component refactor lands first.
