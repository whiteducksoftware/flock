# Parallel Streaming Implementation Proposal

## Overview

This document provides the implementation details for enabling parallel streaming in dashboard/serve mode while maintaining single-stream behavior for CLI compatibility.

## Implementation Files

### 1. Update Runtime Context

**File**: `src/flock/runtime.py`

```python
from typing import Literal

class Context(BaseModel):
    board: Any
    orchestrator: Any
    correlation_id: UUID | None = None
    task_id: str
    state: dict[str, Any] = Field(default_factory=dict)
    runtime_mode: Literal["cli", "dashboard", "api"] = Field(
        default="cli",
        description="Execution mode: cli (terminal), dashboard (web UI), api (REST)"
    )

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    @property
    def allows_parallel_streaming(self) -> bool:
        """Check if current mode supports parallel streaming."""
        return self.runtime_mode in ("dashboard", "api")

    @property
    def is_dashboard_mode(self) -> bool:
        """Check if running in dashboard mode."""
        return self.runtime_mode == "dashboard"

    @property
    def is_cli_mode(self) -> bool:
        """Check if running in CLI mode."""
        return self.runtime_mode == "cli"
```

### 2. Update Orchestrator

**File**: `src/flock/orchestrator.py`

```python
class Flock:
    def __init__(self, model: str | None = None) -> None:
        # ... existing init ...
        self._runtime_mode: Literal["cli", "dashboard", "api"] = "cli"

    async def serve(
        self, *, dashboard: bool = False, host: str = "127.0.0.1", port: int = 8000
    ) -> None:
        """Start HTTP service for the orchestrator (blocking)."""

        # Set runtime mode based on dashboard flag
        if dashboard:
            self._runtime_mode = "dashboard"
            # ... existing dashboard setup ...
        else:
            self._runtime_mode = "api"
            # ... existing API setup ...

    async def _run_agent_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
        correlation_id = artifacts[0].correlation_id if artifacts else uuid4()

        ctx = Context(
            board=BoardHandle(self),
            orchestrator=self,
            task_id=str(uuid4()),
            correlation_id=correlation_id,
            runtime_mode=self._runtime_mode,  # Pass runtime mode
        )
        # ... rest of method ...

    async def direct_invoke(
        self, agent_or_builder: Agent | AgentBuilder, inputs: list[BaseModel]
    ) -> list[Artifact]:
        # ... existing setup ...
        ctx = Context(
            board=BoardHandle(self),
            orchestrator=self,
            task_id=str(uuid4()),
            runtime_mode=self._runtime_mode,  # Pass runtime mode
        )
        # ... rest of method ...
```

### 3. Update DSPy Engine for Parallel Streaming

**File**: `src/flock/engines/dspy_engine.py`

