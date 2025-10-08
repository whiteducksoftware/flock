**Doc/Code Drift Analysis — Flock Flow**

Date: 2025-10-08
Scope: Public docs under `docs/`, `README.md`, `AGENTS.md`, examples, and code under `src/`. Ignored: `docs/internal/*` (per request).

---

**Executive Summary**
- Several user-facing docs are out of sync with the codebase, notably example paths, default model references, frontend location, and version numbers.
- Most impactful issues: broken example paths (Showcase/Features), incorrect frontend directory in contributor docs, inconsistent default model in snippets, and outdated version strings in AGENTS.md.
- API guidance around `invoke(..., publish_outputs=...)` vs `run_until_idle()` in AGENTS.md appears partially outdated relative to the current scheduler/feedback protections.

---

**High-Impact Issues (Fix First)**

- Wrong example paths in multiple docs
  - Docs point to non-existent local paths like `examples/showcase/*` and `examples/features/*`, while the repo uses numbered folders.
  - Evidence:
    - `AGENTS.md: Run Examples` lists `examples/showcase/*` and `examples/features/*`.
    - `docs/examples/index.md` links to GitHub paths for showcase/features that aren’t present locally.
    - Actual structure: `examples/01-the-declarative-way`, `examples/02-the-blackboard`, `examples/03-the-dashboard`, etc. (`examples/:1`).
  - Recommendation: Update all “Showcase/Features” references to the numbered example directories; verify remote GitHub links or change them to the numbered paths.

- Frontend directory mismatch in contributor and tooling docs
  - Docs instruct `cd frontend && npm install`, but the frontend lives at `src/flock/frontend/`.
  - Evidence:
    - Frontend exists at `src/flock/frontend` (`src/flock/frontend/:1`).
    - `docs/about/contributing.md: manual install` shows `cd frontend && npm install`.
    - `AGENTS.md: FAQ` says “Frontend: `/frontend/src`”, also incorrect vs `src/flock/frontend/src`.
  - Recommendation: Standardize on `src/flock/frontend` throughout. Replace all `cd frontend` with `cd src/flock/frontend`.

- Default model inconsistency across docs
  - Some docs use `"openai/gpt-4.1"`, others `"openai/gpt-4o-mini"`. Code defaults align with `gpt-4o-mini`.
  - Evidence:
    - Code fallback used by agents: `os.getenv("DEFAULT_MODEL", "openai/gpt-4o-mini")` in `src/flock/agent.py:304`.
    - `README.md` “Quick Start” uses `openai/gpt-4.1` (README.md: Quick Start section).
    - `docs/getting-started/installation.md` and many guides use `openai/gpt-4o-mini`.
  - Recommendation: Unify snippets to `openai/gpt-4o-mini` (matches code and installation guide). Optionally note that any LiteLLM-compatible model can be supplied.

- Version strings in AGENTS.md are stale
  - Evidence:
    - `AGENTS.md` shows “Current Version: 0.1.16” and a bump example from `0.5.0b56`.
    - Actual backend version: `pyproject.toml:3` → `0.5.0b61`.
    - Frontend version: `src/flock/frontend/package.json:2` → `0.1.4` (AGENTS.md mentions `0.1.2`).
  - Recommendation: Update AGENTS.md to reflect current versions or remove hard-coded numbers and instruct contributors to check `pyproject.toml` and `src/flock/frontend/package.json`.

---

**API/Behavior Guidance Drift**

