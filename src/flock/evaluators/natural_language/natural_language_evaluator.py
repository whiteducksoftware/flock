from typing import Any

from flock.core.flock_evaluator import FlockEvaluator


class NaturalLanguageEvaluator(FlockEvaluator):
    """Evaluator that uses natural language prompting."""

    name: str = "natural_language"
    prompt_template: str = ""
    client: Any = None  # OpenAI client

    async def setup(self, input_schema: str, output_schema: str) -> None:
        """Set up prompt template and client."""
        from openai import AsyncOpenAI

        # Create prompt template
        self.prompt_template = f"""
        You are an AI assistant that processes inputs and generates outputs.
        
        Input Format:
        {input_schema}
        
        Required Output Format:
        {output_schema}
        
        Please process the following input and provide output in the required format:
        {{input}}
        """

        # Set up client
        self.client = AsyncOpenAI()

    async def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Evaluate using natural language."""
        if not self.client:
            raise RuntimeError("Evaluator not set up")

        # Format input for prompt
        input_str = "\n".join(f"{k}: {v}" for k, v in inputs.items())

        # Get completion
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=[
                {
                    "role": "user",
                    "content": self.prompt_template.format(input=input_str),
                }
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        # Parse response into dictionary
        try:
            import json

            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {"result": response.choices[0].message.content}

    async def cleanup(self) -> None:
        """Close client."""
        if self.client:
            await self.client.close()
