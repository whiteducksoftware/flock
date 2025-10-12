# Parallel Streaming Architecture

## Overview

This document describes the architecture for enabling parallel streaming in Flock, removing the artificial limitation that restricts streaming to a single agent when running in dashboard mode.

## Problem Statement

Currently, Flock limits streaming to one agent at a time using an `_active_streams` counter on the orchestrator. This limitation exists purely for CLI display purposes - Rich Live contexts conflict when multiple agents try to update the terminal simultaneously.

However, this restriction unnecessarily limits the dashboard experience, where WebSocket can handle multiple parallel streams without display conflicts.

## Solution: Context-Aware Runtime Modes

### 1. Runtime Mode Enumeration

```python
from enum import Enum

class RuntimeMode(Enum):
    """Execution context for the orchestrator."""
    CLI = "cli"              # Direct script execution with terminal output
    DASHBOARD = "dashboard"  # Web UI with WebSocket streaming
    API = "api"              # REST API service mode
    TEST = "test"            # Test execution mode
```

### 2. Context Enhancement

Add runtime mode tracking to the Context class:

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Context:
    """Execution context passed through the system."""

    # Existing fields
    board: Blackboard
    metadata: dict = field(default_factory=dict)
    correlation_id: Optional[UUID] = None

    # New field for runtime mode
    runtime_mode: RuntimeMode = RuntimeMode.CLI

    @property
    def allows_parallel_streaming(self) -> bool:
        """Check if current runtime supports parallel streaming."""
        return self.runtime_mode in [RuntimeMode.DASHBOARD, RuntimeMode.API]

    @property
    def should_stream_to_console(self) -> bool:
        """Check if streaming should output to console."""
        return self.runtime_mode == RuntimeMode.CLI

    @property
    def should_stream_to_websocket(self) -> bool:
        """Check if streaming should emit WebSocket events."""
        return self.runtime_mode in [RuntimeMode.DASHBOARD, RuntimeMode.API]
```

### 3. Orchestrator Mode Detection

Update the orchestrator to set runtime mode:

```python
class Flock:
    def __init__(self, model: str = None, **kwargs):
        self.model = model
        self._active_streams = 0
        self._context = Context(
            board=self,
            runtime_mode=RuntimeMode.CLI  # Default to CLI
        )

    async def serve(
        self,
        dashboard: bool = False,
        host: str = "0.0.0.0",
        port: int = 8000,
        **kwargs
    ):
        """Start HTTP service with optional dashboard."""

        # Set runtime mode based on configuration
        if dashboard:
            self._context.runtime_mode = RuntimeMode.DASHBOARD
            logger.info("Starting in DASHBOARD mode - parallel streaming enabled")
        else:
            self._context.runtime_mode = RuntimeMode.API
            logger.info("Starting in API mode")

        # Propagate to all agents
        for agent in self.agents:
            agent.context.runtime_mode = self._context.runtime_mode

        # Start services...
        await self._start_services(host, port, dashboard)

    def run_script(self):
        """Direct script execution - CLI mode."""
        self._context.runtime_mode = RuntimeMode.CLI
        logger.info("Running in CLI mode - single stream limit active")
