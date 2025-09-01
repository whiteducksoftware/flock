# Flock Testing Strategy

This document defines a clean, forward-looking testing strategy for Flock after the unified architecture refactor. It prioritizes correctness, contract stability, and contributor ergonomics. The plan resets the existing test suite and rebuilds it in a structured, high‑signal way.

## Goals

- Reliable green = working framework: a concise P0 suite must prove core behavior end‑to‑end.
- High coverage where it matters: serialization, orchestration, registry, and agent lifecycle.
- Fast feedback by default; slow/external tests opt‑in via markers.
- Deterministic, offline by default: no network/LLM calls unless explicitly enabled.
- Easy to contribute: clear layout, helpers, and examples.

## Test Pyramid & Priorities

- P0 — Must‑Have, Blocking CI (fast, deterministic)
  - Orchestration smoke: `Flock.run/run_async` with a minimal `FlockAgent` and components.
  - Serialization contracts: `Flock`, `FlockAgent`, `FlockContext` round‑trip via JSON/YAML and file paths.
  - Registry correctness: `RegistryHub` + component/callable/agent registration, discovery of a small sample module.
  - Agent lifecycle: initialize → evaluate → terminate hooks; primary evaluator/router resolution; component enable/disable.
  - Input/output contract parsing: dynamic signature parsing, DSPy signature creation guarded without importing `dspy` in P0.

- P1 — Core Integration (CI, may run in parallel, still deterministic)
  - Local execution engines: `local_executor`, routing across multiple agents, context propagation, next‑agent resolution.
  - Web API smoke: FastAPI app starts, 2–3 endpoints via `TestClient` (e.g., health, run, simple registry view).
  - Discovery: auto‑register from a toy package; callable/type/component registration mapping and ambiguity handling.
  - Logging/telemetry coupling: span creation on key paths without exporting over network.

- P2 — Extended Integration (non‑blocking in PRs; nightly or opt‑in)
  - Temporal integration: guarded by marker/env; uses in‑process worker path behind `enable_temporal=True`.
  - MCP servers and tools: start lightweight server(s), tool invocation lifecycle, error paths.
  - Web UI routes (HTMX) subset to detect template/render regressions.
  - Example integrations: minimal dataset evaluation path and metrics computation.

- P3 — Performance, Fuzzing, and Regression (scheduled/nightly)
  - Performance budgets: basic timing and memory smoke on orchestrator and serializer.
  - Fuzz inputs for signature/type parser and serializer robustness.
  - Golden outputs/snapshots for key serialization structures.

## Suite Layout

Tests live under `tests/` and mirror runtime concerns rather than files:

- `tests/p0/` — Green‑gate must‑haves (very fast, deterministic)
- `tests/integration/` — Cross‑module flows, local engine, discovery, web API smoke
- `tests/temporal/` — Temporal workflows (guarded)
- `tests/mcp/` — MCP server/tool integration (guarded)
- `tests/web/` — Extended FastAPI/UI coverage (guarded)
- `tests/perf/` — Performance baselines (non‑blocking)

Markers (to add in `pyproject.toml` under `tool.pytest.ini_options`):

- `p0`, `integration`, `temporal`, `mcp`, `web`, `perf`, `slow`, `network`

Common selectors:

- PR default: `-m "p0 or integration" -m "not slow and not temporal and not mcp and not web"`
- Nightly: `-m "p0 or integration or temporal or mcp or web or perf"`

## What To Test (Authoritative List)

P0 exact cases:

- Flock Orchestrator
  - `Flock.run_async` executes a single agent locally; returns dict/Box consistently; error path returns structured error.
  - Start‑agent resolution: explicit name, instance, default to single registered agent; errors for missing/ambiguous.
  - Context creation and `run_id` propagation; history record appended; last agent/result variables updated.

- Agent Lifecycle and Components
  - Lifecycle order: `on_initialize` → `on_pre_evaluate` → evaluator `evaluate_core` → `on_post_evaluate` → router `determine_next_step` → `terminate`.
  - Primary component selection: `get_primary_evaluator/router`; enable/disable filtering; duplicate name overwrite warning.
  - Model propagation via `FlockAgent.set_model` to evaluator config when supported.

