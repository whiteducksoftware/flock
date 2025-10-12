# Streaming Architecture Analysis for Flock

## Executive Summary

The current Flock streaming implementation is constrained to single-agent streaming in CLI mode to prevent Rich Live display conflicts. This analysis explores the architecture for detecting execution context (CLI vs Web/serve mode) and enabling parallel streaming when appropriate.

## Current Implementation

### Core Streaming Logic (dspy_engine.py)

The DSPy engine manages streaming through a sophisticated state machine:

```python
# Lines 228-238: Active stream detection
should_stream = self.stream
if should_stream and ctx:
    orchestrator = getattr(ctx, "orchestrator", None)
    if orchestrator:
        if not hasattr(orchestrator, "_active_streams"):
            orchestrator._active_streams = 0

        if orchestrator._active_streams > 0:
            should_stream = False  # Disable for concurrent agents
        else:
            orchestrator._active_streams += 1
```

**Key Points:**
- Uses `orchestrator._active_streams` counter to track concurrent streaming
- Only allows one stream at a time (`_active_streams > 0` disables streaming)
- This is a **CLI constraint** due to Rich Live terminal rendering limitations

### Streaming Flow

1. **Stream Initialization** (Lines 467-520)
   - Creates Rich Live context for terminal display
   - Sets up WebSocket manager for dashboard streaming
   - Initializes stream listeners for DSPy output fields

2. **Stream Processing** (Lines 586-774)
   - Handles three types of stream events:
     - `StatusMessage`: Tool/reasoning updates
     - `StreamResponse`: Field-specific content
     - `ModelResponseStream`: LLM token streaming
   - Updates both terminal (Rich) and WebSocket simultaneously

3. **Stream Cleanup** (Lines 269-273)
   - Decrements `_active_streams` counter
   - Ensures proper cleanup even on errors

## Execution Contexts

### 1. CLI Mode (Direct Execution)
- **Entry**: `python script.py` or `uv run example.py`
- **Detection**: No `serve()` called, no dashboard components
- **Constraint**: Single stream due to Rich Live terminal limitations
- **Example**: `examples/showcase/03_blog_review.py`

### 2. Dashboard Mode (serve with dashboard=True)
- **Entry**: `await flock.serve(dashboard=True)`
- **Detection**: `_dashboard_collector` present on orchestrator
- **Capability**: Could support parallel streams (WebSocket only)
- **Example**: `examples/showcase/05_dashboard.py`

### 3. API Mode (serve without dashboard)
- **Entry**: `await flock.serve(dashboard=False)`
- **Detection**: No dashboard components
- **Capability**: No streaming UI needed
- **Example**: HTTP API endpoints

## Architecture for Context Detection

### Option 1: Runtime Mode in Context (Recommended)

Add execution mode to the Context object:

```python
# In runtime.py
class Context(BaseModel):
    board: Any
    orchestrator: Any
    correlation_id: UUID | None = None
    task_id: str
    state: dict[str, Any] = Field(default_factory=dict)
    runtime_mode: Literal["cli", "dashboard", "api"] = "cli"  # NEW
```

Update orchestrator to set mode:

```python
# In orchestrator.py serve() method
async def serve(self, *, dashboard: bool = False, ...):
    if dashboard:
        self._runtime_mode = "dashboard"
        # ... dashboard setup
    else:
        self._runtime_mode = "api"
        # ... API setup

# In _run_agent_task and direct_invoke
ctx = Context(
    board=BoardHandle(self),
    orchestrator=self,
    task_id=str(uuid4()),
    runtime_mode=getattr(self, "_runtime_mode", "cli"),  # NEW
)
```

### Option 2: Dashboard Detection via Attributes

Detect dashboard mode through existing attributes:

