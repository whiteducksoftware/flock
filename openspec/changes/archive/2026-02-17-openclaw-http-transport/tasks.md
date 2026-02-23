# Tasks: OpenClaw HTTP Transport Migration

## 1. Configuration (flock-9jf)

- [x] 1.1 Add `agent_id: str = "main"` field to `GatewayConfig` in `config.py`
- [x] 1.2 Add tests for `agent_id` field (default, custom) — config-only, no env var

## 2. Engine Transport — TDD tests first (flock-ctr) → blocked by flock-9jf

- [x] 2.1 Write failing tests for new request format (`/v1/responses` payload shape)
- [x] 2.2 Write failing tests for response parsing (OpenResponses output → JSON extraction)
- [x] 2.3 Write failing tests for error mapping (401/403/400/429/5xx/status:failed)
- [x] 2.4 Write failing tests for agent-id header (default + custom)

## 2b. Engine Transport — Implementation (flock-06e) → blocked by flock-ctr

- [x] 2.5 Implement `_build_responses_payload()` replacing `_build_spawn_payload()`
- [x] 2.6 Implement `_call_responses_api()` replacing `_spawn_once()`
- [x] 2.7 Implement `_parse_responses_output()` replacing `_parse_result_payload()`
- [x] 2.8 Update `evaluate()` to use new methods
- [x] 2.9 Remove old spawn-specific methods (`_build_spawn_payload`, `_spawn_once`, `_parse_result_payload`)
- [x] 2.10 Verify all engine tests pass

## 3. Integration Tests (flock-2qt) → blocked by flock-06e

- [x] 3.1 Update `tests/test_openclaw_engine.py`, `tests/test_openclaw_config.py`, `tests/test_openclaw_builder.py` for new transport shape
- [x] 3.2 Run full openclaw test suite (`uv run pytest tests/test_openclaw_engine.py tests/test_openclaw_config.py tests/test_openclaw_builder.py tests/integration/openclaw/ -v`)
- [x] 3.3 Run broader impacted test suites (`uv run pytest tests/test_engines.py tests/test_agent_builder.py -v`)

## 4. Documentation (flock-xrq) → blocked by flock-06e

- [x] 4.1 Update `docs/guides/openclaw.md` — add gateway config requirement
- [x] 4.2 Update example comments in `examples/11-openclaw/` re: responses endpoint
- [x] 4.3 Update `docs/specs/004-openclaw-integration/concept.md` if needed
- [x] 4.4 (flock-c0n) Add a dedicated setup section for local use and remote-machine use via Tailscale (with concrete config + URL examples)

## 5. Validation (flock-b2u) → blocked by flock-2qt + flock-xrq + flock-c0n

- [x] 5.1 Full test suite passes (`uv run pytest -x`)
- [x] 5.2 Manual smoke test against live OpenClaw gateway (local)
- [x] 5.3 Manual smoke test against remote gateway (via Tailscale Serve)
