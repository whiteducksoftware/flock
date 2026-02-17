# Test Discovery Notes — openclaw-phase1-tdd

Date: 2026-02-11
Lead: Codie

## High-level inventory

- `pytest --collect-only` result: **2160 tests collected**
- Test files discovered (`tests/**/test_*.py`): **132 files**

Top density files by test count (approx.):
- `tests/test_mcp_config.py` (65)
- `tests/test_dspy_engine.py` (58)
- `tests/test_orchestrator_component.py` (58)
- `tests/test_mcp_tool_handlers.py` (55)
- `tests/test_agent_builder.py` (48)
- `tests/test_orchestrator.py` (44)

## Most relevant suites for OpenClaw Phase 1

1. **Engine semantics + call patterns**
   - `tests/test_agent_builder.py`
   - `tests/test_engines.py`

2. **Security constraints for engine context**
   - `tests/test_engine_context.py`
   - `tests/test_context_security.py`

3. **HTTP retry/mocking pattern to reuse**
   - `tests/api/test_webhook_e2e.py` (uses `respx`)

4. **Env/config resolution style**
   - `tests/test_dspy_engine.py` (env model resolution tests)
   - `tests/orchestrator/test_server_manager.py` (env patching patterns)

5. **Contract-style expectations**
   - `tests/contract/*`

## Baseline command checks run

```bash
uv run pytest tests/test_engine_context.py tests/test_context_security.py -k "engine" -q
# 8 passed, 11 deselected

uv run pytest tests/test_agent_builder.py -k "multiple_publishes_calls_engine_multiple_times or single_publishes_calls_engine_once or fan_out_calls_engine_once_generates_multiple or engine_calls_are_sequential_not_parallel or error_in_group_stops_subsequent_groups" -q
# 5 passed, 43 deselected

uv run pytest tests/api/test_webhook_e2e.py -k "retries_on_server_error or gives_up_after_max_retries" -q
# 2 passed, 13 deselected
```

## TDD implications for Phase 1

- Add OpenClaw tests in a dedicated cluster (new files), then wire minimal code until green.
- Reuse `respx` transport mocking approach from webhook tests.
- Keep strict deterministic behavior for parsing and error mapping.
- Preserve existing engine invariants (sequential group calls, context immutability constraints, opt-in execution path).
