# Proposal: OpenClaw Streaming Parity with Native Agents

## Intent

OpenClaw agents currently only stream in dashboard/WebSocket mode. Native DSPy agents stream in **both** dashboard mode (WebSocket) and headless/CLI mode (Rich terminal). This creates inconsistent UX — OpenClaw agents appear "frozen" in CLI while native agents show live token output.

## Scope

Make OpenClaw streaming behavior **identical** to DSPy engine streaming:
- Dashboard mode → WebSocket streaming (already works)
- CLI/headless mode → Rich terminal streaming (NEW)
- Concurrency guard via `Agent._streaming_counter` (NEW)
- `stream` field with pytest auto-disable (NEW)
- Output utility handshake (`_flock_stream_live_active`, `_flock_output_queued`) (PARTIAL → COMPLETE)

## Out of Scope

- SSE parser changes (already complete in Phase 2)
- New sink implementations (reuse existing `RichSink` and `WebSocketSink`)
- Streaming protocol changes

## Approach

Single-pass implementation mirroring DSPy engine's `evaluate()` streaming block:
1. Add `stream` field with DSPy-identical default semantics
2. Replace `_should_stream()` with tri-state routing (off / CLI Rich / dashboard WebSocket)
3. Wire `RichSink` for CLI mode using existing `OpenClawStreamingExecutor`
4. Mirror concurrency guard (`_streaming_counter` increment/decrement/suppress)
5. Complete context state handshake for `OutputUtilityComponent`

## Risk

- **Low:** `RichSink` and `WebSocketSink` already implement `StreamSink` protocol, which `OpenClawStreamingExecutor` consumes via the same `SinkProtocol`
- **Medium:** `RichSink` constructor needs specific args (field name, panel title) — must match OpenClaw output context
- **Mitigation:** DSPy's `RichSink.create()` factory provides the pattern to follow

## Success Criteria

- OpenClaw agent in CLI mode shows live Rich token streaming identical to DSPy agents
- OpenClaw agent in dashboard mode continues working as before
- Concurrency guard prevents overlapping Rich streams
- `stream=False` disables streaming entirely
- Streaming auto-disabled in pytest
