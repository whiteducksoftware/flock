# Flock Code & Design Improvements (Maintainer Review)

This document reviews the current Flock codebase with an eye toward pragmatic refactors that make the framework lighter, more elegant, and easier to extend. It complements (not repeats) the tactical items in docs/internal/must_have_for_0.5.0b.md and the earlier refactor plans.

Focus areas
- Reduce determinism/engine leakage into core (Temporal/DSPy/liteLLM specifics)
- Streamline component model and remove legacy seams
- Slim dependencies: move non‑core to extras; reduce cold‑start and install size
- Modernize orchestration and reactivity with a clean engine boundary
- Improve structure/ownership boundaries: core vs integrations vs web/CLI
- Add a productive, optional fluent DX layer that compiles to core primitives

## 0) Initial Improvement Plan (4‑Week Cut)

Goal for next release window: remove Temporal entirely and ship a DSPy‑only engine while keeping the rest of the codebase stable. No users are on Temporal today; removing it reduces risk and complexity immediately.

Scope (do now)
- Remove temporalio and all workflow/activity code paths (workflow/, temporal_config.py, executor wires, unsafe.imports_passed_through shims).
- Keep a single engine in core: DSPy (via DeclarativeEvaluationComponent), running locally.
- Retain MCP/tooling and web as optional extras; do not expand scope.
- Document a clean path to re‑introduce an external durable engine later (prefer Restate) once we have bandwidth.

Non‑goals for this cut
- No Restate implementation in core yet (we have POCs under vendor/ for prototyping).
- No major re‑structure of folders beyond removing Temporal code; save deeper layout changes for post‑release.

Benefits
- Smaller install, faster runs, fewer moving parts to stabilize in 4 weeks.
- Eliminates the determinism hacks and corner‑cases tied to Temporal’s workflow VM.

Follow‑on (post‑release)
- Introduce an engine boundary and add Restate as an optional engine (engines/restate) when ready.
- Split optional features into extras (see Section 4 and 5).

## 1) Architecture — Engine‑Agnostic, Component‑Centric Core

Current issues
- Temporal constraints bleed into core (unsafe.imports_passed_through in multiple modules; workflow info in logging; activity plumbing logic intertwined with orchestration)
- DSPy glue (signature building/type parsing/tool wrapping) sits in core mixins
- MCP/tooling code appears in core trees and shows up in agent hot paths

Recommendations
- Introduce an `ExecutionEngine` interface (local | temporal | restate). Flock orchestrator delegates to a single engine; engines live in `flock/engines/{local,temporal,restate}`.
  - Core orchestrator: pure async Python with no engine imports.
  - Temporal & Restate: adapters that translate the same “agent loop” (evaluate → route) into their runtime semantics.
- Isolate DSPy behind an `EvaluationEngine` (dspy | pydantic-ai | instructor | baml) surface. The DeclarativeEvaluationComponent picks from engines; core sees only “evaluate(input) -> dict”.
- Move MCP into `flock/integrations/mcp/` with a thin capability interface (list_tools, call_tool). Agent code depends on the interface, not DSPy tool types.

Outcomes
- Engine changes don’t cascade; unsafe import shims disappear from core
- Evaluation logic is swappable without touching agents or serialization
- Clear package boundaries, faster mental model for contributors

Note for the 4‑week cut: implement the “engine boundary” as a no‑op placeholder but keep only DSPy (local) wired. Add Restate/others later.

## 2) Component System — Fewer Concepts, Better Defaults

Current issues
- Unified components exist but still carry legacy patterns (routing/evaluation/utility overlap, some “modules” vestiges)
- Duplicate glue for “primary evaluator/router” selection and stream filtering
- Memory component modifies agent signature strings at runtime

Recommendations
- Codify three component kinds only: Evaluation, Routing, Utility.
  - Each component implements a small, explicit protocol; no extras.
  - Remove string‑based signature mutation from Memory; instead pass context to evaluator; evaluators can conditionally accept extra inputs based on runtime config.
- Add a small “Component Registry” plugin point; third‑party components are loaded by entry point or import path, not scanned implicitly.
- Normalize streaming: components emit Prediction objects (engine‑agnostic) and optional StreamEvents; post‑filters (hide thought/reasoning) apply once in the orchestrator.

Outcomes
- Less magic; fewer side effects; simpler component authorship
- Predictable streaming behaviors; smaller surface for bugs

## 3) Fluent DX Layer (Optional, Compile‑to‑Core)

Idea
- Provide a tiny DSL to define agents and reactive flows with guards, separate from core. The fluent layer compiles into core objects (Agents + Components + simple Routers) and reuses the orchestrator.

Why
- DX matters; most pipelines are simple chains with predicates and light transforms. A fluent API significantly lowers authoring friction while preserving testability through Pydantic IO.

How
- Package as `flock-dx` submodule (or extra). The builder returns a “CompiledFlock” (regular Flock under the hood). Guards compile to a routing component; map() compiles to an input transformer utility.

