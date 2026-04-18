---
title: "Agent Skills Plan: Final Review Findings (Round 4 — Codie Direct Pass)"
date: 2026-04-18
branch: feat/skills
reviewer: Codie (OpenAI Codex / GPT-5.3 Codex) — direct repo-truth final pass
artifacts:
  - docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md
prior_rounds:
  - docs/reviews/2026-04-18-agent-skills-plan-findings.md
  - docs/reviews/2026-04-18-agent-skills-plan-findings-round2.md
  - docs/reviews/2026-04-18-agent-skills-plan-findings-round3.md
method: direct codebase verification against live repo state, not persona dispatch
status: round-4-complete-final-pass-pending-fixes
---

# Agent Skills Plan: Final Review Findings — Round 4

## TL;DR

This was a **final direct pass by Codie**, aimed at finding anything the prior review rounds might still have missed by checking the plan against the live codebase instead of re-running the full document-review pipeline.

Result: **the plan is close, but not fully green yet.** I found:

1. **One P0 contract bug** in the in-process script runner design
2. **Two P1 plan gaps** that will matter once Unit 8 starts
3. **One P2 plan typo** that should be corrected before implementation

The good news: I did **not** find another architectural-collapse issue on the level of round-1 or round-2. This is a narrow final-pass cleanup, not a rethink.

---

## P0 — Must Fix

### #1 — In-process script loading cannot work as written

**Severity:** P0  
**Reviewer:** Codie  
**Confidence:** 0.98

**Plan text:**

> `InProcessRunner`: `importlib.import_module(skill.directory / script.run.split()[-1])`; call `main(args: schema) -> returns` coroutine or sync fn  
> — [docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md](/home/pyro/projects/work/flock/docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md:373)

**Why this is wrong:**

`importlib.import_module()` expects a Python module name, not:

- a filesystem `Path`
- a shell-style `run:` string
- a relative script path like `scripts/extract_text.py`

Your own contracts and surface examples define scripts using shell commands like:

- `python scripts/validate_totals.py` in [.sfd/contracts.md](/home/pyro/projects/work/flock/.sfd/contracts.md:148)
- `python scripts/extract_text.py` in [docs/surface-prototypes/2026-04-17-skills/WALKTHROUGH.md](/home/pyro/projects/work/flock/docs/surface-prototypes/2026-04-17-skills/WALKTHROUGH.md:185)

Direct verification confirms the mismatch:

- `importlib.import_module(Path("/tmp/x.py"))` raises `AttributeError`
- `importlib.import_module("/tmp/x.py")` raises `ModuleNotFoundError`

**Why it matters:**

This is not an implementation detail. It is a contract bug in Unit 3's core execution model. If left as-is, an implementer either:

- follows the plan and hits a dead API immediately, or
- improvises a different meaning for `run:`, which breaks the contract between SKILL authoring and execution.

**What needs to be decided explicitly:**

- Either `inprocess` supports only Python-module entrypoints, with a different frontmatter contract than shell-style `run:`
- Or `inprocess` uses a path-based loader such as `importlib.util.spec_from_file_location(...)`
- Or shell-style `run:` is subprocess-only and `inprocess` gets a separate, stricter field

Until that is clarified, Unit 3 is not implementation-ready.

---

## P1 — Should Fix

### #2 — Unit 8 has no project bootstrap story for the CLI

**Severity:** P1  
**Reviewer:** Codie  
**Confidence:** 0.93

**Plan assumption:**

Unit 8 assumes the CLI can inspect:

- a real `flock` instance
- `flock.agents`
- `agent.skills`
- registered artifact types in `type_registry`

See:

- [docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md](/home/pyro/projects/work/flock/docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md:680)
- [docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md](/home/pyro/projects/work/flock/docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md:688)
- [docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md](/home/pyro/projects/work/flock/docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md:690)

**Live repo truth:**

The current CLI only knows how to bootstrap the demo orchestrator:

- [src/flock/cli.py](/home/pyro/projects/work/flock/src/flock/cli.py:34)
- [src/flock/cli.py](/home/pyro/projects/work/flock/src/flock/cli.py:59)
- [src/flock/cli.py](/home/pyro/projects/work/flock/src/flock/cli.py:74)

There is no existing mechanism for:

- loading a user's real project app
- importing their agent definitions
- populating `type_registry`
- resolving which agents actually have the named skill attached

**Why it matters:**

Without a bootstrap contract, `flock skills optimize <name>` is underspecified at the operator surface. The implementation will have to invent one.

**What needs to be decided explicitly:**

- `--app module:path`
- `--project path/to/app.py`
- convention-based discovery
- or a Python-only API first, with CLI deferred

