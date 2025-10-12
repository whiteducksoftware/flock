# Parallel Streaming Implementation - v0.5.1 Update

**Status**: Current Analysis (January 2025)
**Original Proposal**: `parallel_streaming_implementation.md`
**Framework Version**: 0.5.0b63

---

## Executive Summary

The original proposal laid out a vision for parallel streaming in dashboard mode vs single-stream CLI mode. Since then:

✅ **What's Implemented:**
- Parallel streaming WORKS in dashboard mode (no stream queuing)
- Single-stream limitation enforced in CLI mode via `_active_streams` counter
- WebSocket broadcasting integrated into streaming execution
- Dashboard detection via `orchestrator.is_dashboard` boolean flag

❌ **What's Missing:**
- Separate WebSocket-only streaming method (performance optimization)
- Rich formatting overhead still present in dashboard mode (wasted resources)
- No `runtime_mode` enum in Context (simpler boolean used instead)

🎯 **The Opportunity:**
Adding a dedicated WebSocket-only streaming path would eliminate unnecessary Rich formatting overhead in dashboard mode, improving performance for parallel agent execution.

---

## Current Implementation Analysis

### How It Works Today (v0.5.0b63)

#### 1. Dashboard Detection (`orchestrator.py`)

```python
# Simplified architecture - just a boolean flag
class Flock:
    def __init__(self, ...):
        self.is_dashboard: bool = False  # Set during serve(dashboard=True)
```

**vs Original Proposal:** Proposed a full `runtime_mode` enum (`"cli"`, `"dashboard"`, `"api"`) in Context. Current code just uses a boolean on the orchestrator.

**Assessment:** ✅ Simpler approach is fine - we only need two modes.

---

#### 2. Stream Queuing Logic (`dspy_engine.py:228-241`)

```python
# Detect if there's already an active Rich Live context
should_stream = self.stream
orchestrator = getattr(ctx, "orchestrator", None)
if orchestrator:
    is_dashboard = getattr(orchestrator, "is_dashboard", False)
    # if dashboard we always stream, streaming queue only for CLI output
    if should_stream and ctx and not is_dashboard:
        if not hasattr(orchestrator, "_active_streams"):
            orchestrator._active_streams = 0

        if orchestrator._active_streams > 0:
            should_stream = False  # Queue this stream (CLI mode)
        else:
            orchestrator._active_streams += 1  # First stream active
```

**Key Insight:** The comment says "streaming queue only for CLI output" but the implementation STILL creates Rich Live contexts in dashboard mode (see line 382-397).

**Assessment:** ⚠️ Partially correct - parallel streaming works, but wastes resources on Rich formatting.

---

#### 3. Unified Streaming Method (`dspy_engine.py:506-854`)

Current `_execute_streaming` method handles BOTH:
- Rich Live display (terminal output)
- WebSocket broadcasting (dashboard frontend)

```python
async def _execute_streaming(self, ...):
    # Get WebSocketManager for frontend streaming
    ws_manager = None
    if ctx:
        orchestrator = getattr(ctx, "orchestrator", None)
        if orchestrator:
            collector = getattr(orchestrator, "_dashboard_collector", None)
            if collector:
                ws_manager = getattr(collector, "_websocket_manager", None)

    # PROBLEM: Creates Rich Live context even in dashboard mode!
    formatter = theme_dict = styles = agent_label = None
    live_cm = nullcontext()

    if not self.no_output:  # This doesn't check is_dashboard!
        _ensure_live_crop_above()
        (formatter, theme_dict, styles, agent_label) = self._prepare_stream_formatter(agent)
        initial_panel = formatter.format_result(...)
        live_cm = Live(initial_panel, console=console, ...)  # CPU/memory overhead!

    with live_cm as live:  # Rich Live context active even when not needed
        async for value in stream_generator:
            # ... emit to WebSocket (good!)
            if ws_manager and token:
                event = StreamingOutputEvent(...)
                task = asyncio.create_task(ws_manager.broadcast(event))

            # ... update Rich display (wasted in dashboard mode!)
            if formatter is not None:
                _refresh_panel()  # No one is watching!
```

**vs Original Proposal:** Proposed separate `_execute_streaming_websocket_only` for dashboard mode.

**Assessment:** ❌ Original proposal was RIGHT - we need separation for performance.

---

## What's Changed vs Original Proposal

| Feature | Original Proposal | Current Implementation | Status |
|---------|------------------|------------------------|--------|
| **Runtime Mode Tracking** | `runtime_mode` enum in Context | `is_dashboard` boolean on orchestrator | ✅ Simpler is better |
| **Parallel Streaming** | Proposed | ✅ Works in dashboard mode | ✅ Implemented |
| **Single-Stream CLI** | Proposed | ✅ Works via `_active_streams` | ✅ Implemented |
| **WebSocket-Only Method** | `_execute_streaming_websocket_only` | ❌ Not implemented | ⚠️ Should add |
| **Performance Optimization** | Avoid Rich overhead in dashboard | ❌ Still creates Rich contexts | ⚠️ Needs fixing |
| **Context-Aware Execution** | Pass mode through Context | Check `orchestrator.is_dashboard` | ✅ Works fine |