Outcomes
- Greatly improved ergonomics; no burden on core architecture

## 4) Dependencies — Slim by Default, Rich by Extras

Current issues
- pyproject lists many heavy dependencies (datasets, chromadb, multiple memory libs, azure SDKs, neo4j, opik) which increase install size and cold‑start.
- liteLLM proxy side‑effects try to import proxy deps for logging (apscheduler, cold storage) even when unused.

Recommendations
- Make core install minimal:
  - Keep: pydantic, httpx, python‑box, rich (or make UI logging optional), temporalio or restate only as extras, dspy as extra.
  - Move to extras: opik, datasets/pyarrow, chromadb, neo4j, azure‑* packages, mem libs, web UI deps, telemetry exporters.
  - Provide meta‑extras: `[engines]`, `[mcp]`, `[web]`, `[ai]`, `[memory]`, `[observability]`.
- Guard optional imports behind `try/except ImportError` with narrow shims; never import optional stacks from hot paths.
- Standardize on lightweight usage tracking (DSPy usage tracker or simple counters) and drop “cost” logic by default; expose a pluggable “pricing” adapter for teams who want cost.

Outcomes
- Faster installs and CI, fewer transitive conflicts, smaller containers

## 4.1) “Separate from core” — Packaging & Repo Strategy (with UV)

What “separate from core” means
- The core library (flock-core) contains only the orchestrator, components, serialization, and minimal evaluation adapter (DSPy for now). Everything else (web, MCP, DX layer, optional engines) lives in separate distribution packages. They can share a repo (monorepo) or live in separate repos; the important bit is they are separate Python packages with their own pyproject.toml and optional dependencies.

Recommended shape (monorepo first)
- Reorganize into packages/ with multiple Python dists:
  - packages/flock-core (required)
  - packages/flock-dx (optional fluent API; depends on flock-core)
  - packages/flock-mcp (MCP integration as ToolSpec adapter)
  - packages/flock-web (FastAPI UI; extra)
  - packages/flock-engines-restate (future; extra)
- Each has its own pyproject.toml. The top-level repo keeps a dev convenience script/Makefile.

Using UV in a monorepo
- Add/editable installs during dev: `uv pip install -e packages/flock-core packages/flock-dx`.
- Path deps between local packages: in pyproject, use PEP 508 path dependencies, e.g. `flock-core = { path = "../flock-core" }`.
- Dependency groups: keep `[dependency-groups]` for dev/test tooling. `uv sync --dev --all-groups` supports installing all groups.
- Extras: declare optional features in each package (e.g., `[project.optional-dependencies] web = ["fastapi", ...]`). Install via `uv pip install 'flock-web[all]'`.
- Locking: a single top-level `uv.lock` can be used if you install from the root with all local packages; or each package can maintain its own lock if you prefer isolation.

Separate repo vs submodules
- Start monorepo (simpler cross‑package refactors). Avoid git submodules unless you truly need independent lifecycles and access control — they add friction.
- If you later split repos, keep the same package names and publish to PyPI or an internal index; consumers switch from path deps to versioned deps. UV works fine with both published packages and local paths.

Best practice
- Keep core tiny and stable. Everything optional is a separate package with extras. Use path deps for tight inner‑loop dev, publish versions for consumers.

## 5) Package Layout — Clear Ownership and Isolation

Proposed structure
```
flock/
  core/              # Agent model, orchestrator, context, serialization
  engines/           # execution engines (local/temporal/restate)
  eval/              # evaluation engines (dspy/instructor/baml/pydantic-ai)
  components/        # evaluation/routing/utility
  integrations/
    mcp/
    telemetry/
    web/             # FastAPI (optional extra)
  cli/
  tools/             # small helpers only
```

Guidelines
- No engine or integration import inside core; integrations depend on core.
- Keep web app optional and out of critical path; provide a separate “flock-web” extra or repo.
- Docs/examples per engine and per evaluation backend to avoid conflation.

## 6) Orchestrator & Context — Performance and Clarity

Issues
- Context/history grows without clear caps; serialization copies large dicts.
- Double JSON round‑trips (dicts → pydantic → dicts) in hot paths.

Recommendations
- History/event log: ring buffer or configurable retention; store structured entries but flatten only on export.
- Use msgspec (optional) or pydantic v2 compiled validators to reduce conversion overhead in hot loops.
- Provide a “lightweight result” option that returns only outputs (no echoing inputs) unless a debug flag is set.

Outcomes
- Lower allocations and faster runs for iterative workflows

## 7) Logging/Telemetry — Deterministic and Quiet by Default

Issues
- Temporal replay‑unsafe logging guarded across files; liteLLM’s standard logging pulls optional proxy deps.

Recommendations
- Engine‑specific logging adapters. In engines/temporal, provide a logger that’s replay‑safe; in engines/local, use rich/loguru; in engines/restate, use `restate.getLogger()`.
- Default to minimal logs; enable verbose and exporters via extras. Avoid importing exporters by default.

