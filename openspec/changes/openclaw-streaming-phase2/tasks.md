# Tasks: OpenClaw Streaming Support (Phase 2)

> **Note:** Not yet imported to Beads. Will be imported after `openclaw-http-transport` is complete and this change is approved.

## 1. SSE Consumer

- [ ] 1.1 Write failing tests for SSE line parsing (event + data extraction)
- [ ] 1.2 Write failing tests for SSE event type mapping (delta → on_token, completed → on_final, failed → error)
- [ ] 1.3 Implement SSE consumer with httpx async streaming
- [ ] 1.4 Implement SSE-to-StreamSink event dispatcher

## 2. Streaming Executor

- [ ] 2.1 Write failing tests for `OpenClawStreamingExecutor` (mock SSE stream → sink calls)
- [ ] 2.2 Write failing tests for text accumulation during streaming
- [ ] 2.3 Write failing tests for fallback to non-streaming on SSE failure
- [ ] 2.4 Implement `OpenClawStreamingExecutor` in `streaming.py`
- [ ] 2.5 Wire executor into `engine.py` `evaluate()` (auto-detect sinks)

## 3. Integration

- [ ] 3.1 Write integration test: mocked SSE → WebSocketSink → StreamingOutputEvent
- [ ] 3.2 Write integration test: SSE failure → non-streaming fallback → valid result
- [ ] 3.3 Manual smoke test with live dashboard

## 4. Documentation

- [ ] 4.1 Update `docs/guides/openclaw.md` — document streaming behavior
- [ ] 4.2 Note in examples that dashboard streaming works automatically
