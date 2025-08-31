# 0.5.0b Must-Haves (Release Blockers and High-Value Fixes)

This document lists the issues that must be addressed before publishing 0.5.0b. Each item includes a short description, concrete file references for reproduction or review, acceptance criteria, and a pragmatic implementation plan to help future contributors land the fixes efficiently.

Priorities:
- P0: Must fix before public beta (release blockers)
- P1: Strongly recommended for polish/stability
- P2: Nice-to-have improvements that reduce confusion and support adoption

## P0 Blockers

### 1) Temporal Refactor Completion and Configuration
- Problem: The Temporal path is partially refactored but still contains legacy patterns and hardcoded configuration.
- Symptoms:
  - Hardcoded endpoint and task queue: `src/flock/workflow/temporal_setup.py:9`, `src/flock/workflow/temporal_setup.py:55`.
  - Use of removed `HandOffRequest`: `src/flock/workflow/flock_workflow.py:163`, `src/flock/workflow/agent_execution_activity.py:150-199`.
  - Fragile worker start heuristic with `sleep(2)`: `src/flock/core/execution/temporal_executor.py:77-78`.
  - Incorrect header comment paths: `src/flock/core/execution/local_executor.py:1`, `src/flock/core/execution/temporal_executor.py:1`.
- Acceptance Criteria:
  - Code: No references to `HandOffRequest` remain; routing uses `agent.next_agent` and routing components return `str | None` (string agent name or `None`).
  - Config: Temporal client address comes from `flock.config.TEMPORAL_SERVER_URL` and/or `TemporalWorkflowConfig` (no hardcoded host/queue anywhere).
  - Engine: No hardcoded task queue names; workflow and activity queues resolve from config (workflow or per‑agent activity config) consistently.
  - Lifecycle: In‑process worker startup/shutdown is robust (no fixed sleep), and worker is always cleaned up.
  - Tests: Add `tests/temporal/` (marked `@pytest.mark.temporal`) including:
    - a smoke test that starts the in‑process worker and executes a 1‑agent workflow end‑to‑end (skips if Temporal server unreachable),
    - a config test that sets `TEMPORAL_SERVER_URL` and asserts the client is created with that address (mocked client factory),
    - a routing test that asserts next‑agent is a string/None and no `HandOffRequest` is imported.
- Implementation Plan:
  - Remove `HandOffRequest` logic from workflow and activities; route via `RoutingComponent.determine_next_step` returning name/None. Update:
    - `src/flock/workflow/agent_execution_activity.py` to compute next agent string and return a serializable dict with `{"next_agent": str | None, "override_context": dict | None}` if needed, or simply the string/None.
    - `src/flock/workflow/flock_workflow.py` to consume the new structure and set `FLOCK_CURRENT_AGENT` accordingly.
  - Parameterize Temporal client and worker:
    - Change `create_temporal_client()` to accept config or read from `flock.config.TEMPORAL_SERVER_URL`; propagate from `Flock.temporal_config` in `run_temporal_workflow`.
    - Replace hardcoded `"flock-queue"` with values from `TemporalWorkflowConfig`/`TemporalActivityConfig`.
  - Replace `await asyncio.sleep(2)` with a readiness approach: await first poll or add retry/backoff around `start_workflow`; optionally expose a `start_in_process_worker` context manager that ensures cleanup.
  - Fix header docstrings and ensure modules live under `src/flock/...`.
  - Add tests under `tests/p0_temporal/` guarded by `@pytest.mark.temporal` to validate basic roundtrip with in-process worker (skip when Temporal server is absent).

### 2) Registry Back-Compat Sweep (Remove Internal Dict Access + Old Imports)
- Problem: Several modules directly access internal dicts of the registry or import the pre-refactor `flock_registry` symbol. This bypasses the new thread-safe `RegistryHub` API and will break users.
- Symptoms:
  - Old import used in CLI/web: `src/flock/cli/registry_management.py:17`, `src/flock/cli/yaml_editor.py:162,219,259`, `src/flock/core/util/file_path_utils.py:208`.
  - Internal attributes leaked: `registry._types`, `registry._components`, `registry._callables`, `registry._component_file_paths` in CLI and webapp: `src/flock/cli/registry_management.py:78-329,757-876`, `src/flock/webapp/app/services/flock_service.py:298-318`.
  - Serialization touching internals: `src/flock/core/serialization/serialization_utils.py:78-85`, `:256-260`.
