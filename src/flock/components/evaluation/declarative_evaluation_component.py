# src/flock/components/evaluation/declarative_evaluation_component.py
"""DeclarativeEvaluationComponent - DSPy-based evaluation using the unified component system."""

from collections import OrderedDict
from collections.abc import Callable, Generator
from contextlib import nullcontext
from typing import Any, Literal, override

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    import dspy

from pydantic import Field, PrivateAttr

from flock.core.component.agent_component_base import AgentComponentConfig
from flock.core.component.evaluation_component import EvaluationComponent
from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.mixin.prompt_parser import PromptParserMixin
from flock.core.registry import flock_component

logger = get_logger("components.evaluation.declarative")


_live_patch_applied = False


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
        lines = console.render_lines(
            renderable, options, style=style, pad=False
        )
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


class DeclarativeEvaluationConfig(AgentComponentConfig):
    """Configuration for the DeclarativeEvaluationComponent."""

    override_evaluator_type: str | None = None
    model: str | None = "openai/gpt-4o"
    use_cache: bool = True
    temperature: float = 1.0
    max_tokens: int = 32000
    max_retries: int = 3
    max_tool_calls: int = 10
    no_output: bool = Field(
        default=False,
        description="Disable output from the underlying DSPy program.",
    )
    stream: bool = Field(
        default=False,
        description="Enable streaming output from the underlying DSPy program.",
    )
    include_thought_process: bool = Field(
        default=False,
        description="Include the thought process in the output.",
    )
    include_reasoning: bool = Field(
        default=False,
        description="Include the reasoning in the output.",
    )
    adapter: Literal["chat", "json", "xml", "two_step"] | None = Field(
        default=None,
        description="Optional DSPy adapter to use for formatting/parsing.",
    )
    extraction_model: str | None = Field(
        default=None,
        description="Extraction LM for TwoStepAdapter when adapter='two_step'",
    )
    stream_callbacks: list[Callable[..., Any] | Any] | None = None
    stream_vertical_overflow: Literal[
        "crop", "ellipsis", "crop_above", "visible"
    ] = Field(
        default="crop_above",
        description=(
            "Rich Live vertical overflow strategy; select how tall output is handled; 'crop_above' keeps the most recent rows visible."
        ),
    )
    kwargs: dict[str, Any] = Field(default_factory=dict)