---

## Performance Impact Analysis

### Current Overhead in Dashboard Mode

When multiple agents stream in parallel in dashboard mode:

```python
# PER AGENT executing in parallel:
✅ WebSocket broadcast (needed)          ~100-500μs per token
❌ Rich formatter.format_result()        ~1-5ms per refresh (wasted!)
❌ Live.update() with full panel         ~2-10ms per refresh (wasted!)
❌ Theme loading & syntax highlighting   ~5-20ms setup per agent (wasted!)
```

**With 5 agents streaming in parallel:**
- Current: 5 × Rich overhead = 35-150ms wasted CPU every refresh cycle
- Optimized: 0ms Rich overhead (WebSocket-only path)

**With 10+ agents (stress test scenario):**
- Current: Potential terminal scrambling (Rich Live conflicts)
- Optimized: Clean parallel WebSocket streams

---

## Recommended Implementation (v0.5.1)

### Option A: Minimal Change (Performance Fix)

Keep architecture simple, just add conditional Rich formatting:

```python
async def _execute_streaming(self, dspy_mod, program, signature, *, ...):
    # Get WebSocketManager
    ws_manager = None
    if ctx:
        orchestrator = getattr(ctx, "orchestrator", None)
        if orchestrator:
            collector = getattr(orchestrator, "_dashboard_collector", None)
            if collector:
                ws_manager = getattr(collector, "_websocket_manager", None)

    # NEW: Only create Rich formatter if NOT dashboard mode
    formatter = theme_dict = styles = agent_label = None
    live_cm = nullcontext()
    is_dashboard = orchestrator and getattr(orchestrator, "is_dashboard", False)

    if not self.no_output and not is_dashboard:  # ← KEY CHANGE
        _ensure_live_crop_above()
        (formatter, theme_dict, styles, agent_label) = self._prepare_stream_formatter(agent)
        initial_panel = formatter.format_result(...)
        live_cm = Live(...)

    with live_cm as live:
        async for value in stream_generator:
            # Always emit to WebSocket if available
            if ws_manager and token:
                event = StreamingOutputEvent(...)
                await ws_manager.broadcast(event)

            # Only update Rich display in CLI mode
            if formatter is not None and not is_dashboard:
                _refresh_panel()
```

**Pros:**
- ✅ Minimal code change (5-10 lines)
- ✅ Immediate performance benefit
- ✅ Zero breaking changes
- ✅ Keeps single method (simpler maintenance)

**Cons:**
- ⚠️ Still has Rich import/setup code that never runs in dashboard
- ⚠️ Method remains large and dual-purpose

---

### Option B: Dedicated WebSocket Path (Original Vision)

Split into two methods as originally proposed:

```python
async def _execute_streaming(self, ...):
    """Full streaming with Rich display (CLI mode)."""
    # Current implementation, but remove WebSocket logic
    # (WebSocket broadcasting moves to separate method)

async def _execute_streaming_websocket_only(self, ...):
    """Streaming for WebSocket only (dashboard mode).

    Optimized path that skips all Rich formatting overhead.
    Used when multiple agents stream in parallel to dashboard.
    """
    # Get WebSocketManager
    ws_manager = None
    if ctx:
        orchestrator = getattr(ctx, "orchestrator", None)
        if orchestrator:
            collector = getattr(orchestrator, "_dashboard_collector", None)
            if collector:
                ws_manager = getattr(collector, "_websocket_manager", None)

    if not ws_manager:
        # Fallback to standard execution if no WebSocket
        return await self._execute_standard(dspy_mod, program, ...)

    # Create streaming task
    streaming_task = dspy_mod.streamify(program, is_async_program=True, ...)
    stream_generator = streaming_task(...)

    # Stream processing loop (WebSocket only, no Rich)
    final_result = None
    stream_sequence = 0

    async for value in stream_generator:
        if isinstance(value, StatusMessage):
            token = getattr(value, "message", "")
            if token:
                event = StreamingOutputEvent(
                    agent_name=agent.name,
                    output_type="log",
                    content=str(token + "\n"),
                    sequence=stream_sequence,
                    is_final=False,
                )
                await ws_manager.broadcast(event)
                stream_sequence += 1

        elif isinstance(value, (StreamResponse, ModelResponseStream)):
            token = extract_token(value)  # Helper
            if token:
                event = StreamingOutputEvent(
                    agent_name=agent.name,
                    output_type="llm_token",
                    content=str(token),
                    sequence=stream_sequence,
                    is_final=False,
                )
                await ws_manager.broadcast(event)
                stream_sequence += 1

        elif isinstance(value, dspy_mod.Prediction):
            final_result = value
            # Emit final event
            event = StreamingOutputEvent(
                agent_name=agent.name,
                output_type="log",
                content="--- End of output ---",
                sequence=stream_sequence,
                is_final=True,
            )
            await ws_manager.broadcast(event)

    if final_result is None:
        raise RuntimeError("Streaming did not yield a final prediction.")

    return final_result, None  # No display data needed

# Update evaluate() to choose method:
async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
    # ... setup code ...

    if should_stream:
        is_dashboard = orchestrator and getattr(orchestrator, "is_dashboard", False)

        if is_dashboard and orchestrator._active_streams > 0:
            # Parallel streaming in dashboard - use optimized path
            raw_result, _ = await self._execute_streaming_websocket_only(
                dspy_mod, program, signature, ...
            )
        else:
            # Single stream (CLI or first dashboard stream) - use Rich display
            raw_result, stream_data = await self._execute_streaming(
                dspy_mod, program, signature, ...
            )
```