- Acceptance Criteria:
  - API: All imports reference `from flock.core.registry import get_registry` (and decorators) exclusively.
  - Encapsulation: No `registry._...` access remains in source; only public Hub APIs are called (agents/servers/callables/types/components sub‑registries).
  - UX: CLI and Web app views render identical content using public APIs.
  - Tests: Add unit/integration coverage that:
    - exercises the web service helpers that list registry entries using public getters,
    - runs a slim CLI path that enumerates registry contents (without user prompts; factor a pure function for listing) and asserts no internal fields are accessed (mock/spy on hub methods),
    - verifies serialization utils do not touch `_types` directly (e.g., via monkeypatch and failing if internal attr is accessed).
- Implementation Plan:
  - Update imports in CLI/web modules to `from flock.core.registry import get_registry`.
  - Replace internal dict reads with public getters. Where “file paths per component” were shown, build paths on-demand using `inspect.getfile(cls)` rather than storing a shadow map.
  - In `serialization_utils`:
    - Replace lookups on `registry._types` with `registry.types.get_all_types()` or add a small helper on `TypeRegistry` to get a friendly name for a type.
    - Replace `_get_path_string` with a public `registry.callables.get_callable_path_string` or add a `get_type_path_string(type) -> str | None` helper in a suitable registry.
  - Add a temporary compatibility adapter only if unavoidable (e.g., properties on `RegistryHub` that return copies from sub-registries), but prefer refactoring call sites.
  - Add p0 tests for CLI/web service helpers that previously relied on internals, focusing on read-only operations.

### 3) Component Auto-Discovery Package List
- Problem: Discovery scans a non-existent package `flock.tools`.
- Symptoms: `src/flock/core/registry/component_discovery.py:28-31` includes `"flock.tools"` but tools live under `src/flock/core/tools`.
- Acceptance Criteria:
  - Discovery scans `flock.components` and `flock.core.tools` (if present) and gracefully skips missing packages without error.
  - Tests: Add an integration test that creates a tmp package with a callable and a component, ensures they are discovered and registered correctly. Add a separate test that injects a fake missing package into the scan list and asserts a warning and no exception.
- Implementation Plan:
  - Update `_packages_to_scan` to `["flock.components", "flock.core.tools"]`.
  - Add p0 integration tests that create a temp package with a module exposing a component + callable and verify auto-registration.

### 4) Logging Consistency (exc_info and kwarg safety)
- Problem: Mixed patterns across the codebase with `error=e` and `exc_info=True` on the same call; Temporal’s workflow logger and Loguru bindings differ in kwargs semantics.
- Symptoms:
  - Examples: `src/flock/workflow/flock_workflow.py:211`, `src/flock/core/orchestration/flock_execution.py:169`, many files via search.
- Acceptance Criteria:
  - Code: Consistent pattern documented and applied: use `logger.exception("...", ...)` when logging exceptions; for errors, use `logger.error("...", exc_info=True)` without extra `error=` kwarg.
  - Safety: FlockLogger sanitizes kwargs for Temporal `workflow.logger` delegation (drop unsupported keys like `error`).
  - Tests: Unit tests for both local (Loguru) and mocked workflow logger paths ensure calls with `exc_info=True` and with/without stray kwargs do not crash and produce log entries.
- Implementation Plan:
  - Sweep and normalize calls: replace `logger.error(..., error=..., exc_info=True)` with `logger.exception("...: %s", str(e))` or `logger.error("...", exc_info=True)`.
  - In `FlockLogger`, sanitize/whitelist kwargs passed to Temporal `workflow.logger` to avoid incompatibilities (or filter out unsupported keys like `error`).
  - Add a quick unit test that exercises both code paths (local Loguru and mocked workflow logger) with `logger.error/exception` calls.

