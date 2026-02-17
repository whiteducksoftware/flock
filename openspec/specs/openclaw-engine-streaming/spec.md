# openclaw-engine-streaming Specification

## Purpose
TBD - created by archiving change openclaw-streaming-parity. Update Purpose after archive.
## Requirements
### Requirement: OpenClaw Streaming Activation
The OpenClaw engine SHALL stream token output in both dashboard (WebSocket) and CLI (Rich terminal) modes, matching DSPy engine behavior.
(Previously: streaming only activated in dashboard/WebSocket mode)

#### Scenario: Dashboard streaming active
- GIVEN an OpenClaw agent execution with dashboard/WebSocket sinks available
- WHEN streaming is enabled
- THEN token output is emitted through WebSocket streaming events

#### Scenario: CLI streaming active
- GIVEN an OpenClaw agent execution without dashboard sinks
- WHEN streaming is enabled
- THEN token output is emitted through Rich terminal streaming

### Requirement: Streaming Default
The `stream` field SHALL use a `default_factory` that returns `False` when `PYTEST_CURRENT_TEST` environment variable is set, and `True` otherwise. Explicit assignment of `stream=True` SHALL always override the default, even in pytest.
(Previously: no explicit `stream` field; streaming decision based solely on `_websocket_broadcast_global`)

#### Scenario: Pytest default disables streaming
- GIVEN tests running with `PYTEST_CURRENT_TEST` set
- WHEN `stream` is not explicitly configured
- THEN streaming defaults to disabled

#### Scenario: Explicit override in pytest
- GIVEN tests running with `PYTEST_CURRENT_TEST` set
- WHEN `stream=True` is explicitly configured
- THEN streaming remains enabled

### Requirement: CLI Rich Streaming
When streaming is enabled and no dashboard is active, the engine MUST use `RichSink` to display live token output in the terminal, identical to DSPy engine behavior.

#### Scenario: Rich sink routing
- GIVEN streaming is enabled and no WebSocket sink is available
- WHEN the engine starts evaluation
- THEN the engine routes streaming output to `RichSink`

### Requirement: Streaming Concurrency Guard
The engine MUST use `Agent._streaming_counter` to prevent overlapping Rich terminal streams:
- If counter > 0 when streaming would start, streaming SHALL be suppressed
- Counter MUST be incremented before streaming and decremented in a `finally` block
- Suppressed agents MUST set `ctx.state["_flock_output_queued"] = True`

#### Scenario: Suppress overlapping streams
- GIVEN one Rich streaming execution is already active
- WHEN another streaming execution starts
- THEN the second execution suppresses live Rich streaming
- AND sets `ctx.state["_flock_output_queued"] = True`

#### Scenario: Counter lifecycle
- GIVEN a streaming execution starts
- WHEN execution completes or errors
- THEN `_streaming_counter` is decremented in `finally`

### Requirement: Output Utility Handshake
When streaming is active, the engine MUST set `ctx.state["_flock_stream_live_active"] = True` to prevent `OutputUtilityComponent` from duplicate static rendering.
When streaming is suppressed due to concurrency, the engine MUST set `ctx.state["_flock_output_queued"] = True`.

#### Scenario: Active streaming handshake
- GIVEN live streaming is active
- WHEN output utility rendering is evaluated
- THEN `_flock_stream_live_active` is present and static duplicate rendering is avoided

#### Scenario: Suppressed streaming handshake
- GIVEN streaming is suppressed due to concurrency
- WHEN output utility rendering is evaluated
- THEN `_flock_output_queued` is present and deferred output behavior applies

