"""DSPy-powered engine component that mirrors the design implementation."""

from __future__ import annotations

import asyncio
import json
import os
from collections import OrderedDict, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from contextlib import nullcontext
from typing import Any, Literal

from pydantic import BaseModel, Field

from flock.artifacts import Artifact
from flock.components import EngineComponent
from flock.dashboard.events import StreamingOutputEvent
from flock.logging.logging import get_logger
from flock.registry import type_registry
from flock.runtime import EvalInputs, EvalResult


logger = get_logger(__name__)


_live_patch_applied = False


# T071: Auto-detect test environment for streaming
def _default_stream_value() -> bool:
    """Return default stream value based on environment.

    Returns False in pytest (clean test output), True otherwise (rich streaming).
    """
    import sys

    return "pytest" not in sys.modules


# Apply the Rich Live patch immediately on module import
def _apply_live_patch_on_import() -> None:
    """Apply Rich Live crop_above patch when module is imported."""
    try:
        _ensure_live_crop_above()
    except Exception:
        pass  # Silently ignore if Rich is not available


def _ensure_live_crop_above() -> None:
    """Monkeypatch rich.live_render to support 'crop_above' overflow."""
    global _live_patch_applied
    if _live_patch_applied:
        return
    try:
        from typing import Literal as _Literal

        from rich import live_render as _lr
    except Exception:
        return

    # Extend the accepted literal at runtime so type checks don't block the new option.
    current_args = getattr(_lr.VerticalOverflowMethod, "__args__", ())
    if "crop_above" not in current_args:
        _lr.VerticalOverflowMethod = _Literal["crop", "crop_above", "ellipsis", "visible"]  # type: ignore[assignment]

    if getattr(_lr.LiveRender.__rich_console__, "_flock_crop_above", False):
        _live_patch_applied = True
        return

    Segment = _lr.Segment
    Text = _lr.Text
    loop_last = _lr.loop_last

    def _patched_rich_console(self, console, options):
        renderable = self.renderable
        style = console.get_style(self.style)
        lines = console.render_lines(renderable, options, style=style, pad=False)
        shape = Segment.get_shape(lines)

        _, height = shape
        max_height = options.size.height
        if height > max_height:
            if self.vertical_overflow == "crop":
                lines = lines[:max_height]
                shape = Segment.get_shape(lines)
            elif self.vertical_overflow == "crop_above":
                lines = lines[-max_height:]
                shape = Segment.get_shape(lines)
            elif self.vertical_overflow == "ellipsis" and max_height > 0:
                lines = lines[: (max_height - 1)]
                overflow_text = Text(
                    "...",
                    overflow="crop",
                    justify="center",
                    end="",
                    style="live.ellipsis",
                )
                lines.append(list(console.render(overflow_text)))
                shape = Segment.get_shape(lines)
        self._shape = shape

        new_line = Segment.line()
        for last, line in loop_last(lines):
            yield from line
            if not last:
                yield new_line

    _patched_rich_console._flock_crop_above = True  # type: ignore[attr-defined]
    _lr.LiveRender.__rich_console__ = _patched_rich_console
    _live_patch_applied = True


