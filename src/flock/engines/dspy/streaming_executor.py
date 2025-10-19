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
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Sequence

from pydantic import BaseModel

from flock.dashboard.events import StreamingOutputEvent
from flock.engines.streaming.sinks import RichSink, StreamSink, WebSocketSink
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
        self._model_stream_cls: Any | None = None

    def _make_listeners(self, dspy_mod, signature) -> list[Any]:
        """Create DSPy stream listeners for string output fields."""
        streaming_mod = getattr(dspy_mod, "streaming", None)
        if not streaming_mod or not hasattr(streaming_mod, "StreamListener"):
            return []

        listeners: list[Any] = []
        try:
            for name, field in getattr(signature, "output_fields", {}).items():
                if getattr(field, "annotation", None) is str:
                    listeners.append(
                        streaming_mod.StreamListener(signature_field_name=name)
                    )
        except Exception:
            return []
        return listeners

    def _payload_kwargs(self, *, payload: Any, description: str) -> dict[str, Any]:
        """Normalize payload variations into kwargs for streamify."""
        if isinstance(payload, dict) and "description" in payload:
            return payload

        if isinstance(payload, dict) and "input" in payload:
            return {
                "description": description,
                "input": payload["input"],
                "context": payload.get("context", []),
            }

        # Legacy fallback: treat payload as the primary input.
        return {"description": description, "input": payload, "context": []}

    def _artifact_type_label(self, agent: Any, output_group: Any) -> str:
        """Derive user-facing artifact label for streaming events."""
        outputs_to_display = (
            getattr(output_group, "outputs", None)
            if output_group and hasattr(output_group, "outputs")
            else getattr(agent, "outputs", [])
            if hasattr(agent, "outputs")
            else []
        )

        if not outputs_to_display:
            return "output"

        # Preserve ordering while avoiding duplicates.
        seen: set[str] = set()
        segments: list[str] = []
        for output in outputs_to_display:
            type_name = getattr(getattr(output, "spec", None), "type_name", None)
            if type_name and type_name not in seen:
                seen.add(type_name)
                segments.append(type_name)

        return ", ".join(segments) if segments else "output"

    def _streaming_classes_for(self, dspy_mod: Any) -> tuple[type | None, type | None]:
        streaming_mod = getattr(dspy_mod, "streaming", None)
        if not streaming_mod:
            return None, None
        status_cls = getattr(streaming_mod, "StatusMessage", None)
        stream_cls = getattr(streaming_mod, "StreamResponse", None)
        return status_cls, stream_cls

    def _resolve_model_stream_cls(self) -> Any | None:
        if self._model_stream_cls is None:
            try:
                from litellm import ModelResponseStream  # type: ignore
            except Exception:  # pragma: no cover - litellm optional at runtime
                self._model_stream_cls = False
            else:
                self._model_stream_cls = ModelResponseStream
        return self._model_stream_cls or None

    @staticmethod
    def _normalize_status_message(
        value: Any,
    ) -> tuple[str, str | None, str | None, Any | None]:
        message = getattr(value, "message", "")
        return "status", str(message), None, None

    @staticmethod
    def _normalize_stream_response(
        value: Any,
    ) -> tuple[str, str | None, str | None, Any | None]:
        chunk = getattr(value, "chunk", None)
        signature_field = getattr(value, "signature_field_name", None)
        return "token", ("" if chunk is None else str(chunk)), signature_field, None

    @staticmethod
    def _normalize_model_stream(
        value: Any,
    ) -> tuple[str, str | None, str | None, Any | None]:
        token_text = ""
        try:
            token_text = value.choices[0].delta.content or ""
        except Exception:  # pragma: no cover - defensive parity with legacy path
            token_text = ""
        signature_field = getattr(value, "signature_field_name", None)
        return "token", str(token_text), signature_field, None

    def _initialize_display_data(
        self,
        *,
        signature_order: Sequence[str],
        agent: Any,
        ctx: Any,
        pre_generated_artifact_id: Any,
        output_group: Any,
        status_field: str,
    ) -> tuple[OrderedDict[str, Any], str]:
        """Build the initial Rich display structure for CLI streaming."""
        display_data: OrderedDict[str, Any] = OrderedDict()
        display_data["id"] = str(pre_generated_artifact_id)

        artifact_type_name = self._artifact_type_label(agent, output_group)
        display_data["type"] = artifact_type_name

        payload_section: OrderedDict[str, Any] = OrderedDict()
        for field_name in signature_order:
            if field_name != "description":
                payload_section[field_name] = ""
        display_data["payload"] = payload_section

        display_data["produced_by"] = getattr(agent, "name", "")
        correlation_id = None
        if ctx and getattr(ctx, "correlation_id", None):
            correlation_id = str(ctx.correlation_id)
        display_data["correlation_id"] = correlation_id
        display_data["partition_key"] = None
        display_data["tags"] = "set()"
        display_data["visibility"] = OrderedDict([("kind", "Public")])
        display_data["created_at"] = "streaming..."
        display_data["version"] = 1
        display_data["status"] = status_field

        return display_data, artifact_type_name

    def _prepare_rich_env(
        self,
        *,
        console,
        display_data: OrderedDict[str, Any],
        agent: Any,
        overflow_mode: str,
    ) -> tuple[Any, dict[str, Any], dict[str, Any], str, Any]:
        """Create formatter metadata and Live context for Rich output."""
        from rich.live import Live

        from flock.engines.dspy_engine import _ensure_live_crop_above

        _ensure_live_crop_above()
        formatter, theme_dict, styles, agent_label = self.prepare_stream_formatter(
            agent
        )
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
        return formatter, theme_dict, styles, agent_label, live_cm

    def _build_rich_sink(
        self,
        *,
        live: Any,
        formatter: Any | None,
        display_data: OrderedDict[str, Any],
        agent_label: str | None,
        theme_dict: dict[str, Any] | None,
        styles: dict[str, Any] | None,
        status_field: str,
        signature_order: Sequence[str],
        stream_buffers: defaultdict[str, list[str]],
        timestamp_factory: Callable[[], str],
    ) -> RichSink | None:
        if formatter is None or live is None:
            return None

        def refresh_panel() -> None:
            live.update(
                formatter.format_result(display_data, agent_label, theme_dict, styles)
            )

        return RichSink(
            display_data=display_data,
            stream_buffers=stream_buffers,
            status_field=status_field,
            signature_order=signature_order,
            formatter=formatter,
            theme_dict=theme_dict,
            styles=styles,
            agent_label=agent_label,
            refresh_panel=refresh_panel,
            timestamp_factory=timestamp_factory,
        )

    def _build_websocket_sink(
        self,
        *,
        ws_broadcast: Callable[[StreamingOutputEvent], Awaitable[None]] | None,
        ctx: Any,
        agent: Any,
        pre_generated_artifact_id: Any,
        artifact_type_name: str,
    ) -> WebSocketSink | None:
        if not ws_broadcast:
            return None

        def event_factory(
            output_type: str, content: str, sequence: int, is_final: bool
        ) -> StreamingOutputEvent:
            return self._build_event(
                ctx=ctx,
                agent=agent,
                artifact_id=pre_generated_artifact_id,
                artifact_type=artifact_type_name,
                output_type=output_type,
                content=content,
                sequence=sequence,
                is_final=is_final,
            )

        return WebSocketSink(ws_broadcast=ws_broadcast, event_factory=event_factory)

    def _collect_sinks(
        self,
        *,
        rich_sink: RichSink | None,
        ws_sink: WebSocketSink | None,
    ) -> list[StreamSink]:
        sinks: list[StreamSink] = []
        if rich_sink:
            sinks.append(rich_sink)
        if ws_sink:
            sinks.append(ws_sink)
        return sinks

    async def _dispatch_to_sinks(
        self, sinks: Sequence[StreamSink], method: str, *args: Any
    ) -> None:
        for sink in sinks:
            await getattr(sink, method)(*args)

    async def _consume_stream(
        self,
        stream_generator: Any,
        sinks: Sequence[StreamSink],
        dspy_mod: Any,
    ) -> tuple[Any | None, int]:
        tokens_emitted = 0
        final_result: Any | None = None

        async for value in stream_generator:
            kind, text, signature_field, prediction = self._normalize_value(
                value, dspy_mod
            )

            if kind == "status" and text:
                await self._dispatch_to_sinks(sinks, "on_status", text)
                continue

            if kind == "token" and text:
                tokens_emitted += 1
                await self._dispatch_to_sinks(sinks, "on_token", text, signature_field)
                continue

            if kind == "prediction":
                final_result = prediction
                await self._dispatch_to_sinks(
                    sinks, "on_final", prediction, tokens_emitted
                )
                await self._close_stream_generator(stream_generator)
                return final_result, tokens_emitted

        return final_result, tokens_emitted

    async def _flush_sinks(self, sinks: Sequence[StreamSink]) -> None:
        for sink in sinks:
            await sink.flush()

    def _finalize_stream_display(
        self,
        *,
        rich_sink: RichSink | None,
        formatter: Any | None,
        display_data: OrderedDict[str, Any],
        theme_dict: dict[str, Any] | None,
        styles: dict[str, Any] | None,
        agent_label: str | None,
    ) -> tuple[Any, OrderedDict, dict | None, dict | None, str | None]:
        if rich_sink:
            return rich_sink.final_display_data
        return formatter, display_data, theme_dict, styles, agent_label

    @staticmethod
    async def _close_stream_generator(stream_generator: Any) -> None:
        aclose = getattr(stream_generator, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except GeneratorExit:
                pass
            except BaseExceptionGroup as exc:  # pragma: no cover - defensive logging
                remaining = [
                    err
                    for err in getattr(exc, "exceptions", [])
                    if not isinstance(err, GeneratorExit)
                ]
                if remaining:
                    logger.debug("Error closing stream generator", exc_info=True)
            except Exception:
                logger.debug("Error closing stream generator", exc_info=True)

    def _build_event(
        self,
        *,
        ctx: Any,
        agent: Any,
        artifact_id: Any,
        artifact_type: str,
        output_type: str,
        content: str,
        sequence: int,
        is_final: bool,
    ) -> StreamingOutputEvent:
        """Construct a StreamingOutputEvent with consistent metadata."""
        correlation_id = ""
        run_id = ""
        if ctx:
            correlation_id = str(getattr(ctx, "correlation_id", "") or "")
            run_id = str(getattr(ctx, "task_id", "") or "")

        return StreamingOutputEvent(
            correlation_id=correlation_id,
            agent_name=getattr(agent, "name", ""),
            run_id=run_id,
            output_type=output_type,
            content=content,
            sequence=sequence,
            is_final=is_final,
            artifact_id=str(artifact_id) if artifact_id is not None else "",
            artifact_type=artifact_type,
        )

    def _normalize_value(
        self, value: Any, dspy_mod: Any
    ) -> tuple[str, str | None, str | None, Any | None]:
        """Normalize raw DSPy streaming values into (kind, text, field, final)."""
        status_cls, stream_cls = self._streaming_classes_for(dspy_mod)
        model_stream_cls = self._resolve_model_stream_cls()
        prediction_cls = getattr(dspy_mod, "Prediction", None)

        if status_cls and isinstance(value, status_cls):
            return self._normalize_status_message(value)

        if stream_cls and isinstance(value, stream_cls):
            return self._normalize_stream_response(value)

        if model_stream_cls and isinstance(value, model_stream_cls):
            return self._normalize_model_stream(value)

        if prediction_cls and isinstance(value, prediction_cls):
            return "prediction", None, None, value

        return "unknown", None, None, None

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

        artifact_type_name = self._artifact_type_label(agent, output_group)
        listeners = self._make_listeners(dspy_mod, signature)

        # Create streaming task
        streaming_task = dspy_mod.streamify(
            program,
            is_async_program=True,
            stream_listeners=listeners if listeners else None,
        )

        stream_kwargs = self._payload_kwargs(payload=payload, description=description)
        stream_generator = streaming_task(**stream_kwargs)

        def event_factory(
            output_type: str, content: str, sequence: int, is_final: bool
        ) -> StreamingOutputEvent:
            return self._build_event(
                ctx=ctx,
                agent=agent,
                artifact_id=pre_generated_artifact_id,
                artifact_type=artifact_type_name,
                output_type=output_type,
                content=content,
                sequence=sequence,
                is_final=is_final,
            )

        sink: StreamSink = WebSocketSink(
            ws_broadcast=ws_broadcast,
            event_factory=event_factory,
        )

        final_result = None
        tokens_emitted = 0

        async for value in stream_generator:
            kind, text, signature_field, prediction = self._normalize_value(
                value, dspy_mod
            )

            if kind == "status" and text:
                await sink.on_status(text)
                continue

            if kind == "token" and text:
                tokens_emitted += 1
                await sink.on_token(text, signature_field)
                continue

            if kind == "prediction":
                final_result = prediction
                await sink.on_final(prediction, tokens_emitted)
                await self._close_stream_generator(stream_generator)
                break

        await sink.flush()

        if final_result is None:
            raise RuntimeError(
                f"Agent {agent.name}: Streaming did not yield a final prediction"
            )

        logger.info(
            f"Agent {agent.name}: WebSocket streaming completed ({tokens_emitted} tokens)"
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
        """Execute DSPy program in streaming mode with Rich table updates."""

        from rich.console import Console

        console = Console()

        # Get WebSocket broadcast function (security: wrapper prevents object traversal)
        from flock.core import Agent

        ws_broadcast = Agent._websocket_broadcast_global

        listeners = self._make_listeners(dspy_mod, signature)
        streaming_task = dspy_mod.streamify(
            program,
            is_async_program=True,
            stream_listeners=listeners if listeners else None,
        )

        stream_kwargs = self._payload_kwargs(payload=payload, description=description)
        stream_generator = streaming_task(**stream_kwargs)

        status_field = self.status_output_field
        try:
            signature_order = list(signature.output_fields.keys())
        except Exception:
            signature_order = []

        display_data, artifact_type_name = self._initialize_display_data(
            signature_order=signature_order,
            agent=agent,
            ctx=ctx,
            pre_generated_artifact_id=pre_generated_artifact_id,
            output_group=output_group,
            status_field=status_field,
        )

        stream_buffers: defaultdict[str, list[str]] = defaultdict(list)
        overflow_mode = self.stream_vertical_overflow

        if not self.no_output:
            (
                formatter,
                theme_dict,
                styles,
                agent_label,
                live_cm,
            ) = self._prepare_rich_env(
                console=console,
                display_data=display_data,
                agent=agent,
                overflow_mode=overflow_mode,
            )
        else:
            formatter = theme_dict = styles = agent_label = None
            live_cm = nullcontext()

        timestamp_factory = lambda: datetime.now(UTC).isoformat()

        final_result: Any = None
        tokens_emitted = 0
        sinks: list[StreamSink] = []
        rich_sink: RichSink | None = None

        with live_cm as live:
            rich_sink = self._build_rich_sink(
                live=live,
                formatter=formatter,
                display_data=display_data,
                agent_label=agent_label,
                theme_dict=theme_dict,
                styles=styles,
                status_field=status_field,
                signature_order=signature_order,
                stream_buffers=stream_buffers,
                timestamp_factory=timestamp_factory,
            )

            ws_sink = self._build_websocket_sink(
                ws_broadcast=ws_broadcast,
                ctx=ctx,
                agent=agent,
                pre_generated_artifact_id=pre_generated_artifact_id,
                artifact_type_name=artifact_type_name,
            )

            sinks = self._collect_sinks(rich_sink=rich_sink, ws_sink=ws_sink)
            final_result, tokens_emitted = await self._consume_stream(
                stream_generator, sinks, dspy_mod
            )

        await self._flush_sinks(sinks)

        if final_result is None:
            raise RuntimeError("Streaming did not yield a final prediction.")

        stream_display = self._finalize_stream_display(
            rich_sink=rich_sink,
            formatter=formatter,
            display_data=display_data,
            theme_dict=theme_dict,
            styles=styles,
            agent_label=agent_label,
        )

        logger.info(
            f"Agent {agent.name}: Rich streaming completed ({tokens_emitted} tokens)"
        )

        return final_result, stream_display

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
