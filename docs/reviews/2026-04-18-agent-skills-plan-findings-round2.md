---
title: "Agent Skills Plan: Document Review Findings (Round 2 — Regression Check)"
date: 2026-04-18
branch: feat/skills
reviewer: Claude (Opus 4.7) via compound-engineering:document-review
artifacts:
  - docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md
prior_round: docs/reviews/2026-04-18-agent-skills-plan-findings.md
amendment_commit_under_review: c60336ce
personas:
  always_on: [coherence, feasibility]
  conditional: [security-lens, scope-guardian, adversarial]
  not_re_dispatched: [product-lens, design-lens]
status: round-2-complete-refinement-pending
---

# Agent Skills Plan: Document Review Findings — Round 2

## TL;DR

Round 2 was a focused regression check after the three P0 resolutions in commit `c60336ce`. **Five reviewers re-dispatched** (coherence, feasibility, security-lens, adversarial, scope-guardian); product-lens skipped because its round-1 findings (DSPy-coupling trajectory, premise evidence, learning-floor API) were untouched by the P0 amendments and re-running would just re-flag the same items.

**Two new P0s surfaced — both auto-fixed:**

1. **The engine-patch ReAct attribute paths were wrong.** Round-1 amendments specified `program.react.react.demos` and `program.react.extract.demos`, with the claim "verified in DSPy 3.0.3 source." Feasibility reviewer ran a live DSPy REPL and confirmed both raise `AttributeError`. Real `dspy.ReAct.__init__` does `self.react = dspy.Predict(...)` (so `.react` IS the inner Predict — has `.demos` directly, no further nesting) and `self.extract = dspy.ChainOfThought(...)` (which wraps a Predict at `.predict`). Correct paths: **`program.react.demos` + `program.extract.predict.demos`**. The original "verified" claim was unverified — this is a Claude-got-it-wrong call-out. Fix applied to 8 locations across the plan.

2. **`resolve_sandbox` self-contradicted on `./.claude/skills/`.** Round-1 P0 #3 fix said: paths under `project_root` → inprocess; paths under `~/.flock/skills/`, `./.claude/skills/`, or anything outside `project_root` → subprocess. But `./.claude/skills/` resolves UNDER `project_root` for any project that uses Claude Code (verified: this repo has `/home/pyro/projects/work/flock/.claude/skills/`). Test scenario said `./.claude/skills/foo/` → subprocess; the algorithm classified it as inprocess. Restructured as ordered precedence (frontmatter > managed-roots > in-repo > default-subprocess) with `Path.resolve()` canonicalization and `project_root` captured at `Flock.__init__` via marker walk-up (`pyproject.toml`/`flock.yaml`/`.git`).

**10 auto-fixes applied total** (full list below). **16 findings remain present** for author judgment, including 9 P1s — most are either carried-from-round-1 (resolve_pydantic_class code-exec, optimizer plaintext payloads, mode precedence ambiguity) or new structural critiques surfaced by the amendments themselves (no-upstream trainset coverage, three-class type collapse post-SkillsComponent, frontmatter inprocess override gating).

The plan is materially stronger than after round 1 — both new P0s were catchable mistakes that round-1 dispatch didn't have the live-verification angle to catch. Round 2's payoff is exactly the kind of deep cross-checking that justifies an adversarial second pass before code.

---

## What Changed Since Round 1

The amendment commit `c60336ce` resolved all three round-1 P0s by:

| P0 | Round-1 design | Round-1 amendment | Round-2 verdict |
|----|----------------|--------------------|-----------------|
| #1 Demo-attachment lifecycle | `SkillsComponent.on_pre_evaluate` (architecturally impossible — wrong signature, fires before engine evaluation) | Drop `SkillsComponent`. Stash demos on `agent.skill_demos` at config time; `DSPyEngine.evaluate` attaches them after `_choose_program` | **Mechanism right; ReAct paths in the patch were wrong** (NEW P0 caught + auto-fixed). Two-seam claim is post-hoc rationalization (P2 stands) |
| #2 Trainset input signal | Plan referenced `artifact_consumed` events with zero emitters in codebase | Switch to publish-to-publish correlation within `correlation_id`; document attribution noise for predicated/multi-skill agents | **Algorithm has zero coverage for no-upstream agents** (NEW P1) — CLI-triggered, scheduled, external publishes have no upstream events to pair |
| #3 Sandbox default | "Trust the skill author by default" (60% local-helpers rationale conflicted with R2 interop premise) | Path-based default — in-repo → inprocess; installed → subprocess | **Path rule self-contradicted on `./.claude/skills/`** (NEW P0 caught + auto-fixed). Frontmatter inprocess override on installed skills remains ungated (P1 stands) |

---

## Auto-fixes Applied (10)

Applied inline to `docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md`. No rewrite, no scope addition.

