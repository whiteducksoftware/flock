# Flock Skills — Derived Contracts (SFD Phase 4)

**Derived from:** `docs/surface-prototypes/2026-04-17-skills/` (surface converged 2026-04-17)
**Status:** Draft — pending Andre's manual pass before plan hand-off
**Companion:** `.sfd/decision-log.md`

These are the concrete decisions the converged surface demands. Anything under-specified here will bite during implementation.

---

## 1. Public API Surface (FlockAgent)

One new method on `FlockAgent`:

```python
class FlockAgent:
    def with_skills(
        self,
        *sources: str | Path | Skill,
        runtime: bool = False,
        token_budget: int | None = None,
    ) -> Self:
        """
        Attach skills to this agent.

        Args:
            *sources: Zero or more of:
                - Directory path (recursive SKILL.md discovery): "./skills/"
                - File path (single SKILL.md): "./skills/foo/SKILL.md"
                - Glob pattern: "~/.flock/skills/finance/*"
                - Skill object (pre-loaded)

                If empty, uses default discovery precedence:
                    ./skills/  →  ~/.flock/skills/  →  ./.claude/skills/

            runtime: If True, force MAF-style runtime tool injection (#2 path)
                for ALL discovered skills, regardless of frontmatter or size.
                Default False = shape-driven mode selection.

            token_budget: Max tokens for compile-time skill bodies merged into
                the signature. Skills exceeding this budget fall back to
                runtime tool mode (mixed-mode agent). Default: engine-specific
                (DSPyEngine default = 8000).

        Returns:
            self (fluent API)

        Raises:
            SkillNotFoundError: source path/glob matched zero skills
            SkillParseError: malformed SKILL.md frontmatter
            SkillSchemaResolutionError: flock.outputs dotted path cannot resolve
        """
```

No `with_skills_compiled()` / `with_skills_available()` variants. One method, shape-driven.

---

## 2. Frontmatter Schema

SKILL.md frontmatter is the Anthropic standard **plus** an optional `flock:` namespace. Anthropic fields are passed through unchanged; Flock ignores what it doesn't own.

### Anthropic standard (pass-through, validated loosely)

```yaml
name: string (required, ≤64 chars, lowercase-hyphen)
description: string (required, ≤1024 chars)
license: string (optional)
compatibility: string (optional)
metadata: object (optional, passed through)
allowed-tools: list[string] (optional, advisory only — Flock does its own sandboxing)
```

### Flock extensions (`flock:` namespace, all optional)

```python
from pydantic import BaseModel
from typing import Literal

class FlockSkillMetadata(BaseModel):
    """Schema for the `flock:` key in SKILL.md frontmatter."""

    outputs: str | None = None
    """Dotted import path to a Pydantic BaseModel describing the skill's
    structured output. When present, skill participates in compile-time
    signature mutation (#5 path). Example: 'flock.examples.schemas.InvoiceExtracted'"""

    demos: str | None = None
    """Relative path (from SKILL.md) to a JSONL file of demonstration examples.
    Each line is {input: {...}, output: {...}} matching the signature.
    Used by dspy.BootstrapFewShot / MIPROv2."""

    mode: Literal["auto", "inline", "tool"] = "auto"
    """Override the compiler's shape-driven mode selection.
    - auto (default): compiler picks by shape + token budget
    - inline: force compile-time merge into signature (#5)
    - tool: force runtime tool path (#2) regardless of caller's runtime=False"""

    sandbox: Literal["inprocess", "subprocess"] = "inprocess"
    """Script execution isolation level.
    - inprocess (default): scripts run as Python imports in the agent's process
    - subprocess: scripts run via subprocess.run with Flock-provided isolation"""

    scripts: dict[str, ScriptSpec] | None = None
    """Named scripts exposed as Flock tools. Keys become tool names:
        <skill_name>__<script_name>"""

    token_cost_estimate: int | None = None
    """Optional hint — overrides auto-estimation for budget decisions.
    Useful for skills with large non-prose assets (tables, reference material)."""


class ScriptSpec(BaseModel):
    run: str
    """Shell command to invoke the script.
    Relative paths resolve from the skill directory."""

    schema: str | None = None
    """Dotted import path to a Pydantic BaseModel describing script arguments.
    When present, Flock validates args before invocation and generates a JSON
    Schema for the LLM tool surface."""

    returns: str | None = None
    """Dotted import path to the script's return type (Pydantic model or primitive).
    Used for downstream typed publishing if the script's result becomes an artifact."""

    timeout_seconds: int = 60
    """Hard timeout for script execution. Subprocess scripts are SIGKILLed;
    in-process scripts are monitored via asyncio.wait_for."""
```

