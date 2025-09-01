# Flock Testing TODOs

This plan tracks the next concrete tasks to complete and extend the test framework for the current Flock architecture. Items are ordered by priority and grouped for clarity.

## P0 — Stabilization and Quality Gates

- DONE Fix pytest config warning
  - Replaced `adopts` with `addopts` in `pyproject.toml`.

- WIP Enforce coverage per critical module
  - Current quick suite gates coverage at 50% for critical modules. Plan to raise to 60–70% as P1 expands, then 85%+ later.

- DONE Snapshot/golden tests for serialization
  - Added `tests/p0/test_serialization_snapshots.py` for `FlockAgent.to_dict()` (normalized).

## P1 — Broader Integration Coverage

- DONE Local executor paths
  - `tests/integration/test_local_context_and_history.py`: verifies namespaced inputs, run_id, and history records.

- DONE Error-path tests
  - Orchestrator: missing start agent raises `ValueError` (P0 test added).
  - Registry: ambiguous callable simple-name lookup raises `KeyError`.
  - Serialization: invalid component type is ignored (no component added).

- PARTIAL Telemetry attributes
  - Verified `run_id` presence and context variables; optional otel-marked span test added with in-memory exporter. Consider a future `FLOCK_OTEL_TEST` env-based shim to include span checks in default runs without external exporters.

- DONE Web API essentials
  - POST route with query/body models added in `tests/integration/test_webapi_post.py`.

## P2 — Optional Integrations (guarded by markers)

- Temporal integration (marker: `temporal`)
  - Tests that use `enable_temporal=True` and `temporal_start_in_process_worker=True` to run a single agent; verify result and context history.
  - Add env-guard and skip when Temporal server/tooling is not available.

- MCP integration (marker: `mcp`)
  - Register a minimal `FlockMCPServer`, expose one tool, and invoke it through an agent; assert result and lifecycle hooks.
  - Include error-path when server/tool is unregistered.

- Web UI subset (marker: `web`)
  - Smoke GET routes for a couple of HTMX views (200 + key template markers) to detect regressions without pulling frontend/JS.

## P3 — Performance and Robustness (non‑blocking)

- Performance baselines (marker: `perf`)
  - Measure time/memory budgets for Flock run and serializer on representative inputs; assert within thresholds (non-blocking in PRs, reported in CI job).

- Fuzz tests for type/signature parsing (optional dependency)
  - Use Hypothesis or lightweight generators to fuzz `serialization_utils` and `util.splitter.parse_schema`; validate no crashes and sensible fallbacks.

## Tooling and DX

- Optional speedups
  - Add `pytest-xdist` as an optional dev dependency and document `-n auto` usage for local runs (not required in CI).

- CI matrix and jobs
  - Ensure CI runs `uv run poe test` on PRs and a nightly job runs `uv run poe test-all`.
  - Upload coverage artifact; integrate Codecov (optional) for diff coverage comments.

- Contributor templates
  - Add a template example test file in `tests/_helpers/EXAMPLE.md` with a short walkthrough.

## Ownership and Tracking

## Release Must‑Haves (v0.5.0)

- Coverage (Core 80–85%)
  - Raise quick-suite gate incrementally to 80–85% for: `flock.core.flock`, `flock.core.flock_agent`, `flock.core.registry/*`, `flock.core.serialization/*`, `flock.core.context/*`, `flock.core.orchestration/*`.
  - Add targeted tests for weak spots: orchestration error paths (`_format_result`, exception → error dict vs Box), decorators error branches, serialization_utils dynamic imports.

- CI Integration
  - GitHub Actions matrix: Linux + macOS; Python 3.10/3.11/3.12.
  - PR quick job: `uv run poe test` (no network, excludes `otel`, `perf`).
  - Nightly job: `uv run poe test-all` (includes `otel`, `perf`, `temporal`, `mcp` when env present).
  - Upload coverage artifact; optional Codecov for PR diff coverage.

- Packaging Sanity
  - Build wheel/sdist: `uv build`.
  - Import sanity on built wheel: `python -c "import flock; import flock.core"`.

- Snapshot Contracts
  - Golden snapshots for `FlockAgent.to_dict` (simple + router+evaluator variants) and `Flock.to_dict` (two-agent, router present). Keep snapshots stable and intentional.

- Orchestration/Execution
  - Tests for `_execution.run_async` exception formatting and `_format_result` box vs raw.
  - Confirm local execution updates context/history (already covered) and memo handling if present.

- Discovery
  - Ensure “skip private modules” behavior and resilient logging on import errors (no crash) with a targeted test.

- Stability/Determinism
  - Confirm default suite performs no network/Temporal/MCP unless markers selected. Verify lazy imports avoid heavy deps during collection.

- Docs
  - Ensure `docs/testing_strategy.md`, `docs/testing_guide.md`, `docs/testing_todo.md` are linked in CONTRIBUTING/README and reflect final gates and commands.

## Strongly Recommended (Pre‑ or Post‑Release)

- Temporal integration test (marker `temporal`) using in‑process worker; skip when unavailable.
- MCP minimal test (marker `mcp`) with stub server + tool roundtrip.
- Telemetry shim `FLOCK_OTEL_TEST=1` to allow span assertions in default runs without exporters.
- Concurrency smoke for `RegistryHub` to validate thread safety.
- Property‑based fuzz tests for `splitter.parse_schema` and `serialization_utils.deserialize_item` (optional dep).

## Implementation Notes (Quick Guide)

- Use fixtures from `tests/conftest.py`; registry is auto‑cleared.
- For servers in tests, prefer minimal stubs with `.config.name` for registry exercises.
- For discovery tests, create temporary packages under `tmp_path` and update `sys.path` within the test.
- Telemetry: default is disabled via `FLOCK_DISABLE_TELEMETRY_AUTOSETUP=1`; run `-m otel` for optional span tests.

- Create GitHub issues for each bullet (link back to this file); tag with `tests` and the relevant area (orchestrator, registry, serialization, web, temporal, mcp).
- Use milestones: `Testing P0`, `Testing P1`, etc., to visualize progress.

---

If you want, I can start with the P0 fixes (pyproject `addopts` and adding a couple of snapshot tests) and open corresponding issues to track the rest.

