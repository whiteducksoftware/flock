# Design: OpenClaw Streaming Support (Phase 2)

## Context

Flock's DSPy engine streams to the dashboard via a composable sink pattern:

```
DSPy LM stream → DSPyStreamingExecutor → [RichSink, WebSocketSink] → Dashboard
```

OpenClaw's `/v1/responses` with `stream: true` emits SSE events:
```
response.created → response.in_progress → response.output_text.delta (×N) → response.completed
```

Goal: connect these two with minimal new code.

## Decisions

### Decision 1 — Reuse existing StreamSink protocol
- **Decision:** OpenClaw streaming uses the same `StreamSink` protocol as DSPy. No new sink types.
- **Rationale:** Dashboard already consumes `StreamingOutputEvent` from `WebSocketSink`. Reusing it means zero frontend changes.

### Decision 2 — SSE-to-Sink event mapping
- **Decision:** Map OpenClaw SSE events to sink methods:

| OpenClaw SSE Event | Sink Method | Notes |
|---|---|---|
| `response.created` | `on_status("OpenClaw agent started")` | Initial status |
| `response.in_progress` | `on_status("Processing...")` | Agent is thinking |
| `response.output_text.delta` | `on_token(delta.text, "output")` | Main streaming content |
| `response.output_text.done` | (no-op, wait for completed) | Intermediate |
| `response.completed` | `on_final(full_text, usage)` | Terminal event |
| `response.failed` | raise `RuntimeError` | Error mid-stream |

- **Rationale:** Direct mapping, no intermediate abstraction needed.

### Decision 3 — Create OpenClawStreamingExecutor
- **Decision:** New class `OpenClawStreamingExecutor` in `flock/integrations/openclaw/streaming.py`, following `DSPyStreamingExecutor` patterns.
- **Responsibilities:**
  - Open SSE connection to `/v1/responses` with `stream: true`
  - Parse SSE event lines (`event:`, `data:`)
  - Dispatch to registered sinks
  - Handle connection errors and timeouts
  - Generate `StreamingOutputEvent` with correct correlation IDs
  - Pre-generate artifact IDs for streaming (same pattern as DSPy)
- **Rationale:** Keeps streaming logic isolated from core engine. Engine delegates to executor when streaming is appropriate.

### Decision 4 — Automatic streaming activation
- **Decision:** When dashboard/WebSocket is active, engine automatically uses streaming path. When running headless, uses non-streaming path (current behavior).
- **Rationale:** Matches DSPy behavior. No user config needed.
- **Detection:** Check if `WebSocketSink` broadcast function is available in the execution context.

### Decision 5 — SSE parsing approach
- **Decision:** Use `httpx` with manual SSE line parsing (or `httpx-sse` if available). No heavy SSE library dependency.
- **Rationale:** SSE format is simple (`event: <type>\ndata: <json>\n\n`). Custom parsing keeps dependencies minimal.
- **Fallback:** If SSE connection fails, fall back to non-streaming request transparently.

### Decision 6 — Accumulate full response for artifact creation
- **Decision:** While streaming tokens to sinks, also accumulate the full response text. After `response.completed`, parse accumulated text as JSON for artifact creation (same as non-streaming path).
- **Rationale:** Artifact creation requires the complete, validated JSON. Streaming is for UI feedback only.

## Architecture

### Data Flow

```
OpenClaw /v1/responses (SSE)
    ↓
OpenClawStreamingExecutor
    ├── on_token() → WebSocketSink → Dashboard (real-time)
    ├── on_token() → RichSink → Terminal (real-time)
    └── accumulate full text
            ↓
        on_final() → JSON parse → artifact creation → EvalResult
```

### New Files

| File | Purpose |
|------|---------|
| `src/flock/integrations/openclaw/streaming.py` | `OpenClawStreamingExecutor` |
| `tests/test_openclaw_streaming.py` | SSE parsing, sink dispatch, error handling |

### Modified Files

| File | Change |
|------|--------|
| `engine.py` | Add streaming path in `evaluate()` when sinks available |
| `__init__.py` | Export streaming executor |

### Unchanged

- `StreamSink` protocol — reused as-is
- `WebSocketSink` / `RichSink` — reused as-is
- `StreamingOutputEvent` model — reused as-is
- Dashboard frontend — already handles the events
- Orchestrator — streaming is engine-internal

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| SSE connection drops mid-stream | Partial output lost | Fallback to non-streaming retry |
| OpenClaw SSE format changes | Parse failures | Defensive parsing, version-check if needed |
| Token accumulation memory for very long responses | High memory | Same as non-streaming (bounded by timeout) |
| Sink errors during streaming | Stream aborted | Existing sink error contract: sinks catch own errors |

## Effort Estimate

~1 focused session:
- SSE consumer + parser: ~30 min
- StreamSink adapter/executor: ~45 min
- Tests (mocked SSE): ~45 min
- Wire into engine + smoke test: ~30 min