### Example: full-featured skill

```yaml
---
name: invoice-extractor
description: Extract structured data from invoice PDFs
license: MIT
allowed-tools: [Bash]

flock:
  outputs: flock.examples.schemas.InvoiceExtracted
  demos: ./demos.jsonl
  mode: auto
  sandbox: inprocess
  scripts:
    validate_totals:
      run: python scripts/validate_totals.py
      schema: flock.examples.schemas.ValidateTotalsArgs
      returns: flock.examples.schemas.ValidationResult
      timeout_seconds: 30
---
```

### Example: pure-prose skill (minimal)

```yaml
---
name: dhh-rails-style
description: Write Ruby on Rails code in DHH's 37signals style
---
```

No `flock:` block → mode defaults to `auto` → compiler detects no types, no scripts, no demos → falls back to instructions-only merge.

---

## 3. Core Types

File layout: `src/flock/skills/` (new module)

```python
# src/flock/skills/types.py

from dataclasses import dataclass
from pathlib import Path
from typing import Type
from pydantic import BaseModel


@dataclass(frozen=True)
class Skill:
    """A single loaded skill. Immutable snapshot — reload by re-discovering."""

    name: str
    description: str
    body: str                           # SKILL.md body (frontmatter stripped)
    directory: Path                     # absolute path to the skill directory
    flock_meta: FlockSkillMetadata      # parsed flock: frontmatter (defaults if absent)
    anthropic_meta: dict                # remaining frontmatter (pass-through)
    outputs_model: Type[BaseModel] | None = None  # resolved from flock.outputs
    demos: list[dict] | None = None     # loaded from flock.demos JSONL
    resources: dict[str, Path] | None = None  # references/*, lazy-loaded
    content_hash: str = ""              # SHA-256 of body + frontmatter (cache key)

    @property
    def qualified_name(self) -> str:
        """For tool namespacing: always <skill_name>__*"""
        return self.name

    def estimated_tokens(self) -> int:
        """Uses flock.token_cost_estimate if set, else heuristic (chars / 4)."""
```

```python
# src/flock/skills/registry.py

class SkillRegistry:
    """Discovery + caching. One registry per Flock instance."""

    def __init__(self, flock: Flock):
        self.flock = flock
        self._cache: dict[str, Skill] = {}

    def discover(
        self,
        *sources: str | Path | Skill,
        use_defaults: bool = False,
    ) -> list[Skill]:
        """Resolve sources to a flat list of Skills.
        Applies precedence rule: first match wins for same-named skills."""

    def by_name(self, name: str) -> Skill | None: ...
    def invalidate(self, path: Path | None = None) -> None: ...
```

---

## 4. Discovery Algorithm

```
Input: sources (list of Path | str | Skill), use_defaults (bool)
Output: ordered list of Skills, deduplicated by name (first wins)

1. If sources is empty AND use_defaults:
     sources = [
       "./skills/",
       "~/.flock/skills/",
       "./.claude/skills/",
     ]
   Else if sources is empty:
     return []

2. For each source in order:
   a. If Skill object → yield directly
   b. If path ends in SKILL.md → load single skill
   c. If glob pattern (contains * or ?) → expand via pathlib.Path.glob
   d. If directory → recursively find all SKILL.md files (depth-first, alphabetical)

3. Deduplicate by Skill.name, first occurrence wins.
   Log a DEBUG message when later skills are shadowed by earlier ones.

4. Validate each skill's frontmatter (raise SkillParseError on failure).

5. Cache all resolved skills in registry._cache, keyed by content_hash.
```

**Precedence rationale:** local project > user global > Claude Code compat. Matches Claude Code's conventions while letting project skills override globals.

---

## 5. Compilation Contract (Shape → Mode Selection)

When `agent.with_skills(...)` is called:

