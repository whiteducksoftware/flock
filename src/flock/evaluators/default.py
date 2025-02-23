from typing import Any

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin


class DefaultEvaluator(FlockEvaluator, DSPyIntegrationMixin):
    """Evaluator that uses DSPy for generation."""

    async def evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate using DSPy."""
        self.__dspy_signature = self.create_dspy_signature_class(
            self.name,
            agent.description,
            f"{agent.input} -> {agent.output}",
        )
        self._configure_language_model()
        agent_task = self._select_task(
            self.__dspy_signature,
            agent_type_override=agent.config.agent_type_override,
        )
        # Execute the task.
        result = agent_task(**inputs)
        result = self._process_result(result, inputs)
        return result
