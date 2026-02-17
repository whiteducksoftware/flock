## Why

`05_competitive_intelligence.py` runs exposed an observability gap in failure handling:

- OpenClaw parse/timeouts can include JSON-heavy payload text.
- Logger calls that passed `exc_info=...` into Loguru formatting could treat kwargs as format variables.
- Result: secondary logging errors (e.g. unmatched `{` / formatting failures) that obscured the original failure cause.

When logging itself fails, diagnosis becomes guesswork.

## What Changes

1. **Quick hardening fix (implemented in this change):**
   - Add safe `exc_info` handling in `FlockLogger` by mapping to Loguru `opt(exception=...)` instead of forwarding as formatting kwargs.
   - Update orchestrator agent-failure logging call to structured placeholder formatting.
   - Add regression tests covering JSON/braces + `exc_info` behavior.

2. **Logging improvement concepts (documented for next iteration):**
   - Structured error envelope for orchestrator/background task failures.
   - Consistent error classification tags (`timeout`, `parse_error`, `schema_error`, etc.).
   - Bounded but recoverable error payload capture (preview + full hash/id).
   - Unified end-of-run failure summary to reduce triage guesswork.

3. **Add a fast orchestration smoke example (`06_...`)** in `examples/11-openclaw/`:
   - headless only,
   - explicit stream ON/OFF toggle,
   - exercises the recently fixed behaviors (datetime-safe prompt shaping, fan-out artifact identity uniqueness),
   - completes much faster than `05_competitive_intelligence.py`.

## Scope

### In scope
- `src/flock/logging/logging.py`
- `src/flock/core/orchestrator.py`
- `tests/test_logging_config.py`
- `examples/11-openclaw/06_fast_orchestration_smoke.py`
- `examples/11-openclaw/README.md` (example index update)
- OpenSpec planning artifacts for broader logging improvements.

### Out of scope
- Full observability pipeline redesign.
- Dashboard UI changes.
- Rewriting all legacy log call-sites in one pass.

## Risks

- Changing logger semantics could affect call-sites relying on kwargs formatting quirks.

## Mitigation

- Preserve existing `*args/**kwargs` behavior except `exc_info`, which is now explicitly normalized.
- Add focused regression tests.