```
For each discovered skill:
  effective_mode = skill.flock_meta.mode
  if effective_mode == "auto":
      effective_mode = _shape_select(skill, caller_runtime_flag, running_token_budget)

  if caller passed runtime=True:
      effective_mode = "tool"  # caller override wins over auto

  if skill.flock_meta.mode == "tool":
      effective_mode = "tool"  # frontmatter force wins even over caller

  → attach to agent per effective_mode

_shape_select(skill, caller_runtime, budget) logic:
  if caller_runtime is True:
      return "tool"
  if budget - running_total < skill.estimated_tokens():
      return "tool"   # token budget exceeded
  return "inline"     # default path
```

### Inline mode → how skill flows into `dspy.Signature`

Given a skill with `outputs_model = InvoiceExtracted` and body = `"Use when..."`:

```python
# Before compilation:
# DSPyEngine builds signature from consumes=[RawInvoice], publishes=[InvoiceExtracted]

class _RawInvoiceToInvoiceExtracted(dspy.Signature):
    """<<< skill body goes here as docstring instruction >>>"""
    raw_invoice: RawInvoice = dspy.InputField(desc=...)
    invoice_extracted: InvoiceExtracted = dspy.OutputField(desc=...)

# After compilation with skill:
_SKILL_INSTRUCTIONS = """
## When to use
Use when given a raw invoice PDF...
## How to extract
1. Scan header for vendor...
"""  # = skill.body verbatim

class _RawInvoiceToInvoiceExtractedWithSkill(dspy.Signature):
    __doc__ = _SKILL_INSTRUCTIONS + "\n\n" + _base_doc
    raw_invoice: RawInvoice = dspy.InputField(desc=...)
    invoice_extracted: InvoiceExtracted = dspy.OutputField(desc=...)

# Demos (if present) feed dspy.Predict / dspy.ReAct via bootstrap
if skill.demos:
    for demo in skill.demos:
        dspy.settings.compiler.add_demo(demo)  # pseudocode — actual API TBD
```

**Rules:**
- Multiple inline skills → bodies concatenated in discovery order, separated by `## --- <skill_name> ---` headers
- Skill body becomes part of signature docstring; DSPy treats this as instruction
- Skill's `outputs_model` must be compatible with the agent's declared `.publishes(...)` (validated at `.with_skills()` time — raise `SkillOutputMismatchError` otherwise)
- If skill declares `outputs_model` but agent has no `.publishes(...)`, skill becomes a *signature-refiner* only (no schema change, body merged as instructions)

### Tool mode → runtime injection contract

When any skill resolves to `mode="tool"`, the agent's `combined_tools` list gains three tools:

```python
@tool
def load_skill(name: str) -> str:
    """Load the full body of a named skill. Returns markdown instructions."""

@tool
def read_skill_resource(skill: str, resource: str) -> str:
    """Read a file from a skill's references/ directory."""

@tool
def run_skill_script(skill: str, script: str, args: dict) -> dict:
    """Invoke a named script from a skill. Args must match the script's declared schema."""
```

System prompt preamble (injected by `SkillsContextProvider`):

```
You have access to {n} skills:
{name_description_table}

Call load_skill(name) to load a skill's full instructions when the task matches.
Call read_skill_resource(skill, resource) for additional reference material.
Call run_skill_script(skill, script, args) to execute a skill's helper script.
```

**Rule:** `mode="tool"` auto-upgrades the DSPy engine from `dspy.Predict` to `dspy.ReAct` because tools are now present. This is existing Flock behavior; skills simply trigger it.

### Mixed mode (same agent, some inline some tool)

When some skills fit the budget and others don't, both paths coexist:
- Inline skills: bodies merged into signature
- Tool-mode skills: metadata in system prompt preamble, bodies lazy via `load_skill`
- Engine: ReAct (because tools present)

---

## 6. `SkillsContextProvider` Contract

Subclass of Flock's existing `ContextProvider`. Plugs into the standard lifecycle.

```python
# src/flock/skills/context_provider.py

class SkillsContextProvider(ContextProvider):
    """Injects skill context into the engine pipeline.

    Lifecycle hooks used:
        - initialize(): resolve skills via registry, decide per-skill mode
        - pre_evaluate(): build signature mutation + tool list for this invocation
    """

    def __init__(
        self,
        skills: list[Skill],
        runtime_override: bool = False,
        token_budget: int = 8000,
    ): ...

    async def pre_evaluate(self, ctx: AgentContext) -> AgentContext:
        """Returns a context with:
        - ctx.signature_overrides: instructions merge from inline skills
        - ctx.additional_tools: [load_skill, read_skill_resource, run_skill_script]
            (only if any tool-mode skills attached)
        - ctx.system_prompt_preamble: skill catalog table (tool mode only)
        """
```

