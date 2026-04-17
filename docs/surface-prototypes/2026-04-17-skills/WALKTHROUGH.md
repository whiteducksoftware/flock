# Flock Skills — Surface Prototype (Round 1)

**Status:** Surface-first round 1. This is the opinionated developer experience I'm proposing. Nothing behind it is wired up yet. Walk through the 4 scenarios, tell me what feels wrong, what's missing, what should work differently. **Don't worry about internals.**

## The one-paragraph API

```python
agent.with_skills(
    "./skills/",              # directory (recursive discovery)
    "~/.flock/skills/",       # global skills
    runtime=False,            # False = compile-time (#5), True = MAF-style tool path (#2)
)
```

That's it. The compiler picks the mode per skill based on shape (types → compile; prose → compile as instructions; huge library → tool path). Frontmatter `flock.mode: tool` overrides per-skill.

**Discovery precedence** (first match wins for same-named skills):
1. `./skills/` (project)
2. `~/.flock/skills/` (user global)
3. `./.claude/skills/` (Claude Code compat — same files, same format)

---

## Scenario 1 — Typed-Output Skill (compile-time, happy path)

**Goal:** An `invoice-extractor` skill produces a typed `InvoiceExtracted` artifact. The skill is compiled into the agent's DSPy signature at registration.

**Skill authoring** — `example_skills/invoice-extractor/SKILL.md`:

```yaml
---
name: invoice-extractor
description: Extract structured data from unpaid invoice PDFs with high accuracy on totals and due dates.
license: MIT

flock:
  outputs: flock.examples.schemas.InvoiceExtracted
  demos: ./demos.jsonl
---

## When to use

Use when given a raw invoice PDF or image and asked to extract structured fields.
Prioritize the **total amount due** and **payment due date** — these are the most
frequently-wrong fields in downstream processing.

## How to extract

1. Scan header for vendor name and invoice number
2. Locate the "Total Due" / "Balance Due" field — not "Subtotal"
3. Parse the due date in ISO 8601
4. If line items are present, extract as a list; otherwise leave empty
```

**Consumer code** — `scenario_1_typed_output.py`:

```python
from flock import Flock
from flock.examples.schemas import RawInvoice, InvoiceExtracted

flock = Flock()

# The ONLY new API surface: .with_skills()
extractor = (
    flock.agent("invoice-extractor")
    .consumes(RawInvoice)
    .publishes(InvoiceExtracted)
    .with_skills("./example_skills/invoice-extractor/")
)

# Run it like any other Flock agent — skill behavior is transparent
async with flock.run() as session:
    await session.publish(RawInvoice(pdf_bytes=open("invoice.pdf", "rb").read()))
    await session.run_until_idle()
    result = session.query(InvoiceExtracted).one()
    print(result.total_due, result.due_date)
```

**What happens at registration** (simulated trace):

```
[flock.skills] Discovered 1 skill at ./example_skills/invoice-extractor/
[flock.skills] Compiling 'invoice-extractor' into agent 'invoice-extractor' signature
[flock.skills]   → outputs schema: InvoiceExtracted (resolved from flock.outputs)
[flock.skills]   → loaded 12 demos from demos.jsonl
[flock.skills]   → merged 847 chars of instructions into dspy.Signature
[flock.skills]   → mode: compile-time (shape: typed+demos)
[flock.engine] Agent 'invoice-extractor' ready with dspy.Predict(RawInvoice -> InvoiceExtracted)
```

**What happens at invocation** (simulated trace):

```
[flock.blackboard] publish: RawInvoice(pdf_bytes=<8432 bytes>)
[flock.scheduler] matched: agent 'invoice-extractor' (consumes=RawInvoice)
[flock.engine] dspy.Predict call (signature instructions include invoice-extractor skill body)
[flock.engine]   → tokens in: 1847 | out: 312
[flock.blackboard] publish: InvoiceExtracted(total_due=$4,823.00, due_date=2026-05-15, ...)
[flock.changelog] recorded: skill='invoice-extractor', success_signal=pending
```

