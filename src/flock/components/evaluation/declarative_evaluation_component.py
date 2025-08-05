# src/flock/components/evaluation/declarative_evaluation_component.py
"""DeclarativeEvaluationComponent - DSPy-based evaluation using the unified component system."""

from collections.abc import Generator
from typing import Any

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


class DeclarativeEvaluationConfig(AgentComponentConfig):
    """Configuration for the DeclarativeEvaluationComponent."""

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

    async def evaluate_core(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Core evaluation logic using DSPy - migrated from DeclarativeEvaluator."""
        logger.debug(f"Starting declarative evaluation for component '{self.name}'")

        # Setup DSPy context with LM (directly from original implementation)
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
                return await self._execute_streaming(agent_task, inputs, agent, console)
            else:
                return await self._execute_standard(agent_task, inputs, agent)

    async def _execute_streaming(self, agent_task, inputs: dict[str, Any], agent: Any, console) -> dict[str, Any]:
        """Execute DSPy program in streaming mode (from original implementation)."""
        logger.info(f"Evaluating agent '{agent.name}' with async streaming.")

        if not callable(agent_task):
            logger.error("agent_task is not callable, cannot stream.")
            raise TypeError("DSPy task could not be created or is not callable.")

        streaming_task = dspy.streamify(agent_task, is_async_program=True)
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

            result_dict, cost, lm_history = self._process_result(chunk, inputs)
            self._cost = cost
            self._lm_history = lm_history

        console.print("\n")
        result_dict = self.filter_reasoning(
                    result_dict, self.config.include_reasoning
                )
        return self.filter_thought_process(
            result_dict, self.config.include_thought_process
        )

    async def _execute_standard(self, agent_task, inputs: dict[str, Any], agent: Any) -> dict[str, Any]:
        """Execute DSPy program in standard mode (from original implementation)."""
        logger.info(f"Evaluating agent '{agent.name}' without streaming.")

        try:
            # Ensure the call is awaited if the underlying task is async
            result_obj = await agent_task.acall(**inputs)
            result_dict, cost, lm_history = self._process_result(result_obj, inputs)
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

