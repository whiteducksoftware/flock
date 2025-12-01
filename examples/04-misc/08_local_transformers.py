"""Local Transformers Model Example.

Demonstrates running Flock agents with local Hugging Face models.
No API keys required - runs entirely on your hardware!

Usage:
    uv run python examples/04-misc/06_local_transformers.py

Requirements:
    - transformers (included in flock[semantic])
    - torch
    - A GPU with enough VRAM for your chosen model (or CPU with patience)

The model is downloaded automatically on first run and cached locally.
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock, flock_type


@flock_type
class Question(BaseModel):
    """A question to answer."""

    text: str = Field(description="The question to answer")

@flock_type
class Answer(BaseModel):
    """An answer to a question."""

    response: str = Field(description="The answer to the question")
    confidence: str = Field(
        description="How confident the model is: low, medium, or high"
    )


# Use a local quantized model - downloads automatically on first run
# This 4-bit quantized model runs well on consumer GPUs
flock = Flock(
    "transformers/unsloth/Qwen3-4B-Instruct-2507-bnb-4bit"
)

qa_agent = (
    flock.agent("qa_expert")
    .description("An expert at answering questions clearly and concisely")
    .consumes(Question)
    .publishes(Answer)
)


async def main():
    print("🤗 Local Transformers Example")
    print("=" * 40)
    print("Loading model (first run downloads it)...\n")

    question = Question(text="What is the blackboard pattern in software architecture?")
    print(f"Question: {question.text}\n")

    await flock.publish(question)
    await flock.run_until_idle()

    # Get the answer from the store
    answers = await flock.store.get_by_type(Answer)
    if answers:
        answer = answers[0]
        print(f"Answer: {answer.response}")
        print(f"Confidence: {answer.confidence}")
    else:
        print("No answer generated")


if __name__ == "__main__":
    asyncio.run(main())