**Feel check:** One method call. No ceremony. Skill is invisible from the caller's perspective except for the `.with_skills(...)` line.

---

## Scenario 2 — Pure-Prose Skill (methodology, no types)

**Goal:** A `dhh-rails-style` skill that teaches an agent how to write Rails code in DHH's opinionated style. No typed output — it's methodology injected into any agent that wants to produce Ruby.

**Skill authoring** — `example_skills/dhh-rails-style/SKILL.md`:

```yaml
---
name: dhh-rails-style
description: Write Ruby on Rails code in DHH's 37signals style — fat models, thin controllers, Hotwire over SPA, convention over configuration.
license: MIT
# No flock: block — pure prose, compile-as-instructions path
---

## Principles

1. **Fat models, thin controllers.** Business logic belongs in the model layer.
2. **REST resources over bespoke endpoints.** Seven actions. That's it.
3. **Hotwire over SPA.** Turbo frames, Stimulus, no React.
4. **Current attributes over thread locals.** Use `Current.user`, not `Thread.current[:user]`.
5. **Convention over configuration.** Don't configure what Rails already knows.

## How to apply

When generating Rails code, prefer:
- `ActiveRecord::Base` inheritance without STI unless forced
- `has_many :through` over join tables with explicit models
- Integer primary keys unless UUIDs are required for security
- `concerns/` for shared behavior across models
```

**Consumer code** — `scenario_2_pure_prose.py`:

```python
from flock import Flock
from flock.examples.schemas import RailsFeatureSpec, RailsCode

flock = Flock()

code_gen = (
    flock.agent("rails-coder")
    .consumes(RailsFeatureSpec)
    .publishes(RailsCode)
    .with_skills("./example_skills/dhh-rails-style/")  # same API, pure prose
)
```

**Simulated registration trace:**

```
[flock.skills] Discovered 1 skill at ./example_skills/dhh-rails-style/
[flock.skills] Compiling 'dhh-rails-style' into agent 'rails-coder' signature
[flock.skills]   → no typed outputs declared (pure prose)
[flock.skills]   → no demos
[flock.skills]   → merged 612 chars of instructions into dspy.Signature
[flock.skills]   → mode: compile-time (shape: prose-only — instructions-merge)
```

**Feel check:** Same API. Skill author didn't have to declare Pydantic types. Compiler handled the "no typed output" case automatically.

---

## Scenario 3 — Script-Heavy Skill (scripts + resources)

**Goal:** A `pdf-extract` skill has helper scripts in `scripts/` (PDF-to-text) and reference material in `references/`. Agent should be able to call scripts as tools.

**Skill authoring** — `example_skills/pdf-extract/SKILL.md`:

```yaml
---
name: pdf-extract
description: Extract text from PDF files with layout preservation. Uses pdfplumber for native PDFs and Tesseract for scanned ones.
license: MIT
allowed-tools: [Bash]

flock:
  sandbox: subprocess   # scripts run in isolated subprocess
  scripts:
    extract_text:
      run: python scripts/extract_text.py
      schema: flock.examples.schemas.ExtractTextArgs
    detect_scanned:
      run: python scripts/detect_scanned.py
      schema: flock.examples.schemas.DetectScannedArgs
---

## When to use

Given a PDF path, first call `detect_scanned` to choose the extraction path.
If native: call `extract_text` with `mode=native`.
If scanned: call `extract_text` with `mode=ocr` (slower, requires Tesseract).

## Scripts

- `scripts/extract_text.py` — native text extraction + OCR fallback
- `scripts/detect_scanned.py` — heuristic scanned-vs-native detection

## References

- `references/pdfplumber-cheatsheet.md` — coordinate math, table extraction tricks
- `references/tesseract-tuning.md` — language packs, DPI settings
```

**Consumer code** — `scenario_3_script_heavy.py`:

