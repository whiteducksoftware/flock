from typing import Any

from pydantic import Field

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.mixin.prompt_parser import PromptParserMixin


class DeclarativeEvaluatorConfig(FlockEvaluatorConfig):
    """Configuration for the DeclarativeEvaluator."""

    agent_type_override: str | None = None
    model: str | None = "openai/gpt-4o"
    use_cache: bool = True
    temperature: float = 0.0
    max_tokens: int = 4096


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
        """Evaluate using DSPy."""
        _dspy_signature = self.create_dspy_signature_class(
            agent.name,
            agent.description,
            f"{agent.input} -> {agent.output}",
        )
        self._configure_language_model(
            model=self.config.model,
            use_cache=self.config.use_cache,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        agent_task = self._select_task(
            _dspy_signature,
            agent_type_override=self.config.agent_type_override,
            tools=tools,
        )
        # Execute the task.
        result = agent_task(**inputs)
        result = self._process_result(result, inputs)
        return result