```

### 4. DSPy Engine Parallel Streaming

Update the DSPy engine to respect runtime mode:

```python
class DSPyEngine(EngineComponent):
    async def evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        """Execute DSPy chain with runtime-aware streaming."""

        # Determine if we can stream
        can_stream = self._can_stream(agent, ctx)

        if can_stream:
            if ctx.should_stream_to_console:
                # CLI mode - use Rich Live (exclusive)
                return await self._execute_streaming_console(agent, ctx, inputs)
            elif ctx.should_stream_to_websocket:
                # Dashboard/API mode - WebSocket only
                return await self._execute_streaming_websocket(agent, ctx, inputs)
        else:
            # No streaming
            return await self._execute_non_streaming(agent, ctx, inputs)

    def _can_stream(self, agent: Agent, ctx: Context) -> bool:
        """Determine if streaming is possible."""

        # Check basic streaming support
        if not self.enable_streaming or not hasattr(self.chain, "stream"):
            return False

        # In CLI mode, only one stream allowed
        if ctx.runtime_mode == RuntimeMode.CLI:
            orchestrator = ctx.board
            if orchestrator._active_streams > 0:
                logger.debug(f"CLI mode: streaming disabled (active: {orchestrator._active_streams})")
                return False

        # Dashboard/API modes support parallel streaming
        return True

    async def _execute_streaming_console(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs
    ) -> EvalResult:
        """Stream to console using Rich Live (CLI mode)."""

        orchestrator = ctx.board
        orchestrator._active_streams += 1

        try:
            # Use Rich Live for console output
            with Live(console=console, refresh_per_second=10) as live:
                content = ""
                async for chunk in self.chain.stream(prompt):
                    content += chunk
                    live.update(Panel(content, title=agent.name))

                    # Also emit to WebSocket if available
                    if ctx.should_stream_to_websocket:
                        await self._emit_stream_event(agent, chunk)

                return self._create_result(content)
        finally:
            orchestrator._active_streams -= 1

    async def _execute_streaming_websocket(
        self,
        agent: Agent,
        ctx: Context,
        inputs: EvalInputs
    ) -> EvalResult:
        """Stream only to WebSocket (Dashboard/API mode)."""

        # No stream counting needed - unlimited parallel streams
        content = ""
        async for chunk in self.chain.stream(prompt):
            content += chunk
            await self._emit_stream_event(agent, chunk)

        return self._create_result(content)

    async def _emit_stream_event(self, agent: Agent, chunk: str):
        """Emit streaming chunk to WebSocket."""

        if hasattr(agent, "_event_collector") and agent._event_collector:
            await agent._event_collector.collect_stream_chunk(
                agent_name=agent.name,
                chunk=chunk,
                timestamp=time.time()
            )
```

### 5. WebSocket Stream Handling

Enhance WebSocket to handle multiple parallel streams:

```python
class WebSocketManager:
    def __init__(self):
        self.connections: set[WebSocket] = set()
        self.active_streams: dict[str, StreamState] = {}  # agent_name -> state

    async def handle_stream_chunk(self, event: StreamChunkEvent):
        """Handle streaming chunk from any agent."""

        # Track active streams
        if event.agent_name not in self.active_streams:
            self.active_streams[event.agent_name] = StreamState(
                agent_name=event.agent_name,
                started_at=time.time(),
                chunks=[]
            )

        state = self.active_streams[event.agent_name]
        state.chunks.append(event.chunk)

        # Broadcast to all connections
        message = {
            "type": "stream_chunk",
            "agent_name": event.agent_name,
            "chunk": event.chunk,
            "stream_id": state.stream_id,
            "timestamp": event.timestamp
        }

        await self.broadcast(json.dumps(message))

    async def handle_stream_end(self, agent_name: str):
        """Mark stream as complete."""

        if agent_name in self.active_streams:
            state = self.active_streams[agent_name]

            message = {
                "type": "stream_complete",
                "agent_name": agent_name,
                "stream_id": state.stream_id,
                "full_content": "".join(state.chunks),
                "duration": time.time() - state.started_at
            }

            await self.broadcast(json.dumps(message))
            del self.active_streams[agent_name]
```

### 6. Frontend Parallel Stream Display

Update frontend to handle multiple concurrent streams:

```typescript
interface StreamState {
  agentName: string;
  streamId: string;
  content: string;
  isStreaming: boolean;
  startedAt: number;
}

class WebSocketStore {
  activeStreams: Map<string, StreamState> = new Map();

  handleStreamChunk(message: StreamChunkMessage) {
    const { agent_name, chunk, stream_id } = message;

    // Get or create stream state
    let stream = this.activeStreams.get(agent_name);
    if (!stream) {
      stream = {
        agentName: agent_name,
        streamId: stream_id,
        content: '',
        isStreaming: true,
        startedAt: Date.now()
      };
      this.activeStreams.set(agent_name, stream);
    }

    // Append chunk
    stream.content += chunk;

    // Notify UI components
    this.notifyStreamUpdate(agent_name, stream);
  }

