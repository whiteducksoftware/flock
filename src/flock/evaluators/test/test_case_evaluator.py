from typing import Any

from pydantic import Field

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin


class TestCaseEvaluatorConfig(FlockEvaluatorConfig):
    """Configuration for the TestCaseEvaluator."""

    pass


class TestCaseEvaluator(FlockEvaluator, DSPyIntegrationMixin):
    """Evaluator for test cases."""

    config: TestCaseEvaluatorConfig = Field(
        default_factory=TestCaseEvaluatorConfig,
        description="Evaluator configuration",
    )

    async def evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any], tools: list[Any]
    ) -> dict[str, Any]:
        _dspy_signature = self.create_dspy_signature_class(
            agent.name,
            agent.description,
            f"{agent.input} -> {agent.output}",
        )
        output_field_names = list(_dspy_signature.output_fields.keys())
        result = {}
        for output_field_name in output_field_names:
            result[output_field_name] = "Test Result"
        return result
