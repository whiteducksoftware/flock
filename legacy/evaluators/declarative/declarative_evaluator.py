from collections.abc import Generator
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    import dspy

from pydantic import Field, PrivateAttr

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.flock_registry import flock_component
from flock.core.logging.logging import get_logger
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.mixin.prompt_parser import PromptParserMixin

logger = get_logger("evaluators.declarative")


class DeclarativeEvaluatorConfig(FlockEvaluatorConfig):
    """Configuration for the DeclarativeEvaluator."""

    override_evaluator_type: str | None = None
    model: str | None = "openai/gpt-4o"
    use_cache: bool = True
    temperature: float = 0.0
    max_tokens: int = 4096
    max_retries: int = 3
    max_tool_calls: int = 10
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
    kwargs: dict[str, Any] = Field(default_factory=dict)


@flock_component(config_class=DeclarativeEvaluatorConfig)
class DeclarativeEvaluator(
    FlockEvaluator, DSPyIntegrationMixin, PromptParserMixin
):
    """Evaluator that uses DSPy for generation."""

    config: DeclarativeEvaluatorConfig = Field(
        default_factory=DeclarativeEvaluatorConfig,
        description="Evaluator configuration",
    )

    _cost: float = PrivateAttr(default=0.0)
    _lm_history: list = PrivateAttr(default_factory=list)

    # def __init__(self, name: str, config: DeclarativeEvaluatorConfig) -> None:
    #     super().__init__(name=name, config=config)
    # self._configure_language_model(
    #     model=config.model,
    #     use_cache=config.use_cache,
    #     temperature=config.temperature,
    #     max_tokens=config.max_tokens,
    # )

    async def evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        tools: list[Any],
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate using DSPy, with optional asynchronous streaming."""
        # --- Setup Signature and LM ---

        with dspy.context(
            lm=dspy.LM(
                model=self.config.model or agent.model,
                cache=self.config.use_cache,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                num_retries=self.config.max_retries,
            )
        ):
            try:
                from rich.console import Console

                console = Console()
                _dspy_signature = self.create_dspy_signature_class(
                    agent.name,
                    agent.description,
                    f"{agent.input} -> {agent.output}",
                )
                # --- Get output field names ---
                # dspy.Signature holds fields in .output_fields attribute
                output_field_names = list(_dspy_signature.output_fields.keys())
                if not output_field_names:
                    logger.warning(
                        f"DSPy signature for agent '{agent.name}' has no defined output fields. Streaming might not produce text."
                    )
                # -----------------------------

                agent_task = self._select_task(
                    _dspy_signature,
                    override_evaluator_type=self.config.override_evaluator_type,
                    tools=tools,
                    max_tool_calls=self.config.max_tool_calls,
                    mcp_tools=mcp_tools,
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

            # --- Conditional Evaluation (Stream vs No Stream) ---
            if self.config.stream:
                logger.info(
                    f"Evaluating agent '{agent.name}' with async streaming."
                )
                if not callable(agent_task):
                    logger.error("agent_task is not callable, cannot stream.")
                    raise TypeError(
                        "DSPy task could not be created or is not callable."
                    )

                streaming_task = dspy.streamify(
                    agent_task, is_async_program=True
                )
                stream_generator: Generator = streaming_task(**inputs)
                delta_content = ""

                console.print("\n")
                async for chunk in stream_generator:
                    if (
                        hasattr(chunk, "choices")
                        and chunk.choices
                        and hasattr(chunk.choices[0], "delta")
                        and chunk.choices[0].delta
                        and hasattr(chunk.choices[0].delta, "content")
                    ):
                        delta_content = chunk.choices[0].delta.content

                    if delta_content:
                        console.print(delta_content, end="")

                    result_dict, cost, lm_history = self._process_result(
                        chunk, inputs
                    )
                    self._cost = cost
                    self._lm_history = lm_history

                console.print("\n")
                result_dict = self.filter_reasoning(
                    result_dict, self.config.include_reasoning
                )
                return self.filter_thought_process(
                    result_dict, self.config.include_thought_process
                )

            else:  # Non-streaming path
                logger.info(
                    f"Evaluating agent '{agent.name}' without streaming."
                )
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

    def filter_thought_process(
        self, result_dict: dict[str, Any], include_thought_process: bool
    ) -> dict[str, Any]:
        """Filter out thought process from the result dictionary."""
        if include_thought_process:
            return result_dict
        else:
            return {
                k: v
                for k, v in result_dict.items()
                if not (k.startswith("trajectory"))
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
