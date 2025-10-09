#!/usr/bin/env python
"""
Example: Configure Flock Flow to use Ollama running on localhost:1134

This example demonstrates how to configure the framework to connect to your
local Ollama instance with the granite3.3:2b model.
"""

import asyncio
import os

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


# Define your artifact types
@flock_type
class Question(BaseModel):
    """A question to be answered."""

    text: str = Field(description="The question text")


@flock_type
class Answer(BaseModel):
    """An answer to a question."""

    text: str = Field(description="The answer text")


async def main():
    """Run the example with Ollama configuration."""

    # ============================================================
    # METHOD 1: Using Environment Variables (Recommended)
    # ============================================================
    # Set these before running the script:
    # export TRELLIS_MODEL="ollama/granite3.3:2b"
    # export OLLAMA_API_BASE="http://localhost:11434"

    # ============================================================
    # METHOD 2: Set the Variables manually
    # ============================================================
    os.environ["DEFAULT_MODEL"] = "ollama/granite3.3:2b"
    os.environ["OLLAMA_API_BASE"] = "http://localhost:11434"

    # Create the Flock orchestrator
    # The model can also be passed directly here:
    orchestrator = Flock("ollama/granite3.3:2b")

    # Create an agent that answers questions
    answerer = (
        orchestrator.agent("answerer")
        .description("Answer questions concisely and accurately")
        .consumes(Question)
        .publishes(Answer)
    )

    # Create a test question
    question = Question(text="What is the capital of France?")

    print("🚀 Running agent with Ollama configuration...")
    print("   Model: ollama/granite3.3:2b")
    print("   API Base: http://localhost:11434")
    print("   Question: {question.text}")

    try:
        question = Question(text="Who is the author of the lord of the rings trilogy?")
        await orchestrator.publish(question)
        await orchestrator.run_until_idle()


        # Print the results
        print("✅ Agent execution completed!")

    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("💡 Troubleshooting:")
        print("   1. Ensure Ollama is running: ollama serve")
        print("   2. Verify the model is available: ollama list")
        print("   3. Pull the model if needed: ollama pull granite3.3:2b")
        print("   4. Check that Ollama is running on port 1134")
        print("      Default is 11434, so you may need to start it with:")
        print("      OLLAMA_HOST=0.0.0.0:1134 ollama serve")


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