```python
# In dspy_engine.py
def _is_dashboard_mode(self, ctx: Any) -> bool:
    """Detect if running in dashboard/serve mode."""
    if not ctx:
        return False

    orchestrator = getattr(ctx, "orchestrator", None)
    if not orchestrator:
        return False

    # Check for dashboard-specific attributes
    return any([
        hasattr(orchestrator, "_dashboard_collector"),
        hasattr(orchestrator, "_dashboard_launcher"),
        hasattr(orchestrator, "_websocket_manager"),
    ])
```

### Option 3: Environment Variable

Use environment variable for mode detection:

```python
# Set in serve() method
os.environ["FLOCK_RUNTIME_MODE"] = "dashboard"

# Check in engine
is_dashboard = os.getenv("FLOCK_RUNTIME_MODE") == "dashboard"
```

## Parallel Streaming Architecture

### Modified Streaming Logic

```python
# In dspy_engine.py evaluate() method
async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
    # ... existing setup ...

    # Determine if parallel streaming is allowed
    runtime_mode = getattr(ctx, "runtime_mode", "cli")
    allow_parallel_streaming = runtime_mode == "dashboard"

    # Modified stream detection
    should_stream = self.stream
    if should_stream and ctx:
        orchestrator = getattr(ctx, "orchestrator", None)
        if orchestrator:
            if not hasattr(orchestrator, "_active_streams"):
                orchestrator._active_streams = 0

            # Only limit streaming in CLI mode
            if runtime_mode == "cli" and orchestrator._active_streams > 0:
                should_stream = False
            else:
                orchestrator._active_streams += 1
```

### WebSocket-Only Streaming

For dashboard mode with parallel agents:

```python
async def _execute_streaming_websocket_only(
    self,
    dspy_mod,
    program,
    signature,
    *,
    description: str,
    payload: dict[str, Any],
    agent: Any,
    ctx: Any,
    pre_generated_artifact_id: Any,
) -> Any:
    """Execute streaming for WebSocket only (no Rich display)."""

    # Get WebSocket manager
    ws_manager = self._get_websocket_manager(ctx)
    if not ws_manager:
        # Fall back to standard execution
        return await self._execute_standard(
            dspy_mod, program,
            description=description, payload=payload
        )

    # Stream processing without Rich Live
    # ... similar to existing but without Rich components
```

## Implementation Recommendations

### Phase 1: Context Detection (Foundation)
1. Implement Option 1 (runtime_mode in Context)
2. Update orchestrator to set mode appropriately
3. Add helper methods for mode checking

### Phase 2: Parallel Streaming Support
1. Modify stream limiting logic to check runtime mode
2. Create WebSocket-only streaming method
3. Route to appropriate streaming method based on mode

### Phase 3: Enhanced Features
1. Add streaming configuration per mode
2. Implement stream prioritization for dashboard
3. Add metrics for parallel stream performance

## Benefits of This Architecture

1. **Backward Compatibility**: CLI mode continues with single stream
2. **Enhanced Dashboard**: Parallel streaming for real-time multi-agent view
3. **Clean Separation**: Clear distinction between execution contexts
4. **Future Flexibility**: Easy to add new runtime modes
5. **Performance**: Removes artificial constraint in non-CLI modes

## Testing Strategy

1. **Unit Tests**: Mock context with different runtime modes
2. **Integration Tests**: Test streaming in each mode
3. **Performance Tests**: Measure parallel streaming overhead
4. **UI Tests**: Verify dashboard handles parallel streams

## Migration Path

1. **Step 1**: Add runtime_mode field (backward compatible with default "cli")
2. **Step 2**: Update serve() to set mode
3. **Step 3**: Modify streaming logic to check mode
4. **Step 4**: Test thoroughly in all modes
5. **Step 5**: Document new capabilities

## Conclusion

The current single-stream limitation is a CLI-specific constraint that unnecessarily limits the dashboard experience. By implementing context-aware streaming, we can enable parallel streaming for web dashboards while maintaining CLI compatibility. The recommended approach using runtime_mode in Context provides the cleanest, most maintainable solution.