class DSPyEngine(EngineComponent):
    """Execute a minimal DSPy program backed by a hosted LLM.

    Behavior intentionally mirrors ``design/dspy_engine.py`` so that orchestration
    relies on the same model resolution, signature preparation, and result
    normalization logic.
    """

    name: str | None = "dspy"
    model: str | None = None
    instructions: str | None = None
    temperature: float = 1.0
    max_tokens: int = 32000
    max_tool_calls: int = 10
    max_retries: int = 0
    stream: bool = Field(
        default_factory=lambda: _default_stream_value(),
        description="Enable streaming output from the underlying DSPy program. Auto-disables in pytest.",
    )
    no_output: bool = Field(
        default=False,
        description="Disable output from the underlying DSPy program.",
    )
    stream_vertical_overflow: Literal["crop", "ellipsis", "crop_above", "visible"] = Field(
        default="crop_above",
        description=(
            "Rich Live vertical overflow strategy; select how tall output is handled; 'crop_above' keeps the most recent rows visible."
        ),
    )
    status_output_field: str = Field(
        default="_status_output",
        description="The field name for the status output.",
    )
    theme: str = Field(
        default="afterglow",
        description="Theme name for Rich output formatting.",
    )
    enable_cache: bool = Field(
        default=False,
        description="Enable caching of DSPy program results",
    )

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:  # type: ignore[override]
        if not inputs.artifacts:
            return EvalResult(artifacts=[], state=dict(inputs.state))

        model_name = self._resolve_model_name()
        dspy_mod = self._import_dspy()

        lm = dspy_mod.LM(
            model=model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            cache=self.enable_cache,
            num_retries=self.max_retries,
        )

        primary_artifact = self._select_primary_artifact(inputs.artifacts)
        input_model = self._resolve_input_model(primary_artifact)
        validated_input = self._validate_input_payload(input_model, primary_artifact.payload)
        output_model = self._resolve_output_model(agent)

        # Fetch conversation context from blackboard
        context_history = await self.fetch_conversation_context(ctx)
        has_context = bool(context_history) and self.should_use_context(inputs)

        # Prepare signature with optional context field
        signature = self._prepare_signature_with_context(
            dspy_mod,
            description=self.instructions or agent.description,
            input_schema=input_model,
            output_schema=output_model,
            has_context=has_context,
        )

        sys_desc = self._system_description(self.instructions or agent.description)

        # Pre-generate the artifact ID so it's available from the start
        from uuid import uuid4

        pre_generated_artifact_id = uuid4()

        # Build execution payload with context
        if has_context:
            execution_payload = {
                "input": validated_input,
                "context": context_history,
            }
        else:
            # Backwards compatible - direct input
            execution_payload = validated_input

        # Merge native tools with MCP tools
        native_tools = list(agent.tools or [])

        # Lazy-load MCP tools for this agent
        try:
            mcp_tools = await agent._get_mcp_tools(ctx)
            logger.debug(f"Loaded {len(mcp_tools)} MCP tools for agent {agent.name}")
        except Exception as e:
            # Architecture Decision: AD007 - Graceful Degradation
            # If MCP loading fails, continue with native tools only
            logger.error(f"Failed to load MCP tools in engine: {e}", exc_info=True)
            mcp_tools = []

        # Combine both lists
        # Architecture Decision: AD003 - MCP tools are namespaced, so no conflicts
        combined_tools = native_tools + mcp_tools
        logger.debug(
            f"Total tools for agent {agent.name}: {len(combined_tools)} (native: {len(native_tools)}, mcp: {len(mcp_tools)})"
        )

        with dspy_mod.context(lm=lm):
            program = self._choose_program(dspy_mod, signature, combined_tools)

            # Detect if there's already an active Rich Live context
            should_stream = self.stream
            orchestrator = getattr(ctx, "orchestrator", None)
            if orchestrator:
                is_dashboard = getattr(orchestrator, "is_dashboard", False) if ctx else False
                # if dashboard we always stream, streamin queue only for CLI output
                if should_stream and ctx and not is_dashboard:
                    if not hasattr(orchestrator, "_active_streams"):
                        orchestrator._active_streams = 0

                    if orchestrator._active_streams > 0:
                        should_stream = False
                    else:
                        orchestrator._active_streams += 1

            try:
                if should_stream:
                    # Choose streaming method based on dashboard mode
                    is_dashboard = orchestrator and getattr(orchestrator, "is_dashboard", False)

                    # DEBUG: Log routing decision
                    logger.info(
                        f"[STREAMING ROUTER] agent={agent.name}, is_dashboard={is_dashboard}, orchestrator={orchestrator is not None}"
                    )

                    if is_dashboard:
                        # Dashboard mode: WebSocket-only streaming (no Rich overhead)
                        # This eliminates the Rich Live context that causes deadlocks with MCP tools
                        logger.info(
                            f"[STREAMING ROUTER] Routing {agent.name} to WebSocket-only method (dashboard mode)"
                        )
                        (
                            raw_result,
                            _stream_final_display_data,
                        ) = await self._execute_streaming_websocket_only(
                            dspy_mod,
                            program,
                            signature,
                            description=sys_desc,
                            payload=execution_payload,
                            agent=agent,
                            ctx=ctx,
                            pre_generated_artifact_id=pre_generated_artifact_id,
                        )
                    else:
                        # CLI mode: Rich streaming with terminal display
                        logger.info(
                            f"[STREAMING ROUTER] Routing {agent.name} to Rich streaming method (CLI mode)"
                        )
                        (
                            raw_result,
                            _stream_final_display_data,
                        ) = await self._execute_streaming(
                            dspy_mod,
                            program,
                            signature,
                            description=sys_desc,
                            payload=execution_payload,
                            agent=agent,
                            ctx=ctx,
                            pre_generated_artifact_id=pre_generated_artifact_id,
                        )
                    if not self.no_output and ctx:
                        ctx.state["_flock_stream_live_active"] = True
                else:
                    orchestrator = getattr(ctx, "orchestrator", None) if ctx else None

                    raw_result = await self._execute_standard(
                        dspy_mod,
                        program,
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

        normalized_output = self._normalize_output_payload(getattr(raw_result, "output", None))
        artifacts, errors = self._materialize_artifacts(
            normalized_output,
            agent.outputs,
            agent.name,
            pre_generated_id=pre_generated_artifact_id,
        )

        state = dict(inputs.state)
        state.setdefault("dspy", {})
        state["dspy"].update({"model": model_name, "raw": normalized_output})

        logs: list[str] = []
        if normalized_output is not None:
            try:
                logs.append(f"dspy.output={json.dumps(normalized_output)}")
            except TypeError:
                logs.append(f"dspy.output={normalized_output!r}")
        logs.extend(f"dspy.error={message}" for message in errors)

        result_artifacts = artifacts if artifacts else list(inputs.artifacts)
        return EvalResult(artifacts=result_artifacts, state=state, logs=logs)

    # ------------------------------------------------------------------
    # Helpers mirroring the design engine

    def _resolve_model_name(self) -> str:
        model = self.model or os.getenv("TRELLIS_MODEL") or os.getenv("OPENAI_MODEL")
        if not model:
            raise NotImplementedError(
                "DSPyEngine requires a configured model (set TRELLIS_MODEL, OPENAI_MODEL, or pass model=...)."
            )
        return model

    def _import_dspy(self):  # pragma: no cover - import guarded by optional dependency
        try:
            import dspy
        except Exception as exc:
            raise NotImplementedError("DSPy is not installed or failed to import.") from exc
        return dspy

    def _select_primary_artifact(self, artifacts: Sequence[Artifact]) -> Artifact:
        return artifacts[-1]

    def _resolve_input_model(self, artifact: Artifact) -> type[BaseModel] | None:
        try:
            return type_registry.resolve(artifact.type)
        except KeyError:
            return None

    def _resolve_output_model(self, agent) -> type[BaseModel] | None:
        if not getattr(agent, "outputs", None):
            return None
        return agent.outputs[0].spec.model

    def _validate_input_payload(
        self,
        schema: type[BaseModel] | None,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        data = dict(payload or {})
        if schema is None:
            return data
        try:
            return schema(**data).model_dump()
        except Exception:
            return data

    def _prepare_signature_with_context(
        self,
        dspy_mod,
        *,
        description: str | None,
        input_schema: type[BaseModel] | None,
        output_schema: type[BaseModel] | None,
        has_context: bool = False,
    ) -> Any:
        """Prepare DSPy signature, optionally including context field."""
        fields = {
            "description": (str, dspy_mod.InputField()),
        }

        # Add context field if we have conversation history
        if has_context:
            fields["context"] = (
                list,
                dspy_mod.InputField(
                    desc="Previous conversation artifacts providing context for this request"
                ),
            )

        fields["input"] = (input_schema or dict, dspy_mod.InputField())
        fields["output"] = (output_schema or dict, dspy_mod.OutputField())

        signature = dspy_mod.Signature(fields)

        instruction = description or "Produce a valid output that matches the 'output' schema."
        if has_context:
            instruction += " Consider the conversation context provided to inform your response."
        instruction += " Return only JSON."

        return signature.with_instructions(instruction)

    def _choose_program(self, dspy_mod, signature, tools: Iterable[Any]):
        tools_list = list(tools or [])
        try:
            if tools_list:
                return dspy_mod.ReAct(signature, tools=tools_list, max_iters=self.max_tool_calls)
            return dspy_mod.Predict(signature)
        except Exception:
            return dspy_mod.Predict(signature)

    def _system_description(self, description: str | None) -> str:
        if description:
            return description
        return "Produce a valid output that matches the 'output' schema. Return only JSON."

    def _normalize_output_payload(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, BaseModel):
            return raw.model_dump()
        if isinstance(raw, str):
            text = raw.strip()
            candidates: list[str] = []

            # Primary attempt - full string
            if text:
                candidates.append(text)

            # Handle DSPy streaming markers like `[[ ## output ## ]]`
            if text.startswith("[[") and "]]" in text:
                _, remainder = text.split("]]", 1)
                remainder = remainder.strip()
                if remainder:
                    candidates.append(remainder)

            # Handle Markdown-style fenced blocks
            if text.startswith("```") and text.endswith("```"):
                fenced = text.strip("`").strip()
                if fenced:
                    candidates.append(fenced)

            # Extract first JSON-looking segment if present
            for opener, closer in (("{", "}"), ("[", "]")):
                start = text.find(opener)
                end = text.rfind(closer)
                if start != -1 and end != -1 and end > start:
                    segment = text[start : end + 1].strip()
                    if segment:
                        candidates.append(segment)

            seen: set[str] = set()
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

            return {"text": text}
        if isinstance(raw, Mapping):
            return dict(raw)
        return {"value": raw}

    def _materialize_artifacts(
        self,
        payload: dict[str, Any],
        outputs: Iterable[Any],
        produced_by: str,
        pre_generated_id: Any = None,
    ):
        artifacts: list[Artifact] = []
        errors: list[str] = []
        for output in outputs or []:
            model_cls = output.spec.model
            data = self._select_output_payload(payload, model_cls, output.spec.type_name)
            try:
                instance = model_cls(**data)
            except Exception as exc:  # noqa: BLE001 - collect validation errors for logs
                errors.append(str(exc))
                continue

            # Use the pre-generated ID if provided (for streaming), otherwise let Artifact auto-generate
            artifact_kwargs = {
                "type": output.spec.type_name,
                "payload": instance.model_dump(),
                "produced_by": produced_by,
            }
            if pre_generated_id is not None:
                artifact_kwargs["id"] = pre_generated_id

            artifacts.append(Artifact(**artifact_kwargs))
        return artifacts, errors

    def _select_output_payload(
        self,
        payload: Mapping[str, Any],
        model_cls: type[BaseModel],
        type_name: str,
    ) -> dict[str, Any]:
        candidates = [
            payload.get(type_name),
            payload.get(model_cls.__name__),
            payload.get(model_cls.__name__.lower()),
        ]
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                return dict(candidate)
        if isinstance(payload, Mapping):
            return dict(payload)
        return {}

    async def _execute_standard(
        self, dspy_mod, program, *, description: str, payload: dict[str, Any]
    ) -> Any:
        """Execute DSPy program in standard mode (no streaming)."""
        # Handle new format: {"input": ..., "context": ...}
        if isinstance(payload, dict) and "input" in payload:
            return program(
                description=description,
                input=payload["input"],
                context=payload.get("context", []),
            )

        # Handle old format: direct payload (backwards compatible)
        return program(description=description, input=payload, context=[])

    async def _execute_streaming_websocket_only(
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
    ) -> tuple[Any, None]:
        """Execute streaming for WebSocket only (no Rich display).

        Optimized path for dashboard mode that skips all Rich formatting overhead.
        Used when multiple agents stream in parallel to avoid terminal conflicts
        and deadlocks with MCP tools.

        This method eliminates the Rich Live context that can cause deadlocks when
        combined with MCP tool execution and parallel agent streaming.
        """
        logger.info(f"Agent {agent.name}: Starting WebSocket-only streaming (dashboard mode)")

        # Get WebSocketManager
        ws_manager = None
        if ctx:
            orchestrator = getattr(ctx, "orchestrator", None)
            if orchestrator:
                collector = getattr(orchestrator, "_dashboard_collector", None)
                if collector:
                    ws_manager = getattr(collector, "_websocket_manager", None)

        if not ws_manager:
            logger.warning(
                f"Agent {agent.name}: No WebSocket manager, falling back to standard execution"
            )
            result = await self._execute_standard(
                dspy_mod, program, description=description, payload=payload
            )
            return result, None

        # Get artifact type name for WebSocket events
        artifact_type_name = "output"
        if hasattr(agent, "outputs") and agent.outputs:
            artifact_type_name = agent.outputs[0].spec.type_name

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
                        task = asyncio.create_task(ws_manager.broadcast(event))
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
                        task = asyncio.create_task(ws_manager.broadcast(event))
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
                        task = asyncio.create_task(ws_manager.broadcast(event))
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
                    task = asyncio.create_task(ws_manager.broadcast(event))
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
                    task = asyncio.create_task(ws_manager.broadcast(event))
                    ws_broadcast_tasks.add(task)
                    task.add_done_callback(ws_broadcast_tasks.discard)
                except Exception as e:
                    logger.warning(f"Failed to emit final streaming event: {e}")

        if final_result is None:
            raise RuntimeError(f"Agent {agent.name}: Streaming did not yield a final prediction")

        logger.info(f"Agent {agent.name}: WebSocket streaming completed ({stream_sequence} tokens)")
        return final_result, None

    async def _execute_streaming(
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
    ) -> Any:
        """Execute DSPy program in streaming mode with Rich table updates."""
        from rich.console import Console
        from rich.live import Live

        console = Console()

        # Get WebSocketManager for frontend streaming
        ws_manager = None
        if ctx:
            orchestrator = getattr(ctx, "orchestrator", None)
            if orchestrator:
                collector = getattr(orchestrator, "_dashboard_collector", None)
                if collector:
                    ws_manager = getattr(collector, "_websocket_manager", None)

        # Prepare stream listeners for output field
        listeners = []
        try:
            streaming_mod = getattr(dspy_mod, "streaming", None)
            if streaming_mod and hasattr(streaming_mod, "StreamListener"):
                for name, field in signature.output_fields.items():
                    if field.annotation is str:
                        listeners.append(streaming_mod.StreamListener(signature_field_name=name))
        except Exception:
            listeners = []

        streaming_task = dspy_mod.streamify(
            program,
            is_async_program=True,
            stream_listeners=listeners if listeners else None,
        )

        # Handle new format vs old format
        if isinstance(payload, dict) and "input" in payload:
            stream_generator = streaming_task(
                description=description,
                input=payload["input"],
                context=payload.get("context", []),
            )
        else:
            # Old format - backwards compatible
            stream_generator = streaming_task(description=description, input=payload, context=[])

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
        if hasattr(agent, "outputs") and agent.outputs:
            artifact_type_name = agent.outputs[0].spec.type_name

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
            _ensure_live_crop_above()
            (
                formatter,
                theme_dict,
                styles,
                agent_label,
            ) = self._prepare_stream_formatter(agent)
            initial_panel = formatter.format_result(display_data, agent_label, theme_dict, styles)
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
                live.update(formatter.format_result(display_data, agent_label, theme_dict, styles))

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
                        if ws_manager and token:
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
                                task = asyncio.create_task(ws_manager.broadcast(event))
                                ws_broadcast_tasks.add(task)
                                task.add_done_callback(ws_broadcast_tasks.discard)
                                stream_sequence += 1
                            except Exception as e:
                                logger.warning(f"Failed to emit streaming event: {e}")
                        else:
                            logger.debug("No WebSocket manager present for streaming event.")

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
                            if ws_manager:
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
                                    task = asyncio.create_task(ws_manager.broadcast(event))
                                    ws_broadcast_tasks.add(task)
                                    task.add_done_callback(ws_broadcast_tasks.discard)
                                    stream_sequence += 1
                                except Exception as e:
                                    logger.warning(f"Failed to emit streaming event: {e}")

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
                    if ws_manager and token:
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
                            task = asyncio.create_task(ws_manager.broadcast(event))
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
                    if ws_manager:
                        try:
                            event = StreamingOutputEvent(
                                correlation_id=str(ctx.correlation_id)
                                if ctx and ctx.correlation_id
                                else "",
                                agent_name=agent.name,
                                run_id=ctx.task_id if ctx else "",
                                output_type="log",
                                content="\nAmount of output tokens: " + str(stream_sequence),
                                sequence=stream_sequence,
                                is_final=True,  # Mark as final
                                artifact_id=str(
                                    pre_generated_artifact_id
                                ),  # Phase 6: Track artifact for message streaming
                                artifact_type=display_data["type"],  # Phase 6: Artifact type name
                            )
                            # Use create_task to avoid blocking the streaming loop
                            task = asyncio.create_task(ws_manager.broadcast(event))
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
                                artifact_type=display_data["type"],  # Phase 6: Artifact type name
                            )
                            # Use create_task to avoid blocking the streaming loop
                            task = asyncio.create_task(ws_manager.broadcast(event))
                            ws_broadcast_tasks.add(task)
                            task.add_done_callback(ws_broadcast_tasks.discard)
                        except Exception as e:
                            logger.warning(f"Failed to emit final streaming event: {e}")

                    if formatter is not None:
                        # Update payload section with final values
                        payload_data = OrderedDict()
                        for field_name in signature_order:
                            if field_name != "description" and hasattr(final_result, field_name):
                                field_value = getattr(final_result, field_name)
                                # If the field is a BaseModel, unwrap it to dict
                                if isinstance(field_value, BaseModel):
                                    payload_data.update(field_value.model_dump())
                                else:
                                    payload_data[field_name] = field_value

                        # Update all fields with actual values
                        display_data["payload"].clear()
                        display_data["payload"].update(payload_data)

                        # Update timestamp
                        from datetime import datetime, timezone

                        display_data["created_at"] = datetime.now(timezone.utc).isoformat()

                        # Remove status field from display
                        display_data.pop("status", None)
                        _refresh_panel()

        if final_result is None:
            raise RuntimeError("Streaming did not yield a final prediction.")

        # Return both the result and the display data for final ID update
        return final_result, (formatter, display_data, theme_dict, styles, agent_label)

    def _prepare_stream_formatter(
        self, agent: Any
    ) -> tuple[Any, dict[str, Any], dict[str, Any], str]:
        """Build formatter + theme metadata for streaming tables."""
        import pathlib

        from flock.logging.formatters.themed_formatter import (
            ThemedAgentResultFormatter,
            create_pygments_syntax_theme,
            get_default_styles,
            load_syntax_theme_from_file,
            load_theme_from_file,
        )

        themes_dir = pathlib.Path(__file__).resolve().parents[1] / "themes"
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

        model_label = self.model or ""
        agent_label = agent.name if not model_label else f"{agent.name} - {model_label}"

        return formatter, theme_dict, styles, agent_label

    def _print_final_stream_display(
        self,
        stream_display_data: tuple[Any, OrderedDict, dict, dict, str],
        artifact_id: str,
        artifact: Artifact,
    ) -> None:
        """Print the final streaming display with the real artifact ID."""
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
        display_data["tags"] = "set()" if not artifact.tags else f"set({list(artifact.tags)})"

        # Print the final panel
        console = Console()
        final_panel = formatter.format_result(display_data, agent_label, theme_dict, styles)
        console.print(final_panel)


__all__ = ["DSPyEngine"]


# Apply the Rich Live patch when this module is imported
_apply_live_patch_on_import()

# Apply the DSPy streaming patch to fix deadlocks with MCP tools
try:
    from flock.patches.dspy_streaming_patch import apply_patch as apply_dspy_streaming_patch

    apply_dspy_streaming_patch()
except Exception:
    pass  # Silently ignore if patch fails to apply
