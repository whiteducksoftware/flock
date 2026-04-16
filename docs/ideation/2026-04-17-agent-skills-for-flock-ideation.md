---
date: 2026-04-17
topic: agent-skills-for-flock
focus: how should internal Flock agents run Agent Skills (Anthropic SKILL.md / progressive disclosure pattern)
---

# Ideation: Agent Skills for Internal Flock Agents

## Codebase Context

### Flock architecture (what we're ideating for)

- **Blackboard / event-driven.** Agents subscribe to typed Pydantic schemas. No explicit DAG. Execution: `publish → scheduler matches subscriptions → engine evaluates → output publishes → cascade`.
- **Primary internal engine: `DSPyEngine`.** Uses `dspy.ReAct(signature, tools, max_iters)` when tools are present; otherwise `dspy.Predict`. Signature is compiled per-call from Pydantic `consumes`/`publishes` types. No hand-written prompt template.
- **Tool surface today:** `agent.with_tools(callables)` + `agent.with_mcps({server: {tool_whitelist}})`. Both merged into `combined_tools` at DSPy eval time.
- **Context Providers** — existing primitive that sits between orchestrator and engine, filters/redacts/injects artifacts per agent. This is Flock's existing dynamic-context-injection seam and the natural plug point for any new capability layer.
- **`ExternalEngineComponent`** — engine-swap pattern for out-of-process work. `ClaudeCodeRuntime` and `OpenClawEngine` already work this way. External engines effectively "have" skills today via the Claude Code CLI's own runtime; internal DSPy agents don't.
- **`AgentSnapshotRecord`** ≈ capability manifest today.
- **Changelog stream + cursor replay** (shipped by the meta-orchestrator refactor) is already a durable-execution primitive.
- **Past retro (`docs/retro-sfd-vs-spec-driven.md`):** *"External agents are just agents with a different engine. Surface-first. Don't build parallel infrastructure if engine-swap suffices."* Load-bearing principle for this ideation.
- **`docs/skills-proposal/` exists but is empty.** This is a greenfield decision.

### External framework patterns (grounding)

| Framework | Native skills? | Mechanism | Progressive disclosure |
|---|---|---|---|
| Anthropic Claude Agent SDK | yes, filesystem-only | single `"Skill"` tool | 3-level |
| **Microsoft Agent Framework (MAF)** | **yes, first-class** | `SkillsProvider` as ContextProvider → 3 tools (`load_skill`, `read_skill_resource`, `run_skill_script`). File + inline + class-based skills, DI, approval gating, caching, filter predicates | explicit 4-stage |
| pydantic-ai-skills (community) | yes (community) | 4 tools incl. `list_skills` | 3-level |
| LangChain Deep Agents | yes (in `deepagents`) | skills dir passed to `create_deep_agent`; body read via existing fs tools | metadata + lazy body |
| CrewAI | yes | `discover_skills` + `activate_skill`, prompt-injected ("skills ≠ tools, skills = methodology") | partial (eager after activation) |
| AutoGen | no (maintenance mode) | — | — |
| LangGraph core | no | — | — |
| DSPy | no native — but can **optimize** SKILL.md bodies externally | — | — |
| Letta Code (CLI) | yes | 5-tier priority (project > agent > global > bundled), system-reminder injection | yes |

**Two architectural camps** have formed in the ecosystem:
- **Tool-injection** (MAF, pydantic-ai, Claude SDK) — skills become classical ReAct tools. Lazy. Scales to hundreds.
- **Prompt-injection** (CrewAI, Letta) — skills mutate the system/task prompt directly. Simple. Caps at ~10 skills.

### The core tension for Flock

- DSPy wants **typed signatures** (`InputField`/`OutputField`). Skills are **free-form markdown**.
- Blackboard wants **Pydantic artifacts**. Skills live as **files** (SKILL.md + resources/scripts).
- ReAct loop wants **tool calls**. `dspy.Predict` (the non-ReAct path) has no tool loop at all.
- External engines (Claude Code CLI) already handle skills. Internal DSPy agents don't — this is the gap to close.

## Ranked Ideas

Ideas are ordered risk-graded (safe → ambitious). The **selected** set (for the combined path) is marked `Status: Selected`.

---

### 1. Delegate Skills to `ExternalEngineComponent` — Don't Build

**Description:** Agents that need skills auto-swap their engine to `ClaudeCodeRuntime` via `ExternalEngineComponent`. Add a `.requires_skills()` hint on the agent; engine resolution prefers external when set. Zero new internal code.

