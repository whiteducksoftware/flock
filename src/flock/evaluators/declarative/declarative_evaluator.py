from collections.abc import Generator
from typing import Any

import dspy
from pydantic import Field
from rich.console import Console

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.logging.logging import get_logger
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.mixin.prompt_parser import PromptParserMixin

console = Console()

logger = get_logger("evaluators.declarative")


class DeclarativeEvaluatorConfig(FlockEvaluatorConfig):
    """Configuration for the DeclarativeEvaluator."""

    agent_type_override: str | None = None
    model: str | None = "openai/gpt-4o"
    use_cache: bool = True
    temperature: float = 0.0
    max_tokens: int = 4096
    stream: bool = Field(
        default=False,
        description="Enable streaming output from the underlying DSPy program.",
    )


class DeclarativeEvaluator(
    FlockEvaluator, DSPyIntegrationMixin, PromptParserMixin
):
    """Evaluator that uses DSPy for generation."""

    config: DeclarativeEvaluatorConfig = Field(
        default_factory=DeclarativeEvaluatorConfig,
        description="Evaluator configuration",
    )

    async def evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any], tools: list[Any]
    ) -> dict[str, Any]:
        """Evaluate using DSPy, with optional asynchronous streaming."""
        # --- Setup Signature and LM ---
        try:
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

            self._configure_language_model(
                model=self.config.model or agent.model,
                use_cache=self.config.use_cache,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            agent_task = self._select_task(
                _dspy_signature,
                agent_type_override=self.config.agent_type_override,
                tools=tools,
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

            streaming_task = dspy.streamify(agent_task)
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

                result_dict = self._process_result(chunk, inputs)

            console.print("\n")
            return result_dict

        else:  # Non-streaming path
            logger.info(f"Evaluating agent '{agent.name}' without streaming.")
            try:
                # Ensure the call is awaited if the underlying task is async
                result_obj = agent_task(**inputs)
                result_dict = self._process_result(result_obj, inputs)
                return result_dict
            except Exception as e:
                logger.error(
                    f"Error during non-streaming evaluation for agent '{agent.name}': {e}",
                    exc_info=True,
                )
                raise RuntimeError(f"Evaluation failed: {e}") from e
