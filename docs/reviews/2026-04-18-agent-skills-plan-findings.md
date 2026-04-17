---
title: "Agent Skills Plan: Document Review Findings (Round 1)"
date: 2026-04-18
branch: feat/skills
reviewer: Claude (Opus 4.7) via compound-engineering:document-review
artifacts:
  - docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md
origin_chain:
  - docs/surface-prototypes/2026-04-17-skills/ (SFD rounds 1-4)
  - .sfd/contracts.md
  - docs/ideation/2026-04-17-agent-skills-for-flock-ideation.md
personas:
  always_on: [coherence, feasibility]
  conditional: [product-lens, security-lens, scope-guardian, adversarial]
  not_activated: [design-lens]
status: round-1-complete-refinement-pending
---

# Agent Skills Plan: Document Review Findings

## TL;DR

Six reviewer personas dispatched in parallel against the 708-line implementation plan. 37 unique findings surfaced after dedup (3 cross-persona merges). 7 auto-fixed silently; 30 require author decisions. **Three P0 blockers identified that no auto-fix can resolve** — each is a load-bearing architectural claim in the plan that contact with the codebase falsifies:

1. **Demo-attachment lifecycle is architecturally impossible** as described. The plan's `SkillsComponent.on_pre_evaluate(ctx, program)` cannot exist: the real `AgentComponent.on_pre_evaluate(agent, ctx, inputs) -> EvalInputs` signature has no `program` parameter, and the hook fires BEFORE `DSPyEngine._choose_program()` constructs the program. Three reviewers caught this independently (feasibility, scope-guardian, adversarial).

2. **Unit 8 depends on `artifact_consumed` events that have zero emitters.** The event type exists in `ChangelogEventType` enum but is never appended to the changelog anywhere in the codebase. The plan describes trainset reconstruction as "best-effort" but the gap is total — there is no input signal at all.

3. **In-process sandbox default contradicts the plan's own interop premise.** R2 commits to SKILL.md interop with Claude Code / MAF / pydantic-ai — i.e., skills as shareable artifacts from PyPI/GitHub/team libraries. The "trust the skill author by default" rationale cites "60% are helpers the agent author wrote themselves" — a world where the interop story doesn't matter. Either skills are local-only (why the interop?) or they're shared (why in-process default?).

Seven auto-fixes applied silently (YAML safe_load, `query_changelog` signature correction, CLI path, examples/11→13 renumber, `agent.tools` is a set not a list, `.with_description()` → `.description(text)`, hostile-YAML test case). Plan is refinable — these are correctable design decisions, not dead ends — but Phase 1 should not start coding until the P0s are resolved.

---

## Review Workflow

**Document type:** plan
**Trigger thresholds met:** >5 implementation units, new abstractions (SkillRegistry, SkillsComponent, ScriptRunner, OptimizationResult), explicit architectural decisions with rationale, plan already corrected origin contracts once (signal of load-bearing design).

**Persona activation rationale:**
| Persona | Activated | Reason |
|---------|-----------|--------|
| coherence | always-on | — |
| feasibility | always-on | — |
| product-lens | yes | Premise claim ("internal DSPy agents need skills"), strategic weight on Flock's DSPy coupling vs engine-swap positioning |
| security-lens | yes | Script execution with in-process default, dynamic `importlib` resolution from frontmatter, subprocess sandbox opt-in |
| scope-guardian | yes | 8 units across 2 phases, extensive deferred-items list, multiple explicit "No X" boundaries |
| adversarial | yes | 8 units, new abstractions, plan pre-corrected origin contracts |
| design-lens | no | No UI/UX/frontend |

**Confidence floor:** 0.60 across all personas (adversarial and scope-guardian used non-standard labels; normalized post-dispatch).

**Total raw findings:** 42 (1 coherence + 13 feasibility + 7 product-lens + 6 security-lens + 7 scope-guardian + 8 adversarial).
**Post-dedup:** 37 unique (3 cross-persona merges: demo-lifecycle, FlockError-missing, pdfplumber-missing).
**Routed auto:** 7 applied silently. **Routed present:** 30 require decisions.

---

## Auto-fixes Applied to Plan

Applied inline to `docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md` via Edit. No rewrite, no scope addition.

