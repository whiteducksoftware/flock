# Architecture Improvements Index

**Purpose:** Centralize proposed backend design upgrades so teams can quickly see what is planned, why it matters, and the current status.

---

## Current Portfolio

| Improvement | Summary | Status | Value (1–10) | Notes |
|-------------|---------|--------|--------------|-------|
| **Context Provider Blueprint** | Introduces pluggable context providers so engines can fetch curated history beyond correlation-only defaults. | Draft design (`docs/internal/context-provider/README.md`) | 8 | Enables reusable policies, redaction, and richer memory without bespoke utilities. |
| **Orchestrator Component System** | Refactors scheduling logic into lifecycle-driven components (circuit breaker, dedupe, batching, etc.). | In spec (`docs/internal/system-improvements/orchestrator-component-design.md`) | 9 | Major maintainability win; unlocks third-party extensions. |

---

## Candidate Improvements

| Improvement | Summary | Suggested Value (1–10) | Rationale | References |
|-------------|---------|-------------------------|-----------|------------|
| **EvalResult Error Propagation** | Make `EvalResult` expose a first-class `errors` collection so components/tests stop losing diagnostic data. | 8 | `EvalResult` silently drops `errors=` kwargs because the field isn’t defined; tests already try to pass errors (`tests/test_engines.py:152`). Adding the field improves observability and API correctness. | `src/flock/runtime.py:58`, `tests/test_engines.py:152` |
| **Invoke Correlation Support** | Allow `invoke()` to accept/propagate a `correlation_id` so cascades triggered from direct calls stay linked. | 7 | Direct invokes create a context with no correlation id, so downstream artifacts publish without linkage, breaking tracing and context assembly. | `src/flock/orchestrator.py:820`, `src/flock/agent.py:317` |
| **Event-Driven Idle Detection** | Replace the 10 ms polling loop in `run_until_idle()` with awaited task completion signals. | 7 | Current busy-wait loop (`asyncio.sleep(0.01)`) wastes cycles and delays shutdown, especially under load or large batches. Event-driven tracking tightens latency and reduces CPU. | `src/flock/orchestrator.py:451` |
| **Workflow Output Collector** | Provide helpers to gather outputs for the latest publish/traced run instead of manual `store.list()` scans. | 6 | Examples repeatedly query the entire store and filter by agent; a correlation-aware collector reduces boilerplate and keeps UX consistent. | `examples/05-engines/potion_batch_engine.py:111`, `examples/06-agent-components/cheer_meter_component.py:108` |
| **CLI Banner Throttling** | Gate the console banner so successive `publish()` calls don’t clear the terminal repeatedly. | 5 | `publish()` calls `init_console(clear_screen=True)` every time in CLI mode, causing flicker and extra work for batch publishes. | `src/flock/orchestrator.py:733` |
| **publish_many Parallelism** | Batch artifact normalization and persistence instead of awaiting each `publish()` sequentially. | 5 | `publish_many()` loops and awaits `publish()` per item, redoing banner init and scheduling overhead. Preparing artifacts first or using `asyncio.gather` improves throughput. | `src/flock/orchestrator.py:790` |
| **Dict Correlation Defaults** | Default dict-based `publish()` inputs to a generated correlation id like BaseModel inputs. | 4 | BaseModel publishes get a UUID, but dict inputs leave `correlation_id=None`, fragmenting traces for external integrations. | `src/flock/orchestrator.py:771` |


---

## Magnifying Glass Findings

Targeted spelunking across `src/flock/`, test suites, and example scripts surfaced the following opportunities (score = impact/urgency out of 10):

- **9/10 – Orchestrator Component System** (`docs/internal/system-improvements/orchestrator-component-design.md`): Modularize `_schedule_artifact` into lifecycle hooks so circuit breakers, batching, and future policies plug in cleanly.
- **8/10 – Context Provider Blueprint** (`docs/internal/context-provider/README.md`): Give engines pluggable context providers instead of hard-coded correlation history.
- **8/10 – EvalResult Error Propagation** (`src/flock/runtime.py:58`, `tests/test_engines.py:152`): Add an `errors` field so components stop losing diagnostic info they already attempt to report.
- **7/10 – Invoke Correlation Support** (`src/flock/orchestrator.py:820`, `src/flock/agent.py:317`): Let `invoke()` set a correlation id so cascades triggered from direct calls remain traceable.
- **7/10 – Event-Driven Idle Detection** (`src/flock/orchestrator.py:451`): Replace the 10 ms polling loop in `run_until_idle()` with awaited task completion signals.
- **6/10 – Workflow Output Collector** (`examples/05-engines/potion_batch_engine.py:111`, `examples/06-agent-components/cheer_meter_component.py:108`): Provide helpers to pull outputs for the current workflow instead of scanning the entire store.
- **5/10 – CLI Banner Throttling** (`src/flock/orchestrator.py:733`): Avoid reinitializing the console banner on every `publish()` call in CLI mode.
- **5/10 – publish_many Parallelism** (`src/flock/orchestrator.py:790`): Batch artifact prep instead of sequentially awaiting each `publish()`.
- **4/10 – Dict Correlation Defaults** (`src/flock/orchestrator.py:771`): Generate correlation ids for dict inputs so external publishers match BaseModel behavior.

Use this list as a shopping cart when prioritizing backend efforts—several smaller fixes can ride along with the marquee redesigns.

---

## How to Use This Index

1. **Add new proposals** with a short description, current status, and an initial value ranking.
2. **Link to the canonical design doc** so readers can deep-dive quickly.
3. **Update status** as ideas move from concept → spec → implementation.
4. **Archive completed work** at the bottom once shipped, preserving the history.

For questions or edits, contact the Architecture Guild or drop a note in `#flock-architecture`.
