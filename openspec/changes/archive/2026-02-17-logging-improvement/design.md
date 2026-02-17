# Design: logging-improvemen

## Quick fix architecture (implemented)

### 1) Safe exception-path emission in `FlockLogger`

Introduce a shared `_emit(...)` helper that:

- pops `exc_info` from kwargs,
- maps it to Loguru `logger.opt(exception=...)`,
- emits with the requested level method.

Behavior:
- `exc_info=True` -> `opt(exception=True)`
- `exc_info=<Exception>` -> `opt(exception=<Exception>)`
- normal `*args/**kwargs` formatting continues to work.

Why this works:
- avoids passing `exc_info` as format kwargs,
- prevents JSON/braces in message text from being misinterpreted as format fields during error paths.

### 2) Structured orchestrator failure logging

Switch orchestrator error logging from interpolated f-string to positional placeholder formatting:

```py
self._logger.error(
  "Agent '{}' failed (task={}): {}",
  agent.name,
  ctx.task_id,
  exc,
  exc_info=exc,
)
```

This keeps exception payload as an argument (not inline formatted text), and stack association is preserved.

---

## Improvement concepts (next iteration)

### Concept A — Error Envelope Contract
Define a small structured dict for all orchestrator/engine error logs:

- `error_class`
- `agent`
- `task_id`
- `correlation_id`
- `stage` (evaluate/parse/materialize/publish)
- `summary`
- `cause_type`
- `cause_preview`

Goal: machine-parseable diagnostics and consistent triage.

### Concept B — Error Classification
Add canonical classification helper:

- `gateway_timeout`
- `response_parse_error`
- `schema_validation_error`
- `retry_exhausted`
- `downstream_publish_error`

Goal: aggregate failure modes without scraping raw strings.

### Concept C — Safe Payload Capture Policy
For JSON-heavy failures, log:

- preview (bounded chars),
- length,
- optional stable hash of full payload.

Goal: preserve forensic value without exploding logs or leaking oversized payloads.

### Concept D — Task Exception Drain / Summary
Collect background task failures and emit one concise run summary at idle:

- total failures,
- grouped by classification,
- representative task/agent IDs.

Goal: remove "silent async exception" guesswork.

---

## Fast example design (06)

Create `examples/11-openclaw/06_fast_orchestration_smoke.py` as a compact, deterministic headless pipeline:

- OpenClaw fan-out scout (`fan_out=2`) from one brief.
- Native signal enrichment step adds `datetime` fields.
- OpenClaw batch synthesis consumes enriched artifacts (ensures datetime appears in OpenClaw input/context shaping paths).
- OpenClaw final report step.
- CLI flag `--stream on|off` toggles OpenClaw streaming in headless mode for all OpenClaw agents.
- Runtime assertions:
  - fan-out publishes 2 artifacts,
  - artifact IDs are unique,
  - final report exists,
  - any `WorkflowError` artifacts are printed for diagnostics.

This keeps orchestration coverage high while avoiding the long-running web-research workload in `05_competitive_intelligence.py`.

## Validation plan

- Regression tests for `exc_info` + JSON/braces behavior.
- Targeted orchestrator smoke tests to ensure failure path still publishes `WorkflowError` and does not crash logging.
- Run `06_fast_orchestration_smoke.py` in both `--stream off` and `--stream on` modes.
