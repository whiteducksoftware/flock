# Design: OpenClaw Streaming Parity

## Reference Implementation

DSPy engine streaming block in `src/flock/engines/dspy_engine.py` lines 318-414.

## Architecture

### Streaming Decision (mirrors DSPy exactly)

```
stream field = True (default, auto-False in pytest)
  │
  ├─ stream=False → non-streaming path (existing)
  │
  ├─ Agent._websocket_broadcast_global != None → dashboard WebSocket streaming
  │     └─ sinks = [WebSocketSink] (existing behavior)
  │
  └─ CLI/headless mode
        ├─ Agent._streaming_counter > 0 → suppress, set _flock_output_queued
        └─ Agent._streaming_counter == 0 → Rich terminal streaming
              ├─ increment _streaming_counter
              └─ sinks = [RichSink]
```

### Modified Components

#### `OpenClawEngine` (`engine.py`)

**New field:**
```python
stream: bool = Field(default_factory=lambda: not bool(os.environ.get("PYTEST_CURRENT_TEST")))
# Default is True in production, False in pytest.
# Explicit override (stream=True) always wins — only the default is auto-disabled.
```

**Replace `_should_stream()`** with inline tri-state routing in `evaluate()`:
```python
should_stream = self.stream  # Explicit value always honored

if should_stream and ctx:
    is_dashboard = Agent._websocket_broadcast_global is not None
    if should_stream and not is_dashboard:
        if Agent._streaming_counter > 0:
            should_stream = False  # suppress
        else:
            Agent._streaming_counter += 1
```

**Replace `_build_streaming_sinks()`** with mode-aware sink factory:
- Dashboard → `WebSocketSink` (existing)
- CLI → `RichSink` (new path)

**Add `finally` block** for counter decrement (mirrors DSPy):
```python
finally:
    if should_stream and ctx and not is_dashboard:
        Agent._streaming_counter = max(0, Agent._streaming_counter - 1)
```

**Context state handshake:**
- Streaming active → set `ctx.state["_flock_stream_live_active"] = True`
- Streaming suppressed → set `ctx.state["_flock_output_queued"] = True`

#### `RichSink` Usage

`RichSink` is constructed directly (no factory method). Follow the DSPy streaming executor's pattern for setup:
- Instantiate `RichSink` with formatter, theme, live refresh config, and signature field order
- Reference: `DSPyStreamingExecutor._build_sinks()` for the exact constructor args pattern
- `signature_field` → output field name from output group (e.g. "output")
- Agent name for panel title
- `pre_generated_artifact_id` for event correlation

The existing `OpenClawStreamingExecutor` calls `on_token(text, signature_field)`, `on_status(text)`, `on_final(result, tokens_emitted)`, and `flush()` — all of which `RichSink` implements via `StreamSink` protocol.

### Unchanged Components

- `OpenClawStreamingExecutor` — already sink-agnostic
- `OpenClawSSEDispatcher` — already dispatches to any `SinkProtocol`
- `OpenClawSSEConsumer` — SSE transport layer, unaffected
- `WebSocketSink` — dashboard path unchanged

## Key Constraint

`RichSink` creates a Rich Live context that takes over the terminal. Only one can be active at a time — hence the `_streaming_counter` guard. This is identical to DSPy's constraint.