**Rationale:** Honors the retro lesson (*"don't build parallel infrastructure if engine-swap suffices"*). `ClaudeCodeRuntime` already handles `.claude/skills/` via the CLI's own runtime. Cheapest possible ship.

**Downsides:** Doesn't solve the stated problem — internal DSPy agents remain skill-less. Pays 500ms–2s CLI subprocess spawn per call. No typed-cascade benefits. Punts on the architectural question.

**Confidence:** 85% (it works — question is whether it's *enough*)
**Complexity:** Low (days)
**Status:** Rejected by Pyro (2026-04-17) — the point is explicitly internal skills.

---

### 2. MAF-Style `SkillsContextProvider` (Port the Baseline)

**Description:** New `SkillsContextProvider` subclass of Flock's ContextProvider. Scans `~/.claude/skills/` + `./skills/` (same dirs Claude Code reads). Injects three classical tools into the DSPy ReAct path: `load_skill(name)`, `read_skill_resource(skill, resource)`, `run_skill_script(skill, script, args)`. Metadata (~50 tokens/skill) in system prompt at startup; body on `load_skill` call; resources/scripts lazy.

**Rationale:** Proven pattern. MAF does exactly this well. Uses Flock's existing ContextProvider seam — no new concept. Interop-first: reads the same SKILL.md format as Claude Code, MAF, and pydantic-ai-skills. Skills written once work everywhere.

**Downsides:** Only works when the engine resolves to ReAct (tools present). `dspy.Predict` agents get nothing. Script execution needs sandbox design (MAF ships its `SubprocessScriptRunner` with "demo-only" warnings). Adds 3 tools to every skill-enabled agent. Flock catches up to MAF, doesn't leapfrog.

**Confidence:** 80%
**Complexity:** Medium (1–2 weeks)
**Status:** Selected — alternative/fallback mode alongside #5/#6.

---

### 3. SKILL.md → Auto-Generated MCP Server

**Description:** `flock skills mcp-serve` reads a skill directory and emits an MCP server: each skill = one MCP tool, `scripts/` = additional tools, `resources/` = MCP resources. Agents consume via existing `with_mcps({server: {tool_whitelist}})`. One skill definition serves internal DSPy agents, external engines, and non-Flock consumers uniformly.

**Rationale:** Flock's MCP infrastructure already handles tool whitelisting, remoting, auth, caching, lazy loading. Skills inherit all of it for free.

**Downsides:** MCP conflates "methodology prose" with "callable tool" — CrewAI's explicit design stance ("skills ≠ tools") exists for a reason. Out-of-process hop per call. SKILL.md → MCP mapping requires a convention invention and defense.

**Confidence:** 70%
**Complexity:** Medium (~2 weeks)
**Status:** Rejected by Pyro (2026-04-17) — didn't catch.

---

### 4. Event-Triggered Signature Mutation (No `load_skill` Tool)

**Description:** No `load_skill` tool exposed to DSPy. When a blackboard artifact matches a skill's frontmatter `triggers:` (Pydantic type pattern), a ContextProvider rewrites the DSPy signature for the next engine call — body merged into `instructions`, helper callables appended to `tools`. Variant: a trace-watcher injects mid-ReAct when the LLM mentions a skill name (zero round-trip). Progressive disclosure done BY the orchestrator, not BY the LLM.

**Rationale:** DSPy signatures are typed and compiled — LLM-driven skill selection fights that model. Orchestrator-driven disclosure is deterministic, auditable, and Flock-unique (no other framework has compile-time signatures + blackboard to pull it off).

**Downsides:** Trigger DSL needs careful design (type-pattern matching is subtle). Non-LLM selection can miss soft matches the LLM would catch. Breaks DSPy's "one canonical signature" mental model.

**Confidence:** 65%
**Complexity:** Medium-High (~3 weeks)
**Status:** Rejected by Pyro (2026-04-17) — didn't catch.

---

### 5. Compile SKILL.md into DSPy Signatures at Registration

**Description:** At `agent.with_skills([...])`, a compiler parses SKILL.md frontmatter + body and merges into the DSPy signature:
- body → enriched `instructions` / `InputField` descriptions
- frontmatter `outputs:` → implicit output schema hints
- demo examples (if present) → bootstrap training data
- scripts → MCP side-channel (or `with_tools` if simple)

No runtime skill loader. Skills ARE the prompt. Optimizer-compatible: `MIPROv2`/`BootstrapFewShot` can operate on the resulting signature unchanged.

**Rationale:** DSPy is fundamentally a compiler. Pretending skills are dynamic is fighting the framework. Baked-in skills have zero token overhead for selection, full optimizer compatibility, and zero runtime tool-call surprises. Also: works for `dspy.Predict` agents (which #2 doesn't).

**Downsides:** Skills are static per agent (no per-call variance). Signatures grow with skill count. Diverges from Claude Code's filesystem-discovery convention — explicit `with_skills()` required. Pure-prose skills that don't fit the signature model are awkward (fall back to #2 mode).

**Confidence:** 70%
**Complexity:** Medium-High (2–3 weeks)
**Status:** Selected — primary compile-time mode.

---

### 6. Skills as Typed Blackboard Agents

**Description:** SKILL.md frontmatter declares `consumes:` / `publishes:` with real Pydantic type references. Loading a skill materializes a synthetic Flock agent subscribed to those types. Invocation = typed publish → cascade fires downstream subscribers. Script-based skills: each `scripts/foo.py` becomes its own ephemeral sub-agent (no `SubprocessScriptRunner`). `SkillSnapshotRecord` extends `AgentSnapshotRecord` naturally for discoverability + visibility + replay.

**Rationale:** The Flock-native answer. Leverages *every* unique substrate primitive: typed blackboard, automatic cascade, changelog replay, visibility filters, OTel tracing, batchspec parallelism. Skills become composable pipeline units. Impossible in MAF/CrewAI/LangGraph — they lack the substrate.

**Downsides:** Extends Anthropic's SKILL.md schema (interop risk — skills written this way won't run natively in Claude Code). Skill authors need Pydantic literacy. Pure-prose skills don't fit this mode (need #5 fallback). Biggest architectural commitment.

**Confidence:** 60%
**Complexity:** High (4–6 weeks)
**Status:** Rejected by Pyro (2026-04-17, scope cut) — cognitive load of "write SKILL.md so it becomes a blackboard agent" is too high for a PoC phase. Also: #5 already buys blackboard interaction for free, because the consuming agent still publishes through the normal cascade — skills don't need to be first-class blackboard citizens for cascades to fire. Revisit post-PoC if real-world use surfaces a need.

---

### 7. DSPy Optimizes SKILL.md Bodies Against Changelog Traces

**Description:** Flock's changelog already records every engine call with inputs/outputs. A periodic job feeds traces into DSPy's optimizer (`MIPROv2` / `BootstrapFewShot`) with the skill body as a tunable prompt. Optimized body writes back to `SKILL.optimized.md` (or versioned in-place with frontmatter stats). Skills self-improve from real production use — compounds across the team's Flock deployments.

**Rationale:** Literally no other framework can do this. DSPy is Flock's engine; changelog is Flock's training corpus. Every agent run makes the skill library measurably better. Biggest possible differentiator.

**Downsides:** Requires a baseline primitive first (#2, #5, or #6) — this is purely additive. Needs a success/failure signal on changelog entries (labels, heuristics, or downstream cascade validation). Risk of optimizer converging to brittle prose that wins on training but fails in prod. Authors lose authorship intent when bodies are overwritten.

**Confidence:** 70% (conditional on baseline)
**Complexity:** Medium additive (~2 weeks after baseline)
**Status:** Selected — force multiplier on top of #5/#6.

---

## Selected Path: #5 + #7 with #2 as alt-mode

Pyro's picks (2026-04-17, refined):
- **Primary:** #5 (compile SKILL.md into DSPy signatures at registration)
- **Multiplier:** #7 (DSPy optimizes skill bodies against changelog traces)
- **Alt-mode / fallback:** #2 (MAF-style `SkillsContextProvider` — runtime tool path for cases where compile-time doesn't fit)
- **Out:** #1 (explicitly want internal skills), #3 (didn't catch), #4 (didn't catch), #6 (scope cut — cognitive load too high for PoC; #5 already yields blackboard interaction via the consuming agent's normal cascade)

### Key insight from scope cut

**#5 alone already makes skill-enhanced agents full blackboard citizens.** The agent that has a skill compiled into its signature still publishes to the blackboard, still fires cascades, still shows up in OTel traces and changelog replay. Skills don't need to *be* first-class blackboard citizens for the cascade to work — the consuming agent carries them into the cascade transparently. #6's "skill = agent" abstraction was architecturally exciting but its interop cost (breaking Anthropic's SKILL.md schema, forcing Pydantic literacy on skill authors) is too high to pay until a real use case demands it.

### Core tension to resolve in surface-first (simplified)

With #6 out, the design space collapses to: **#5 (compile-time) + #2 (runtime fallback) — who decides which a given skill uses?**

**Option A — mode declared in SKILL.md frontmatter:**
```yaml
# skills/pdf-extract/SKILL.md
mode: inline   # body compiled into consumer's signature (#5)
# vs
mode: tool     # load_skill tool injected, body lazy-loaded (#2)
```

**Option B — caller picks the mode explicitly:**
```python
flock.agent(...).with_skills_compiled([...])    # #5
flock.agent(...).with_skills_available([...])   # #2 fallback
```

**Option C — unified API, compiler picks by shape:**
```python
flock.agent(...).with_skills([...])
# compiler: if signature-enrichable (prose + demos) → #5
#           else (too dynamic, or agent uses dspy.Predict) → #2
```

Graceful degradation for pure-prose skills ("how to write DHH-style Rails code" — no typed output, no demos) is the correctness constraint. Option C handles it most naturally; A forces every SKILL.md to pick; B is explicit but noisy.

### Proposed next steps

1. **Surface-first prototype** via `limitless:surface-first-development` — write sample user code for 3–4 realistic scenarios (typed-output skill, pure-prose skill, script-heavy skill, skill shared across agents) before touching architecture. Converge on Option A/B/C.
2. **Throwaway prototype on `feat/skills` branch** — implement #5 first (cheapest to feel), then layer #2 fallback, then #7 optimizer loop.
3. **Only after the surface feels right**, decide final architecture and write implementation plan.

Pyro's explicit concern: *"I can't tell how the proposed solutions 'feel' in the end without actually trying them."* → surface-first is the right workflow.

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Delegate to `ExternalEngineComponent` | Pyro explicitly wants internal DSPy agents to run skills, not punt to external |
| 3 | SKILL.md → auto-generated MCP server | Didn't catch Pyro; also: MCP conflates methodology with callable tool (CrewAI's concern) |
| 4 | Event-triggered signature mutation | Didn't catch Pyro; also: fights DSPy's "one canonical signature" mental model |
| 6 | Skills as typed blackboard agents | Scope cut — cognitive load too high for PoC; #5 already gives blackboard cascade via the consuming agent's publish. Revisit post-PoC if real use surfaces a need. |
| R1 | Skills as RAG corpus (embedding retrieval per call) | New infra (embedding index), uncertain win, duplicates filesystem/MCP semantics |
| R2 | Skills are the product, agents are scaffolding | Product pivot, not an "agents-run-skills" answer — better as brainstorm variant |
| R3 | Batch-apply skill across artifact collections | Contingent follow-on once baseline exists |
| R4 | Skills write learnings back to knowledge graph | Cross-cuts KG project; not skills-specific |
| R5 | Skill hot-reload + diff in dashboard | DX polish, not architectural |
| R6 | Per-agent skill glob scopes (`with_skills(["finance/*"])`) | Access-control polish; attaches to any baseline |
| R7 | OTel span per skill hop | Already covered (Flock has OTel); automatic with #6 |
| R8 | Two-mode Predict/ReAct split | Implementation detail of #2 |
| R9 | Skills compose skills via `uses:` dep graph | Ambitious follow-on; needs baseline |
| R10 | `SkillSnapshotRecord` as standalone idea | Falls out of #6 naturally |
| R11 | Lowering compiler (SKILL.md → right primitive) | Meta-story of #2+#3+#5 combined; cleaner split as separate ideas |
| R12 | Compile-time skill *selection* via optimizer | Overlaps #5 and #7 — nuance, not distinct |

## Session Log

- **2026-04-17:** Initial ideation — 40 raw candidates across 4 parallel ideation frames (user pain, inversion, reframing, leverage/compounding), deduped to ~19 unique concepts, second stricter pass → 7 survivors + cross-cutting combinations. Pyro initially selected #5+#6+#7 with #2 as alt-mode. Branch `feat/skills` created from `feat/meta-orchestrator` to host prototype work.
- **2026-04-17 (revision):** Pyro cut #6 from scope — reasoning: cognitive load of "write SKILL.md so it becomes a blackboard agent" is too high for PoC phase, and #5 already yields blackboard interaction for free via the consuming agent's normal publish/cascade. Final selected path is #5 + #7 + #2 (fallback). Surface-first design question simplified from 3-way (A/B/C over 3 modes) to 2-mode (compile-time vs runtime tool). Next step: route to `limitless:surface-first-development`.
