"""DSPy-powered engine component that mirrors the design implementation."""

from __future__ import annotations

import asyncio
import json
import os
from collections import OrderedDict, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from contextlib import nullcontext
from datetime import UTC
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

        # Generate signature with semantic field naming
        signature = self._prepare_signature_for_output_group(
            dspy_mod,
            agent=agent,
            inputs=inputs,
            output_group=output_group,
            has_context=has_context,
            batched=batched,
        )

        sys_desc = self._system_description(self.instructions or agent.description)

        # Pre-generate the artifact ID so it's available from the start
        from uuid import uuid4

        pre_generated_artifact_id = uuid4()

        # Build execution payload with semantic field names matching signature
        execution_payload = self._prepare_execution_payload_for_output_group(
            inputs,
            output_group,
            batched=batched,
            has_context=has_context,
            context_history=context_history,
            sys_desc=sys_desc,
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
                from flock.agent import Agent

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
                    from flock.agent import Agent

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
                        ) = await self._execute_streaming_websocket_only(
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
                        ) = await self._execute_streaming(
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
                    raw_result = await self._execute_standard(
                        dspy_mod,
                        program,
                        description=sys_desc,
                        payload=execution_payload,
                    )
                    # Phase 6+7 Security Fix: Check streaming state from Agent class variable
                    from flock.agent import Agent

                    if ctx and Agent._streaming_counter > 0:
                        ctx.state["_flock_output_queued"] = True
            finally:
                # Phase 6+7 Security Fix: Decrement counter using Agent class variable
                if should_stream and ctx:
                    from flock.agent import Agent

                    Agent._streaming_counter = max(0, Agent._streaming_counter - 1)

        # Extract semantic fields from Prediction
        normalized_output = self._extract_multi_output_payload(raw_result, output_group)

        artifacts, errors = self._materialize_artifacts(
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

    def _type_to_field_name(self, type_class: type) -> str:
        """Convert Pydantic model class name to snake_case field name.

        Examples:
            Movie → "movie"
            ResearchQuestion → "research_question"
            APIResponse → "api_response"
            UserAuthToken → "user_auth_token"

        Args:
            type_class: The Pydantic model class

        Returns:
            snake_case field name
        """
        import re

        name = type_class.__name__
        # Convert CamelCase to snake_case
        snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        return snake_case

    def _pluralize(self, field_name: str) -> str:
        """Convert singular field name to plural for lists.

        Examples:
            "idea" → "ideas"
            "movie" → "movies"
            "story" → "stories" (y → ies)
            "analysis" → "analyses" (is → es)
            "research_question" → "research_questions"

        Args:
            field_name: Singular field name in snake_case

        Returns:
            Pluralized field name
        """
        # Simple English pluralization rules
        if (
            field_name.endswith("y")
            and len(field_name) > 1
            and field_name[-2] not in "aeiou"
        ):
            # story → stories (consonant + y)
            return field_name[:-1] + "ies"
        if field_name.endswith(("s", "x", "z", "ch", "sh")):
            # analysis → analyses, box → boxes
            return field_name + "es"
        # idea → ideas, movie → movies
        return field_name + "s"

    def _needs_multioutput_signature(self, output_group) -> bool:
        """Determine if OutputGroup requires multi-output signature generation.

        Args:
            output_group: OutputGroup to analyze

        Returns:
            True if multi-output signature needed, False for single output (backward compat)
        """
        if (
            not output_group
            or not hasattr(output_group, "outputs")
            or not output_group.outputs
        ):
            return False

        # Multiple different types → multi-output
        if len(output_group.outputs) > 1:
            return True

        # Fan-out (single type, count > 1) → multi-output
        if output_group.outputs[0].count > 1:
            return True

        return False

    def _prepare_signature_with_context(
        self,
        dspy_mod,
        *,
        description: str | None,
        input_schema: type[BaseModel] | None,
        output_schema: type[BaseModel] | None,
        has_context: bool = False,
        batched: bool = False,
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

        if batched:
            if input_schema is not None:
                input_type = list[input_schema]
            else:
                input_type = list[dict[str, Any]]
        else:
            input_type = input_schema or dict

        fields["input"] = (input_type, dspy_mod.InputField())
        fields["output"] = (output_schema or dict, dspy_mod.OutputField())

        signature = dspy_mod.Signature(fields)

        instruction = (
            description or "Produce a valid output that matches the 'output' schema."
        )
        if has_context:
            instruction += (
                " Consider the conversation context provided to inform your response."
            )
        if batched:
            instruction += (
                " The 'input' field will contain a list of items representing the batch; "
                "process the entire collection coherently."
            )
        # instruction += " Return only JSON."

        return signature.with_instructions(instruction)

    def _prepare_signature_for_output_group(
        self,
        dspy_mod,
        *,
        agent,
        inputs: EvalInputs,
        output_group,
        has_context: bool = False,
        batched: bool = False,
    ) -> Any:
        """Prepare DSPy signature dynamically based on OutputGroup with semantic field names.

        This method generates signatures using semantic field naming:
        - Type names → snake_case field names (Task → "task", ResearchQuestion → "research_question")
        - Pluralization for fan-out (Idea → "ideas" for lists)
        - Pluralization for batching (Task → "tasks" for list[Task])
        - Multi-input support for joins (multiple input artifacts with semantic names)
        - Collision handling (same input/output type → prefix with "input_" or "output_")

        Examples:
            Single output: .consumes(Task).publishes(Report)
            → {"task": (Task, InputField()), "report": (Report, OutputField())}

            Multiple inputs (joins): .consumes(Document, Guidelines).publishes(Report)
            → {"document": (Document, InputField()), "guidelines": (Guidelines, InputField()),
               "report": (Report, OutputField())}

            Multiple outputs: .consumes(Task).publishes(Summary, Analysis)
            → {"task": (Task, InputField()), "summary": (Summary, OutputField()),
               "analysis": (Analysis, OutputField())}

            Fan-out: .publishes(Idea, fan_out=5)
            → {"topic": (Topic, InputField()), "ideas": (list[Idea], OutputField(...))}

            Batching: evaluate_batch([task1, task2, task3])
            → {"tasks": (list[Task], InputField()), "reports": (list[Report], OutputField())}

        Args:
            dspy_mod: DSPy module
            agent: Agent instance
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what to generate
            has_context: Whether conversation context should be included
            batched: Whether this is a batch evaluation (pluralizes input fields)

        Returns:
            DSPy Signature with semantic field names
        """
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

        # Track used field names for collision detection
        used_field_names: set[str] = {"description", "context"}

        # 1. Generate INPUT fields with semantic names
        #    Multi-input support: handle all input artifacts for joins
        #    Batching support: pluralize field names and use list[Type] when batched=True
        if inputs.artifacts:
            # Collect unique input types (avoid duplicates if multiple artifacts of same type)
            input_types_seen: dict[type, list[Artifact]] = {}
            for artifact in inputs.artifacts:
                input_model = self._resolve_input_model(artifact)
                if input_model is not None:
                    if input_model not in input_types_seen:
                        input_types_seen[input_model] = []
                    input_types_seen[input_model].append(artifact)

            # Generate fields for each unique input type
            for input_model, artifacts_of_type in input_types_seen.items():
                field_name = self._type_to_field_name(input_model)

                # Handle batching: pluralize field name and use list[Type]
                if batched:
                    field_name = self._pluralize(field_name)
                    input_type = list[input_model]
                    desc = f"Batch of {input_model.__name__} instances to process"
                    fields[field_name] = (input_type, dspy_mod.InputField(desc=desc))
                else:
                    # Single input: use singular field name
                    input_type = input_model
                    fields[field_name] = (input_type, dspy_mod.InputField())

                used_field_names.add(field_name)

            # Fallback: if we couldn't resolve any types, use generic "input"
            if not input_types_seen:
                fields["input"] = (dict, dspy_mod.InputField())
                used_field_names.add("input")

        # 2. Generate OUTPUT fields with semantic names
        for output_decl in output_group.outputs:
            output_schema = output_decl.spec.model
            type_name = output_decl.spec.type_name

            # Generate semantic field name
            field_name = self._type_to_field_name(output_schema)

            # Handle fan-out: pluralize field name and use list[Type]
            if output_decl.count > 1:
                field_name = self._pluralize(field_name)
                output_type = list[output_schema]

                # Create description with count hint
                desc = f"Generate exactly {output_decl.count} {type_name} instances"
                if output_decl.group_description:
                    desc = f"{desc}. {output_decl.group_description}"

                fields[field_name] = (output_type, dspy_mod.OutputField(desc=desc))
            else:
                # Single output
                output_type = output_schema

                # Handle collision: if field name already used, prefix with "output_"
                if field_name in used_field_names:
                    field_name = f"output_{field_name}"

                desc = f"{type_name} output"
                if output_decl.group_description:
                    desc = output_decl.group_description

                fields[field_name] = (output_type, dspy_mod.OutputField(desc=desc))

            used_field_names.add(field_name)

        # 3. Create signature
        signature = dspy_mod.Signature(fields)

        # 4. Build instruction
        description = self.instructions or agent.description
        instruction = (
            description
            or f"Process input and generate {len(output_group.outputs)} outputs."
        )

        if has_context:
            instruction += (
                " Consider the conversation context provided to inform your response."
            )

        # Add batching hint
        if batched:
            instruction += " Process the batch of inputs coherently, generating outputs for each item."

        # Add semantic field names to instruction for clarity
        output_field_names = [
            name for name in fields.keys() if name not in {"description", "context"}
        ]
        if len(output_field_names) > 2:  # Multiple outputs
            instruction += f" Generate ALL output fields as specified: {', '.join(output_field_names[1:])}."

        # instruction += " Return only valid JSON."

        return signature.with_instructions(instruction)

    def _prepare_execution_payload_for_output_group(
        self,
        inputs: EvalInputs,
        output_group,
        *,
        batched: bool,
        has_context: bool,
        context_history: list | None,
        sys_desc: str,
    ) -> dict[str, Any]:
        """Prepare execution payload with semantic field names matching signature.

        This method builds a payload dict with semantic field names that match the signature
        generated by `_prepare_signature_for_output_group()`.

        Args:
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup (not used here but kept for symmetry)
            batched: Whether this is a batch evaluation
            has_context: Whether conversation context should be included
            context_history: Optional conversation history
            sys_desc: System description for the "description" field

        Returns:
            Dict with semantic field names ready for DSPy program execution

        Examples:
            Single input: {"description": desc, "task": {...}}
            Multi-input: {"description": desc, "task": {...}, "topic": {...}}
            Batched: {"description": desc, "tasks": [{...}, {...}, {...}]}
        """
        payload = {"description": sys_desc}

        # Add context if present
        if has_context and context_history:
            payload["context"] = context_history

        # Build semantic input fields
        if inputs.artifacts:
            # Collect unique input types (same logic as signature generation)
            input_types_seen: dict[type, list[Artifact]] = {}
            for artifact in inputs.artifacts:
                input_model = self._resolve_input_model(artifact)
                if input_model is not None:
                    if input_model not in input_types_seen:
                        input_types_seen[input_model] = []
                    input_types_seen[input_model].append(artifact)

            # Generate payload fields for each unique input type
            for input_model, artifacts_of_type in input_types_seen.items():
                field_name = self._type_to_field_name(input_model)

                # Validate and prepare payloads
                validated_payloads = [
                    self._validate_input_payload(input_model, art.payload)
                    for art in artifacts_of_type
                ]

                if batched:
                    # Batch mode: pluralize field name and use list
                    field_name = self._pluralize(field_name)
                    payload[field_name] = validated_payloads
                else:
                    # Single mode: use first (or only) artifact
                    # For multi-input joins, we have one artifact per type
                    payload[field_name] = (
                        validated_payloads[0] if validated_payloads else {}
                    )

        return payload

    def _extract_multi_output_payload(self, prediction, output_group) -> dict[str, Any]:
        """Extract semantic fields from DSPy Prediction for multi-output scenarios.

        Maps semantic field names (e.g., "movie", "ideas") back to type names (e.g., "Movie", "Idea")
        for artifact materialization compatibility.

        Args:
            prediction: DSPy Prediction object with semantic field names
            output_group: OutputGroup defining expected outputs

        Returns:
            Dict mapping type names to extracted values

        Examples:
            Prediction(movie={...}, summary={...})
            → {"Movie": {...}, "Summary": {...}}

            Prediction(ideas=[{...}, {...}, {...}])
            → {"Idea": [{...}, {...}, {...}]}
        """
        payload = {}

        for output_decl in output_group.outputs:
            output_schema = output_decl.spec.model
            type_name = output_decl.spec.type_name

            # Generate the same semantic field name used in signature
            field_name = self._type_to_field_name(output_schema)

            # Handle fan-out: field name is pluralized
            if output_decl.count > 1:
                field_name = self._pluralize(field_name)

            # Extract value from Prediction
            if hasattr(prediction, field_name):
                value = getattr(prediction, field_name)

                # Store using type_name as key (for _select_output_payload compatibility)
                payload[type_name] = value
            else:
                # Fallback: try with "output_" prefix (collision handling)
                prefixed_name = f"output_{field_name}"
                if hasattr(prediction, prefixed_name):
                    value = getattr(prediction, prefixed_name)
                    payload[type_name] = value

        return payload

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
        """Materialize artifacts from payload, handling fan-out (count > 1).

        For fan-out outputs (count > 1), splits the list into individual artifacts.
        For single outputs (count = 1), creates one artifact from dict.

        Args:
            payload: Normalized output dict from DSPy
            outputs: AgentOutput declarations defining what to create
            produced_by: Agent name
            pre_generated_id: Pre-generated ID for streaming (only used for single outputs)

        Returns:
            Tuple of (artifacts list, errors list)
        """
        artifacts: list[Artifact] = []
        errors: list[str] = []
        for output in outputs or []:
            model_cls = output.spec.model
            data = self._select_output_payload(
                payload, model_cls, output.spec.type_name
            )

            # FAN-OUT: If count > 1, data should be a list and we create multiple artifacts
            if output.count > 1:
                if not isinstance(data, list):
                    errors.append(
                        f"Fan-out expected list for {output.spec.type_name} (count={output.count}), "
                        f"got {type(data).__name__}"
                    )
                    continue

                # Create one artifact for each item in the list
                for item_data in data:
                    try:
                        instance = model_cls(**item_data)
                    except Exception as exc:  # noqa: BLE001 - collect validation errors for logs
                        errors.append(f"{output.spec.type_name}: {exc!s}")
                        continue

                    # Fan-out artifacts auto-generate their IDs (can't reuse pre_generated_id)
                    artifact_kwargs = {
                        "type": output.spec.type_name,
                        "payload": instance.model_dump(),
                        "produced_by": produced_by,
                    }
                    artifacts.append(Artifact(**artifact_kwargs))
            else:
                # SINGLE OUTPUT: Create one artifact from dict
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
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Select the correct output payload from the normalized output dict.

        Handles both simple type names and fully qualified names (with module prefix).
        Returns either a dict (single output) or list[dict] (fan-out/batch).
        """
        candidates = [
            payload.get(type_name),  # Try exact type_name (may be "__main__.Movie")
            payload.get(model_cls.__name__),  # Try simple class name ("Movie")
            payload.get(model_cls.__name__.lower()),  # Try lowercase ("movie")
        ]

        # Extract value based on type
        for candidate in candidates:
            if candidate is not None:
                # Handle lists (fan-out and batching)
                if isinstance(candidate, list):
                    # Convert Pydantic instances to dicts
                    return [
                        item.model_dump() if isinstance(item, BaseModel) else item
                        for item in candidate
                    ]
                # Handle single Pydantic instance
                if isinstance(candidate, BaseModel):
                    return candidate.model_dump()
                # Handle dict
                if isinstance(candidate, Mapping):
                    return dict(candidate)

        # Fallback: return entire payload (will likely fail validation)
        if isinstance(payload, Mapping):
            return dict(payload)
        return {}

    async def _execute_standard(
        self, dspy_mod, program, *, description: str, payload: dict[str, Any]
    ) -> Any:
        """Execute DSPy program in standard mode (no streaming)."""
        # Handle semantic fields format: {"description": ..., "task": ..., "report": ...}
        if isinstance(payload, dict) and "description" in payload:
            # Semantic fields: pass all fields as kwargs
            return program(**payload)

        # Handle legacy format: {"input": ..., "context": ...}
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
        output_group=None,
    ) -> tuple[Any, None]:
        """Execute streaming for WebSocket only (no Rich display).

        Optimized path for dashboard mode that skips all Rich formatting overhead.
        Used when multiple agents stream in parallel to avoid terminal conflicts
        and deadlocks with MCP tools.

        This method eliminates the Rich Live context that can cause deadlocks when
        combined with MCP tool execution and parallel agent streaming.
        """
        logger.info(
            f"Agent {agent.name}: Starting WebSocket-only streaming (dashboard mode)"
        )

        # Get WebSocket broadcast function (security: wrapper prevents object traversal)
        # Phase 6+7 Security Fix: Use broadcast wrapper from Agent class variable (prevents GOD MODE restoration)
        from flock.agent import Agent

        ws_broadcast = Agent._websocket_broadcast_global

        if not ws_broadcast:
            logger.warning(
                f"Agent {agent.name}: No WebSocket manager, falling back to standard execution"
            )
            result = await self._execute_standard(
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
        output_group=None,
    ) -> Any:
        """Execute DSPy program in streaming mode with Rich table updates."""
        from rich.console import Console
        from rich.live import Live

        console = Console()

        # Get WebSocket broadcast function (security: wrapper prevents object traversal)
        # Phase 6+7 Security Fix: Use broadcast wrapper from Agent class variable (prevents GOD MODE restoration)
        from flock.agent import Agent

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
            _ensure_live_crop_above()
            (
                formatter,
                theme_dict,
                styles,
                agent_label,
            ) = self._prepare_stream_formatter(agent)
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
        display_data["tags"] = (
            "set()" if not artifact.tags else f"set({list(artifact.tags)})"
        )

        # Print the final panel
        console = Console()
        final_panel = formatter.format_result(
            display_data, agent_label, theme_dict, styles
        )
        console.print(final_panel)


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
