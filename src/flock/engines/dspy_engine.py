"""DSPy-powered engine component that mirrors the design implementation."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

from flock.components.agent import EngineComponent
from flock.core.artifacts import Artifact
from flock.engines.dspy.artifact_materializer import DSPyArtifactMaterializer
from flock.engines.dspy.signature_builder import DSPySignatureBuilder
from flock.engines.dspy.streaming_executor import DSPyStreamingExecutor
from flock.logging.logging import get_logger
from flock.registry import type_registry
from flock.utils.runtime import EvalInputs, EvalResult


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
        _lr.VerticalOverflowMethod = _Literal[
            "crop", "crop_above", "ellipsis", "visible"
        ]  # type: ignore[assignment]

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
    stream_vertical_overflow: Literal["crop", "ellipsis", "crop_above", "visible"] = (
        Field(
            default="crop_above",
            description=(
                "Rich Live vertical overflow strategy; select how tall output is handled; 'crop_above' keeps the most recent rows visible."
            ),
        )
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

    def model_post_init(self, __context: Any) -> None:
        """Initialize helper instances after Pydantic model initialization."""
        super().model_post_init(__context)
        # Initialize delegated helper classes
        self._signature_builder = DSPySignatureBuilder()
        self._streaming_executor = DSPyStreamingExecutor(
            status_output_field=self.status_output_field,
            stream_vertical_overflow=self.stream_vertical_overflow,
            theme=self.theme,
            no_output=self.no_output,
        )
        self._artifact_materializer = DSPyArtifactMaterializer()

    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:  # type: ignore[override]
        """Universal evaluation with auto-detection of batch and fan-out modes.

        This single method handles ALL evaluation scenarios by auto-detecting:
        - Batching: Via ctx.is_batch flag (set by orchestrator for BatchSpec)
        - Fan-out: Via output_group.outputs[*].count (signature building adapts)
        - Multi-output: Via len(output_group.outputs) (multiple types in one call)

        The signature building in _prepare_signature_for_output_group() automatically:
        - Pluralizes field names for batching ("tasks" vs "task")
        - Uses list[Type] for batching and fan-out
        - Generates semantic field names for all modes

        Args:
            agent: Agent instance
            ctx: Execution context (ctx.is_batch indicates batch mode)
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce

        Returns:
            EvalResult with artifacts matching output_group specifications

        Examples:
            Single: .publishes(Report) → {"report": Report}
            Batch: BatchSpec(size=3) + ctx.is_batch=True → {"reports": list[Report]}
            Fan-out: .publishes(Idea, fan_out=5) → {"ideas": list[Idea]}
            Multi: .publishes(Summary, Analysis) → {"summary": Summary, "analysis": Analysis}
        """
        # Auto-detect batching from context flag
        batched = bool(getattr(ctx, "is_batch", False))

        # Fan-out and multi-output detection happens automatically in signature building
        # via output_group.outputs[*].count and len(output_group.outputs)
        return await self._evaluate_internal(
            agent, ctx, inputs, batched=batched, output_group=output_group
        )

    async def _evaluate_internal(
        self,
        agent,
        ctx,
        inputs: EvalInputs,
        *,
        batched: bool,
        output_group=None,
    ) -> EvalResult:
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
        if batched:
            validated_input = [
                self._validate_input_payload(input_model, artifact.payload)
                for artifact in inputs.artifacts
            ]
        else:
            validated_input = self._validate_input_payload(
                input_model, primary_artifact.payload
            )
        output_model = self._resolve_output_model(agent)

        # Phase 8: Use pre-filtered conversation context from Context (security fix)
        # Orchestrator evaluates context BEFORE creating Context, so engines just read ctx.artifacts
        # This fixes Vulnerability #4: Engines can no longer query arbitrary data via ctx.store

        # Filter out input artifacts to avoid duplication in context
        context_history = ctx.artifacts if ctx else []

        has_context = bool(context_history) and self.should_use_context(inputs)

        # Generate signature with semantic field naming (delegated to SignatureBuilder)
        signature = self._signature_builder.prepare_signature_for_output_group(
            dspy_mod,
            agent=agent,
            inputs=inputs,
            output_group=output_group,
            has_context=has_context,
            batched=batched,
            engine_instructions=self.instructions,
        )

        sys_desc = self._system_description(self.instructions or agent.description)

        # Pre-generate the artifact ID so it's available from the start
        from uuid import uuid4

        pre_generated_artifact_id = uuid4()

        # Build execution payload with semantic field names matching signature (delegated to SignatureBuilder)
        execution_payload = (
            self._signature_builder.prepare_execution_payload_for_output_group(
                inputs,
                output_group,
                batched=batched,
                has_context=has_context,
                context_history=context_history,
                sys_desc=sys_desc,
            )
        )

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
            # Phase 6+7 Security Fix: Use Agent class variables for streaming coordination
            if ctx:
                from flock.core import Agent

                # Check if dashboard mode (WebSocket broadcast is set)
                is_dashboard = Agent._websocket_broadcast_global is not None
                # if dashboard we always stream, streaming queue only for CLI output
                if should_stream and not is_dashboard:
                    # Get current active streams count from Agent class variable (shared across all agents)
                    active_streams = Agent._streaming_counter

                    if active_streams > 0:
                        should_stream = False  # Suppress - another agent streaming
                    else:
                        Agent._streaming_counter = (
                            active_streams + 1
                        )  # Mark as streaming

            try:
                if should_stream:
                    # Choose streaming method based on dashboard mode
                    # Phase 6+7 Security Fix: Check dashboard mode via Agent class variable
                    from flock.core import Agent

                    is_dashboard = (
                        Agent._websocket_broadcast_global is not None if ctx else False
                    )

                    # DEBUG: Log routing decision
                    logger.info(
                        f"[STREAMING ROUTER] agent={agent.name}, is_dashboard={is_dashboard}"
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
                        ) = await self._streaming_executor.execute_streaming_websocket_only(
                            dspy_mod,
                            program,
                            signature,
                            description=sys_desc,
                            payload=execution_payload,
                            agent=agent,
                            ctx=ctx,
                            pre_generated_artifact_id=pre_generated_artifact_id,
                            output_group=output_group,
                        )
                    else:
                        # CLI mode: Rich streaming with terminal display
                        logger.info(
                            f"[STREAMING ROUTER] Routing {agent.name} to Rich streaming method (CLI mode)"
                        )
                        (
                            raw_result,
                            _stream_final_display_data,
                        ) = await self._streaming_executor.execute_streaming(
                            dspy_mod,
                            program,
                            signature,
                            description=sys_desc,
                            payload=execution_payload,
                            agent=agent,
                            ctx=ctx,
                            pre_generated_artifact_id=pre_generated_artifact_id,
                            output_group=output_group,
                        )
                    if not self.no_output and ctx:
                        ctx.state["_flock_stream_live_active"] = True
                else:
                    raw_result = await self._streaming_executor.execute_standard(
                        dspy_mod,
                        program,
                        description=sys_desc,
                        payload=execution_payload,
                    )
                    # Phase 6+7 Security Fix: Check streaming state from Agent class variable
                    from flock.core import Agent

                    if ctx and Agent._streaming_counter > 0:
                        ctx.state["_flock_output_queued"] = True
            finally:
                # Phase 6+7 Security Fix: Decrement counter using Agent class variable
                if should_stream and ctx:
                    from flock.core import Agent

                    Agent._streaming_counter = max(0, Agent._streaming_counter - 1)

        # Extract semantic fields from Prediction (delegated to SignatureBuilder)
        normalized_output = self._signature_builder.extract_multi_output_payload(
            raw_result, output_group
        )

        # Materialize artifacts (delegated to ArtifactMaterializer)
        artifacts, errors = self._artifact_materializer.materialize_artifacts(
            normalized_output,
            output_group.outputs,
            agent.name,
            pre_generated_id=pre_generated_artifact_id,
        )
        logger.info(f"[_materialize_artifacts] normalized_output {normalized_output}")
        logger.info(f"[_materialize_artifacts] artifacts {artifacts}")
        logger.info(f"[_materialize_artifacts] errors {errors}")

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
        model = self.model or os.getenv("DEFAULT_MODEL")
        if not model:
            raise NotImplementedError(
                "DSPyEngine requires a configured model (set DEFAULT_MODEL, or pass model=...)."
            )
        return model

    def _import_dspy(self):  # pragma: no cover - import guarded by optional dependency
        try:
            import dspy
        except Exception as exc:
            raise NotImplementedError(
                "DSPy is not installed or failed to import."
            ) from exc
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

    def _choose_program(self, dspy_mod, signature, tools: Iterable[Any]):
        tools_list = list(tools or [])
        try:
            if tools_list:
                return dspy_mod.ReAct(
                    signature, tools=tools_list, max_iters=self.max_tool_calls
                )
            return dspy_mod.Predict(signature)
        except Exception:
            return dspy_mod.Predict(signature)

    def _system_description(self, description: str | None) -> str:
        if description:
            return description
        return "Produce a valid output that matches the 'output' schema."  # Return only JSON.


__all__ = ["DSPyEngine"]


# Apply the Rich Live patch when this module is imported
_apply_live_patch_on_import()

# Apply the DSPy streaming patch to fix deadlocks with MCP tools
try:
    from flock.patches.dspy_streaming_patch import (
        apply_patch as apply_dspy_streaming_patch,
    )

    apply_dspy_streaming_patch()
except Exception:
    pass  # Silently ignore if patch fails to apply