```python
class DSPyEngine(EngineComponent):
    # ... existing fields ...

    parallel_streaming: bool = Field(
        default=True,
        description="Allow parallel streaming when in dashboard/API mode"
    )

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        # ... existing setup through line 226 ...

        with dspy_mod.context(lm=lm):
            program = self._choose_program(dspy_mod, signature, combined_tools)

            # Enhanced streaming logic with context awareness
            should_stream = self.stream
            if should_stream and ctx:
                orchestrator = getattr(ctx, "orchestrator", None)
                if orchestrator:
                    if not hasattr(orchestrator, "_active_streams"):
                        orchestrator._active_streams = 0

                    # Check if we need to limit streaming
                    if ctx.is_cli_mode:
                        # CLI mode: maintain single stream limitation
                        if orchestrator._active_streams > 0:
                            should_stream = False
                            logger.debug(f"Agent {agent.name}: Streaming disabled (CLI mode, active streams: {orchestrator._active_streams})")
                        else:
                            orchestrator._active_streams += 1
                            logger.debug(f"Agent {agent.name}: Streaming enabled (CLI mode)")
                    elif ctx.allows_parallel_streaming and self.parallel_streaming:
                        # Dashboard/API mode: allow parallel streaming
                        orchestrator._active_streams += 1
                        logger.info(f"Agent {agent.name}: Parallel streaming enabled (mode: {ctx.runtime_mode}, active streams: {orchestrator._active_streams})")
                    else:
                        # Parallel streaming disabled by config
                        if orchestrator._active_streams > 0:
                            should_stream = False

            try:
                if should_stream:
                    # Determine streaming method based on context
                    if ctx and ctx.is_dashboard_mode and orchestrator._active_streams > 1:
                        # Use WebSocket-only streaming for parallel agents in dashboard
                        raw_result, stream_final_display_data = await self._execute_streaming_websocket_only(
                            dspy_mod, program, signature,
                            description=sys_desc,
                            payload=execution_payload,
                            agent=agent,
                            ctx=ctx,
                            pre_generated_artifact_id=pre_generated_artifact_id,
                        )
                    else:
                        # Use standard streaming with Rich display
                        raw_result, stream_final_display_data = await self._execute_streaming(
                            dspy_mod, program, signature,
                            description=sys_desc,
                            payload=execution_payload,
                            agent=agent,
                            ctx=ctx,
                            pre_generated_artifact_id=pre_generated_artifact_id,
                        )

                    if not self.no_output and ctx:
                        ctx.state["_flock_stream_live_active"] = True
                else:
                    # Non-streaming execution
                    raw_result = await self._execute_standard(
                        dspy_mod, program,
                        description=sys_desc,
                        payload=execution_payload,
                    )
                    if ctx and orchestrator and getattr(orchestrator, "_active_streams", 0) > 0:
                        ctx.state["_flock_output_queued"] = True
            finally:
                if should_stream and ctx:
                    if orchestrator is None:
                        orchestrator = getattr(ctx, "orchestrator", None)
                    if orchestrator and hasattr(orchestrator, "_active_streams"):
                        orchestrator._active_streams = max(0, orchestrator._active_streams - 1)
                        logger.debug(f"Agent {agent.name}: Stream completed (remaining active: {orchestrator._active_streams})")

        # ... rest of method unchanged ...

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
    ) -> tuple[Any, None]:
        """Execute streaming for WebSocket only (no Rich display).

        Used for parallel streaming in dashboard mode where multiple
        agents stream simultaneously to the WebSocket.
        """
        logger.info(f"Agent {agent.name}: Starting WebSocket-only streaming")

        # Get WebSocket manager
        ws_manager = None
        if ctx:
            orchestrator = getattr(ctx, "orchestrator", None)
            if orchestrator:
                collector = getattr(orchestrator, "_dashboard_collector", None)
                if collector:
                    ws_manager = getattr(collector, "_websocket_manager", None)

        if not ws_manager:
            logger.warning(f"Agent {agent.name}: No WebSocket manager, falling back to standard execution")
            result = await self._execute_standard(dspy_mod, program, description=description, payload=payload)
            return result, None

        # Prepare stream listeners
        listeners = []
        try:
            streaming_mod = getattr(dspy_mod, "streaming", None)
            if streaming_mod and hasattr(streaming_mod, "StreamListener"):
                for name, field in signature.output_fields.items():
                    if field.annotation is str:
                        listeners.append(streaming_mod.StreamListener(signature_field_name=name))
        except Exception:
            listeners = []

        # Create streaming task
        streaming_task = dspy_mod.streamify(
            program,
            is_async_program=True,
            stream_listeners=listeners if listeners else None,
        )

        # Execute with appropriate payload format
        if isinstance(payload, dict) and "input" in payload:
            stream_generator = streaming_task(
                description=description,
                input=payload["input"],
                context=payload.get("context", []),
            )
        else:
            stream_generator = streaming_task(description=description, input=payload, context=[])

        # Process stream (WebSocket only, no Rich display)
        final_result = None
        stream_sequence = 0
        stream_buffers = defaultdict(list)

        async for value in stream_generator:
            try:
                from dspy.streaming import StatusMessage, StreamResponse
                from litellm import ModelResponseStream
            except Exception:
                StatusMessage = object
                StreamResponse = object
                ModelResponseStream = object

            if isinstance(value, StatusMessage):
                token = getattr(value, "message", "")
                if token:
                    event = StreamingOutputEvent(
                        correlation_id=str(ctx.correlation_id) if ctx and ctx.correlation_id else "",
                        agent_name=agent.name,
                        run_id=ctx.task_id if ctx else "",
                        output_type="log",
                        content=str(token + "\n"),
                        sequence=stream_sequence,
                        is_final=False,
                    )
                    await ws_manager.broadcast(event)
                    stream_sequence += 1

            elif isinstance(value, StreamResponse):
                token = getattr(value, "chunk", None)
                if token:
                    event = StreamingOutputEvent(
                        correlation_id=str(ctx.correlation_id) if ctx and ctx.correlation_id else "",
                        agent_name=agent.name,
                        run_id=ctx.task_id if ctx else "",
                        output_type="llm_token",
                        content=str(token),
                        sequence=stream_sequence,
                        is_final=False,
                    )
                    await ws_manager.broadcast(event)
                    stream_sequence += 1

            elif isinstance(value, ModelResponseStream):
                chunk = value
                token = chunk.choices[0].delta.content or ""
                if token:
                    event = StreamingOutputEvent(
                        correlation_id=str(ctx.correlation_id) if ctx and ctx.correlation_id else "",
                        agent_name=agent.name,
                        run_id=ctx.task_id if ctx else "",
                        output_type="llm_token",
                        content=str(token),
                        sequence=stream_sequence,
                        is_final=False,
                    )
                    await ws_manager.broadcast(event)
                    stream_sequence += 1

            elif isinstance(value, dspy_mod.Prediction):
                final_result = value
                # Send final event
                event = StreamingOutputEvent(
                    correlation_id=str(ctx.correlation_id) if ctx and ctx.correlation_id else "",
                    agent_name=agent.name,
                    run_id=ctx.task_id if ctx else "",
                    output_type="log",
                    content=f"Streaming completed. Total tokens: {stream_sequence}",
                    sequence=stream_sequence,
                    is_final=True,
                )
                await ws_manager.broadcast(event)

        if final_result is None:
            raise RuntimeError(f"Agent {agent.name}: Streaming did not yield a final prediction")

        logger.info(f"Agent {agent.name}: WebSocket streaming completed ({stream_sequence} tokens)")
        return final_result, None
```

