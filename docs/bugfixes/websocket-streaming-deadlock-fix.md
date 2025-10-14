# WebSocket Streaming Deadlock Fix

## Issue Description

**Symptom**: When using the dashboard UI, agent execution would freeze (deadlock) when the agent called MCP tools during streaming, particularly with filesystem operations. The issue did NOT occur when running via CLI without the dashboard.

**Affected Component**: `src/flock/engines/dspy_engine.py` - streaming execution with WebSocket broadcasting

## Root Cause Analysis

### The Deadlock Scenario

The deadlock occurred due to a **circular wait condition** in the async event loop:

1. **Agent starts streaming** tokens via WebSocket: `await ws_manager.broadcast(event)`
2. **Agent calls an MCP tool** (e.g., filesystem read) - this is an `await` operation
3. **WebSocket send buffer fills up** because the client can't process messages fast enough
4. **`broadcast()` blocks** waiting for `client.send_text(message)` to complete (500ms timeout)
5. **Client is blocked** waiting for the agent to finish
6. **Agent can't continue** because it's waiting for `broadcast()` to return

This creates a **circular dependency**:
```
Streaming loop → await broadcast() → await client.send_text() →
  → client waiting for response → agent waiting to send →
    → agent blocked on MCP tool → deadlock!
```

### Why It Only Happened with Dashboard

- **CLI mode**: No WebSocket, streaming goes directly to console (no blocking I/O to client)
- **Dashboard mode**: WebSocket adds network I/O and client buffering, creating blocking points

### Key Code Pattern (Before Fix)

```python
async for value in stream_generator:
    if isinstance(value, StatusMessage):
        # ... process token ...

        # BLOCKING: Waits for WebSocket to complete send
        await ws_manager.broadcast(event)  # ← DEADLOCK HERE

    # ... later ...

    # MCP tool call happens here
    result = await server.call_tool(...)  # ← Can't reach if blocked above
```

## The Fix

### Solution: Non-Blocking WebSocket Broadcasts

Changed all `await ws_manager.broadcast(event)` calls inside the streaming loop to **fire-and-forget** using `asyncio.create_task()`:

```python
# Before (blocking)
await ws_manager.broadcast(event)

# After (non-blocking)
task = asyncio.create_task(ws_manager.broadcast(event))
ws_broadcast_tasks.add(task)
task.add_done_callback(ws_broadcast_tasks.discard)
```

### Changes Made

**File**: `src/flock/engines/dspy_engine.py`

1. **Added asyncio import**:
   ```python
   import asyncio
   ```

2. **Track background tasks** to prevent garbage collection:
   ```python
   # Track background WebSocket broadcast tasks to prevent garbage collection
   ws_broadcast_tasks: set[asyncio.Task] = set()
   ```

3. **Updated all broadcast calls** (4 locations in streaming loop):
   - `StatusMessage` handling (line ~625)
   - `StreamResponse` handling (line ~670)
   - `ModelResponseStream` handling (line ~715)
   - Final `Prediction` handling (lines ~745, ~760)

### Why This Works

1. **Breaks the circular wait**: Streaming loop doesn't wait for WebSocket sends to complete
2. **Maintains order**: Tasks are created in sequence, AsyncIO scheduler maintains order
3. **Prevents garbage collection**: Tasks stored in set until completion
4. **Graceful error handling**: Errors in broadcast don't crash the streaming loop
5. **Timeout still applies**: WebSocket still has 500ms timeout per client (in broadcast method)

## Testing

### Before Fix
```bash
# This would deadlock when agent calls filesystem tool
uv run python examples/03-the-dashboard/test_streaming_fix.py
# Result: Hangs indefinitely when tool is called
```

### After Fix
```bash
# Should complete successfully
uv run python examples/03-the-dashboard/test_streaming_fix.py
# Result: Streams tokens, calls tool, completes normally
```

### Verification Steps

1. **Start dashboard example** with MCP filesystem tools
2. **Publish artifact** that triggers agent with tool calls
3. **Observe streaming**: Should see tokens streaming in real-time
4. **Tool execution**: Agent should call filesystem tools without freezing
5. **Completion**: Agent should finish and display final output

## Related Code

### WebSocket Timeout Protection

The WebSocket broadcast already had timeout protection (500ms per client):

```python
# In src/flock/dashboard/websocket.py
send_tasks = [
    asyncio.wait_for(client.send_text(message), timeout=0.5)  # 500ms timeout
    for client in clients_list
]
results = await asyncio.gather(*send_tasks, return_exceptions=True)
```

This timeout prevented infinite hangs on individual client sends, but didn't prevent the streaming loop from blocking.

### MCP Tool Execution

MCP tools are async operations that can take time:

```python
# In src/flock/mcp/tool.py
async def func(*args, **kwargs):
    result = await server.call_tool(
        agent_id=self.agent_id,
        run_id=self.run_id,
        name=self.name,
        arguments=kwargs,
    )
    return self._convert_mcp_tool_result(result)
```

When streaming loop blocks on `await broadcast()`, it can't reach tool execution.

## Lessons Learned

### Async Programming Gotchas

1. **Never block in a loop that generates async events**: Use `create_task()` for background operations
2. **Always track background tasks**: Prevents garbage collection and allows cleanup
3. **WebSocket I/O is a blocking point**: Even with timeouts, can create circular waits
4. **Test with real network conditions**: CLI vs Dashboard revealed the issue

### Best Practices Applied

1. ✅ **Fire-and-forget for broadcasts**: Don't wait for all clients to receive
2. ✅ **Task tracking**: Prevent garbage collection with set + done_callback
3. ✅ **Timeout protection**: Already in place at WebSocket level (500ms)
4. ✅ **Error isolation**: try/except around each broadcast creation
5. ✅ **Sequence preservation**: Tasks maintain order in AsyncIO scheduler

## Impact

### Fixed
- ✅ Dashboard streaming works with MCP tool calls
- ✅ No more deadlocks during agent execution
- ✅ Real-time token streaming continues during tool execution

### No Regressions
- ✅ CLI mode still works (no WebSocket = no change)
- ✅ Streaming order preserved (AsyncIO guarantees)
- ✅ Error handling unchanged (try/except still catches failures)
- ✅ Client timeout protection still active (500ms per client)

## Future Considerations

### Potential Improvements

1. **Backpressure handling**: Could monitor `ws_broadcast_tasks` size and pause streaming if queue gets too large
2. **Broadcast batching**: Could batch multiple tokens into single broadcast for efficiency
3. **Client-side buffering**: Could implement client-side buffer to handle burst traffic
4. **Metrics**: Could track broadcast task queue size and completion time

### Architecture Decision

**Decision**: Use fire-and-forget for WebSocket broadcasts during streaming
**Rationale**: Streaming must not block on network I/O; client displays are eventually consistent
**Trade-off**: Slight delay in UI updates vs. preventing deadlocks (clear win for preventing deadlocks)

## Version

- **Fixed in**: v0.5.0b64 (or current version)
- **Issue discovered**: October 9, 2025
- **Fix applied**: October 9, 2025