### 5) Remove/Quarantine Legacy Router Code
- Problem: Remaining legacy router modules under `src/flock/routers/` conflict with the unified component approach and confuse contributors.
- Symptoms: Folder exists with legacy structure; not used by tests.
- Acceptance Criteria:
  - Packaging: Legacy routers are excluded from distribution or, if kept, importing `flock.routers` raises a clear `DeprecationWarning` with guidance to new component locations.
  - (Tests optional): If a deprecation path is chosen, add a tiny test asserting the warning is emitted on import.
- Implementation Plan:
  - Option A (preferred): Move `src/flock/routers/` under `legacy/` (already present) and exclude from packaging.
  - Option B: Keep package but add `DeprecationWarning` upon import and clear README/docs indicating new components to use.
  - Update docs to link to `src/flock/components/routing/*` equivalents.

### 6) WebApp and CLI Registry Views
- Problem: Web service and CLI pages depend on registry internals; they currently render but are fragile post-refactor.
- Symptoms: `src/flock/webapp/app/services/flock_service.py:298-318` and `src/flock/cli/registry_management.py` read internals.
- Acceptance Criteria:
  - Views fetch and render via public RegistryHub APIs only.
  - Tests: Unit tests for the web service helpers (`get_registered_items_service`, etc.) against a pre‑populated fake registry assert correct rendering without touching internals.
- Implementation Plan:
  - Replace internals with: `reg.types.get_all_types()`, `reg.callables.get_all_callables()`, `reg.components.get_all_components()`, etc.
  - Compute module/file paths using `inspect.getfile` at display time.
  - Add a couple of lightweight tests (unit-style) for the service helpers using a small pre-populated registry.

## P1 (Strongly Recommended)

### 7) Serialization Utils Public API Alignment
- Problem: `serialization_utils` reaches into `registry._types` and pseudo-private methods.
- Symptoms: `src/flock/core/serialization/serialization_utils.py:78-85`, `:256-260`.
- Acceptance Criteria:
  - Utils use public `RegistryHub` APIs only for both type and callable resolution; no references to `_types` or private helpers.
  - Tests: Expand existing serialization snapshot tests to cover type refs and callable refs resolved via public APIs; add a unit test that monkeypatches a registry lacking `_types` to ensure no AttributeError leaks.
- Implementation Plan:
  - Add a `TypeRegistry.get_registered_name_for_type(type) -> str | None` helper or iterate `types.get_all_types()` to find friendly names.
  - Add a public `CallableRegistry.get_type_path_string(type) -> str | None` or move generic “path of object” utility to `serialization_utils`.
  - Update serializers accordingly and add/adjust p0 tests that snapshot `to_dict()` shapes for agents and flocks (already exist; expand for type refs).

### 8) FlockAPI Runner Alignment
- Problem: `api/runner.py` references `FlockAPI` that is no longer exported the same way and may cause import confusion.
- Symptoms: `src/flock/core/api/runner.py` vs `src/flock/core/api/main.py` role split.
- Acceptance Criteria:
  - A single, documented entry point (e.g., `start_flock_api`) constructs the app and attaches routes, and `FlockAPI` remains as the custom‑endpoint helper. Public import paths are stable.
  - Tests: Reuse/expand `tests/integration/test_webapi_smoke.py` to assert the canonical runner path and a custom endpoint both work; ensure imports succeed via the chosen public API.
- Implementation Plan:
  - Decide on a single entry (recommended: keep `start_flock_api` in `runner.py` that constructs a FastAPI app and attaches endpoints from `endpoints.py`, and optionally adds custom ones via `main.FlockAPI`).
  - Update `__all__` exports accordingly and add a small integration test hitting a custom endpoint (exists: `tests/integration/test_webapi_smoke.py`).

### 9) Deprecations and Dead Files Cleanup
- Problem: Deprecated or confusing leftovers create noise for contributors.
- Symptoms: `src/flock/core/mixin/prompt_parser.py` marked “DELETE THIS FILE!”; header path typos (`src/your_package/...`).
- Acceptance Criteria:
  - No dead/incorrectly named files ship in the wheel; headers reflect `src/flock/...` structure; file marked “TODO: DELETE” is gone or moved to `legacy/` with warnings.
  - (Tests optional): A simple static check in CI (ripgrep) ensures no “TODO: DELETE THIS FILE!” remains under `src/flock/`.