  handleStreamComplete(message: StreamCompleteMessage) {
    const { agent_name, full_content } = message;

    const stream = this.activeStreams.get(agent_name);
    if (stream) {
      stream.isStreaming = false;
      stream.content = full_content;  // Use complete content
      this.notifyStreamUpdate(agent_name, stream);
    }
  }
}
```

### 7. UI Components for Parallel Streams

```typescript
const ParallelStreamDisplay: React.FC = () => {
  const activeStreams = useWebSocketStore(s => s.activeStreams);

  return (
    <div className="parallel-streams-container">
      {Array.from(activeStreams.values()).map(stream => (
        <StreamPanel
          key={stream.streamId}
          agentName={stream.agentName}
          content={stream.content}
          isStreaming={stream.isStreaming}
        />
      ))}
    </div>
  );
};

const StreamPanel: React.FC<StreamPanelProps> = ({
  agentName,
  content,
  isStreaming
}) => {
  return (
    <div className={`stream-panel ${isStreaming ? 'streaming' : ''}`}>
      <div className="stream-header">
        <span className="agent-name">{agentName}</span>
        {isStreaming && <StreamingIndicator />}
      </div>
      <div className="stream-content">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  );
};
```

## Benefits

### 1. **Improved Dashboard Experience**
- Multiple agents can stream simultaneously
- Real-time parallel processing visualization
- Better representation of actual system behavior

### 2. **Backward Compatibility**
- CLI users see no change in behavior
- Existing scripts continue to work
- No breaking API changes

### 3. **Clean Architecture**
- Clear separation of concerns
- Context-driven behavior
- No hacks or workarounds

### 4. **Performance**
- Removes artificial bottleneck
- True parallel execution in dashboard
- Better resource utilization

### 5. **Extensibility**
- Easy to add new runtime modes
- Configurable streaming behavior
- Plugin-friendly architecture

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Add RuntimeMode enum
- [ ] Enhance Context with runtime_mode
- [ ] Update Orchestrator.serve() to set mode
- [ ] Add mode detection helpers

### Phase 2: Streaming Updates
- [ ] Update DSPyEngine evaluation logic
- [ ] Implement parallel streaming methods
- [ ] Remove artificial stream limiting in dashboard mode
- [ ] Add WebSocket stream tracking

### Phase 3: Frontend Support
- [ ] Update WebSocket store for multiple streams
- [ ] Create parallel stream UI components
- [ ] Add stream state management
- [ ] Implement stream visualization

### Phase 4: Testing & Polish
- [ ] Unit tests for runtime mode detection
- [ ] Integration tests for parallel streaming
- [ ] Performance testing with many streams
- [ ] Documentation updates

## Testing Strategy

### Unit Tests
```python
def test_runtime_mode_detection():
    orchestrator = Flock()
    assert orchestrator._context.runtime_mode == RuntimeMode.CLI

    await orchestrator.serve(dashboard=True)
    assert orchestrator._context.runtime_mode == RuntimeMode.DASHBOARD
    assert orchestrator._context.allows_parallel_streaming

def test_parallel_streaming_in_dashboard():
    orchestrator = Flock()
    orchestrator._context.runtime_mode = RuntimeMode.DASHBOARD

    # Should allow multiple streams
    engine1 = DSPyEngine()
    engine2 = DSPyEngine()

    assert engine1._can_stream(agent1, orchestrator._context)
    assert engine2._can_stream(agent2, orchestrator._context)
```

### Integration Tests
- Test multiple agents streaming simultaneously
- Verify WebSocket receives all stream events
- Check frontend handles parallel updates
- Validate no CLI interference

## Performance Considerations

### Stream Throttling
- Limit chunk frequency to 10-20 per second
- Batch small chunks together
- Use requestAnimationFrame for UI updates

### Memory Management
- Limit stored content per stream (e.g., last 100KB)
- Clean up completed streams after timeout
- Use virtual scrolling for long content

### WebSocket Optimization
- Compress large messages
- Use binary frames for efficiency
- Implement backpressure handling

## Security Considerations

- Validate runtime mode cannot be changed externally
- Sanitize streamed content before display
- Rate limit stream events per connection
- Implement proper authentication for WebSocket

## Conclusion

This architecture elegantly solves the parallel streaming limitation by introducing runtime mode awareness. The CLI maintains its single-stream behavior for clean terminal output, while the dashboard unleashes full parallel streaming capabilities. This approach is backward compatible, architecturally clean, and provides a foundation for future enhancements.