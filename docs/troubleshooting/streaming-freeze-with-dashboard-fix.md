# Streaming Freeze Bug Investigation - Dashboard Mode

## Issue Summary

When running the framework with `flock.serve(dashboard=True)`, the streaming output freezes when the LLM decides to call a tool. The display shows a partial tool name (e.g., `filesystem__list_allowed_dire`) and then stops updating, even though the agent is still working in the background.

## Current Investigation

### Hypothesis 1: Missing Panel Refresh (INCOMPLETE FIX)
Initially identified missing `_refresh_panel()` call after token updates - this was partially correct but didn't solve the freeze.

### Hypothesis 2: Tool Call Streaming Logic
The freeze occurs specifically when tool calls are being streamed. The tool name comes through `tool_call_delta[0].function.name` but may be:
1. Coming in character-by-character and we're not displaying it incrementally
2. Being sent as a complete name but we're not refreshing the panel
3. Being handled differently between dashboard and non-dashboard modes

## Current Fix Attempt

Modified `/src/flock/engines/dspy_engine.py` around line 700-740 to:
1. Stream tool names as they arrive (character by character)
2. Refresh panel after each tool name chunk
3. Add debug logging to trace what's happening

## Debug Steps

Run with debug logging enabled to see the actual streaming behavior:

```python
configure_logging(
    flock_level="DEBUG",
    external_level="ERROR",
    specific_levels={
        "flock.engines.dspy_engine": "DEBUG",  # Enable detailed streaming logs
    }
)
```

Look for log messages like:
- `[STREAMING] Tool call detected in delta: ...`
- `[STREAMING] Token present: True/False, token value: '...'`

## Next Steps

1. Run `test.py` with debug logging
2. Capture the debug output when freeze occurs
3. Analyze whether:
   - Tool name is streaming character-by-character or all at once
   - Panel refresh is being called
   - Both token AND tool_call are present simultaneously