```python
from flock import Flock
from flock.examples.schemas import PDFPath, ExtractedText

flock = Flock()

extractor = (
    flock.agent("pdf-extractor")
    .consumes(PDFPath)
    .publishes(ExtractedText)
    .with_skills("./example_skills/pdf-extract/")  # scripts become tools automatically
)
```

**Simulated registration trace:**

```
[flock.skills] Discovered 1 skill at ./example_skills/pdf-extract/
[flock.skills] Compiling 'pdf-extract' into agent 'pdf-extractor' signature
[flock.skills]   → 2 scripts discovered: extract_text, detect_scanned
[flock.skills]   → script sandbox: subprocess (per frontmatter flock.sandbox)
[flock.skills]   → scripts exposed as tools: pdf-extract__extract_text, pdf-extract__detect_scanned
[flock.skills]   → engine auto-upgraded: dspy.Predict → dspy.ReAct (scripts present)
[flock.skills]   → references/ cataloged (lazy-loaded via read_skill_resource tool)
[flock.skills]   → merged 284 chars of instructions + 2 tools + 1 lazy-read tool
[flock.skills]   → mode: compile-time + ReAct (shape: scripts+resources)
```

**Feel check:** Scripts automatically surface as Flock tools. Engine silently switches to ReAct. `references/` stay lazy (only loaded when agent calls `read_skill_resource`). The `flock.sandbox: subprocess` keeps authors in control without forcing a bad default.

---

## Scenario 4 — Shared Skill Library Across Multiple Agents

**Goal:** One skill library (`~/.flock/skills/`) serves multiple agents. Each agent picks which skills it wants via glob patterns.

**Consumer code** — `scenario_4_shared_library.py`:

```python
from flock import Flock

flock = Flock()

# Agent 1: finance pipeline — only wants finance + methodology skills
invoice_agent = (
    flock.agent("invoice-processor")
    .consumes(RawInvoice)
    .publishes(InvoiceExtracted)
    .with_skills(
        "~/.flock/skills/finance/*",          # glob
        "~/.flock/skills/methodology/accounting-rules",  # explicit
    )
)

# Agent 2: security reviewer — wants security skills only, and forces runtime mode
# because the skill library has 50+ skills and wouldn't fit at compile time
security_agent = (
    flock.agent("security-reviewer")
    .consumes(CodeDiff)
    .publishes(SecurityFindings)
    .with_skills(
        "~/.flock/skills/security/*",
        runtime=True,  # opt into MAF-style tool path (#2)
    )
)

# Agent 3: general-purpose — inherits all globals + project-local skills
generalist = (
    flock.agent("assistant")
    .consumes(UserQuery)
    .publishes(Response)
    .with_skills()  # no args = use default discovery: ./skills/ + ~/.flock/skills/ + ./.claude/skills/
)
```

**Simulated registration trace (agent 2 — runtime mode):**

```
[flock.skills] Discovered 52 skills at ~/.flock/skills/security/
[flock.skills] Mode: runtime (caller opted in via runtime=True)
[flock.skills] Injecting tools into agent 'security-reviewer':
[flock.skills]   → load_skill(name: str) → str
[flock.skills]   → read_skill_resource(skill: str, resource: str) → str
[flock.skills]   → run_skill_script(skill: str, script: str, args: dict) → Any
[flock.skills] System prompt preamble: "You have access to 52 security skills. Call load_skill(...) to read a skill's body."
[flock.skills] Skill metadata injected (52 × ~80 tokens = 4160 tokens)
[flock.skills]   → mode: runtime (MAF-style tool injection)
[flock.engine] Agent 'security-reviewer' ready with dspy.ReAct(...)
```

**Feel check:** Same `.with_skills()` method. Glob patterns work. `runtime=True` is the single knob to flip when a library is too big for compile-time.

---

## #7 Optimizer CLI (Scenario 5 — bonus, not yet converged)

**Proposed CLI session** — `flock skills optimize invoice-extractor`:

```
$ flock skills optimize invoice-extractor \
    --from-changelog=last-30d \
    --success-signal=downstream-cascade-completed \
    --optimizer=MIPROv2

Loading traces from changelog (2026-03-18 → 2026-04-17)...
  Found 847 invocations of 'invoice-extractor'
  Filtering by success signal: 612 positive, 235 negative

Running dspy.MIPROv2 with SKILL.md body as tunable prompt...
  [Epoch 1/5] baseline score: 0.74
  [Epoch 2/5] score: 0.79 (+6.8%)
  [Epoch 3/5] score: 0.82 (+10.8%)
  [Epoch 4/5] score: 0.85 (+14.9%)
  [Epoch 5/5] score: 0.86 (+16.2%)

Proposed diff to ./example_skills/invoice-extractor/SKILL.md:
  @@ -12,3 +12,5 @@
   ## How to extract

  -1. Scan header for vendor name and invoice number
  +1. Scan header for vendor name and invoice number (often in top-right on US
  +   invoices, top-left on European ones)
   2. Locate the "Total Due" / "Balance Due" field — not "Subtotal"
  +3. If "Total Due" is absent, sum line items + tax — but flag this as uncertain

Apply? [y/n/d(iff)/s(ave-as-candidate)] _
```

**Feel check:** Manual trigger. Shows diff before writing. Save-as-candidate option lets you keep the optimized version side-by-side (`SKILL.optimized.md`) for A/B comparison.

---

## Decisions baked into this prototype (reacting welcome)

1. **One method (`.with_skills`), not three.** No `.with_skills_compiled()` / `.with_skills_available()` split. The compiler picks mode by shape; frontmatter or `runtime=True` overrides.
2. **Interop-first.** Anthropic's SKILL.md format is the wire format. Flock-specific metadata sits under `flock:` frontmatter key. Skills written for Claude Code work unchanged.
3. **Discovery defaults** are project → user global → Claude Code compat, first-match wins.
4. **Sandbox default by discovery path** — in-repo skills (`./skills/`, project-relative paths) default to `inprocess` (same trust boundary as your code); installed skills (`~/.flock/skills/`, `./.claude/skills/`) default to `subprocess` (third-party isolation). `flock.sandbox: inprocess|subprocess` in frontmatter overrides either default. *(Updated 2026-04-18 from "always in-process default" after document review.)*
5. **`#7 optimizer is CLI-triggered, not automatic.** Shows diffs, never overwrites silently.
6. **Engine selection is automatic** — scripts present → ReAct; no scripts + prose-only → Predict.

## What I want Andre to react to

- Does the one-method API (`.with_skills(...)`) feel right? Or should there be explicit compile/runtime variants?
- Does `flock:` frontmatter namespace feel clean? Or should Flock extensions be inline with Anthropic fields?
- ~~Is in-process the right default for scripts? Or should subprocess be the safe default with `sandbox: inprocess` as the opt-in?~~ **Resolved 2026-04-18 (document review):** sandbox default is by discovery path. In-repo → `inprocess`; installed (`~/.flock/skills/`, `./.claude/skills/`) → `subprocess`. `flock.sandbox` frontmatter overrides. Reconciles R2 (interop = shared skills) with the original "trust local authors" intuition without forcing every author to choose.
- Does `runtime=True` (single knob) cover enough cases, or do you want per-skill runtime-vs-compile control?
- The optimizer CLI — good enough, or do you want it hookable from a Python API too (e.g., `flock.optimize_skills(agent='invoice-extractor')`)?
- Anything about the 4 scenarios that doesn't cover a real case you have in mind?

---

## Out of scope for this prototype

- Authentication / ACLs on skills (can attach later to any baseline)
- Hot reload of SKILL.md (DX polish; not architectural)
- Cross-skill composition (`uses:` frontmatter) — deferred
- Skills publishing back to knowledge graph — deferred
- Blackboard-native skills (scope cut)