**Integration with existing Context Providers:** composable. `SkillsContextProvider` runs *before* `DefaultContextProvider` so skill instructions are visible but user-supplied context still wins on conflict. Composition order is configurable on the agent.

---

## 7. Script Execution Contract

```python
# src/flock/skills/scripts.py

class ScriptRunner:
    """Strategy interface for script execution."""

    async def run(
        self,
        skill: Skill,
        script_name: str,
        args: dict,
    ) -> dict: ...


class InProcessRunner(ScriptRunner):
    """Default. Imports the script module; calls a main(args) function.
    Script must expose: def main(args: <schema>) -> <returns>"""

class SubprocessRunner(ScriptRunner):
    """Invoked when flock.sandbox: subprocess in frontmatter.
    Calls frontmatter.scripts[script_name].run via asyncio.create_subprocess_exec.
    Stdin = JSON-encoded args. Stdout = JSON-encoded result.
    Honors timeout_seconds. SIGKILL on overrun."""
```

**Security:** `allowed-tools` frontmatter is advisory only in Flock (Anthropic spec compat) — Flock's real isolation layer is `flock.sandbox`. Document this clearly; MAF makes the same choice.

**Error contract:** script runners raise `SkillScriptError` on non-zero exit / timeout / schema-validation-failure. Error includes stderr, exit code, elapsed time. Agent handles it like any other tool error.

---

## 8. Optimizer CLI Contract (`#7`)

New CLI command under `flock skills ...`:

```
flock skills optimize <skill_name>
  --from-changelog <since>       # e.g. "last-30d", "2026-03-18..", "last-1000"
  --success-signal <signal>      # "downstream-cascade-completed" | "no-errors" |
                                 #   "user-feedback-positive" | custom expression
  --optimizer <name>             # "MIPROv2" | "BootstrapFewShot" | custom
  --apply                        # skip confirmation prompt, write directly
  --save-as-candidate            # write to SKILL.optimized.md instead of overwriting
  --output <path>                # explicit output path
```

**Changelog query contract:**
```python
traces = changelog.query(
    skill_name=skill_name,
    since=parse_time_spec(since),
    agent_name_filter=None,  # all agents that used this skill
).as_dspy_trainset(success_predicate=success_signal)
# → list[dspy.Example] with input/output/score
```

**Output:** unified diff against SKILL.md; prompt user to apply unless `--apply`. Writes:
- `SKILL.md` (if applied)
- `.flock/skills/optimization-history/{skill}-{timestamp}.json` (audit trail: score before/after, optimizer config, trace IDs used)

**Python API (symmetric to CLI):**
```python
from flock.skills.optimize import optimize_skill

result = await optimize_skill(
    skill_name="invoice-extractor",
    flock=flock,
    since="last-30d",
    success_signal="downstream-cascade-completed",
    optimizer="MIPROv2",
)
# result: OptimizationResult(before_score, after_score, diff, optimized_body)
```

---

## 9. Error Taxonomy

```python
# src/flock/skills/errors.py

class SkillError(FlockError): ...  # base

class SkillNotFoundError(SkillError):
    """Source path/glob matched zero skills."""

class SkillParseError(SkillError):
    """SKILL.md frontmatter or body malformed."""

class SkillSchemaResolutionError(SkillError):
    """flock.outputs / flock.scripts.*.schema / .returns dotted path unresolvable."""

class SkillOutputMismatchError(SkillError):
    """Skill's outputs_model incompatible with agent's .publishes() signature."""

class SkillBudgetExceededError(SkillError):
    """Raised only in strict mode; normally budget overflow silently falls to tool mode."""

class SkillScriptError(SkillError):
    """Script execution failure — exit code, timeout, schema validation, etc."""

class SkillConflictError(SkillError):
    """Two skills with same name in explicit sources (not discovery precedence)."""
```

**Agent-level error handling:** script errors surface to the engine as tool errors (existing handling). Compile errors raise at `.with_skills()` time — fail fast, clearly.

---

## 10. Testing Contract

What we need for confidence:

