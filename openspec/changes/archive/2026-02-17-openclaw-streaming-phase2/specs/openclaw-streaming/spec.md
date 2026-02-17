# Delta Spec: OpenClaw Streaming

## ADDED Requirements

### Requirement: SSE Streaming Support
The OpenClawEngine MUST support streaming responses via SSE when a dashboard or terminal sink is active.

#### Scenario: Dashboard active
- GIVEN a running Flock dashboard with WebSocket connection
- WHEN an OpenClaw agent executes
- THEN the engine sends `stream: true` to `/v1/responses`
- AND streams tokens to the dashboard in real time

#### Scenario: No dashboard
- GIVEN headless execution (no sinks registered)
- WHEN an OpenClaw agent executes
- THEN the engine uses non-streaming mode (current behavior)

### Requirement: SSE Event Parsing
The engine MUST parse OpenClaw SSE events and dispatch to registered `StreamSink` implementations.

#### Scenario: Token delta events
- GIVEN an active SSE stream
- WHEN `response.output_text.delta` events arrive
- THEN each delta is dispatched to all sinks via `on_token()`
- AND the delta text is accumulated for final parsing

#### Scenario: Completion event
- GIVEN an active SSE stream
- WHEN `response.completed` arrives
- THEN the accumulated text is parsed as JSON
- AND `on_final()` is called on all sinks
- AND the result is returned as an `EvalResult`

#### Scenario: Failure event mid-stream
- GIVEN an active SSE stream
- WHEN `response.failed` arrives
- THEN a `RuntimeError` is raised
- AND the error is eligible for retry per existing retry logic

### Requirement: Streaming Fallback
The engine MUST fall back to non-streaming mode if the SSE connection fails.

#### Scenario: SSE connection error
- GIVEN an OpenClaw gateway that rejects SSE connections
- WHEN the engine attempts streaming
- THEN it falls back to non-streaming request
- AND logs a warning

### Requirement: StreamingOutputEvent Compatibility
The streaming executor MUST produce `StreamingOutputEvent` instances compatible with the existing `WebSocketSink` and `RichSink`.

#### Scenario: Dashboard receives events
- GIVEN an OpenClaw agent streaming via SSE
- WHEN tokens are dispatched to `WebSocketSink`
- THEN the dashboard renders them identically to DSPy streaming events
