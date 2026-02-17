# Delta Spec: OpenClaw Engine Streaming

## MODIFIED Requirements

### Requirement: OpenClaw Streaming Activation
The OpenClaw engine SHALL stream token output in both dashboard (WebSocket) and CLI (Rich terminal) modes, matching DSPy engine behavior.
(Previously: streaming only activated in dashboard/WebSocket mode)

### Requirement: Streaming Default
The `stream` field SHALL use a `default_factory` that returns `False` when `PYTEST_CURRENT_TEST` environment variable is set, and `True` otherwise. Explicit assignment of `stream=True` SHALL always override the default, even in pytest.
(Previously: no explicit `stream` field; streaming decision based solely on `_websocket_broadcast_global`)

## ADDED Requirements

### Requirement: CLI Rich Streaming
When streaming is enabled and no dashboard is active, the engine MUST use `RichSink` to display live token output in the terminal, identical to DSPy engine behavior.

### Requirement: Streaming Concurrency Guard
The engine MUST use `Agent._streaming_counter` to prevent overlapping Rich terminal streams:
- If counter > 0 when streaming would start, streaming SHALL be suppressed
- Counter MUST be incremented before streaming and decremented in a `finally` block
- Suppressed agents MUST set `ctx.state["_flock_output_queued"] = True`

### Requirement: Output Utility Handshake
When streaming is active, the engine MUST set `ctx.state["_flock_stream_live_active"] = True` to prevent `OutputUtilityComponent` from duplicate static rendering.
When streaming is suppressed due to concurrency, the engine MUST set `ctx.state["_flock_output_queued"] = True`.