### Unit tests
- `test_frontmatter_parse` — Anthropic + `flock:` variants, minimum fields, malformed cases
- `test_discovery_precedence` — shadow rules, glob expansion, defaults
- `test_shape_select` — inline vs tool decision matrix
- `test_signature_mutation` — skill body → dspy.Signature docstring
- `test_tool_injection` — load_skill/read_skill_resource/run_skill_script tool schemas
- `test_script_runner_inprocess` / `test_script_runner_subprocess` — happy path + timeout + schema validation

### Integration tests (against real DSPy + blackboard)
- `test_scenario_1_typed_output` — scenario_1_typed_output.py runs end-to-end with a mocked LLM
- `test_scenario_2_pure_prose` — same for scenario 2
- `test_scenario_3_script_heavy` — subprocess runner, ReAct engine, references lazy-loaded
- `test_scenario_4_shared_library` — multi-agent, glob, runtime=True, default discovery

### Optimizer tests (deferred until baseline ships)
- `test_changelog_query_to_trainset` — DSPy example format conversion
- `test_optimize_skill_dry_run` — produces diff without writing

---

## 11. File Layout (proposed)

```
src/flock/skills/
  __init__.py                 # public exports: Skill, FlockSkillMetadata
  types.py                    # Skill, FlockSkillMetadata, ScriptSpec
  registry.py                 # SkillRegistry, discovery algorithm
  frontmatter.py              # YAML parsing + Anthropic/flock: schema
  context_provider.py         # SkillsContextProvider
  compilation.py              # shape-select, signature-mutation, demo injection
  tools.py                    # load_skill / read_skill_resource / run_skill_script
  scripts.py                  # ScriptRunner, InProcess, Subprocess
  errors.py                   # SkillError hierarchy
  optimize/
    __init__.py
    cli.py                    # flock skills optimize command
    trainset.py               # changelog → dspy.Example conversion
    runner.py                 # MIPROv2 / BootstrapFewShot drivers
tests/skills/
  unit/
    test_frontmatter.py
    test_registry.py
    test_compilation.py
    test_scripts.py
    ...
  integration/
    test_scenario_1.py
    test_scenario_2.py
    test_scenario_3.py
    test_scenario_4.py
examples/skills/              # runnable examples (separate from tests)
  invoice-extractor/
  dhh-rails-style/
  pdf-extract/
  ...
```

Integration point on `FlockAgent`: new file or extend existing?
- **Preferred:** extend `src/flock/core/agent.py` with one method (`.with_skills()` near `.with_tools()` / `.with_mcps()`). Keep `src/flock/skills/` as the implementation surface; `agent.py` imports from it.

---

## 12. Open Questions (flagging for plan hand-off)

1. **DSPy demo injection API** — needs verification. Does `dspy.Predict.forward()` accept per-call demos, or do demos have to be set via `dspy.settings.compiler`? If the latter, skill demos compete globally with user-registered demos. → research during implementation.

2. **Token estimation accuracy** — simple `len(text) / 4` is approximate. Is tiktoken worth the dep for budget decisions? → start cheap; add tiktoken if users report bad mode decisions.

3. **Script sandbox defaults** — I proposed `inprocess` default. Security-conscious users might disagree. Revisit after dogfood — if someone footguns, flip to `subprocess` default with explicit `inprocess` opt-in. Low blast radius either way since both are per-skill.

4. **Subscription-based skill loading** — deferred per ideation (scope #6 out). But: is there a natural hook where SKILL.md can still declare blackboard-artifact awareness without going full-agent? E.g., `flock.auto_attach_to: [InvoiceExtracted consumer agents]` as a convenience? → post-PoC decision.

5. **Changelog success signal grammar** — `"downstream-cascade-completed"` is a convenient string; what's the actual predicate language? Small DSL? Python callable? → design in plan phase, not now.

---

## What a Successful Implementation Looks Like

The minimum viable shipping definition (Gate 4):

- `scenario_1_typed_output.py` runs end-to-end, produces an `InvoiceExtracted` artifact, hits the blackboard, triggers any downstream subscriber
- `scenario_2_pure_prose.py` runs end-to-end, rails-coder produces Ruby code
- `scenario_3_script_heavy.py` runs end-to-end with subprocess sandbox
- `scenario_4_shared_library.py` — all three agents start, agent 2 (runtime mode) exposes the 3 tools in its ReAct loop
- `flock skills optimize` produces a non-trivial diff on a seeded changelog
- Full test matrix green in CI
- No regressions in the existing 2558 passing tests

Everything else is polish.