- Registry Hub
  - Thread‑safe registration for agents, components, callables, servers; idempotency and overwrite warnings.
  - Callable lookup: exact name, suffix match, dynamic import, ambiguous name error; path string round‑trip.
  - Component discovery of a tiny module with 1 function, 1 dataclass/Pydantic type, 1 AgentComponent subclass.

- Serialization
  - `FlockAgent.to_dict/from_dict` preserves components, tool paths, dynamic specs (description/input/output), and next‑agent spec.
  - `FlockSerializer` includes component/type/callable definitions; file path handling for relative/absolute modes.
  - `FlockContext` history/state round‑trip; `next_input_for` behavior for 1 key vs multiple keys.

- Contract Parsing
  - Type resolution for simple and generic types; graceful fallback when unknown types; no import of he

## Fixtures and Utilities

- `registry_clear` (autouse): `get_registry().clear_all()` before/after to isolate tests.
- `simple_agent` factory: returns a `FlockAgent` with `FakeEvaluator` and optional router.
- `context_factory`: empty `FlockContext` with helpers for seeding variables/history.
- `test_pkg_factory(tmp_path)`: writes a tiny package to disk for discovery tests, adds to `sys.path` during test, and remove in `finally`.
- `web_app` factory: constructs FastAPI app router subset for smoke tests.

Place common fixtures in `tests/conftest.py`. Keep names stable and documented.

## Coverage Targets and Reporting

- Use `pytest-cov` with branch coverage on core source only: `--cov=src/flock --cov-branch`.
- Global threshold: 85% lines, 70% branches.
- Critical modules target: 90–95% lines (`core/flock.py`, `core/flock_agent.py`, `core/registry/*`, `core/serialization/*`, `core/context/*`).
- Fail CI if thresholds unmet; allow lower thresholds for P2/P3 only areas.

## CI Profiles (uv)

- Setup: `uv sync --dev --all-groups`.
- Fast check (PR default): `uv run pytest -q -m "p0 or integration" --cov=src/flock --cov-branch --cov-report=term-missing:skip-covered --cov-fail-under=85`.
- Full check (nightly): `uv run pytest -m "p0 or integration or temporal or mcp or web or perf"`.

Optional speedups: `pytest -n auto` with `pytest-xdist` (add later if needed).

## Contributor Guide (Quick Start)

1) Sync dev deps: `uv sync --dev --all-groups`
2) Run fast suite: `uv run poe test -q -m 'p0 or integration'`
3) Add tests near your change:
   - Create a small `FlockAgent` with a `FakeEvaluator` to keep tests deterministic.
   - Use `registry_clear` fixture; avoid real network/Temporal/LLMs.
4) Validate coverage locally using the PR command above.

Example minimal P0 test (sketch):

```python
def test_flock_smoke(simple_agent):
    flock = Flock(name="t", show_flock_banner=False)
    flock.add_agent(simple_agent)
    out = flock.run({"message": "hi"})
    assert out == {"result": "hi"}
```

## Implementation Plan (Phased)

Phase A — Scaffolding (day 1)
- Add `tests/p0`, `tests/integration`, `tests/temporal`, `tests/mcp`, `tests/web`, `tests/perf` folders.
- Create `tests/conftest.py` with core fixtures (`registry_clear`, `simple_agent`).
- Implement `FakeEvaluator`, `FakeRouter` test helpers inside `tests/_helpers`.
- Add pytest markers to `pyproject.toml`.

Phase B — P0 Coverage (days 1–2)
- Flock orchestrator smoke + errors; agent lifecycle; registry core; serializer round‑trip; context helpers; contract parsing.

Phase C — P1 Integration (days 2–3)
- Local multi‑agent routing; discovery; web API smoke; telemetry attributes.

Phase D — P2 Extended (days 3–4)
- Temporal in‑process path; MCP minimal scenario; limited UI route checks.

Phase E — P3 Non‑blocking (ongoing)
- Performance baselines; fuzzing; golden snapshots for serializer outputs.

## Definition of Green

- All P0 tests pass locally and in CI.
- Coverage meets global threshold; critical modules ≥ target.
- Integration smoke (`integration` marker) passes without network.
- No unexpected network/Temporal/LLM access in default runs.

When these conditions hold, the framework is considered healthy for contributors and downstream users.

