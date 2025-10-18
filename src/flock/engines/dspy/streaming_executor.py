"""DSPy streaming execution with Rich display and WebSocket support.

Phase 6: Extracted from dspy_engine.py to reduce file size and improve modularity.

This module handles all streaming-related logic for DSPy program execution,
including two modes:
- CLI mode: Rich Live display with terminal formatting (agents.run())
- Dashboard mode: WebSocket-only streaming for parallel execution (no Rich overhead)
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict, defaultdict
from contextlib import nullcontext
from datetime import UTC
from typing import Any

from pydantic import BaseModel

from flock.dashboard.events import StreamingOutputEvent
from flock.logging.logging import get_logger


logger = get_logger(__name__)


class DSPyStreamingExecutor:
    """Executes DSPy programs in streaming mode with Rich or WebSocket output.

    Responsibilities:
    - Standard (non-streaming) execution
    - WebSocket-only streaming (dashboard mode, no Rich overhead)
    - Rich CLI streaming with formatted tables
    - Stream formatter setup (themes, styles)
    - Final display rendering with artifact metadata
    """

    def __init__(
        self,
        *,
        status_output_field: str,
        stream_vertical_overflow: str,
        theme: str,
        no_output: bool,
    ):
        """Initialize streaming executor with configuration.

        Args:
            status_output_field: Field name for status output
            stream_vertical_overflow: Rich Live vertical overflow strategy
            theme: Theme name for Rich output formatting
            no_output: Whether to disable output
        """
        self.status_output_field = status_output_field
        self.stream_vertical_overflow = stream_vertical_overflow
        self.theme = theme
        self.no_output = no_output

    async def execute_standard(
        self, dspy_mod, program, *, description: str, payload: dict[str, Any]
    ) -> Any:
        """Execute DSPy program in standard mode (no streaming).

        Args:
            dspy_mod: DSPy module
            program: DSPy program (Predict or ReAct)
            description: System description
            payload: Execution payload with semantic field names

        Returns:
            DSPy Prediction result
        """
        # Handle semantic fields format: {"description": ..., "task": ..., "report": ...}
        if isinstance(payload, dict) and "description" in payload:
            # Semantic fields: pass all fields as kwargs
            return program(**payload)

        # Fallback for unexpected payload format
        raise ValueError(
            f"Invalid payload format: expected dict with 'description' key, got {type(payload).__name__}"
        )

    async def execute_streaming_websocket_only(
        self,
        dspy_mod,
        program,
        signature,
        *,
        description: str,
        payload: dict[str, Any],
        agent: Any,
        ctx: Any = None,
        pre_generated_artifact_id: Any = None,
        output_group=None,
    ) -> tuple[Any, None]:
        """Execute streaming for WebSocket only (no Rich display).

        Optimized path for dashboard mode that skips all Rich formatting overhead.
        Used when multiple agents stream in parallel to avoid terminal conflicts
        and deadlocks with MCP tools.

        This method eliminates the Rich Live context that can cause deadlocks when
        combined with MCP tool execution and parallel agent streaming.

        Args:
            dspy_mod: DSPy module
            program: DSPy program (Predict or ReAct)
            signature: DSPy Signature
            description: System description
            payload: Execution payload with semantic field names
            agent: Agent instance
            ctx: Execution context
            pre_generated_artifact_id: Pre-generated artifact ID for streaming
            output_group: OutputGroup defining expected outputs

        Returns:
            Tuple of (DSPy Prediction result, None)
        """
        logger.info(
            f"Agent {agent.name}: Starting WebSocket-only streaming (dashboard mode)"
        )

        # Get WebSocket broadcast function (security: wrapper prevents object traversal)
        # Phase 6+7 Security Fix: Use broadcast wrapper from Agent class variable (prevents GOD MODE restoration)
        from flock.core import Agent

        ws_broadcast = Agent._websocket_broadcast_global

        if not ws_broadcast:
            logger.warning(
                f"Agent {agent.name}: No WebSocket manager, falling back to standard execution"
            )
            result = await self.execute_standard(
                dspy_mod, program, description=description, payload=payload
            )
            return result, None

        # Get artifact type name for WebSocket events
        artifact_type_name = "output"
        # Use output_group.outputs (current group) if available, otherwise fallback to agent.outputs (all groups)
        outputs_to_display = (
            output_group.outputs
            if output_group and hasattr(output_group, "outputs")
            else agent.outputs
            if hasattr(agent, "outputs")
            else []
        )

        if outputs_to_display:
            artifact_type_name = outputs_to_display[0].spec.type_name

        # Prepare stream listeners
        listeners = []
        try:
            streaming_mod = getattr(dspy_mod, "streaming", None)
            if streaming_mod and hasattr(streaming_mod, "StreamListener"):
                for name, field in signature.output_fields.items():
                    if field.annotation is str:
                        listeners.append(
                            streaming_mod.StreamListener(signature_field_name=name)
                        )
        except Exception:
            listeners = []

        # Create streaming task
        streaming_task = dspy_mod.streamify(
            program,
            is_async_program=True,
            stream_listeners=listeners if listeners else None,
        )

        # Execute with appropriate payload format
        if isinstance(payload, dict) and "description" in payload:
            # Semantic fields: pass all fields as kwargs
            stream_generator = streaming_task(**payload)
        elif isinstance(payload, dict) and "input" in payload:
            # Legacy format: {"input": ..., "context": ...}
            stream_generator = streaming_task(
                description=description,
                input=payload["input"],
                context=payload.get("context", []),
            )
        else:
            # Old format: direct payload
            stream_generator = streaming_task(
                description=description, input=payload, context=[]
            )

        # Process stream (WebSocket only, no Rich display)
        final_result = None
        stream_sequence = 0

        # Track background WebSocket broadcast tasks to prevent garbage collection
        # Using fire-and-forget pattern to avoid blocking DSPy's streaming loop
        ws_broadcast_tasks: set[asyncio.Task] = set()

        async for value in stream_generator:
            try:
                from dspy.streaming import StatusMessage, StreamResponse
                from litellm import ModelResponseStream
            except Exception:
                StatusMessage = object  # type: ignore
                StreamResponse = object  # type: ignore
                ModelResponseStream = object  # type: ignore

            if isinstance(value, StatusMessage):
                token = getattr(value, "message", "")
                if token:
                    try:
                        event = StreamingOutputEvent(
                            correlation_id=str(ctx.correlation_id)
                            if ctx and ctx.correlation_id
                            else "",
                            agent_name=agent.name,
                            run_id=ctx.task_id if ctx else "",
                            output_type="log",
                            content=str(token + "\n"),
                            sequence=stream_sequence,
                            is_final=False,
                            artifact_id=str(pre_generated_artifact_id),
                            artifact_type=artifact_type_name,
                        )
                        # Fire-and-forget to avoid blocking DSPy's streaming loop
                        task = asyncio.create_task(ws_broadcast(event))
                        ws_broadcast_tasks.add(task)
                        task.add_done_callback(ws_broadcast_tasks.discard)
                        stream_sequence += 1
                    except Exception as e:
                        logger.warning(f"Failed to emit streaming event: {e}")

            elif isinstance(value, StreamResponse):
                token = getattr(value, "chunk", None)
                if token:
                    try:
                        event = StreamingOutputEvent(
                            correlation_id=str(ctx.correlation_id)
                            if ctx and ctx.correlation_id
                            else "",
                            agent_name=agent.name,
                            run_id=ctx.task_id if ctx else "",
                            output_type="llm_token",
                            content=str(token),
                            sequence=stream_sequence,
                            is_final=False,
                            artifact_id=str(pre_generated_artifact_id),
                            artifact_type=artifact_type_name,
                        )
                        # Fire-and-forget to avoid blocking DSPy's streaming loop
                        task = asyncio.create_task(ws_broadcast(event))
                        ws_broadcast_tasks.add(task)
                        task.add_done_callback(ws_broadcast_tasks.discard)
                        stream_sequence += 1
                    except Exception as e:
                        logger.warning(f"Failed to emit streaming event: {e}")

            elif isinstance(value, ModelResponseStream):
                chunk = value
                token = chunk.choices[0].delta.content or ""
                if token:
                    try:
                        event = StreamingOutputEvent(
                            correlation_id=str(ctx.correlation_id)
                            if ctx and ctx.correlation_id
                            else "",
                            agent_name=agent.name,
                            run_id=ctx.task_id if ctx else "",
                            output_type="llm_token",
                            content=str(token),
                            sequence=stream_sequence,
                            is_final=False,
                            artifact_id=str(pre_generated_artifact_id),
                            artifact_type=artifact_type_name,
                        )
                        # Fire-and-forget to avoid blocking DSPy's streaming loop
                        task = asyncio.create_task(ws_broadcast(event))
                        ws_broadcast_tasks.add(task)
                        task.add_done_callback(ws_broadcast_tasks.discard)
                        stream_sequence += 1
                    except Exception as e:
                        logger.warning(f"Failed to emit streaming event: {e}")

            elif isinstance(value, dspy_mod.Prediction):
                final_result = value
                # Send final events
                try:
                    event = StreamingOutputEvent(
                        correlation_id=str(ctx.correlation_id)
                        if ctx and ctx.correlation_id
                        else "",
                        agent_name=agent.name,
                        run_id=ctx.task_id if ctx else "",
                        output_type="log",
                        content=f"\nAmount of output tokens: {stream_sequence}",
                        sequence=stream_sequence,
                        is_final=True,
                        artifact_id=str(pre_generated_artifact_id),
                        artifact_type=artifact_type_name,
                    )
                    # Fire-and-forget to avoid blocking DSPy's streaming loop
                    task = asyncio.create_task(ws_broadcast(event))
                    ws_broadcast_tasks.add(task)
                    task.add_done_callback(ws_broadcast_tasks.discard)

                    event = StreamingOutputEvent(
                        correlation_id=str(ctx.correlation_id)
                        if ctx and ctx.correlation_id
                        else "",
                        agent_name=agent.name,
                        run_id=ctx.task_id if ctx else "",
                        output_type="log",
                        content="--- End of output ---",
                        sequence=stream_sequence + 1,
                        is_final=True,
                        artifact_id=str(pre_generated_artifact_id),
                        artifact_type=artifact_type_name,
                    )
                    # Fire-and-forget to avoid blocking DSPy's streaming loop
                    task = asyncio.create_task(ws_broadcast(event))
                    ws_broadcast_tasks.add(task)
                    task.add_done_callback(ws_broadcast_tasks.discard)
                except Exception as e:
                    logger.warning(f"Failed to emit final streaming event: {e}")

        if final_result is None:
            raise RuntimeError(
                f"Agent {agent.name}: Streaming did not yield a final prediction"
            )

        logger.info(
            f"Agent {agent.name}: WebSocket streaming completed ({stream_sequence} tokens)"
        )
        return final_result, None

    async def execute_streaming(
        self,
        dspy_mod,
        program,
        signature,
        *,
        description: str,
        payload: dict[str, Any],
        agent: Any,
        ctx: Any = None,
        pre_generated_artifact_id: Any = None,
        output_group=None,
    ) -> Any:
        """Execute DSPy program in streaming mode with Rich table updates.

        Args:
            dspy_mod: DSPy module
            program: DSPy program (Predict or ReAct)
            signature: DSPy Signature
            description: System description
            payload: Execution payload with semantic field names
            agent: Agent instance
            ctx: Execution context
            pre_generated_artifact_id: Pre-generated artifact ID for streaming
            output_group: OutputGroup defining expected outputs

        Returns:
            Tuple of (DSPy Prediction result, stream display data for final rendering)
        """
        from rich.console import Console
        from rich.live import Live

        console = Console()

        # Get WebSocket broadcast function (security: wrapper prevents object traversal)
        # Phase 6+7 Security Fix: Use broadcast wrapper from Agent class variable (prevents GOD MODE restoration)
        from flock.core import Agent

        ws_broadcast = Agent._websocket_broadcast_global

        # Prepare stream listeners for output field
        listeners = []
        try:
            streaming_mod = getattr(dspy_mod, "streaming", None)
            if streaming_mod and hasattr(streaming_mod, "StreamListener"):
                for name, field in signature.output_fields.items():
                    if field.annotation is str:
                        listeners.append(
                            streaming_mod.StreamListener(signature_field_name=name)
                        )
        except Exception:
            listeners = []

        streaming_task = dspy_mod.streamify(
            program,
            is_async_program=True,
            stream_listeners=listeners if listeners else None,
        )

        # Execute with appropriate payload format
        if isinstance(payload, dict) and "description" in payload:
            # Semantic fields: pass all fields as kwargs
            stream_generator = streaming_task(**payload)
        elif isinstance(payload, dict) and "input" in payload:
            # Legacy format: {"input": ..., "context": ...}
            stream_generator = streaming_task(
                description=description,
                input=payload["input"],
                context=payload.get("context", []),
            )
        else:
            # Old format: direct payload
            stream_generator = streaming_task(
                description=description, input=payload, context=[]
            )

        signature_order = []
        status_field = self.status_output_field
        try:
            signature_order = list(signature.output_fields.keys())
        except Exception:
            signature_order = []

        # Initialize display data in full artifact format (matching OutputUtilityComponent display)
        display_data: OrderedDict[str, Any] = OrderedDict()

        # Use the pre-generated artifact ID that was created before execution started
        display_data["id"] = str(pre_generated_artifact_id)

        # Get the artifact type name from agent configuration
        artifact_type_name = "output"
        # Use output_group.outputs (current group) if available, otherwise fallback to agent.outputs (all groups)
        outputs_to_display = (
            output_group.outputs
            if output_group and hasattr(output_group, "outputs")
            else agent.outputs
            if hasattr(agent, "outputs")
            else []
        )

        if outputs_to_display:
            artifact_type_name = outputs_to_display[0].spec.type_name
            for output in outputs_to_display:
                if output.spec.type_name not in artifact_type_name:
                    artifact_type_name += ", " + output.spec.type_name

        display_data["type"] = artifact_type_name
        display_data["payload"] = OrderedDict()

        # Add output fields to payload section
        for field_name in signature_order:
            if field_name != "description":  # Skip description field
                display_data["payload"][field_name] = ""

        display_data["produced_by"] = agent.name
        display_data["correlation_id"] = (
            str(ctx.correlation_id) if ctx and ctx.correlation_id else None
        )
        display_data["partition_key"] = None
        display_data["tags"] = "set()"
        display_data["visibility"] = OrderedDict([("kind", "Public")])
        display_data["created_at"] = "streaming..."
        display_data["version"] = 1
        display_data["status"] = status_field

        stream_buffers: defaultdict[str, list[str]] = defaultdict(list)
        stream_buffers[status_field] = []
        stream_sequence = 0  # Monotonic sequence for ordering

        # Track background WebSocket broadcast tasks to prevent garbage collection
        ws_broadcast_tasks: set[asyncio.Task] = set()

        formatter = theme_dict = styles = agent_label = None
        live_cm = nullcontext()
        overflow_mode = self.stream_vertical_overflow

        if not self.no_output:
            # Import the patch function here to ensure it's applied
            from flock.engines.dspy_engine import _ensure_live_crop_above

            _ensure_live_crop_above()
            (
                formatter,
                theme_dict,
                styles,
                agent_label,
            ) = self.prepare_stream_formatter(agent)
            initial_panel = formatter.format_result(
                display_data, agent_label, theme_dict, styles
            )
            live_cm = Live(
                initial_panel,
                console=console,
                refresh_per_second=4,
                transient=False,
                vertical_overflow=overflow_mode,
            )

        final_result: Any = None

        with live_cm as live:

            def _refresh_panel() -> None:
                if formatter is None or live is None:
                    return
                live.update(
                    formatter.format_result(
                        display_data, agent_label, theme_dict, styles
                    )
                )

            async for value in stream_generator:
                try:
                    from dspy.streaming import StatusMessage, StreamResponse
                    from litellm import ModelResponseStream
                except Exception:
                    StatusMessage = object  # type: ignore
                    StreamResponse = object  # type: ignore
                    ModelResponseStream = object  # type: ignore

                if isinstance(value, StatusMessage):
                    token = getattr(value, "message", "")
                    if token:
                        stream_buffers[status_field].append(str(token) + "\n")
                        display_data["status"] = "".join(stream_buffers[status_field])

                        # Emit to WebSocket (non-blocking to prevent deadlock)
                        if ws_broadcast and token:
                            try:
                                event = StreamingOutputEvent(
                                    correlation_id=str(ctx.correlation_id)
                                    if ctx and ctx.correlation_id
                                    else "",
                                    agent_name=agent.name,
                                    run_id=ctx.task_id if ctx else "",
                                    output_type="llm_token",
                                    content=str(token + "\n"),
                                    sequence=stream_sequence,
                                    is_final=False,
                                    artifact_id=str(
                                        pre_generated_artifact_id
                                    ),  # Phase 6: Track artifact for message streaming
                                    artifact_type=artifact_type_name,  # Phase 6: Artifact type name
                                )
                                # Use create_task to avoid blocking the streaming loop
                                task = asyncio.create_task(ws_broadcast(event))
                                ws_broadcast_tasks.add(task)
                                task.add_done_callback(ws_broadcast_tasks.discard)
                                stream_sequence += 1
                            except Exception as e:
                                logger.warning(f"Failed to emit streaming event: {e}")
                        else:
                            logger.debug(
                                "No WebSocket manager present for streaming event."
                            )

                        if formatter is not None:
                            _refresh_panel()
                    continue

                if isinstance(value, StreamResponse):
                    token = getattr(value, "chunk", None)
                    signature_field = getattr(value, "signature_field_name", None)
                    if signature_field and signature_field != "description":
                        # Update payload section - accumulate in "output" buffer
                        buffer_key = f"_stream_{signature_field}"
                        if token:
                            stream_buffers[buffer_key].append(str(token))
                            # Show streaming text in payload
                            display_data["payload"]["_streaming"] = "".join(
                                stream_buffers[buffer_key]
                            )

                            # Emit to WebSocket (non-blocking to prevent deadlock)
                            if ws_broadcast:
                                logger.info(
                                    f"[STREAMING] Emitting StreamResponse token='{token}', sequence={stream_sequence}"
                                )
                                try:
                                    event = StreamingOutputEvent(
                                        correlation_id=str(ctx.correlation_id)
                                        if ctx and ctx.correlation_id
                                        else "",
                                        agent_name=agent.name,
                                        run_id=ctx.task_id if ctx else "",
                                        output_type="llm_token",
                                        content=str(token),
                                        sequence=stream_sequence,
                                        is_final=False,
                                        artifact_id=str(
                                            pre_generated_artifact_id
                                        ),  # Phase 6: Track artifact for message streaming
                                        artifact_type=artifact_type_name,  # Phase 6: Artifact type name
                                    )
                                    # Use create_task to avoid blocking the streaming loop
                                    task = asyncio.create_task(ws_broadcast(event))
                                    ws_broadcast_tasks.add(task)
                                    task.add_done_callback(ws_broadcast_tasks.discard)
                                    stream_sequence += 1
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to emit streaming event: {e}"
                                    )

                        if formatter is not None:
                            _refresh_panel()
                    continue

                if isinstance(value, ModelResponseStream):
                    chunk = value
                    token = chunk.choices[0].delta.content or ""
                    signature_field = getattr(value, "signature_field_name", None)

                    if signature_field and signature_field != "description":
                        # Update payload section - accumulate in buffer
                        buffer_key = f"_stream_{signature_field}"
                        if token:
                            stream_buffers[buffer_key].append(str(token))
                            # Show streaming text in payload
                            display_data["payload"]["_streaming"] = "".join(
                                stream_buffers[buffer_key]
                            )
                    elif token:
                        stream_buffers[status_field].append(str(token))
                        display_data["status"] = "".join(stream_buffers[status_field])

                    # Emit to WebSocket (non-blocking to prevent deadlock)
                    if ws_broadcast and token:
                        try:
                            event = StreamingOutputEvent(
                                correlation_id=str(ctx.correlation_id)
                                if ctx and ctx.correlation_id
                                else "",
                                agent_name=agent.name,
                                run_id=ctx.task_id if ctx else "",
                                output_type="llm_token",
                                content=str(token),
                                sequence=stream_sequence,
                                is_final=False,
                                artifact_id=str(
                                    pre_generated_artifact_id
                                ),  # Phase 6: Track artifact for message streaming
                                artifact_type=display_data[
                                    "type"
                                ],  # Phase 6: Artifact type name from display_data
                            )
                            # Use create_task to avoid blocking the streaming loop
                            task = asyncio.create_task(ws_broadcast(event))
                            ws_broadcast_tasks.add(task)
                            task.add_done_callback(ws_broadcast_tasks.discard)
                            stream_sequence += 1
                        except Exception as e:
                            logger.warning(f"Failed to emit streaming event: {e}")

                    if formatter is not None:
                        _refresh_panel()
                    continue

                if isinstance(value, dspy_mod.Prediction):
                    final_result = value

                    # Emit final streaming event (non-blocking to prevent deadlock)
                    if ws_broadcast:
                        try:
                            event = StreamingOutputEvent(
                                correlation_id=str(ctx.correlation_id)
                                if ctx and ctx.correlation_id
                                else "",
                                agent_name=agent.name,
                                run_id=ctx.task_id if ctx else "",
                                output_type="log",
                                content="\nAmount of output tokens: "
                                + str(stream_sequence),
                                sequence=stream_sequence,
                                is_final=True,  # Mark as final
                                artifact_id=str(
                                    pre_generated_artifact_id
                                ),  # Phase 6: Track artifact for message streaming
                                artifact_type=display_data[
                                    "type"
                                ],  # Phase 6: Artifact type name
                            )
                            # Use create_task to avoid blocking the streaming loop
                            task = asyncio.create_task(ws_broadcast(event))
                            ws_broadcast_tasks.add(task)
                            task.add_done_callback(ws_broadcast_tasks.discard)
                            event = StreamingOutputEvent(
                                correlation_id=str(ctx.correlation_id)
                                if ctx and ctx.correlation_id
                                else "",
                                agent_name=agent.name,
                                run_id=ctx.task_id if ctx else "",
                                output_type="log",
                                content="--- End of output ---",
                                sequence=stream_sequence,
                                is_final=True,  # Mark as final
                                artifact_id=str(
                                    pre_generated_artifact_id
                                ),  # Phase 6: Track artifact for message streaming
                                artifact_type=display_data[
                                    "type"
                                ],  # Phase 6: Artifact type name
                            )
                            # Use create_task to avoid blocking the streaming loop
                            task = asyncio.create_task(ws_broadcast(event))
                            ws_broadcast_tasks.add(task)
                            task.add_done_callback(ws_broadcast_tasks.discard)
                        except Exception as e:
                            logger.warning(f"Failed to emit final streaming event: {e}")

                    if formatter is not None:
                        # Update payload section with final values
                        payload_data = OrderedDict()
                        for field_name in signature_order:
                            if field_name != "description" and hasattr(
                                final_result, field_name
                            ):
                                field_value = getattr(final_result, field_name)

                                # Convert BaseModel instances to dicts for proper table rendering
                                if isinstance(field_value, list):
                                    # Handle lists of BaseModel instances (fan-out/batch)
                                    payload_data[field_name] = [
                                        item.model_dump()
                                        if isinstance(item, BaseModel)
                                        else item
                                        for item in field_value
                                    ]
                                elif isinstance(field_value, BaseModel):
                                    # Handle single BaseModel instance
                                    payload_data[field_name] = field_value.model_dump()
                                else:
                                    # Handle primitive types
                                    payload_data[field_name] = field_value

                        # Update all fields with actual values
                        display_data["payload"].clear()
                        display_data["payload"].update(payload_data)

                        # Update timestamp
                        from datetime import datetime

                        display_data["created_at"] = datetime.now(UTC).isoformat()

                        # Remove status field from display
                        display_data.pop("status", None)
                        _refresh_panel()

        if final_result is None:
            raise RuntimeError("Streaming did not yield a final prediction.")

        # Return both the result and the display data for final ID update
        return final_result, (formatter, display_data, theme_dict, styles, agent_label)

    def prepare_stream_formatter(
        self, agent: Any
    ) -> tuple[Any, dict[str, Any], dict[str, Any], str]:
        """Build formatter + theme metadata for streaming tables.

        Args:
            agent: Agent instance

        Returns:
            Tuple of (formatter, theme_dict, styles, agent_label)
        """
        import pathlib

        # Import model from local context since we're in a separate module
        from flock.engines.dspy_engine import DSPyEngine
        from flock.logging.formatters.themed_formatter import (
            ThemedAgentResultFormatter,
            create_pygments_syntax_theme,
            get_default_styles,
            load_syntax_theme_from_file,
            load_theme_from_file,
        )

        # Get themes directory relative to engine module
        themes_dir = (
            pathlib.Path(DSPyEngine.__module__.replace(".", "/")).parent.parent
            / "themes"
        )
        # Fallback: use __file__ if module path doesn't work
        if not themes_dir.exists():
            import flock.engines.dspy_engine as engine_mod

            themes_dir = (
                pathlib.Path(engine_mod.__file__).resolve().parents[1] / "themes"
            )

        theme_filename = self.theme
        if not theme_filename.endswith(".toml"):
            theme_filename = f"{theme_filename}.toml"
        theme_path = themes_dir / theme_filename

        try:
            theme_dict = load_theme_from_file(theme_path)
        except Exception:
            fallback_path = themes_dir / "afterglow.toml"
            theme_dict = load_theme_from_file(fallback_path)
            theme_path = fallback_path

        from flock.logging.formatters.themes import OutputTheme

        formatter = ThemedAgentResultFormatter(theme=OutputTheme.afterglow)
        styles = get_default_styles(theme_dict)
        formatter.styles = styles

        try:
            syntax_theme = load_syntax_theme_from_file(theme_path)
            formatter.syntax_style = create_pygments_syntax_theme(syntax_theme)
        except Exception:
            formatter.syntax_style = None

        # Get model label from agent if available
        model_label = getattr(agent, "engine", None)
        if model_label and hasattr(model_label, "model"):
            model_label = model_label.model or ""
        else:
            model_label = ""

        agent_label = agent.name if not model_label else f"{agent.name} - {model_label}"

        return formatter, theme_dict, styles, agent_label

    def print_final_stream_display(
        self,
        stream_display_data: tuple[Any, OrderedDict, dict, dict, str],
        artifact_id: str,
        artifact,
    ) -> None:
        """Print the final streaming display with the real artifact ID.

        Args:
            stream_display_data: Tuple of (formatter, display_data, theme_dict, styles, agent_label)
            artifact_id: Final artifact ID
            artifact: Artifact instance with metadata
        """
        from rich.console import Console

        formatter, display_data, theme_dict, styles, agent_label = stream_display_data

        # Update display_data with the real artifact information
        display_data["id"] = artifact_id
        display_data["created_at"] = artifact.created_at.isoformat()

        # Update all artifact metadata
        display_data["correlation_id"] = (
            str(artifact.correlation_id) if artifact.correlation_id else None
        )
        display_data["partition_key"] = artifact.partition_key
        display_data["tags"] = (
            "set()" if not artifact.tags else f"set({list(artifact.tags)})"
        )

        # Print the final panel
        console = Console()
        final_panel = formatter.format_result(
            display_data, agent_label, theme_dict, styles
        )
        console.print(final_panel)


__all__ = ["DSPyStreamingExecutor"]
