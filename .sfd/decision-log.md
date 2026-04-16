## SFD Decision Log

### Surface Type
API / library (developer-facing feature — Flock agent authors writing Python code + SKILL.md files)

### Convergence Status
Iterating (prototype round 1 written 2026-04-17)

### Project Context
- **Ideation doc:** `docs/ideation/2026-04-17-agent-skills-for-flock-ideation.md`
- **Selected implementation path:** #5 compile-time signature baking (primary) + #7 DSPy optimizer (multiplier) + #2 MAF-style runtime fallback
- **Branch:** `feat/skills` (pushed to origin)

### Surface Prototype Location
`docs/surface-prototypes/2026-04-17-skills/`
- `WALKTHROUGH.md` — narrative cover page
- `scenario_1_typed_output.py` — typed-output skill (compile-time path)
- `scenario_2_pure_prose.py` — pure methodology skill (compile-time, no types)
- `scenario_3_script_heavy.py` — skill with scripts/ directory
- `scenario_4_shared_library.py` — shared skill library across multiple agents
- `example_skills/*/SKILL.md` — example authored skills

### Decisions (provisional — subject to iteration)

- **2026-04-17 — Option C wins by default (compiler picks mode by shape).** Single unified API `agent.with_skills(...)`. Compile-time path (#5) by default; runtime tool path (#2) triggered by either (a) skill frontmatter `flock.mode: tool`, (b) caller passing `runtime=True`, or (c) skill library exceeding token budget at compile time. Rationale: minimizes user-facing API surface, handles pure-prose skills naturally via compile-to-instructions fallback. Rejected Option A (frontmatter-driven mode) as too noisy for skill authors who mostly shouldn't care. Rejected Option B (separate `.with_skills_compiled()` vs `.with_skills_available()` methods) as forcing a decision the user shouldn't have to make.

- **2026-04-17 — Interop-first: read Anthropic SKILL.md format unchanged.** Flock-specific metadata goes under an optional `flock:` frontmatter key. Skills written for Claude Code / MAF / pydantic-ai-skills run in Flock without modification. Rejected inventing a new skill format.

- **2026-04-17 — Discovery defaults: `./skills/`, `~/.flock/skills/`, `./.claude/skills/` in that precedence order.** Reuses Claude Code's convention; adds Flock-specific `~/.flock/skills/` for global reuse. Letta-style 5-tier priority was considered and rejected as overkill.

- **2026-04-17 — `.with_skills()` accepts directory paths, file paths, glob patterns, or `Skill` objects.** Mirrors `with_tools()` and `with_mcps()` ergonomics. No separate `discover_skills()` ceremony (CrewAI's two-phase API rejected).

- **2026-04-17 — Scripts run in-process by default, sandboxed subprocess on request.** `flock:sandbox: subprocess` in SKILL.md frontmatter opts into subprocess isolation. Follows MAF's explicit warning that `SubprocessScriptRunner` is demo-quality — Flock ships with a proper sandbox layer from day one (or defaults to safe in-process for trusted skills).

- **2026-04-17 — `#7 optimizer` lives under `flock skills optimize <name>` CLI.** Not auto-triggered. Authors opt in per skill. Writes diffs for review, never overwrites silently.

### Derived Contracts
See `.sfd/contracts.md` (drafted 2026-04-17 after Andre approved surface round 1).
Covers: public API surface, frontmatter schema (Anthropic + `flock:` namespace),
core types, discovery algorithm, compilation contract (shape-select + signature
mutation + tool injection), `SkillsContextProvider`, script execution,
optimizer CLI + Python API, error taxonomy, testing contract, file layout,
open questions.

Awaiting Andre's manual pass before Gate 2 close-out and plan hand-off.

### Hardening Status
- [ ] Persistence (N/A — skills are filesystem-based)
- [ ] Auth (N/A — no per-skill auth in scope for PoC)
- [ ] Domain logic (currently: surface prototype only, no real execution)
- [ ] Error handling (currently: happy-path in surface prototype)
- [ ] Performance (currently: unoptimized)

### Gate Status
- [x] **Gate 1: Surface Converged** — Andre approved round 1 on 2026-04-17 ("gut reaction aligns to your proposals")
- [ ] **Gate 2: Contracts Frozen** — draft complete in `.sfd/contracts.md`, awaiting Andre's manual pass
- [ ] Gate 3: Architecture Review
- [ ] Gate 4: Hardening Complete
- [ ] Gate 5: Release Ready
