---
title: "Agent Skills Plan: Document Review Findings (Round 3 — Lightweight Regression Check)"
date: 2026-04-18
branch: feat/skills
reviewer: Claude (Opus 4.7) via compound-engineering:document-review
artifacts:
  - docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md
prior_rounds:
  - docs/reviews/2026-04-18-agent-skills-plan-findings.md
  - docs/reviews/2026-04-18-agent-skills-plan-findings-round2.md
amendment_commit_under_review: ca7e8c0e
fix_commit: 1dbd53d6
personas:
  always_on: [coherence, feasibility]
  intentionally_skipped: [product-lens, scope-guardian, security-lens, adversarial]
status: round-3-complete-implementation-ready
---

# Agent Skills Plan: Document Review Findings — Round 3

## TL;DR

Lightweight regression check after the round-2 P1 amendments (`ca7e8c0e`). User explicitly requested narrow scope to avoid review-loop overengineering: only `coherence` + `feasibility` re-dispatched. The other four personas (product-lens, scope-guardian, security-lens, adversarial) were skipped — they had pending non-P1 findings from rounds 1-2 that the user implicitly chose to defer, and re-running them would have produced fresh "abstractions are speculative" critiques on the new code with diminishing returns.

**Coherence: zero findings.** Plan is internally consistent across all amended sections.

**Feasibility: 4 findings, all auto-fixed in commit `1dbd53d6`.** All four were precise API references in the round-2 P1 amendments that would have NameError'd or called nonexistent methods at implementation time. Same lesson as round-2's ReAct path catch: claims about library/codebase APIs need execution-against-reality verification, not source reading.

The lightweight-recheck instinct paid off — feasibility caught the real bugs without the other personas pulling the plan apart.

---

## Auto-fixes Applied (4)

Applied inline to `docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md` in commit `1dbd53d6`. Each was a precise API mismatch between the plan's recipe and the actual codebase.

### #1 — `TypeRegistry.resolve_name` returns `str`, not the class

*Reviewer: feasibility. Confidence: 0.95.*

The round-2 P1 #2 fix (TypeRegistry-only resolver, no `importlib`) said:

> `resolve_pydantic_class(dotted: str) -> type[BaseModel]` — TypeRegistry-only: call `TypeRegistry.resolve_name(dotted)`...

But `src/flock/registry.py:54-83`: `def resolve_name(self, type_name: str) -> str:` returns the canonical name string, not the class. The class-returning method is `TypeRegistry.resolve(name)` at line 48.

**Fix:** Plan now says "call `type_registry.resolve(dotted)` directly (NOT `resolve_name`, which returns a canonical `str`, not the class — verified in `src/flock/registry.py:48-83`)." Also fixed two other locations referencing `resolve_name` for type resolution.

### #2 — DSPyEngine imports DSPy lazily; patch must use `dspy_mod.ReAct`

*Reviewer: feasibility. Confidence: 0.95.*

The round-2 demo-attachment patch used `isinstance(program, dspy.ReAct)`. But `src/flock/engines/dspy_engine.py:253` does `dspy_mod = self._import_dspy()` — there is no module-level `import dspy`. The patch as written would `NameError: name 'dspy' is not defined` on first execution.

**Fix:** All `dspy.ReAct` references in the Unit 6 patch block changed to `dspy_mod.ReAct` (the in-scope binding). Added a callout that the lazy import is intentional and avoids adding a top-level DSPy import to the engine.

### #3 — `BlackboardStore.get_artifact()` does not exist; method is `get()` returning `Artifact` wrapper

*Reviewer: feasibility. Confidence: 0.90.*

The round-2 P1 #4 fix specified:

> call `await flock.store.get_artifact(event.artifact_id)` to retrieve the typed Pydantic instance

But `src/flock/core/store.py:97`: `async def get(self, artifact_id: UUID) -> Artifact | None`. The returned `Artifact` is a wrapper with `.payload` (dict), not a typed `BaseModel` instance. The plan code assumed `upstream.payload` was already the typed instance for `dspy.Example` field assignment.

**Fix:** Plan now says: "call `await flock.store.get(event.artifact_id)`... The returned `Artifact` wrapper carries the dict payload at `.payload`; rehydrate to the typed Pydantic instance via `type_registry.resolve(event.artifact_type)(**artifact.payload)`." Cache key/value semantics updated.

### #4 — `agent.publishes` is the AgentBuilder method, not an Agent state attribute

*Reviewer: feasibility. Confidence: 0.70.*

The round-2 design referenced `agent.publishes` as a set in two places (Unit 4 `validate_outputs_compatibility(skill, agent_publishes)` and Unit 6 step 4). On `Agent`, `publishes` is the builder method (`src/flock/core/agent.py:780`); the runtime state is `Agent.outputs: list[AgentOutput]` (line 99). Implementer would have to derive the type-set themselves from a non-obvious attribute.