## Usage Examples

### CLI Mode (Single Stream)

```python
# Standard CLI execution - single stream maintained
flock = Flock("openai/gpt-4")
# ... define agents ...
await flock.publish(idea)
await flock.run_until_idle()
# Only one agent streams at a time to terminal
```

### Dashboard Mode (Parallel Streaming)

```python
# Dashboard with parallel streaming
flock = Flock("openai/gpt-4")
# ... define agents ...
await flock.serve(dashboard=True)
# Multiple agents can stream simultaneously to WebSocket
```

### API Mode (Configurable)

```python
# API mode - streaming optional
flock = Flock("openai/gpt-4")
# ... define agents ...
await flock.serve(dashboard=False)
# Streaming behavior depends on client requests
```

## Benefits

1. **Zero Breaking Changes**: Default CLI behavior unchanged
2. **Enhanced Dashboard UX**: Real-time parallel agent execution
3. **Clean Architecture**: Context-driven behavior
4. **Future-Proof**: Easy to add new runtime modes
5. **Debuggable**: Clear logging of streaming decisions

## Testing Checklist

- [ ] CLI mode maintains single stream
- [ ] Dashboard mode enables parallel streaming
- [ ] WebSocket receives all parallel streams
- [ ] Stream counter accurately tracks active streams
- [ ] Graceful fallback when WebSocket unavailable
- [ ] Memory cleanup after streaming completes
- [ ] Performance acceptable with 10+ parallel streams

## Rollout Plan

1. **Phase 1**: Add runtime_mode to Context (backward compatible)
2. **Phase 2**: Implement WebSocket-only streaming method
3. **Phase 3**: Enable parallel streaming in dashboard mode
4. **Phase 4**: Add configuration options
5. **Phase 5**: Performance optimization

## Configuration Options

```python
# Future enhancement: per-agent streaming config
blog_writer = (
    flock.agent("blog_writer")
    .engine(DSPyEngine(
        stream=True,
        parallel_streaming=True,  # Allow in dashboard
        stream_priority="high",   # Future: stream prioritization
    ))
)
```

## Monitoring & Metrics

Track these metrics in dashboard mode:
- Active parallel streams count
- Stream latency per agent
- WebSocket message queue depth
- Token throughput (tokens/second)
- Memory usage with parallel streams

## Conclusion

This implementation enables powerful parallel streaming for dashboard users while maintaining CLI compatibility. The context-aware approach ensures clean separation of concerns and provides a foundation for future enhancements.