1. **Key Technical Decisions — ReAct demo paths corrected.** Old: `program.react.react.demos` + `program.react.extract.demos` (both AttributeError). New: `program.react.demos` + `program.extract.predict.demos`. Decision text now references "verified live against DSPy 3.0.3 (round-2 review 2026-04-18)" with explicit acknowledgment that earlier rounds had wrong paths. *(feasibility, 0.97)*
2. **Unit 6 engine-patch code block — corrected ReAct paths + `getattr` defensive read + `_choose_program` fallback caveat.** Demo block now uses `getattr(agent, "skill_demos", None)` to survive non-`__init__` Agent construction paths. Added implementation requirement: raise `SkillEngineModeError` (or WARN) when tool-mode skill agent gets degraded to Predict by `_choose_program` exception fallback, before demo attachment runs. *(feasibility + adversarial)*
3. **Unit 6 test scenarios + verification — ReAct path assertions updated** to match corrected paths. *(feasibility)*
4. **Lifecycle sequence diagram, Risks table, External References, Open Questions — ReAct paths corrected** (8 locations total swept). *(feasibility)*
5. **Unit 3 `resolve_sandbox` restructured as ordered precedence list.** Rules: (1) explicit frontmatter wins; (2) managed roots (`~/.flock/skills/`, `<project_root>/.claude/skills/`) → subprocess; (3) in-repo (under project_root) → inprocess; (4) anything else → subprocess. All paths canonicalized via `Path.resolve()` (closes symlink bypass). *(feasibility, 0.88)*
6. **`project_root` captured at `Flock.__init__` via marker walk-up** (`pyproject.toml` / `flock.yaml` / `.git`); falls back to `Path.cwd()` with WARNING. Eliminates `chdir()` race conditions between init and discovery. *(security-lens, 0.75)*
7. **Unit 3 sandbox test scenarios expanded** with 5 new cases: managed-root precedence over in-repo (`<project_root>/.claude/skills/foo/` → subprocess), symlink-resolution (symlink under `./skills/` pointing to `~/Downloads/external-pack/` → subprocess via rule 4), project-root stability across `chdir`. *(feasibility + security-lens)*
8. **Phased Delivery exit criteria — `examples/11-skills/` → `examples/13-skills/` at line 688** (missed by round-1 renumber sweep). *(coherence + adversarial, 0.95)*
9. **Unit 8 trainset algorithm — `__flock_type__` reference replaced with `event.artifact_type`** (the correct field on `ChangelogEvent`). Added clarifying note that `__flock_type__` is a class attribute on registered Pydantic models, not a key in event data. *(feasibility, 0.85)*
10. **Trainset diagram — "earlier timestamp" → "earlier seq (event.seq < E.seq)"** (timestamp is wall-clock and drifts; `seq` is the store's monotonic invariant). Output Structure `compilation.py` comment corrected to list actual functions defined in Unit 4. Unit 6 Files note: `dspy.Example` annotation quoted + `import dspy` gated under `if TYPE_CHECKING:` to keep `flock.core.agent` import-light (currently zero `dspy` imports in that file). *(feasibility, 0.78)*

---

## P1 — Should Fix (9)

### Carried from Round 1 (still unaddressed)

**#1 — `shape_select` precedence rule for `(frontmatter inline, caller runtime=True)` is unresolved.**
*Reviewers: coherence, scope-guardian. Confidence: 0.90.*
Decision table row says "inline | (any) | inline" (frontmatter inline is a force). Unit 4 test scenario line 429 says "tool" with note "caller wins when frontmatter is not explicit force; re-verify rule with integration test." Implementer hits an ambiguous spec at Unit 4 start.

**#2 — `resolve_pydantic_class` enables code execution via frontmatter dotted path.**
*Reviewer: security-lens (carried R1 #8). Confidence: 0.91.*
`flock.outputs: os.system` resolves through `importlib.import_module` + `getattr`. Validation (`issubclass(cls, BaseModel)`) happens AFTER import, but the target module's module-level code executes at import time unconditionally. No allowlist, no isolation.

**#3 — Optimizer writes full artifact payloads in plaintext.**
*Reviewer: security-lens (carried R1 #9). Confidence: 0.93.*
`history.record` writes `.flock/skills/optimization-history/{skill}-{timestamp}.json` containing `dspy.Example` objects derived from changelog. Payloads may contain PII / credentials / financial / medical data. No redaction, no encryption, no `.gitignore`, no retention.

### New from Round 2

**#4 — Trainset rehydration needs full payloads but only has `payload_summary`.**
*Reviewer: feasibility (escalated from R1 #10 P2 → P1 because amendment made it more central). Confidence: 0.80.*
Plan calls for `upstream.payload` and `target.payload` as input/output fields for `dspy.Example`. `ChangelogEvent` has only `payload_summary: dict[str, Any]` — by orchestrator convention `payload_summary["payload"]` carries the full payload, but the plan doesn't specify whether to read that, refetch via `store.get_artifact(event.artifact_id)`, or how to rehydrate the typed Pydantic instance.

**#5 — Publish-to-publish trainset has zero coverage for no-upstream agents.**
*Reviewer: adversarial. Confidence: 0.85.*
The amended algorithm requires upstream `artifact_published` events in the same `correlation_id`. But Flock's `ArtifactManager.publish()` accepts external publishes (`produced_by='external'`) with a fresh `correlation_id`. CLI-triggered runs, scheduled kickoffs, dashboard publishes, fixture-seeded test runs all produce a correlation chain with only the agent's own publish — empty input set, trace silently dropped. This is the **most common shape** for cascade-starting agents — exactly the agents the optimizer would most want to optimize. Plan documents predicated-subscription and multi-skill noise but never the no-upstream case.

**#6 — Engine-patch silently masks `_choose_program` exception fallback for tool-mode skill agents.**
*Reviewer: adversarial. Confidence: 0.82. (Partially auto-noted in plan; decision still required.)*
`_choose_program` (`dspy_engine.py:531`) catches any exception during ReAct construction and returns `Predict(signature)`. For a tool-mode skill agent: tools lost, agent runs degraded, demos route to `program.demos` (Predict branch) instead of ReAct branch — call looks successful. Auto-fix added a caveat to the plan; implementation must pick raise (`SkillEngineModeError`) vs WARN. Decision still outstanding.

**#7 — `./skills/` trust assumption depends on repo write access being trusted.**
*Reviewer: security-lens. Confidence: 0.88.*
The path-based default routes in-repo skills to inprocess. Fine for solo developers; debatable for team repos where a hostile contributor (or a supply-chain attack on a dependency that drops files) can write to `./skills/` and gain in-process execution. Risks table mitigation "default-by-discovery-path" doesn't address this — the discovery path IS the trust signal.

**#8 — Frontmatter `flock.sandbox: inprocess` override on installed skills is ungated.**
*Reviewer: security-lens. Confidence: 0.91.*
A malicious skill pack distributed via pip or git can include `flock.sandbox: inprocess` in its SKILL.md, forcing in-process execution despite landing under `~/.flock/skills/`. The path-based default is fully defeatable by the skill author with no user-level authorization, allowlist, or signature.

**#9 — Three-class type split (`Skill` / `FlockSkillMetadata` / `ScriptSpec`) is unjustified post-`SkillsComponent` removal.**
*Reviewer: scope-guardian. Confidence: 0.72.*
The original justification was that `SkillsComponent` needed to operate on `FlockSkillMetadata` without a full `Skill`. That consumer no longer exists. `FlockSkillMetadata` is parsed in Unit 1, immediately embedded into `Skill` in Unit 2, and never passed independently anywhere after. `ScriptSpec` is a sub-model of `FlockSkillMetadata` with no independent consumers either. Speculative generality.

---

## P2 — Consider Fixing (8)

### New from Round 2

**#10 — Two-seam claim is post-hoc rationalization, not a constraint.** *(adversarial, 0.72)*
The plan's "two integration seams" framing claims the engine-patch follows the existing `AgentBuilder` mutation pattern. But pre-amendment `DSPyEngine` had no skill-specific knowledge; post-amendment it has `if agent.skill_demos: ... isinstance(program, dspy.ReAct) ...`. That's the engine acquiring feature-specific knowledge in the hot path — the exact coupling `EngineComponent` / feature-detect was meant to prevent. P1 #7 (DSPy coupling trajectory) is now arguably worse, not better.

**#11 — `agent.skill_demos` may leak via `__repr__` / agent snapshot / OTel spans.** *(security-lens, 0.68)*
Demos may contain sensitive examples. If `Agent.__repr__` or `agent_snapshot_updated` event serialization includes `agent.__dict__`, demo content lands in logs and the changelog itself.

**#12 — `SkillRegistry` is over-engineered post-amendment.** *(scope-guardian, 0.65)*
With `SkillsComponent` gone, the registry's only consumer is `AgentBuilder.with_skills` calling `discover()` and iterating the result list. Could be a module-level cache dict + standalone `discover()` function — eliminates `registry.py` as a separate concept.

**#13 — `resolve_sandbox()` belongs in `registry.py` (Unit 2), not `scripts.py` (Unit 3).** *(scope-guardian, 0.63)*
`project_root` is established at registry-discovery time. Placing `resolve_sandbox` in Unit 3 creates a runtime dependency on state set in Unit 2 — invisible to Unit 2 tests.

**#14 — `Path.cwd()` not a stable trust boundary.** *(adversarial, 0.78. Partially auto-fixed via marker walk-up; monorepo + parent-of-project invocation cases remain.)*
Even with the auto-fix to walk up for `pyproject.toml`/`.git`, monorepos have multiple project roots. A monorepo-root `flock` invocation classifies sibling teams' `apps/team-c/skills/` as in-repo (inprocess), even though they belong to someone else.

### Carried from Round 1

**#15 — `optimize/` 5-file subpackage is disproportionate.** *(scope-guardian, 0.70)*
Three of the five files (trainset.py, runner.py, history.py) contain one function each, called only from `cli.py`. Collapse to two files (`cli.py` + `optimize.py`).

**#16 — 8-subclass `SkillError` hierarchy.** *(scope-guardian, 0.72)*
Most subclasses have one catch-site; `SkillTokenBudgetError` has zero raise sites in the plan. Audit and remove dead subclasses.

**#17 — Split Unit 8 into a separate plan.** *(scope-guardian, 0.75)*
Phase 1 has a clean exit gate; Unit 8 has its own CLI, subpackage, test file, and exit gate. Splitting lets Phase 1 ship and be used before the optimizer is green.

---

## P3 — Nice to Fix (1)

**#18 — `flock._skill_registry` reuse semantics are undefined.** *(adversarial, 0.66)*
Unit 6 step 2 says "reuse `flock._skill_registry` if present, else create." New shared mutable state on `Flock` invites implicit ordering bugs (cache invalidation across multiple `with_skills()` calls, multi-`Flock` test runs, partial-result poisoning). Decide per-agent vs shared; document either way.

---

## Residual Concerns

- DSPy 3.1.3 byte-compatibility claim in the Risks table now references the corrected ReAct paths, but the verification was retroactive — re-pin and re-verify against actual DSPy versions before relying on the compatibility claim for Unit 6.
- Round-1 P1 #5 (optimizer differentiator theater) is not materially mitigated by the publish-to-publish switch — noise just moved from "no input signal" to "noisy input PLUS no signal at all for no-upstream agents." Documentation-in-`OptimizationResult.notes` mitigation remains a warning string, not a product answer.
- DSPy predictor thread-safety under concurrent skill-demo attachment: `program.demos = list(agent.skill_demos)` mutates shared predictor state. Risk depends on whether DSPy reuses `program` instances across calls — verify before assuming concurrency safety.
- Round-1 finding #27 (`flock.examples.schemas` nesting impossible — `src/flock/examples.py` is a single module) is unaddressed and blocks Unit 7 the moment scenario_1 needs to import its Pydantic schema.

---

## Deferred Questions

1. For #1 (mode precedence): is `flock.mode: inline` an unconditional force, or can `runtime=True` override it?
2. For #2 (`resolve_pydantic_class`): what's the allowlist policy — registered packages only? Configured prefixes? CLI flag?
3. For #3 (optimizer plaintext): redact by default with `--include-trainset` opt-in, or store hashes only?
4. For #4 (trainset rehydration): read from `payload_summary["payload"]` (cheap, depends on convention) or refetch via `store.get_artifact(artifact_id)` (clean, slower)?
5. For #5 (no-upstream traces): drop silently, error in CLI, or threshold-based fail (e.g., >80% dropped)?
6. For #6 (engine fallback masks): raise `SkillEngineModeError` or WARN-and-proceed?
7. For #7 (`./skills/` trust): match team-repo threat model (subprocess by default) or solo-developer convenience (inprocess)?
8. For #8 (frontmatter inprocess override): allowlist required for installed skills, CLI prompt, or unconditional honor?
9. For #9 (three-class collapse): fold `FlockSkillMetadata` + `ScriptSpec` inline on `Skill`, or keep the split?

---

## Coverage

| Persona | Status | Findings | Auto | Present | Residual |
|---------|--------|----------|------|---------|----------|
| coherence | completed | 3 | 2 | 1 | 2 |
| feasibility | completed | 7 | 5 | 2 | 3 |
| security-lens | completed | 9 | 1 (project_root marker walk-up) | 8 | 3 |
| scope-guardian | completed | 8 | 1 (compilation.py comment) | 7 | 4 |
| adversarial | completed | 6 | 1 (engine fallback caveat) | 5 | 5 |
| product-lens | not re-dispatched | — | — | — | — |
| design-lens | not activated | — | — | — | — |
| **Total** | | **33** | **10** | **23** | **17** |

Note: counts reflect post-dedup attribution (3 cross-persona merges for the lifecycle/sandbox/path-cwd clusters). Several "carried from round 1" findings appear in both the round-1 doc and here; the count above shows them in their round-2 attribution.

---

## For Future Learning Extraction

This round caught two mistakes Claude made during the round-1 amendments:

- **Cargo-cult API verification:** the "verified in DSPy 3.0.3 source" claim for ReAct attribute paths was unverified. Reviewers caught it via live REPL inspection. Lesson: when a plan documents API paths through library internals, "verified" requires actual execution against the library, not just reading the source.
- **Underspecified path-classification rule:** `resolve_sandbox`'s "outside project_root" branch missed that `./.claude/skills/` IS inside project_root for any Claude-Code-using project. Lesson: path-based rules need explicit precedence ordering (frontmatter > managed-roots > in-repo > default), not informal inside/outside binary tests.

When Phase 1 ships (or scope-cuts), tag each finding here as Held up / Resolved-differently / Noise / Prevented (same retro template as round 1). The high-confidence catches (P0s, ≥0.85 confidence findings) have falsifiable predictions that contact with implementation will settle.
