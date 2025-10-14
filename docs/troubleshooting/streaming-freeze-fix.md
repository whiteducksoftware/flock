# Streaming Freeze Issue - Analysis and Fix

## Problem Description

When an agent with streaming enabled decides to call a tool, the streaming output freezes at the point where it displays the tool name. For example:

```
[[ ## next_thought ## ]]
I need to locate the "Readme.md" file in the filesystem...
[[ ## next_tool_name ## ]]
filesystem__list_allowed   <-- FREEZES HERE
```

The stream appears to hang, giving no indication that the tool is being called or that execution is continuing.

## Root Cause Analysis

### The Issue

The streaming freeze occurs in `/Users/tilmansattler/src/whiteduck/flock/src/flock/engines/dspy_engine.py` in the `_execute_streaming` method.

When a language model decides to call a tool during streaming:

1. **Normal streaming chunks** contain:
   - `delta.content = "some text"` (the actual tokens)
   - This content is displayed in the stream

2. **Tool call chunks** contain:
   - `delta.content = None` or `""` (no text content)
   - `delta.tool_calls = [{"index": 0, "function": {"name": "tool_name", "arguments": "..."}}]`
   - This is the tool call metadata

### The Bug

The original code at line ~676 was:

```python
if isinstance(value, ModelResponseStream):
    chunk = value
    token = chunk.choices[0].delta.content or ""
    signature_field = getattr(value, "signature_field_name", None)

    # ... rest of the code

    if token:  # ❌ This check fails when delta.content is None!
        # Update display
        stream_buffers[buffer_key].append(str(token))
        display_data["payload"]["_streaming"] = "".join(stream_buffers[buffer_key])
```

**The problem**: When `delta.content` is `None` (during tool calls), `token` becomes an empty string. All subsequent `if token:` checks fail, so nothing is displayed. The stream continues in the background, but the UI appears frozen.

## The Fix

Added explicit handling for tool call deltas in the streaming logic:

```python
if isinstance(value, ModelResponseStream):
    chunk = value
    delta = chunk.choices[0].delta
    token = delta.content or ""
    signature_field = getattr(value, "signature_field_name", None)

    # ✅ Check for tool calls in the delta
    tool_call_delta = getattr(delta, "tool_calls", None)
    has_tool_call = tool_call_delta is not None and len(tool_call_delta) > 0

    # ✅ Debug logging
    if has_tool_call:
        logger.debug(f"[STREAMING] Tool call detected in delta: {tool_call_delta}")

    # ... handle different cases ...

    elif has_tool_call:
        # ✅ Handle tool call streaming
        tool_call = tool_call_delta[0]
        tool_name = getattr(tool_call.function, "name", None) if hasattr(tool_call, "function") else None

        if tool_name:
            tool_status = f"\n🔧 Calling tool: {tool_name}"
            stream_buffers[status_field].append(tool_status)
            display_data["status"] = "".join(stream_buffers[status_field])

            # Refresh the display
            if formatter is not None:
                _refresh_panel()
```

## Key Changes

1. **Extract delta object**: Access `delta` directly to check both `content` and `tool_calls`
2. **Detect tool calls**: Check if `delta.tool_calls` exists and is non-empty
3. **Display tool activity**: When a tool call is detected, show a visual indicator (🔧 icon + tool name)
4. **Handle tool arguments**: Accumulate and display streaming tool arguments if present
5. **Emit WebSocket events**: Send tool call events to the frontend dashboard
6. **Debug logging**: Added logging to help diagnose streaming issues

## What Users Will See Now

Instead of freezing, the stream will now display:

```
[[ ## next_thought ## ]]
I need to locate the "Readme.md" file in the filesystem...
[[ ## next_tool_name ## ]]
filesystem__list_allowed
🔧 Calling tool: filesystem__list_allowed
[tool arguments streaming here...]
[tool result displays...]
[agent continues reasoning...]
```

## Testing

A test script has been created at `/Users/tilmansattler/src/whiteduck/flock/test_streaming_fix.py` to verify the fix works correctly.

To test:
```bash
python test_streaming_fix.py
```

Watch the output - streaming should continue smoothly even when tools are called, showing the tool call activity with the 🔧 icon.

## Technical Details

### Streaming Response Types

The DSPy streaming integration handles three types of stream chunks:

1. **StatusMessage** - Internal status messages from DSPy
2. **StreamResponse** - Field-specific responses with signature field names
3. **ModelResponseStream** - Raw LiteLLM streaming chunks (this is where the bug was)

### Delta Structure

A typical `ModelResponseStream` delta can have:

```python
delta = {
    "content": "some text",  # Regular tokens
    # OR
    "tool_calls": [          # Tool call metadata
        {
            "index": 0,
            "id": "call_xxx",
            "type": "function",
            "function": {
                "name": "tool_name",
                "arguments": '{"arg": "value"}'
            }
        }
    ]
}
```

The fix ensures we handle both cases properly.

## Related Files

- **Fixed**: `/Users/tilmansattler/src/whiteduck/flock/src/flock/engines/dspy_engine.py`
- **Test**: `/Users/tilmansattler/src/whiteduck/flock/test_streaming_fix.py`
- **Example**: `/Users/tilmansattler/src/whiteduck/flock/test.py` (original MCP roots example)

## Notes

- This is not an API issue - it's a client-side display issue in the streaming handler
- The execution was always continuing correctly; it was just not being displayed
- The fix is backward compatible - regular text streaming still works exactly as before
- Tool call streaming now provides better visibility into agent behavior