@flock_component(config_class=DeclarativeEvaluationConfig)
class DeclarativeEvaluationComponent(
    EvaluationComponent, DSPyIntegrationMixin, PromptParserMixin
):
    """Evaluation component that uses DSPy for generation.

    This component provides the core intelligence for agents using DSPy's
    declarative programming model. It handles LLM interactions, tool usage,
    and prompt management through DSPy's framework.
    """

    config: DeclarativeEvaluationConfig = Field(
        default_factory=DeclarativeEvaluationConfig,
        description="Evaluation configuration",
    )

    _cost: float = PrivateAttr(default=0.0)
    _lm_history: list = PrivateAttr(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)

    @override
    def set_model(
        self, model: str, temperature: float = 1.0, max_tokens: int = 32000
    ) -> None:
        """Set the model for the evaluation component."""
        self.config.model = model
        self.config.temperature = temperature
        self.config.max_tokens = max_tokens

    async def evaluate_core(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Core evaluation logic using DSPy - migrated from DeclarativeEvaluator."""
        logger.debug(
            f"Starting declarative evaluation for component '{self.name}'"
        )

        # Prepare LM and optional adapter; keep settings changes scoped with dspy.context
        lm = dspy.LM(
            model=self.config.model or agent.model,
            cache=self.config.use_cache,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            num_retries=self.config.max_retries,
        )

        adapter = None
        if self.config.adapter:
            try:
                if self.config.adapter == "json":
                    adapter = dspy.JSONAdapter()
                elif self.config.adapter == "xml":
                    adapter = dspy.XMLAdapter()
                elif self.config.adapter == "two_step":
                    extractor = dspy.LM(
                        self.config.extraction_model or "openai/gpt-4o-mini"
                    )
                    adapter = dspy.TwoStepAdapter(extraction_model=extractor)
                else:
                    # chat is default; leave adapter=None
                    adapter = None
            except Exception as e:
                logger.warning(
                    f"Failed to construct adapter '{self.config.adapter}': {e}. Proceeding without."
                )

        with dspy.context(lm=lm, adapter=adapter):
            try:
                from rich.console import Console

                console = Console()

                # Create DSPy signature from agent definition
                _dspy_signature = self.create_dspy_signature_class(
                    agent.name,
                    agent.description,
                    f"{agent.input} -> {agent.output}",
                )

                # Get output field names for streaming
                output_field_names = list(_dspy_signature.output_fields.keys())
                if not output_field_names:
                    logger.warning(
                        f"DSPy signature for agent '{agent.name}' has no defined output fields. Streaming might not produce text."
                    )

                # Select appropriate DSPy task
                agent_task = self._select_task(
                    _dspy_signature,
                    override_evaluator_type=self.config.override_evaluator_type,
                    tools=tools or [],
                    max_tool_calls=self.config.max_tool_calls,
                    mcp_tools=mcp_tools or [],
                    kwargs=self.config.kwargs,
                )

            except Exception as setup_error:
                logger.error(
                    f"Error setting up DSPy task for agent '{agent.name}': {setup_error}",
                    exc_info=True,
                )
                raise RuntimeError(
                    f"DSPy task setup failed: {setup_error}"
                ) from setup_error

            # Execute with streaming or non-streaming
            if self.config.stream:
                return await self._execute_streaming(
                    _dspy_signature, agent_task, inputs, agent, console
                )
            else:
                return await self._execute_standard(agent_task, inputs, agent)

    async def _execute_streaming(
        self, signature, agent_task, inputs: dict[str, Any], agent: Any, console
    ) -> dict[str, Any]:
        """Execute DSPy program in streaming mode with rich table updates."""
        logger.info(f"Evaluating agent '{agent.name}' with async streaming.")

        if not callable(agent_task):
            logger.error("agent_task is not callable, cannot stream.")
            raise TypeError(
                "DSPy task could not be created or is not callable."
            )

        # Prepare stream listeners for any string output fields
        listeners = []
        try:
            for name, field in signature.output_fields.items():
                if field.annotation is str:
                    listeners.append(
                        dspy.streaming.StreamListener(signature_field_name=name)
                    )
        except Exception:
            listeners = []

        streaming_task = dspy.streamify(
            agent_task,
            is_async_program=True,
            stream_listeners=listeners if listeners else None,
        )
        stream_generator: Generator = streaming_task(**inputs)

        from collections import defaultdict

        from rich.live import Live

        signature_order = []
        try:
            signature_order = list(signature.output_fields.keys())
        except Exception:
            signature_order = []

        display_data: OrderedDict[str, Any] = OrderedDict()
        for key in inputs:
            display_data[key] = inputs[key]

        for field_name in signature_order:
            if field_name not in display_data:
                display_data[field_name] = ""

        stream_buffers: defaultdict[str, list[str]] = defaultdict(list)

        formatter = theme_dict = styles = agent_label = None
        live_cm = nullcontext()
        overflow_mode = self.config.stream_vertical_overflow
        initial_panel = None
        if not self.config.no_output:
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

        final_result: dict[str, Any] | None = None

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
                    import dspy as _d
                    from dspy.streaming import StatusMessage, StreamResponse
                    from litellm import ModelResponseStream
                except Exception:
                    StatusMessage = object  # type: ignore
                    StreamResponse = object  # type: ignore
                    ModelResponseStream = object  # type: ignore
                    _d = None

                if isinstance(value, StatusMessage):
                    message = getattr(value, "message", "")
                    if message and live is not None:
                        live.console.log(f"[status] {message}")
                    continue

                if isinstance(value, StreamResponse):
                    for callback in self.config.stream_callbacks or []:
                        try:
                            callback(value)
                        except Exception as e:
                            logger.warning(f"Stream callback error: {e}")
                    token = getattr(value, "chunk", None)
                    signature_field = getattr(
                        value, "signature_field_name", None
                    )
                    if signature_field:
                        if signature_field not in display_data:
                            display_data[signature_field] = ""
                        if token:
                            stream_buffers[signature_field].append(str(token))
                            display_data[signature_field] = "".join(
                                stream_buffers[signature_field]
                            )
                        if formatter is not None:
                            _refresh_panel()
                    continue

                if isinstance(value, ModelResponseStream):
                    try:
                        chunk = value
                        text = chunk.choices[0].delta.content or ""
                        if text and live is not None:
                            live.console.log(text)
                    except Exception:
                        pass
                    continue

                if _d and isinstance(value, _d.Prediction):
                    result_dict, cost, lm_history = self._process_result(
                        value, inputs
                    )
                    self._cost = cost
                    self._lm_history = lm_history
                    final_result = result_dict

                    if formatter is not None:
                        ordered_final = OrderedDict()
                        for key in inputs:
                            if key in final_result:
                                ordered_final[key] = final_result[key]
                        for field_name in signature_order:
                            if field_name in final_result:
                                ordered_final[field_name] = final_result[
                                    field_name
                                ]
                        for key, val in final_result.items():
                            if key not in ordered_final:
                                ordered_final[key] = val
                        display_data.clear()
                        display_data.update(ordered_final)
                        _refresh_panel()

        if final_result is None:
            raise RuntimeError("Streaming did not yield a final prediction.")

        filtered_result = self.filter_reasoning(
            final_result, self.config.include_reasoning
        )
        filtered_result = self.filter_thought_process(
            filtered_result, self.config.include_thought_process
        )

        if not self.config.no_output:
            context = getattr(agent, "context", None)
            if context is not None:
                context.state["_flock_stream_live_active"] = True

        return filtered_result

    async def _execute_standard(
        self, agent_task, inputs: dict[str, Any], agent: Any
    ) -> dict[str, Any]:
        """Execute DSPy program in standard mode (from original implementation)."""
        logger.info(f"Evaluating agent '{agent.name}' without streaming.")

        try:
            # Ensure the call is awaited if the underlying task is async
            result_obj = await agent_task.acall(**inputs)
            result_dict, cost, lm_history = self._process_result(
                result_obj, inputs
            )
            self._cost = cost
            self._lm_history = lm_history
            result_dict = self.filter_reasoning(
                result_dict, self.config.include_reasoning
            )
            return self.filter_thought_process(
                result_dict, self.config.include_thought_process
            )
        except Exception as e:
            logger.error(
                f"Error during non-streaming evaluation for agent '{agent.name}': {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Evaluation failed: {e}") from e

    def _prepare_stream_formatter(
        self, agent: Any
    ) -> tuple[Any, dict[str, Any], dict[str, Any], str]:
        """Build formatter + theme metadata for streaming tables."""
        import pathlib

        from flock.core.logging.formatters.themed_formatter import (
            ThemedAgentResultFormatter,
            create_pygments_syntax_theme,
            get_default_styles,
            load_syntax_theme_from_file,
            load_theme_from_file,
        )
        from flock.core.logging.formatters.themes import OutputTheme

        stream_theme = OutputTheme.afterglow
        output_component = None
        try:
            output_component = agent.get_component("output_formatter")
        except Exception:
            output_component = None
        if output_component and getattr(output_component, "config", None):
            stream_theme = getattr(
                output_component.config, "theme", stream_theme
            )

        formatter = ThemedAgentResultFormatter(theme=stream_theme)

        themes_dir = pathlib.Path(__file__).resolve().parents[2] / "themes"
        theme_filename = stream_theme.value
        if not theme_filename.endswith(".toml"):
            theme_filename = f"{theme_filename}.toml"
        theme_path = themes_dir / theme_filename

        try:
            theme_dict = load_theme_from_file(theme_path)
        except Exception:
            fallback_path = themes_dir / "afterglow.toml"
            theme_dict = load_theme_from_file(fallback_path)
            theme_path = fallback_path

        styles = get_default_styles(theme_dict)
        formatter.styles = styles
        try:
            syntax_theme = load_syntax_theme_from_file(theme_path)
            formatter.syntax_style = create_pygments_syntax_theme(syntax_theme)
        except Exception:
            formatter.syntax_style = None

        model_label = getattr(agent, "model", None) or self.config.model or ""
        agent_label = (
            agent.name if not model_label else f"{agent.name} - {model_label}"
        )

        return formatter, theme_dict, styles, agent_label

    def filter_thought_process(
        self, result_dict: dict[str, Any], include_thought_process: bool
    ) -> dict[str, Any]:
        """Filter out thought process from the result dictionary (from original implementation)."""
        if include_thought_process:
            return result_dict
        else:
            return {
                k: v
                for k, v in result_dict.items()
                if not (k.startswith("reasoning") or k.startswith("trajectory"))
            }

    def filter_reasoning(
        self, result_dict: dict[str, Any], include_reasoning: bool
    ) -> dict[str, Any]:
        """Filter out reasoning from the result dictionary."""
        if include_reasoning:
            return result_dict
        else:
            return {
                k: v
                for k, v in result_dict.items()
                if not (k.startswith("reasoning"))
            }
