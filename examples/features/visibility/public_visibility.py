"""
Feature Example: Public Visibility

Validates: PublicVisibility - all agents can see public artifacts
"""

import asyncio

from pydantic import BaseModel, Field

from flock.artifacts import Artifact
from flock.components import EngineComponent
from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.runtime import EvalInputs, EvalResult


@flock_type
class Message(BaseModel):
    """Simple message for testing."""

    content: str = Field(description="Message content")


class EchoEngine(EngineComponent):
    """Mock engine that echoes input with a prefix."""

    prefix: str = "Processed"

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        if inputs.artifacts:
            original = inputs.artifacts[0]
            model = Message(**original.payload)
            return EvalResult(
                artifacts=[
                    Artifact(
                        type="Message",
                        payload={"content": f"{self.prefix}: {model.content}"},
                        produced_by=agent.name,
                        visibility=original.visibility,
                    )
                ],
                state={},
            )
        return EvalResult(artifacts=[], state={})


async def main():
    print("🔒 Feature: Public Visibility\n")

    orchestrator = Flock()

    # Create two agents that only consume external messages
    _ = (
        orchestrator.agent("agent_a")
        .description("First agent")
        .consumes(Message, from_agents=["__direct__"])
        .publishes(Message)
        .with_engines(EchoEngine(prefix="A-processed"))
    )

    _ = (
        orchestrator.agent("agent_b")
        .description("Second agent")
        .consumes(Message, from_agents=["__direct__"])
        .publishes(Message)
        .with_engines(EchoEngine(prefix="B-processed"))
    )

    # Publish public message (default visibility is Public)
    public_msg = Message(content="Public announcement")
    await orchestrator.publish(public_msg)

    await orchestrator.run_until_idle()

    # Verify both agents saw and processed the public artifact
    messages = await orchestrator.store.list_by_type("Message")
    agent_a_outputs = [m for m in messages if m.produced_by == "agent_a"]
    agent_b_outputs = [m for m in messages if m.produced_by == "agent_b"]

    print(f"Total messages: {len(messages)}")
    print(f"Agent A outputs: {len(agent_a_outputs)}")
    print(f"Agent B outputs: {len(agent_b_outputs)}")

    # ASSERTIONS
    assert len(messages) == 3, f"Expected 3 messages (external + 2 agents), got {len(messages)}"
    assert len(agent_a_outputs) == 1, f"Agent A should process once, got {len(agent_a_outputs)}"
    assert len(agent_b_outputs) == 1, f"Agent B should process once, got {len(agent_b_outputs)}"

    print("\n✅ All assertions passed!")
    print("✅ Public visibility: Both agents saw the same artifact")


if __name__ == "__main__":
    asyncio.run(main())