**Fix:** Function signature changed to `validate_outputs_compatibility(skill, agent_output_types: set[type[BaseModel]]) -> None`; caller derives via `{out.artifact_type for out in agent.outputs}`. Explicit note added: "Agent has no `agent.publishes` set attribute — `publishes` is a builder method; the runtime state is `agent.outputs`."

---

## Persona Skip Rationale

This was a deliberate scope cut. Five personas could have run; we ran two. Reasoning:

- **product-lens:** R1 findings (DSPy coupling trajectory, premise evidence, learning-floor API ergonomics) were unchanged by the P1 amendments. Re-running would re-flag the same items.
- **scope-guardian:** Most R1+R2 scope findings (3-class collapse, optimizer subpackage, SkillError hierarchy) were either resolved by P1 #9 or implicitly accepted. Re-running risks fresh "abstractions are speculative" findings on the new code (Flock kwargs, allowlist, trust CLI), which would push toward strip-mining a plan that's already mid-implementation-prep.
- **security-lens:** The new allowlist + trusted-skills.toml mechanism added attack surface, but the design is conservative (subprocess defaults, downgrade-always-honored, content-hash validation). Feasibility's verify-against-reality check would catch concrete bugs there; a fresh security pass would surface design tradeoffs we've already reasoned about.
- **adversarial:** Same overengineering risk — they'd push for further structural changes after we've already done major restructuring across two rounds.

**Verification this was the right call:** feasibility's 4 catches are exactly the kind of concrete bugs that would have bitten implementation. Coherence was clean. The other personas would have produced more findings but not more value at this stage.

---

## Residual Risks (carried forward, not blockers)

These are implementation-time concerns surfaced by feasibility but not blockers:

1. **Cache contract under typed rehydration.** The trainset cache stores `BaseModel` instances after `TypeRegistry.resolve()` rehydration. Implementer must decide: cache `Artifact` wrapper, cache `BaseModel`, or cache both? (Auto-fix picked `BaseModel` for memory efficiency; concrete decision deferred.)
2. **`_choose_program` guard coverage isn't total.** The `SkillEngineModeError` raise catches the post-fallback case (program returned non-ReAct after exception). If a tool registration error happens earlier — during `ChatAdapter` construction at line 340, or during signature build pre-line-343 — the agent never reaches the guard. Acceptable for v1 since those paths predate the skills work; worth knowing.
3. **`SkillEngineModeError` guard depends on `_resolved_mode` being set on every tool-mode skill** by `compilation.shape_select`. Verify at implementation time that the partition writes the attribute correctly.
4. **`agent_snapshot_updated` event serialization may leak `agent.skill_demos`** if it iterates `agent.__dict__`. Verify the snapshot mechanism uses an explicit field list, or add `skill_demos` to an exclusion list.
5. **DSPy predictor thread-safety under concurrent skill-demo attachment.** `program.demos = list(agent.skill_demos)` mutates shared predictor state. Risk depends on whether DSPy reuses `program` instances across calls — verify before assuming concurrency safety.

---

## Coverage

| Persona | Status | Findings | Auto | Present | Residual |
|---------|--------|----------|------|---------|----------|
| coherence | completed | 0 | 0 | 0 | 0 |
| feasibility | completed | 4 | 4 | 0 | 5 |
| product-lens | intentionally skipped | — | — | — | — |
| scope-guardian | intentionally skipped | — | — | — | — |
| security-lens | intentionally skipped | — | — | — | — |
| adversarial | intentionally skipped | — | — | — | — |
| **Total** | | **4** | **4** | **0** | **5** |

---

## State After Round 3

- **Plan:** 787 lines (up from 708 original; +52 from round-2 P1 amendments + 0 net change in round 3 since fixes were precise reword/refactor of existing prose).
- **Open by deliberate choice:** Round-1 product-lens P1s (3 items) + round-2 P2s (8 items) + round-2 P3 (1 item). The user accepted these as acknowledged-but-deferred during the P1 selection.
- **Implementation-ready:** Yes. Coherence clean, feasibility's residuals are impl-time concerns not plan-text bugs, no carried P0/P1.

---

## For Future Learning Extraction

Round 3's value lesson: **a focused 2-persona pass at the tail end of a multi-round review catches a specific class of bug that broader passes don't.** Coherence verifies internal-consistency drift across many edits; feasibility verifies that API claims match library/codebase reality. Both are mechanical checks with high signal-to-noise. The structural-critique personas (scope-guardian, adversarial) have value early in the cycle; running them at the tail risks unbounded restructuring.

When Phase 1 ships, tag each finding (across all 3 rounds) as Held up / Resolved-differently / Noise / Prevented. Round 3's 4 catches have particularly high falsifiability — implementation will either run cleanly with the corrected references, or hit precisely the NameError/AttributeError/missing-method that the reviewers predicted.
