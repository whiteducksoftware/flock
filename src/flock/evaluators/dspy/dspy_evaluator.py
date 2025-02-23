from typing import Any

from flock.core.flock_evaluator import FlockEvaluator


class DSPyEvaluator(FlockEvaluator):
    """Evaluator that uses DSPy for generation."""

    name: str = "dspy"
    signature: Any = None  # DSPy signature
    predictor: Any = None  # DSPy predictor

    async def setup(self, input_schema: str, output_schema: str) -> None:
        """Set up DSPy signature and predictor."""
        import dspy

        # Create signature class
        self.signature = dspy.TypedPredictor(
            input_schema=input_schema,
            output_schema=output_schema,
        )

        # Configure model
        dspy.configure(
            lm=dspy.OpenAI(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
        )

        # Create predictor
        self.predictor = self.signature()

    async def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Evaluate using DSPy."""
        if not self.predictor:
            raise RuntimeError("Evaluator not set up")

        result = self.predictor(**inputs)
        return result.to_dict()

    async def cleanup(self) -> None:
        """Nothing to clean up for DSPy."""
        pass
