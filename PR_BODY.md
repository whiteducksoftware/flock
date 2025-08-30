# Testing Framework Overhaul for v0.5.0-beta

This PR rebuilds Flock’s testing stack to be fast, deterministic, and contributor‑friendly, while raising core coverage and adding CI.

## Summary
- Replace legacy tests with a new, structured suite:
  - P0 (must‑have) and Integration tests, optional markers: `otel`, `temporal`, `mcp`, `web`, `perf`.
  - Deterministic fakes (`FakeEvaluator`, `FakeRouter`, `HookRecorder`) in `tests/_helpers`.
  - Registry isolation via autouse fixture.
- Core coverage ≥ 80% in the quick suite, focused on runtime modules:
  - `flock.core.flock`, `flock.core.flock_agent`, `flock.core.registry/*`, `flock.core.context/*`, `flock.core.orchestration.flock_execution`.
  - New tests cover orchestration error paths, run variants, serialization (agents + callables + tools), context introspection, registry (types/config/server/decorators/callables), YAML smoke, and discovery (nested, no private modules).
- Telemetry: safe by default
  - Tests disable auto setup via `FLOCK_DISABLE_TELEMETRY_AUTOSETUP=1`.
  - Added an `otel` marker for optional span tests.
  - Avoid user/provider override; respect existing tracer provider.
- Import side‑effect hardening
  - Guard HuggingFace `datasets` import to avoid pyarrow extension conflicts during tests.
  - Remove orchestration package side‑effect imports (lazy submodule imports).
- CI (GitHub Actions)
  - Quick job: Linux + macOS, Python 3.10/3.11/3.12, runs P0 + integration with an 80% core coverage gate.
  - Lint job: ruff check for src and tests.
  - Package job: build wheel/sdist; import sanity on source + installed wheel.
  - Nightly job (manual/scheduled): runs with optional markers (otel/perf); best‑effort.
- Contributor docs
  - `testing_strategy.md`, `testing_guide.md`, `testing_todo.md` updated.
  - `AGENT.md` adds a “Testing Workstream Guide” and release Must‑Haves.

## Notable Tests Added
- Orchestration errors → error dict/Box; run variants (default start, unknown agent, agents param, instance, Box)
- Agent serialization with callables/tools (to_dict names + from_dict resolution)
- Context: last agent, state vars, history, most recent value
- Registry: dynamic import by path and exact‑name, decorators happy path + error path, config mapping, server registry
- Snapshots: single‑agent and two‑agent (router + evaluator), Flock.to_yaml smoke
- Discovery: nested module registration

## Why this approach
- Fast, deterministic local/CI runs enable confident iteration.
- Scoped coverage gate ensures the most critical runtime surfaces are enforced without penalizing less relevant modules (UI/integrations) in the quick loop.
- Optional markers keep extended and integration‑heavy coverage available without slowing PRs.

## Follow‑ups (Release Must‑Haves → v0.5.0)
- Keep coverage ≥ 80% on core; consider nudging to 85% with a few more orchestration/registry tests.
- CI nightly: enable temporal/mcp tests when infra/credentials are available.
- Optional: `FLOCK_OTEL_TEST=1` shim to allow span assertions in default runs without external exporters.

## Developer Experience
- Run quick suite: `uv run poe test`
- Full/nightly: `uv run poe test-all`
- Select markers: `uv run pytest -m 'p0 or (integration and not otel)'`

This PR establishes a robust testing foundation for the v0.5.0 line, with CI and docs to keep it maintainable.
