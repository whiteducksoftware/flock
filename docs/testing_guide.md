# Flock Testing Guide

This guide helps new contributors write, run, and maintain tests for Flock. It complements testing_strategy.md by focusing on hands‑on workflow, requirements, and examples.

**Quick Start**
- **Install deps:** `uv sync --dev --all-groups`
- **Run quick suite:** `uv run poe test` (P0 + integration, deterministic)
- **Run full suite:** `uv run poe test-all` (includes optional markers)
- **Select markers:** `uv run pytest -m 'p0 and not slow'`

**Suite Structure**
- `tests/p0/`: Must‑have, fast, deterministic checks that gate CI.
- `tests/integration/`: Cross‑module flows (local engine, discovery, web API smoke).
- `tests/temporal/`: Temporal workflows (guarded with `@pytest.mark.temporal`).
- `tests/mcp/`: MCP server/tool integration (guarded with `@pytest.mark.mcp`).
- `tests/web/`: Extended FastAPI/UI routes (guarded with `@pytest.mark.web`).
- `tests/perf/`: Non‑blocking performance baselines.
- `tests/_helpers/`: Shared test helpers (e.g., `FakeEvaluator`, `FakeRouter`, `HookRecorder`).
- `tests/conftest.py`: Global fixtures (`registry_clear`, `register_fakes`, `simple_agent`).

**Core Principles**
- **Deterministic:** No network/LLM/Temporal unless explicitly marked. Results should be repeatable.
- **Isolated:** Use `registry_clear` (autouse) to reset global registry state between tests.
- **Fast:** Keep P0 and integration tests sub‑second when possible; avoid sleeps.
- **Box‑agnostic:** Many APIs return `Box` by default; prefer dict‑equivalent assertions (`== { ... }`).
- **Explicit markers:** Use `@pytest.mark.temporal`, `mcp`, `web`, `perf`, `slow`, `network` as appropriate.
- **Coverage:** CI requires `--cov=src/flock --cov-branch` with ≥85% lines global; aim 90–95% for core modules.

**Process: Adding or Changing Tests**
- **1. Classify:** Decide where your test belongs.
  - Component/API contract → `p0`
  - Cross‑module/local engine/web API smoke → `integration`
  - Temporal/MCP/UI/perf → respective folders; add marker.
- **2. Scaffold:** Create a new `test_*.py`. Import helpers from `tests/_helpers` and fixtures from `conftest`.
- **3. Make it deterministic:**
  - Use `FakeEvaluator`/`FakeRouter` for agent logic and routing.
  - Avoid real network. If unavoidable, mark `@pytest.mark.network` and skip in default runs.
- **4. Register components/callables:**
  - Register custom components in a fixture with `get_registry().register_component(...)`.
  - Register callables via `get_registry().register_callable(...)` if referenced by name.
- **5. Assert behavior, not internals:** Prefer public APIs (`Flock.run_async`, `FlockAgent.run`, serializer round‑trip) over private attributes.
- **6. Run fast suite:** `uv run poe test`. Fix flakiness/perf issues before moving on.
- **7. Update docs if contracts change:** Adjust testing_strategy.md if the testing approach or priorities evolve.

**Writing Tests: Common Patterns**
- **Simple agent run (P0):**
  - Build a `FlockAgent` with `FakeEvaluator(name="eval")`.
  - Orchestrate via `Flock`: `flock.add_agent(agent)` then `flock.run(agent="agent1", input={"message": "hi"})`.
- **Lifecycle hooks:**
  - Use `HookRecorder` to verify `on_initialize → on_pre_evaluate → on_post_evaluate → terminate` order. If needed, pre‑seed `agent.context = FlockContext()`.
- **Routing chain:**
  - First agent includes `FakeRouter` and sets `context` variable `flock.next_agent` or provide `next_agent` in inputs; assert second agent output.
- **Discovery:**
  - Create a temporary package/module under `tmp_path`, then `get_registry().register_module_components("pkg.mod")`; assert callable/type/component available.
- **Web API smoke:**
  - Use `FlockAPI` to add a small route to a `FastAPI` app and `TestClient` to assert 200/JSON.
- **Serialization round‑trip:**
  - `data = agent.to_dict()`; normalize runtime keys (e.g., remove `agent_id`, map `input_spec`→`input`, `output_spec`→`output`) and `FlockAgent.from_dict(data)`.

**Requirements and Conventions**
- **Naming:** `test_*.py` with small, focused tests; descriptive names.
- **Fixtures:** Prefer shared fixtures in `conftest.py`; per‑test fixtures for custom components/callables.
- **No sleeps:** Use event‑loop friendly waits or restructure logic to be synchronous in tests.
- **Limits:** Keep logs concise; avoid printing large payloads; ensure tests run under <1s in P0.
- **Skip policy:**
  - Temporal/MCP/UI/perf are non‑blocking in PRs; mark with their marker.
  - Use environment flags if needed to opt‑in (e.g., credentials) and `pytest.skip` when absent.

**Markers**
- **`p0`**: Must‑have, fast, deterministic; blocks CI.
- **`integration`**: Local engine, discovery, API smoke; deterministic.
- **`temporal`**: Temporal workflows (in‑process worker path).
- **`mcp`**: MCP server/tool integration.
- **`web`**: Extended UI (templates/HTMX).
- **`perf`**: Performance baselines; non‑blocking.
- **`slow`**, **`network`**: Opt‑in only; never part of the default run.

**Running Tests**
- **Default (PR):** `uv run poe test` (equivalent to `-m 'p0 or integration' --cov ...`).
- **Full/nightly:** `uv run poe test-all`.
- **Single test:** `uv run pytest tests/p0/test_flock_smoke.py::test_flock_run_simple -q`.
- **With logs:** add `-vv` and consider local env vars to increase log level.

**Troubleshooting**
- **Start agent missing:** Provide `agent="name"` to `Flock.run(...)` when multiple agents exist.
- **Input resolution surprises:** The orchestrator stores inputs under `flock.<key>`; evaluators should handle both plain and namespaced keys.
- **Context is None in hooks:** Set `agent.context = FlockContext()` for lifecycle tests that inspect context state.
- **Box vs dict:** APIs may return `Box`; equality with dicts is supported, but stay consistent in assertions.
- **Deserialization errors:** Remove runtime fields like `agent_id` and normalize keys (`input_spec`/`output_spec`) before `from_dict`.
- **Telemetry (optional):** By default tests disable auto telemetry setup via `FLOCK_DISABLE_TELEMETRY_AUTOSETUP=1`. If you want to test spans locally, run the `otel`-marked tests explicitly: `uv run pytest -m otel`. In the future we may add a `FLOCK_OTEL_TEST=1` shim to enable span checks in the default suite without external exporters.

**When To Add/Change Tests**
- **New public API or behavior:** Add P0 tests that capture expected contracts and error cases.
- **Refactors:** Preserve behavior with P0 tests; if behavior changes by design, update strategy/docs and tests together.
- **Bugs:** Add a failing P0 test first, fix, then keep the test to prevent regressions.

**Review Checklist**
- **Deterministic:** No external I/O in default runs.
- **Fast:** P0 sub‑second when feasible; no unnecessary sleeps.
- **Isolated:** No global or cross‑test state leakage.
- **Clear:** Readable assertions; minimal mocking; prefer helpers.
- **Covered:** Meaningful lines covered; add tests where coverage dips.

If you’re unsure where a test belongs or need a new helper/fixture, open a short PR or discussion and we’ll converge quickly.

