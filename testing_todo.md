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

- Create GitHub issues for each bullet (link back to this file); tag with `tests` and the relevant area (orchestrator, registry, serialization, web, temporal, mcp).
- Use milestones: `Testing P0`, `Testing P1`, etc., to visualize progress.

---

If you want, I can start with the P0 fixes (pyproject `addopts` and adding a couple of snapshot tests) and open corresponding issues to track the rest.