Outcomes
- Clean console output and no surprise import chains

## 8) CLI & Web — Simplify and Decouple

Issues
- CLI overlaps with web and examples; web adds heft to core installs.

Recommendations
- CLI: focus on a few verbs (init, run, serve) and print actionable hints. Keep advanced commands in a separate “devtools” plugin.
- Web: move FastAPI app to `integrations/web` and guard behind extras; adopt server‑sent events for streaming using evaluation engine’s streaming_response helper.

Outcomes
- Smaller surface area; web evolves independently

## 9) MCP & Tooling — Single Abstraction, No DSPy Leakage

Issues
- Current tool wrappers reflect DSPy’s Tool; MCP conversions exist in core.

Recommendations
- Define a `ToolSpec` (name, args schema, call async) in core; evaluation engines adapt that to their internal types.
- Keep MCP in integrations/mcp, supply a converter MCP→ToolSpec.

Outcomes
- Tools feel consistent regardless of evaluation backend

## 10) Anti‑Patterns to Fix Incrementally

- Bare except/over‑broad exception handlers → replace with specific exceptions and re‑raise with context
- Runtime signature string mutation (Memory) → replace with evaluator‑side optional context consumption
- Global registries with implicit mutation → make registration explicit per test or provide a test‑only autouse fixture (already present in tests) and enforce API usage in code
- Mixed sync/async accessors (e.g., loop.run_until_complete scattered) → centralize sync wrapper in orchestrator only
- Duplicated streaming parsing → rely on prediction/stream events only
- Hard pins (e.g., openai==X) in core → loosen or move to extras

## 11) If I Maintained Flock — 6‑Month Shape

- Month 1: carve out engines and eval adapters; minimal extras split; keep Temporal+DSPy working
- Month 2: remove unsafe import guards from core; refactor Memory/signature mutation; standardize streaming
- Month 3: optional DX layer (fluent) that compiles to core; publish as extra; write 3 end‑to‑end examples
- Month 4: make web optional and adopt SSE streaming; simplify CLI; cut install size by >50%
- Month 5: reactive pilot with Restate engine (awakeables) and a SubscriptionComponent
- Month 6: harden docs + reference examples per engine; deprecate legacy module paths

Deliverables
- A lean core (core+components+orchestrator) with <15 direct deps
- Engines/eval backends in separate namespaces with extras
- Optional DX and web modules that layer on top cleanly

## 12) Concrete Next Steps

- Create `engines/{local,temporal,restate}` and move existing Temporal executor (no behavior change)
- Introduce `eval/{dspy,instructor}` with tiny adapters; move DSPy mixin logic there
- Replace Memory’s signature mutation with evaluator‑side optional context consumption
- Add ToolSpec; adjust MCP converter; stop exposing DSPy Tool types outside eval adapters
- Split pyproject deps into extras as outlined; cut core install
- Add `flock-dx` (optional) that compiles fluent definitions to core

These changes keep Flock’s philosophy (contract‑first, testable, production‑ready) while making the codebase smaller, faster, and friendlier — both for contributors and for the “AI agent orchestration” scenarios we want to excel at.

## 13) Temporal Removal Checklist (4‑Week Release)

- Dependencies
  - Remove `temporalio` and any Temporal-related pins from `pyproject.toml`.
  - Remove or guard any Temporal-specific dev/test deps.

- Source files to delete (or archive under `legacy/`)
  - `src/flock/workflow/` (flock_workflow.py, agent_activities*.py, temporal_config.py, temporal_setup.py, activities.py)
  - Any `orchestration/*` helpers that only exist for Temporal (leave general orchestration intact).

- Imports and guards to remove
  - `from temporalio import workflow` and `workflow.unsafe.imports_passed_through()` usages in core/logging/evaluation/etc.
  - Temporal-specific logging branches and exceptions (e.g., ActivityError handling in workflow code).

- Orchestrator wiring
  - In `FlockExecution`, remove branching to Temporal executor; keep only local run path.
  - Ensure `run()` and `run_async()` execute agents locally with no Temporal references.

- Examples / docs
  - Update examples to show only DSPy/local engine; mark Temporal docs as legacy and move under `docs/legacy/`.
  - Ensure README and getting-started mention only DSPy engine; add a short note that durable engines will return later as optional.

- Tests
  - Remove/skip Temporal-marked tests (`-m temporal`) and references.
  - Ensure quick suite remains green: `uv run poe test` with current coverage target.

- CI / packaging
  - Clean CI jobs of Temporal setup (worker startup, Temporal server spins).
  - Verify `uv build` + `python -c "import flock; import flock.core"` still pass.

- Sanity pass
  - Ripgrep for `temporal`, `workflow.unsafe`, `ActivityError`, `Temporal` and ensure no references remain in core.
  - Confirm import tree of `flock.core` pulls only minimal deps.
