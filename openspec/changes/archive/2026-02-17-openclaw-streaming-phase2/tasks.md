# Tasks: OpenClaw Streaming Support (Phase 2)

> **Note:** Imported to Beads as epic `flock-0gc` on 2026-02-16.

## 1. SSE Consumer

- [x] 1.1 Write failing tests for SSE line parsing (event + data extraction)
- [x] 1.2 Write failing tests for SSE event type mapping (delta → on_token, completed → on_final, failed → error)
- [x] 1.3 Implement SSE consumer with httpx async streaming
- [x] 1.4 Implement SSE-to-StreamSink event dispatcher

## 2. Streaming Executor

- [x] 2.1 Write failing tests for `OpenClawStreamingExecutor` (mock SSE stream → sink calls)
- [x] 2.2 Write failing tests for text accumulation during streaming
- [x] 2.3 Write failing tests for fallback to non-streaming on SSE failure
- [x] 2.4 Implement `OpenClawStreamingExecutor` in `streaming.py`
- [x] 2.5 Wire executor into `engine.py` `evaluate()` (auto-detect sinks)

## 3. Integration

- [x] 3.1 Write integration test: mocked SSE → WebSocketSink → StreamingOutputEvent
- [x] 3.2 Write integration test: SSE failure → non-streaming fallback → valid result
- [x] 3.3 Manual smoke test with live dashboard

## 4. Documentation

- [x] 4.1 Update `docs/guides/openclaw.md` — document streaming behavior
- [x] 4.2 Note in examples that dashboard streaming works automatically
