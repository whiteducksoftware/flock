# Design: OpenClaw HTTP Transport Migration

## Context

Current `OpenClawEngine` sends:
```
POST {gateway_url}/api/sessions/spawn
{
  "task": "...",
  "label": "flock-{alias}-{correlation}",
  "runTimeoutSeconds": 120,
  "cleanup": "delete"
}
```

Target: OpenClaw's documented `/v1/responses` endpoint (OpenResponses-compatible).

## Decisions

### Decision 1 — Use `/v1/responses` as sole transport
- **Decision:** Replace `/api/sessions/spawn` entirely with `/v1/responses`. No fallback, no dual-path.
- **Rationale:** Clean migration. The spawn endpoint is internal/undocumented. Maintaining two paths adds complexity with no benefit.

### Decision 2 — Map spawn task to OpenResponses input
- **Decision:** The task string (schema + input + description) becomes the `input` field. Agent description becomes `instructions`.
- **Rationale:** Direct mapping, preserves existing prompt construction logic.
- **Request shape:**
  ```json
  {
    "model": "openclaw",
    "input": "<task prompt with schema + input>",
    "instructions": "<agent description if present>",
    "stream": false
  }
  ```

### Decision 3 — Parse output from response text content
- **Decision:** Extract the agent's text response from `output[].content[].text`, then parse as JSON (same as current `_parse_result_payload` but extracting from a different envelope).
- **Rationale:** The responses API returns structured output items. We need the text content which contains the JSON the agent produced.
- **Response shape (relevant parts):**
  ```json
  {
    "id": "resp_...",
    "status": "completed",
    "output": [
      {
        "type": "message",
        "role": "assistant",
        "content": [
          {
            "type": "output_text",
            "text": "{\"ingredients\": [...]}"
          }
        ]
      }
    ]
  }
  ```

### Decision 4 — Agent targeting via header
- **Decision:** Use `x-openclaw-agent-id: main` header (or configurable agent ID) rather than encoding in the model field.
- **Rationale:** Cleaner separation. The `model` field stays as `"openclaw"` (or could be configurable for future model routing). Header is explicit.
- **New config field:** `GatewayConfig.agent_id: str = "main"` — optional, defaults to `"main"`.

### Decision 5 — Keep repair/retry logic unchanged
- **Decision:** The existing retry (transient errors) and repair (malformed JSON) logic remains as-is. Only the HTTP request/response format changes.
- **Rationale:** The repair logic is transport-agnostic — it operates on parsed text, not on the HTTP envelope.

### Decision 6 — Error mapping from responses API
- **Decision:** Map HTTP status codes and response error objects to existing exception types:
  - `401/403` → `ValueError` (auth failure) — no retry
  - `400` → `RuntimeError` (bad request) — no retry
  - `429` → `RuntimeError` (rate limit) — immediate retry (same as existing retry logic)
  - `5xx` → `RuntimeError` (server error) — retry
  - Response `status: "failed"` → `RuntimeError` — retry
- **Rationale:** Matches existing exception taxonomy from Phase 1 design decisions.

### Decision 7 — Require explicit gateway config for responses endpoint
- **Decision:** Document that users must enable `gateway.http.endpoints.responses.enabled: true` in their OpenClaw config. Flock does not auto-configure this.
- **Rationale:** This is an OpenClaw-side config. Flock shouldn't assume control over gateway configuration.

## Architecture

### Request Flow (after migration)

```
Flock Agent
  → OpenClawEngine.evaluate()
    → _build_responses_payload()  [NEW: replaces _build_spawn_payload]
      → constructs OpenResponses request body
    → _call_responses_api()  [NEW: replaces _spawn_once]
      → POST /v1/responses with Bearer auth + agent-id header
    → _parse_responses_output()  [NEW: replaces _parse_result_payload]
      → extracts text from output items
      → JSON parses → validates against output schema
    → returns EvalResult with artifact
```

### Changed Files

| File | Change |
|------|--------|
| `engine.py` | Replace endpoint + request/response format |
| `config.py` | Add optional `agent_id` field to `GatewayConfig` |
| `tests/test_openclaw_engine.py` | Update mock responses to OpenResponses format |
| `tests/test_openclaw_config.py` | Add `agent_id` field tests |
| `tests/test_openclaw_builder.py` | Verify builder still works with new engine |
| `tests/integration/openclaw/test_openclaw_pipeline.py` | Update integration test mocks |
| `docs/guides/openclaw.md` | Add gateway config requirement |
| `examples/11-openclaw/*.py` | Update comments re: config requirement |

### Unchanged

- `config.py` `OpenClawConfig` / `OpenClawDefaults` — no changes
- `config.py` `from_env()` — env var pattern unchanged
- Builder API (`flock.openclaw_agent()`) — unchanged
- Retry/repair logic — transport-agnostic
- All existing Flock core code — no changes

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Response format varies across OpenClaw versions | Parse failure | Defensive parsing: handle both `output_text` and plain `text` content types |
| Gateway responses endpoint disabled by default | Connection rejected | Clear docs + error message suggesting config change |
| Response includes tool calls (future) | Unexpected output items | Filter to `message` type items only in Phase 1 |
| Timeout semantics differ | Task killed prematurely | Use `httpx` timeout (client-side) as before; no server-side timeout parameter in responses API |

## Migration Plan

1. Update config (`agent_id` field)
2. Rewrite engine transport methods
3. Update all tests (mock shape changes)
4. Update docs and examples
5. Run full test suite
6. Manual smoke test against live gateway