- “Double execution trap” around `invoke()` + `run_until_idle()`
  - AGENTS.md warns that calling `run_until_idle()` after `invoke(..., publish_outputs=True)` triggers a second execution of the same agent.
  - Current code behavior:
    - `invoke()` (default `publish_outputs=True`) executes the target agent directly and only publishes its outputs; it does not publish the input artifact to the board (`src/flock/orchestrator.py:702–740`).
    - Scheduler prevents self-trigger by default: agents won’t re-consume their own outputs when `prevent_self_trigger=True` (default) (`src/flock/orchestrator.py:818–820`, `src/flock/agent.py:77`).
  - Implication: The originally reported “same-agent double execution” should no longer occur with defaults; `run_until_idle()` will process downstream agents that consume the published outputs, not re-run the invoked agent on the same input.
  - Recommendation: Revise AGENTS.md to clarify current behavior. Keep the guidance about using `publish_outputs=False` for isolated unit tests, but remove/soften the “double execution” claim for the same agent under default settings.

---

**Moderate Issues**

- Node.js version requirement mismatch
  - AGENTS.md and `docs/about/contributing.md` state “Node.js 22+”; frontend README states “Node 18+”.
  - Evidence: `src/flock/frontend/README.md: prerequisites` vs AGENTS.md/Contributing.
  - Recommendation: Align on the minimum version actually required by the frontend (18+ appears sufficient per current tooling). If 22+ is preferred for DevContainers, note it as “recommended”, not “required”.

- MkDocs navigation links to non-existent example categories
  - Evidence: `mkdocs.yml` has nav entries “Showcase” and “Features” pointing to GitHub folders that don’t exist in this repo tree.
  - Recommendation: Either remove those nav items or point to the numbered example directories or curated example pages in `docs/examples/`.

- Package build config includes a missing root `frontend/` package
  - Evidence: `pyproject.toml [tool.hatch.build.targets.wheel].packages = ["src/flock", "frontend/"]` but no `frontend/` at repo root; frontend is at `src/flock/frontend/`.
  - Risk: Potential packaging confusion; not a doc, but relevant to contributor instructions.
  - Recommendation: Update the packaging path or document the intended layout if a move is planned.

- Contributor workflow mentions tasks/hooks that don’t exist or are mis-scoped
  - Evidence:
    - `docs/about/contributing.md` references `poe test-e2e` (no such Poe task found in `pyproject.toml`).
    - Pre-commit frontend build hook filters on `^frontend/` but actually runs `cd src/flock/frontend && npm run build` (`.pre-commit-config.yaml`). This filter likely won’t trigger for changes under `src/flock/frontend`.
  - Recommendation: Remove or add the missing task; fix hook `files` patterns to match `src/flock/frontend/` or make it unconditional on pre-push.

- UV/Poe bootstrap notes don’t match the actual scripts
  - Evidence: `pyproject.toml` defines `_ensure-uv = "python scripts/ensure_uv.py"`, but `scripts/ensure_uv.py` is missing.
  - Impact: `poe install` may fail on the `_init` stage.
  - Recommendation: Add `scripts/ensure_uv.py` or remove the task from the chain; update contributor docs accordingly.

---

**Low-Impact/Editorial**

- Mixed install guidance (UV vs pip)
  - README encourages `pip install`, AGENTS.md stresses “UV (NOT pip!)”, installation doc recommends UV but allows pip. Mixed messaging can confuse new users.
  - Recommendation: Keep installation doc as the source of truth: “UV recommended, pip supported.” Reflect this in README and AGENTS.md for consistency.

- Migration notes
  - `docs/reference/index.md` says “arun() → invoke() (method renamed)”. Code still includes `arun()` as a convenience that wraps `invoke()+run_until_idle()`.
  - Recommendation: Clarify `arun()` remains available for compatibility, while `invoke()` is the preferred explicit API.

---

**Concrete Edit Checklist**

- AGENTS.md
  - Update “Current Version” (or remove hard-coded values).
  - Fix example paths to numbered directories.
  - Change frontend path to `src/flock/frontend` in all sections.
  - Align default model references on `openai/gpt-4.1`.
  - Revise the `invoke()` double-execution warning to reflect current behavior.

- README.md
  - Verify Quick Start uses `openai/gpt-4.1` and keep consistent with code/docs.