This does not block Unit 1-7, but it is a real Unit 8 planning gap.

---

### #3 — Demo shape is still under-specified against Flock’s semantic DSPy field naming

**Severity:** P1  
**Reviewer:** Codie  
**Confidence:** 0.86

**Contract text:**

The contracts define demos as:

> Each line is `{input: {...}, output: {...}}` matching the signature.  
> — [.sfd/contracts.md](/home/pyro/projects/work/flock/.sfd/contracts.md:88)

The plan then says demos become:

> `dspy.Example(**demo).with_inputs(*input_keys)`  
> — [docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md](/home/pyro/projects/work/flock/docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md:441)

and again in:

> `self._agent.skill_demos = [dspy.Example(**demo).with_inputs(*input_keys) ...]`  
> — [docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md](/home/pyro/projects/work/flock/docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md:539)

**Live repo truth:**

Flock’s DSPy signatures are not fixed to generic `input` / `output`. They are generated with semantic field names such as `task`, `document`, `report`, pluralized variants, and join-specific fields:

- [src/flock/engines/dspy/signature_builder.py](/home/pyro/projects/work/flock/src/flock/engines/dspy/signature_builder.py:181)
- [src/flock/engines/dspy/signature_builder.py](/home/pyro/projects/work/flock/src/flock/engines/dspy/signature_builder.py:355)

**Why it matters:**

The plan still leaves a portability ambiguity:

- Are demos authored in a portable `{input, output}` shape and rewritten at attach time?
- Or are they authored using runtime semantic keys that depend on the consuming agent?
- If the skill is reused across agents with different input/output naming shapes, what stays stable?

That translation layer is implied, but not actually specified.

**What needs to be clarified:**

Pick one explicit rule:

- portable canonical demo schema plus runtime remapping
- or agent-specific demo schema with reduced portability

I would strongly recommend the first. The current text is close, but still fuzzy enough that Unit 4/6 could drift.

---

## P2 — Consider Fixing

### #4 — `agent_output_types` still references a non-existent `AgentOutput.artifact_type`

**Severity:** P2  
**Reviewer:** Codie  
**Confidence:** 0.99

The plan currently says:

> `agent_output_types = {out.artifact_type for out in agent.outputs}`  
> — [docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md](/home/pyro/projects/work/flock/docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md:442)

and repeats the same shape in Unit 6:

> `Validate each skill's outputs_model against {out.artifact_type for out in self._agent.outputs}`  
> — [docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md](/home/pyro/projects/work/flock/docs/plans/2026-04-17-001-feat-agent-skills-internal-flock-plan.md:534)

But the live `AgentOutput` shape is:

- `spec: ArtifactSpec`
- `spec.model`
- `spec.type_name`

See:

- [src/flock/core/agent.py](/home/pyro/projects/work/flock/src/flock/core/agent.py:45)

There is no `AgentOutput.artifact_type` attribute.

**Why it matters:**

This one is small, but it’s exactly the sort of copy-paste implementation trap a final review should clear.

**Suggested correction:**

- compare against `{out.spec.model for out in agent.outputs}` if you want classes
- or `{out.spec.type_name for out in agent.outputs}` if you want canonical registered names

---

## State After Round 4

My direct verdict as Codie:

- **No new architectural collapse found**
- **Not fully green yet**
- **Very close**

If you patch:

1. the Unit 3 in-process script contract
2. the Unit 8 CLI/bootstrap contract
3. the demo-shape mapping rule
4. the small `artifact_type` typo

then I would call the plan ready.

One nuance: these findings do **not** mean you need another full review loop before starting all implementation. Unit 1 still looks like a safe place to begin once the small `AgentOutput` typo is corrected. The main hard blocker is the script-runner contract in Unit 3.

---

## Coverage

| Reviewer | Mode | Findings | Severity mix |
|---------|------|----------|--------------|
| Codie | direct repo-truth final pass | 4 | 1 P0, 2 P1, 1 P2 |

This round intentionally did **not** re-run the full persona stack. It was a final evidence pass against:

- the current plan text
- the current live repo
- the current CLI surface
- the current DSPy signature builder
- the current `Agent` / `AgentOutput` / `BlackboardStore` shapes

---

## For Future Learning Extraction

Two meta-lessons from this Codie pass:

1. **Late-stage plan reviews benefit from checking operator surfaces, not just internal consistency.** The CLI bootstrap gap did not show up as a pure document contradiction; it showed up because the live CLI only knows how to boot the demo app.
2. **Any plan that mixes shell-command contracts and Python-import contracts needs an explicit boundary.** `run: python scripts/foo.py` and "import this in-process" are not interchangeable. Leaving that implicit guarantees implementation drift.
