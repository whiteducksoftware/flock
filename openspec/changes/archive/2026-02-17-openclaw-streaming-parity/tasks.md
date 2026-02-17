# Tasks: OpenClaw Streaming Parity

## 1. Engine Streaming Parity (single pass)

- [x] 1.1 Add `stream: bool` field to `OpenClawEngine` with `default_factory` (True in prod, False in pytest; explicit override always wins)
- [x] 1.2 Replace `_should_stream()` with tri-state routing (off / CLI Rich / dashboard WS)
- [x] 1.3 Add concurrency guard using `Agent._streaming_counter` (increment/decrement/suppress)
- [x] 1.4 Wire `RichSink` for CLI streaming mode (direct instantiation, follow DSPy executor's `_build_sinks()` pattern)
- [x] 1.5 Keep `WebSocketSink` path for dashboard mode (existing, verify unchanged)
- [x] 1.6 Add `finally` block for `_streaming_counter` decrement
- [x] 1.7 Set `_flock_stream_live_active` on streaming, `_flock_output_queued` on suppression
- [x] 1.8 Non-streaming path sets `_flock_output_queued` when counter > 0

## 2. Tests

- [x] 2.1 Test: `stream=True` + no dashboard → CLI streaming executor path used
- [x] 2.2 Test: `stream=True` + dashboard active → WebSocket streaming (existing behavior preserved)
- [x] 2.3 (flock-repo-nsl.1) Test: `stream=False` → always non-streaming regardless of sinks
- [x] 2.4 Test: active `_streaming_counter` suppresses streaming + sets `_flock_output_queued`
- [x] 2.5 (flock-repo-nsl.2) Test: `_streaming_counter` decremented in finally (even on error)
- [x] 2.6 Test: pytest auto-disables streaming via default (PYTEST_CURRENT_TEST env var)
- [x] 2.7 Test: explicit `stream=True` overrides pytest auto-disable (default-only behavior)
- [x] 2.8 (flock-repo-nsl.3) Integration test: CLI streaming path selected, context state set correctly (`_flock_stream_live_active`, counter decremented in finally)

## 3. Docs & Examples

- [x] 3.1 Update `docs/guides/openclaw.md` streaming section (dashboard + CLI + concurrency guard)
- [x] 3.2 Update `examples/11-openclaw/04_streaming_on_off.py` to reflect CLI streaming support
- [x] 3.3 Update `examples/11-openclaw/README.md` streaming note
