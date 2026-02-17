# Proposal: OpenClaw Streaming Support (Phase 2)

**Change:** `openclaw-streaming-phase2`
**Parent:** `openclaw-http-transport` (must be completed first)
**Status:** Planning (not yet approved for implementation)
**Date:** 2026-02-16

## Problem

The current OpenClaw engine uses non-streaming HTTP (`stream: false`). This means:
- The dashboard shows no real-time progress for OpenClaw agents
- Users see a blank agent node until the full response arrives
- No way to detect errors mid-execution (must wait for full timeout)

DSPy agents already stream to the dashboard in real time via the `StreamSink` pattern. OpenClaw agents should behave the same way.

## Proposed Solution

Add SSE (Server-Sent Events) streaming support to `OpenClawEngine`, reusing Flock's existing streaming infrastructure (`StreamSink` protocol, `WebSocketSink`, `RichSink`, `StreamingOutputEvent`).

### Why this is tractable

Flock already has all the streaming infrastructure:
- `StreamSink` protocol (`on_status`, `on_token`, `on_final`, `flush`)
- `WebSocketSink` — broadcasts events to dashboard via WebSocket
- `RichSink` — terminal streaming display
- `StreamingOutputEvent` — the event model the dashboard already consumes
- `DSPyStreamingExecutor` — reference implementation for engine-level streaming

OpenClaw's `/v1/responses` endpoint supports `stream: true` with SSE events that map cleanly to the sink protocol.

## Scope

### In Scope
- SSE consumer for `/v1/responses?stream=true`
- SSE-to-StreamSink adapter (maps OpenClaw events to Flock sink protocol)
- `OpenClawStreamingExecutor` (analogous to `DSPyStreamingExecutor`)
- Integration with existing `WebSocketSink` for dashboard real-time updates
- Integration with existing `RichSink` for terminal streaming
- Graceful degradation (fall back to non-streaming if SSE fails)
- Tests with mocked SSE streams

### Out of Scope
- Dashboard frontend changes (already handles `StreamingOutputEvent`)
- New sink implementations
- Client tool call loops (separate Phase 2 concern)
- Session mode (Phase 3)

## Impact

- **Breaking:** No — streaming is opt-in (dashboard mode auto-enables it)
- **API change:** None — `flock.openclaw_agent()` unchanged
- **Dashboard:** Works immediately — same `StreamingOutputEvent` model

## Dependencies

- Requires `openclaw-http-transport` to be completed (uses `/v1/responses`)