1. **Unit 1 Approach — YAML safe-load mandated.** `parse_skill_frontmatter` now specifies `yaml.safe_load()` with explicit rationale (blocks `!!python/object/apply:...` tag-based code execution). *(security-lens, 0.88)*
2. **Unit 1 Test scenarios — hostile-YAML test added.** `!!python/object/apply:os.system [echo pwned]` must raise `SkillParseError`, not execute. *(security-lens, mechanical follow-on)*
3. **Unit 8 Approach — `query_changelog` call corrected.** Replaced fictional `since=` kwarg with real signature: `after_seq` paging in batches of `limit`, `result.events` iteration, client-side `since` filter on `event.timestamp`; changed `produced_by=[...]` to `produced_by={...}` (set, not list). *(feasibility, 0.85)*
4. **Unit 8 Files + Sources & References — CLI path corrected.** `src/flock/api/cli.py` → `src/flock/cli.py` with Typer nesting pattern (`app.add_typer(skills_app, name="skills")`). *(feasibility, 0.88)*
5. **Output Structure + Unit 7 (all file refs) — examples renumbered.** `examples/11-skills/` → `examples/13-skills/` (11-openclaw and 12-external-agents already occupied). *(feasibility, 0.95)*
6. **Context & Research + Unit 6 Approach — `agent.tools` set semantics.** Replaced "append" with `.update({...})`, added note that preamble must sort by skill name for determinism since set order is not stable. *(feasibility, 0.80)*
7. **System-Wide Impact — builder method citation.** `.with_description()` (doesn't exist) → `.description(text)` (matches `core/agent.py:522`). *(feasibility, 0.90)*

---

## P0 — Must Fix (No Auto-fix Possible)

### Error #1: Demo-attachment lifecycle mechanism is architecturally impossible

**Severity:** P0
**Reviewers:** feasibility, scope-guardian, adversarial (three-way consensus)
**Confidence:** 0.95

**Evidence:**
> "Demos attach at `on_pre_evaluate`, not registration. The engine constructs `program = dspy.Predict(sig)` fresh each call. Setting `predictor.demos` needs a post-construction hook — `SkillsComponent.on_pre_evaluate` is the right lifecycle point." *(Plan, Key Technical Decisions)*

> "`SkillsComponent(AgentComponent)`: `on_pre_evaluate(ctx, program)` — attach demos to `program.demos` (Predict) or `program.react.react.demos` + `program.react.extract.demos` (ReAct)" *(Plan, Unit 6 Approach)*

**Codebase ground truth:**
- `src/flock/components/agent/base.py:76` — `on_pre_evaluate(agent, ctx, inputs: EvalInputs) -> EvalInputs` (no `program` parameter)
- `src/flock/core/agent.py:241` — `_run_pre_evaluate` is called BEFORE `_run_engines`
- `src/flock/engines/dspy_engine.py:343` — `program = self._choose_program(...)` happens inside `evaluate()`, not via a lifecycle hook

**Why it matters:** The plan's three-seams architectural rationale ("Config-time + per-invocation + signature-time") names `SkillsComponent.on_pre_evaluate` as the per-invocation seam. That seam doesn't exist and cannot be retrofitted without adding a new lifecycle hook, subclassing `DSPyEngine`, or abandoning `AgentComponent` entirely. An implementer starting Unit 6 blocks immediately.

**Resolution options (plan must choose):**
- (A) Add a new `on_program_ready(agent, ctx, program)` hook to `AgentComponent` + patch `DSPyEngine.evaluate` between `_choose_program` and program invocation. Cost: touches every existing `AgentComponent` subclass.
- (B) Stash demos on `agent.skill_demos` at `.with_skills()` time; patch `DSPyEngine` (3 lines after `_choose_program`) to consult `agent.skill_component` and set demos directly. Cost: engine is no longer purely component-driven for this case.
- (C) Inject demo examples as few-shot prose in the signature instructions, eliminating `predictor.demos` attachment entirely. Cost: loses DSPy's native demo-formatting, but removes the whole seam.
- (D) Adversarial's collapsed-seams variant: if (B) works, delete `SkillsComponent` entirely. Two seams, not three. Entire `component.py` unit goes away.

---

### Error #2: Unit 8 trainset reconstruction has no input signal

**Severity:** P0
**Reviewer:** feasibility
**Confidence:** 0.90

**Evidence:**
> "For each correlation group, pair `artifact_consumed` events (inputs) with `artifact_published` events (outputs) of the matching agent — rehydrate into `dspy.Example(input_field=..., output_field=...).with_inputs(...)`" *(Plan, Unit 8 Approach step 4)*

> "B -->|artifact_consumed| C[collect as INPUT for correlation_id]" *(Plan, Trainset reconstruction flowchart)*

**Codebase ground truth:**
- `ChangelogEventType.artifact_consumed` exists in `src/flock/models/changelog.py:17-65`
- **Zero emitters** — `grep ChangelogEventType.artifact_consumed` across `src/flock/` returns no write-side callers
- `src/flock/orchestrator/artifact_manager.py:227` is the only `append_changelog` call site and only ever emits `artifact_published`

**Why it matters:** The plan frames the attribution gap as "best-effort" degradation for multi-skill agents. The real gap is upstream: there are no input events at all. The optimizer cannot construct `dspy.Example(input=X, output=Y)` pairs because X is never recorded. Unit 8 as written cannot run; "best-effort" framing masks this.

**Resolution options (plan must choose):**
- (A) Add a prerequisite sub-unit (Phase 2.0) that emits `artifact_consumed` at the scheduler/orchestrator layer whenever agents read inputs. Changes changelog write volume.
- (B) Redesign trainset reconstruction to use `artifact_published` only — pair upstream publishes (same `correlation_id`, earlier timestamp) as implicit inputs to downstream publishes. Works today, less clean semantically.
- (C) Cut Unit 8 from this plan entirely; file a separate optimizer plan once a clean input signal exists.

---

### Omission #3: In-process sandbox default contradicts interop premise

**Severity:** P0
**Reviewers:** security-lens, adversarial
**Confidence:** 0.97

**Evidence:**
> "Script sandboxing defaults to in-process. Trust the skill author by default; users who ship untrusted skills use `flock.sandbox: subprocess`. Rationale: ~60% of skill scripts are helpers the agent author wrote themselves" *(Plan, Key Technical Decisions)*

> "R2. SKILL.md format is Anthropic-standard + optional `flock:` frontmatter namespace — skills written for Claude Code run unchanged" *(Plan, Requirements Trace)*

> "Script sandboxing in-process default lets malicious/buggy skills take down the process | Low | High | Document `flock.sandbox: subprocess` prominently. Add lint-style warning at skill-load time if `scripts:` present but `sandbox` unset" *(Plan, Risks & Dependencies)*

**Why it matters:** The two premises are mutually self-defeating. Interop (R2) presupposes skill sharing: PyPI packages, GitHub repos, team-internal libraries. The sandbox rationale ("60% are helpers the agent author wrote themselves") presupposes local authoring — a world where interop doesn't matter. Whichever is true, the other premise is wrong. `InProcessRunner` does `importlib.import_module(skill.directory / script.run.split()[-1])`, which executes module-level code at import time before the Pydantic args-schema gate has any chance to run. A malicious script inside a third-party skill pack gains in-process execution on load. The lint-warning mitigation fails the first time a user silences it.

**Resolution options (plan must choose):**
- (A) Invert the default: `sandbox: subprocess` unless the skill lives in a whitelisted in-repo path (e.g., `./skills/` — the developer's own files). `~/.flock/skills/` and `./.claude/skills/` default to subprocess.
- (B) Require explicit `flock.sandbox: inprocess` opt-in at skill level. No default. Load fails if `scripts:` present and `sandbox:` unset.
- (C) Scope-cut scripts entirely from Phase 1. Skills ship without executable code; revisit post-PoC once a real sandboxing story lands.

---

## P1 — Should Fix

### Errors

**#4 — Mode decision table contradicts Unit 4 test scenarios.** *(coherence, 0.90)*
Decision table row `flock.mode: inline | (any) | inline` treats inline as a force. Unit 4 test scenario line 426 expects `(frontmatter inline, caller runtime=True) → tool` with the note "caller wins when frontmatter is not explicit force; re-verify rule with integration test." Precedence rule is literally flagged as unresolved in the plan. Either the table or the test is wrong.

**#5 — Unit 8 optimizer is differentiator theater risk.** *(product-lens + adversarial, 0.82)*
Plan admits (a) multi-skill agents have no attribution, (b) no `skill_invoked` event, (c) success-signal metric is deferred ("depends on how cleanly we can correlate"), (d) output may converge to brittle prose. Marketed as the Flock-unique differentiator (#7 per ideation). Compounding direction is negative: users optimize, get false-signal diffs, SKILL.md drifts, stop trusting the optimizer. Mitigation "document in `OptimizationResult.notes`" is a warning string, not a product answer.

**#6 — Three-seams rationale may conflate constraint with convention.** *(adversarial, 0.82)*
Plan asserts three seams are forced by architecture ("DSPy's signature-compile-at-call-time plus Flock's immutable Context mean no single hook can carry tools+instructions+demos"). But `AgentBuilder.with_skills` already mutates `agent.description` + `agent.tools` at config time. Demos could stash on `agent.skill_demos` and attach inline in `DSPyEngine` after `_choose_program`. If that works, `SkillsComponent` is a new component class + utility registration + lifecycle integration + `isinstance(ReAct)` dispatch for a two-line assignment. Entire `component.py` unit becomes speculative complexity.

### Omissions

**#7 — DSPy coupling trajectory cost unacknowledged.** *(product-lens, 0.85)*
Plan weaves skills into 6+ DSPy API touchpoints: `Signature.with_instructions`, `predictor.demos`, `react.react.demos` vs `react.extract.demos`, `DSPyEngine._choose_program`, `signature_builder.py`, `Tool._parse_function`. Flock's retro explicitly commits to engine-swap as a core value prop ("external agents are just agents with a different engine"). Skills become a DSPy feature, not a Flock substrate feature — they don't travel when a second internal engine lands. No "Strategic Consequences" section owns this bet.

**#8 — `resolve_pydantic_class` enables code execution via frontmatter.** *(security-lens, 0.91)*
`flock.outputs: os.system` resolves through `importlib.import_module` + `getattr`. Validation (`issubclass(cls, BaseModel)`) happens AFTER import, but the target module's module-level code executes at import time unconditionally. Attack vector: malicious SKILL.md in any skill directory. Mitigation: allowlist top-level package prefixes OR require pre-registration in `TypeRegistry` with `importlib` fallback disabled for untrusted sources.

**#9 — Optimizer writes full artifact payloads in plaintext.** *(security-lens, 0.93)*
`history.record` writes `.flock/skills/optimization-history/{skill}-{timestamp}.json` containing `dspy.Example` objects derived from changelog. Changelog `payload_summary.payload` carries the full artifact payload (confirmed in `orchestrator/artifact_manager.py:234-238`). No redaction, no encryption, no retention policy, no default `.gitignore` entry. Agent inputs may contain PII, credentials, financial/medical data depending on the domain.

---

## P2 — Consider Fixing

### Errors

| # | Section | Issue | Reviewer | Confidence |
|---|---------|-------|----------|------------|
| 10 | Unit 8 Approach | `ChangelogEvent.payload` doesn't exist; only `payload_summary`. Rehydration path unspecified | feasibility | 0.72 |
| 11 | Unit 4 / shape_select | Mode frozen at config-time forecloses per-call variance (e.g., large PDF input triggering budget-overflow after inline was chosen) | adversarial | 0.68 |
| 12 | Unit 4 / compile_inline_skills | Concatenation of free-form prose with separator — conflicting skill directives silently collide in `agent.description`. No lint, no test | adversarial | 0.72 |
| 13 | Unit 1 / errors.py | 8-subclass `SkillError` hierarchy — most subclasses have one catch-site; `SkillTokenBudgetError` has zero explicit consumers | scope-guardian | 0.72 |
| 14 | Unit 3 / scripts.py | `ScriptRunner(Protocol)` + 2 implementations + factory — one abstraction, two impls, no third planned. Collapse to single function branching on `skill.flock_meta.sandbox` | scope-guardian | 0.68 |
| 15 | Phased Delivery | Unit 8 scoped into Phase 2 but shares the plan with Phase 1 — separate CLI, separate MIPROv2 integration, independent exit gate. Splitting into two plans would let Phase 1 ship cleaner | scope-guardian | 0.75 |

### Omissions

| # | Section | Issue | Reviewer | Confidence |
|---|---------|-------|----------|------------|
| 16 | Unit 2/3/8 test scenarios | Shadow paths not traced: malformed SKILL.md during discovery (halt or continue?), subprocess timeout pipe-drain order, paging termination, store error propagation to CLI exit | feasibility | 0.65 |
| 17 | Unit 2 Discovery | No symlink resolution, no path canonicalization, no integrity check. `~/.flock/skills/` shadow attack surface | security-lens | 0.72 |
| 18 | Unit 8 CLI | No actor definition — who can run `flock skills optimize`? Becomes changelog exfiltration vector in shared/remote deployments | security-lens | 0.75 |
| 19 | Scope Boundaries | Anthropic SKILL.md + `flock:` namespace hardens into public API before #6 (blackboard-native skills) can reopen as non-breaking addition | product-lens | 0.72 |
| 20 | Overview / Unit 6 | `with_skills(*sources, runtime=False, token_budget=8000)` forces every caller to reason about modes + budget. MAF/Claude SDK equivalents hide this | product-lens | 0.68 |
| 21 | Problem Frame | "Internal DSPy agents can't use skills" asserts pain without evidence — no issue, anecdote, or usage data cited. `docs/skills-proposal/` is empty | product-lens | 0.65 |
| 22 | Phased Delivery | Success criteria = "tests pass + scenarios run." No adoption metric. Inversion: plan ships, 6 months later <5 users have `.with_skills()` in real code | product-lens | 0.70 |
| 23 | Sources & References | Static-codegen alternative (`flock skills compile` → emits Python module) not considered. Plan's own "skills are static per agent" raises the question why compilation must be runtime | adversarial | 0.66 |
| 24 | Risks & Dependencies | 6 simultaneous DSPy API coupling points (including private `_parse_function`, undocumented `react.react.demos`). Aggregated risk ≠ "low × 6"; any one break affects Units 4 + 6 + 8 | adversarial | 0.70 |

---

## P3 — Nice to Fix

### Errors

| # | Section | Issue | Reviewer | Confidence |
|---|---------|-------|----------|------------|
| 25 | optimize/ subpackage | `history.py` + `trainset.py` each one function, called only from `runner.py`/`cli.py`. Inline or collapse | scope-guardian | 0.65 |

### Omissions

| # | Section | Issue | Reviewer | Confidence |
|---|---------|-------|----------|------------|
| 26 | Unit 7 / pdf-extract | `pdfplumber` not in `pyproject.toml`. Pick now: add extras OR use stdlib byte-sig check | feasibility + scope-guardian | 0.88 |
| 27 | Unit 7 Approach | `flock.examples.schemas` nesting impossible — `src/flock/examples.py` is a single module. Refactor-or-colocate decision deferred | feasibility | 0.78 |
| 28 | System-Wide Impact | `.with_skills()` on non-DSPy-engine agent policy (raise/warn/noop) left to "Unit 6 impl time" | feasibility | 0.66 |
| 29 | Phased Delivery | Unit 5 (runtime-tool mode) carried in Phase 1 MVP. 4 canonical scenarios can run inline-only. Split into 1a/1b to ship probe first | product-lens + adversarial | 0.62 |

---

## Residual Concerns

Findings below 0.60 or un-promoted risks:

1. **`allowed_names` guard consistency** — if built from all_skills rather than tool_mode_skills, inline skills become reachable via runtime tools. *(security-lens)*
2. **DSPy predictor thread-safety** — concurrent requests mutating shared `program.demos` could interleave demos across agents. *(security-lens)*
3. **`build_skill_preamble` log-bleed** — system-prompt-included skill names surface in DSPy prompt tracing, potentially logging confidential skill library names. *(security-lens)*
4. **`_choose_program` silent fallback** — `except Exception: return Predict(...)` at `dspy_engine.py:531` masks skill-tool registration failures as Predict mode. *(feasibility)*
5. **`dspy.Example` API idioms** — zero existing usages in Flock codebase; Unit 4/8 will discover from scratch, risk of incorrect `.with_inputs(*keys)` signature usage. *(feasibility)*
6. **DSPy 3.0.3 `ReAct.react.demos` propagation** — plan's own Risk #1 flags this as Medium/High; blocked by P0 #1 until a real seam exists. *(feasibility)*
7. **Optimizer `--apply` overwriting SKILL.md in CI** — loses human authorship when run without review; no gate proposed beyond interactive prompt. *(adversarial)*

---

## Deferred Questions

Questions for implementation time or follow-on review:

1. For P0 #1 (demo-attachment lifecycle): add `on_program_ready` hook, subclass DSPyEngine, or attach at registration time? *(feasibility, scope-guardian)*
2. For P0 #2 (optimizer input events): emit `artifact_consumed` as prerequisite, or switch reconstruction to publish-to-publish correlation? *(feasibility)*
3. `FlockError` doesn't exist — introduce it, inherit `Exception` directly (matches convention), or reuse `RuntimeError`? *(feasibility, scope-guardian)*
4. `.with_skills()` on non-DSPy engine — raise, warn, or no-op? *(feasibility, product-lens)*
5. Preservation plan for #6 (blackboard-native skills) — which properties of v1 API held invariant so future migration isn't breaking? *(product-lens)*
6. Observed single-skill vs multi-skill agent ratio — determines whether Unit 8 attribution is viable or fundamentally broken. *(adversarial)*
7. Has any real Flock user requested runtime-tool mode, or is Unit 5 entirely speculative? *(adversarial)*

---

## Coverage

| Persona | Status | Findings | Auto | Present | Residual |
|---------|--------|----------|------|---------|----------|
| coherence | completed | 1 | 0 | 1 | 3 |
| feasibility | completed | 9 | 5 | 4 | 3 |
| product-lens | completed | 7 | 0 | 7 | 2 |
| security-lens | completed | 6 | 1 | 5 | 3 |
| scope-guardian | completed | 4 | 0 | 4 | 2 |
| adversarial | completed | 7 | 0 | 7 | 5 |
| design-lens | not activated | — | — | — | — |
| **Total** | | **34** | **6** | **28** | **18** |

Note: counts reflect post-dedup attribution. The YAML safe-load fix is attributed to security-lens as the primary finder; the test-scenario addition follows mechanically. Cross-persona merged findings (demo-lifecycle, FlockError, pdfplumber) attributed to the highest-confidence reviewer.

---

## For Future Learning Extraction

**This review's predictions are testable against implementation reality.** When Phase 1 ships (or is scoped-cut), come back to this doc and tag each finding:

- **Held up** — the finding predicted a real problem that implementation confirmed
- **Resolved-differently** — the finding surfaced a real issue, but the implementation picked a different resolution than the suggested_fix
- **Noise** — the finding described a problem that didn't materialize (reviewer misread the plan or the codebase)
- **Prevented** — the finding triggered a plan refinement that made the problem moot

Particular predictions worth watching:
- **P0 #1 (demo-lifecycle):** Does the implementer actually have to add a new lifecycle hook, or does stashing-on-agent + in-engine attachment work cleanly? If the latter, adversarial #6 (three-seams is speculative) was right and `SkillsComponent` should die.
- **P0 #2 (`artifact_consumed`):** Does the optimizer ship with a prerequisite changelog emission unit, or does publish-to-publish correlation turn out to be sufficient? The former validates this finding; the latter means the gap was real but solvable without new events.
- **P0 #3 (sandbox default):** Once skills start being shared (if they do), does the in-process default cause a real incident, or does the adoption path stay local-author-only (invalidating the interop premise but also the security concern)?
- **P1 #5 (optimizer theater):** If Unit 8 ships, does the output actually move skills in a good direction, or do users stop running it within 30 days?
- **P1 #6 (three-seams collapse):** Same as P0 #1 — if demos attach inline and `SkillsComponent` dies, multiple findings collapse together.
- **P2 #21 (no evidence for premise):** Once shipped, count `.with_skills()` adoption in real Flock projects at 30/90 days. <5 uses at 90d = problem-frame was author-preference, not user-pull.

**Pipeline for learning capture:** once Phase 1 is committed, add a companion doc `2026-MM-DD-agent-skills-findings-retrospective.md` next to this file that tags each finding with its observed fate. That's the signal we can promote to `claude-knowledge` insights.

---

## Recommended Next Action

Refine the plan to address the three P0s. Suggested sequence:

1. **P0 #1 (demo-lifecycle):** Pick a resolution from (A)–(D) above. Option B or D is simplest if they work; verify by prototyping.
2. **P0 #2 (`artifact_consumed`):** Default to option (B) — switch reconstruction to `artifact_published`-only correlation. Cheaper than emitting a new event type, and if the signal quality is poor, that's an argument for option (C) — cut Unit 8 from Phase 1 entirely.
3. **P0 #3 (sandbox default):** Invert the default (option A). Skills in `./skills/` default to in-process; everything else defaults to subprocess. Matches the interop premise and removes the silent-execution footgun.

Then re-review with the same personas (changed sections only) to check for regressions and freshly surfaced issues.