**Pros:**
- ✅ Clean separation of concerns
- ✅ Maximum performance (no Rich overhead)
- ✅ Easier to maintain separate code paths
- ✅ Aligns with original architectural vision

**Cons:**
- ⚠️ More code to maintain (two methods)
- ⚠️ Larger change (30-50 lines)
- ⚠️ Need to keep both methods in sync for WebSocket event format

---

## Recommendation

**For v0.5.1: Go with Option A (Minimal Change)**

Reasons:
1. **Immediate Win**: Performance benefit with minimal risk
2. **Simple**: 5-10 line change vs 50+ line refactor
3. **Incremental**: Can still do Option B later if needed
4. **Safe**: No risk of breaking existing behavior

**For v0.6.0+: Consider Option B**

Once Option A proves stable, refactor to dedicated methods for:
- Better code organization
- Easier future maintenance
- Maximum performance

---

## Implementation Checklist (Option A)

```python
# File: src/flock/engines/dspy_engine.py

# Line ~382: Update Rich formatter creation condition
- if not self.no_output:
+ is_dashboard = orchestrator and getattr(orchestrator, "is_dashboard", False)
+ if not self.no_output and not is_dashboard:

# Line ~452 & ~498 & ~548: Update _refresh_panel() calls
- if formatter is not None:
+ if formatter is not None and not is_dashboard:
      _refresh_panel()
```

**Testing:**
1. CLI mode: Verify Rich display still works
2. Dashboard mode: Verify WebSocket streams work without Rich overhead
3. Parallel dashboard: Run 5+ agents, verify no terminal scrambling
4. Performance: Measure CPU usage before/after with 10 parallel agents

---

## Benefits

### Performance Improvements (Option A)

**Before:**
```
5 parallel agents × 4 refreshes/sec × 5ms Rich overhead = 100ms/sec wasted
10 parallel agents × 4 refreshes/sec × 5ms Rich overhead = 200ms/sec wasted
```

**After:**
```
Dashboard mode: 0ms Rich overhead (WebSocket-only)
CLI mode: Unchanged (still works perfectly)
```

### User Experience Improvements

**Before:**
- Dashboard users: Wasted CPU cycles formatting invisible terminal output
- 10+ agents: Potential Rich Live conflicts causing terminal scrambling
- Performance: Slower parallel execution due to formatting overhead

**After:**
- Dashboard users: Maximum parallel streaming performance
- CLI users: Unchanged experience (still beautiful Rich output)
- 10+ agents: Clean parallel execution without conflicts

---

## Future Enhancements

### 1. Configuration Options (Post v0.5.1)

```python
class DSPyEngine(EngineComponent):
    parallel_streaming: bool = Field(
        default=True,
        description="Allow parallel streaming in dashboard mode"
    )
    websocket_only_dashboard: bool = Field(
        default=True,
        description="Skip Rich formatting in dashboard mode"
    )
```

### 2. Streaming Metrics (Post v0.5.1)

Track in dashboard:
- Active parallel streams count
- Stream latency per agent
- WebSocket message queue depth
- Token throughput (tokens/second)

### 3. Stream Prioritization (Future)

```python
blog_writer = flock.agent("blog_writer").engine(
    DSPyEngine(
        stream=True,
        stream_priority="high",  # Higher priority agents stream first
    )
)
```

---

## Compatibility Notes

### Breaking Changes

**None!** Both Option A and Option B are fully backward compatible.

### Deprecations

**None!** All existing APIs remain unchanged.

### Migration Guide

**Not needed!** Changes are transparent to users.

---

## Conclusion

The original proposal's core insight was **correct**: dashboard mode needs a different streaming strategy than CLI mode. The current implementation (v0.5.0b63) achieves parallel streaming but wastes resources on unused Rich formatting.

**Recommended Path Forward:**
1. ✅ **v0.5.1**: Implement Option A (minimal change, big performance win)
2. 🔄 **v0.6.0**: Consider Option B if separate methods prove valuable
3. 🚀 **Future**: Add configuration, metrics, and prioritization

The startup spirit says: **Ship the 80% solution now (Option A), iterate to 100% later (Option B).**

---

**Last Updated**: January 2025
**Next Review**: After v0.5.1 performance testing with 10+ parallel agents