- docs/
  - `docs/examples/index.md` and `mkdocs.yml`: replace Showcase/Features links with numbered directories or a curated local examples page.
  - `docs/about/contributing.md`: fix frontend path, remove `poe test-e2e` (or add the task), and clarify Node version.
  - `docs/getting-started/*`, `docs/guides/*`: sweep for model strings and normalize to `openai/gpt-4.1` where appropriate.

- Tooling
  - `.pre-commit-config.yaml`: change frontend hook `files:` from `^frontend/` to `^src/flock/frontend/` (or unconditional on pre-push).
  - `pyproject.toml`: correct wheel package paths; remove `_ensure-uv` or add the missing script.

---

**Quick References (Evidence Pointers)**
- Backend version: `pyproject.toml:3`
- Frontend version: `src/flock/frontend/package.json:2`
- Frontend location: `src/flock/frontend/:1`
- Default model fallback: `src/flock/agent.py:304`
- Self-trigger guard: `src/flock/orchestrator.py:818–820`, `src/flock/agent.py:77`
- `invoke()` implementation: `src/flock/orchestrator.py:702–740`
- Examples layout: `examples/:1`
- Contrib doc frontend path: `docs/about/contributing.md`
- Frontend README Node version: `src/flock/frontend/README.md`
- MkDocs nav external example links: `mkdocs.yml`
- Pre-commit frontend hook filter: `.pre-commit-config.yaml`

---

**Notes**
- This analysis intentionally excludes `docs/internal/*` as requested.
- Recommend choosing a single source of truth for model defaults and example tree, then updating all user-facing docs to match.

---

**Proof of Work (2025-10-08)**

Changes implemented on branch `beta/fix/doc-drift`:

- Default model unified to `openai/gpt-4.1`
  - Code: `src/flock/agent.py` – change DSPyEngine fallback to `openai/gpt-4.1`.
  - Docs: `docs/index.md`, `docs/getting-started/installation.md`, `docs/reference/index.md`, `docs/guides/components.md`, `docs/guides/testing.md` updated to use `openai/gpt-4.1`.
  - Orchestrator docstrings: `src/flock/orchestrator.py` examples updated to `openai/gpt-4.1`.

- Examples paths corrected
  - `AGENTS.md` “Run Examples” now points to `examples/01-the-declarative-way/*` and `examples/03-the-dashboard/*`.
  - `docs/examples/index.md` rewritten to reference numbered local example folders and updated run commands.
  - `mkdocs.yml` nav: replaced Showcase/Features links with numbered example directories.

- Frontend path normalized
  - `docs/about/contributing.md`: replaced `cd frontend` with `cd src/flock/frontend` in all commands; updated Node version guidance to “18+ (22+ recommended)”.
  - `.pre-commit-config.yaml`: frontend build hook `files:` pattern corrected to `^src/flock/frontend/`.
  - `scripts/check_version_bump.py`: updated frontend path detection to `src/flock/frontend/...`.

- Version and packaging fixes
  - `AGENTS.md` header “Current Version” set to Backend `0.5.0b62`, Frontend `0.1.4`.
  - Backend version bumped in `pyproject.toml` to `0.5.0b62` (due to code changes).
  - `pyproject.toml` wheel packaging: removed non-existent `frontend/` path; now packages `src/flock` only.
  - Added `scripts/ensure_uv.py` referenced by Poe tasks to prevent install-time failures.

- API guidance corrected
  - `AGENTS.md` section on `invoke()` vs `run_until_idle()` rewritten: clarified that with default `prevent_self_trigger=True`, `run_until_idle()` does not re-run the same agent; downstream agents process published outputs. Kept guidance to use `publish_outputs=False` for unit tests.

- Misc docs cleanups
  - `docs/reference/index.md` environment examples updated (`DEFAULT_MODEL`, config YAML).
  - `AGENTS.md` “Where to save new files” frontend path updated to `src/flock/frontend/src`.
