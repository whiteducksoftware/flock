# Manual Smoke — OpenClaw Streaming + Live Dashboard

Date: 2026-02-16

## Goal
Validate task 3.3 (`flock-0gc.12`): OpenClaw streaming path works with a live dashboard session.

## Procedure
1. Started a local Flock server with dashboard enabled (`serve(dashboard=True, blocking=False)`).
2. Used a temporary OpenClaw streaming monkeypatch (`OpenClawSSEConsumer.stream_events`) to emit realistic SSE frames:
   - `response.created`
   - `response.in_progress`
   - multiple `response.output_text.delta`
   - `response.completed`
   - `done` (`[DONE]`)
3. Opened dashboard at `http://127.0.0.1:8344` (live browser session).
4. Published a test input artifact and executed `run_until_idle()`.
5. Verified output artifact persisted from streamed content.

## Observed Evidence
- Dashboard static assets and graph API endpoints served successfully (`GET /`, `GET /assets/*`, `POST /api/dashboard/graph`).
- Live WebSocket clients connected (`WebSocket /ws accepted`, client count increased to 2).
- Agent execution completed through streaming path and published output artifact.
- Final output observed:
  - `MANUAL_SMOKE_OUTPUT streamed manual smoke`

## Result
✅ PASS — Live dashboard smoke succeeded for OpenClaw streaming path.

## Notes
- On shutdown, uvicorn/websocket stack emitted `CancelledError` noise while closing active websocket tasks. This occurred after successful completion and did not affect result correctness.