- Implementation Plan:
  - Remove `prompt_parser.py` if not imported anywhere; otherwise, move under `legacy/` with explicit deprecation warnings.
  - Fix header comments across files to `src/flock/...`.
  - Add a lint rule or CI check for leftover `TODO: DELETE` markers.

### 10) Temporal Address and TLS/Cloud Readiness
- Problem: Only localhost temporal address supported; no TLS/options.
- Symptoms: `src/flock/workflow/temporal_setup.py:9`.
- Acceptance Criteria:
  - Temporal client supports non‑localhost addresses and optional TLS/auth via `TemporalWorkflowConfig` and/or environment; docs include examples.
  - Tests: Unit test that injects a `TemporalWorkflowConfig` with a non‑default address and asserts the client connect call receives it (mocked), plus an env‑only fallback test.
- Implementation Plan:
  - Extend `TemporalWorkflowConfig` to include server address, TLS creds, namespace, data converter, interceptors.
  - Update `create_temporal_client` to honor config.
  - Document env vars and examples in `README.md` + a short doc page (`docs/temporal_setup.md`).

## P2 (Nice-To-Have)

### 11) Discovery Resilience and Logging
- Problem: Discovery can be noisy and brittle on import errors.
- Acceptance Criteria:
  - Import errors are downgraded to warnings with actionable context; discovery is silent by default and emits debug details only when enabled.
  - Tests: Add a test that injects an import‑erroring module and asserts behavior (warning, no crash).
- Implementation Plan:
  - Tweak `component_discovery.py` to include per-module try/except with concise warnings and a debug switch.
  - Add a test that injects a module raising ImportError during discovery and verifies logging + resilience.

### 12) Examples and DSPy Integration Sanity
- Problem: DSPy integration and examples are present but not exercised in p0 suite.
- Acceptance Criteria:
  - At least one simple DSPy‑backed evaluator example that runs locally without network using mocks.
  - Tests: Unit test for the DSPy evaluator path that verifies prompt wiring and output mapping with a stub model function.
- Implementation Plan:
  - Add a trivial “echo via DSPy” component with injectable model function for tests.
  - Document how to disable DSPy in environments that don’t support it.

### 13) Packaging and Import Sanity CI Gate
- Problem: Drift between source and installed wheel is a common source of regressions.
- Acceptance Criteria:
  - CI builds the wheel and runs an import smoke on the built artifact (e.g., `python -c "import flock; import flock.core"`).
  - Tests: Add a CI job that installs the built wheel in a clean venv and runs the quick test subset; optionally upload coverage to Codecov.
- Implementation Plan:
  - Add a workflow step for `uv build` and `python -c "import flock; import flock.core"` on the built wheel.
  - Optional: upload coverage to Codecov.

## Test Enhancements to Lock Regressions
- p0 tests already present for serialization and registry. Add:
  - Temporal in‑process smoke (skipped when Temporal unavailable).
  - Discovery auto‑scan smoke (component + callable in tmp package).
  - Web/CLI services helpers using public registry APIs.
  - Logging kwarg safety test.
  

## Quick Win Checklist
- Replace `"flock.tools"` → `"flock.core.tools"` in discovery.
- Remove/replace all `registry._...` access with public API.
- Update Temporal client to use `TEMPORAL_SERVER_URL`.
- Remove `HandOffRequest` usage in workflow path.
- Normalize `logger.error/exception` calls.
- Deprecate or move `src/flock/routers/`.
- Remove `prompt_parser.py` or move to `legacy/`.

## Notes on Current State
- p0 and integration tests pass locally (`uv run pytest -m 'p0 or (integration and not otel)'`). Temporal tests are opt-in and currently not part of the quick gate.
- The new RegistryHub and orchestration composition look solid. The gaps are mostly around finishing the migration in CLI/Web/Temporal corners and removing legacy seams.
