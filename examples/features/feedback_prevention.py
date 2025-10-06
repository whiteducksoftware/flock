"""Example demonstrating feedback loop prevention in Flock-Flow.

Shows how the framework prevents infinite self-triggering when an agent
consumes and publishes the same artifact type.
"""

import asyncio

from pydantic import BaseModel, Field

from flock.components import EngineComponent
from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.runtime import EvalInputs


@flock_type
class Document(BaseModel):
    """A document that can be processed."""

    content: str = Field(description="Document content")
    version: int = Field(default=1, description="Processing version")
    depth: int = Field(default=0, description="Recursion depth")


class DocumentProcessor(EngineComponent):
    """Mock engine that increments document version."""

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> Document:
        doc = inputs.first_as(Document)
        return Document(
            content=f"{doc.content} [processed]",
            version=doc.version + 1,
            depth=doc.depth + 1,
        )


async def main():
    print("🔒 Feedback Loop Prevention Demo\n")

    # Example 1: Safe by default (prevent_self_trigger=True)
    print("Example 1: Safe Agent (prevents self-triggering)")
    print("=" * 60)

    orchestrator = Flock()

    (
        orchestrator.agent("safe_processor")
        .description("Process documents but don't trigger on own outputs")
        .consumes(Document)
        .publishes(Document)
        .with_engines(DocumentProcessor())
        # prevent_self_trigger=True by default
    )

    # Publish initial document - use publish() not arun()
    initial_doc = Document(content="Initial document", version=1, depth=0)
    await orchestrator.publish(initial_doc)
    await orchestrator.run_until_idle()

    # Check results
    artifacts = await orchestrator.store.list_by_type("Document")
    print(f"Total documents: {len(artifacts)}")
    print("No infinite loop! Agent executed once for external input only.\n")

    assert len(artifacts) == 2, f"Expected 2 documents (input + processed), got {len(artifacts)}"

    # Example 2: Controlled feedback with depth limit
    print("\nExample 2: Controlled Feedback (with depth limit)")
    print("=" * 60)

    orchestrator2 = Flock()

    (
        orchestrator2.agent("recursive")
        .description("Process documents recursively up to depth 3")
        .consumes(Document, where=lambda d: d.depth < 3)  # Predicate limit
        .publishes(Document)
        .with_engines(DocumentProcessor())
        .prevent_self_trigger(False)  # Explicitly allow feedback
    )

    seed_doc = Document(content="Seed document", version=1, depth=0)
    await orchestrator2.publish(seed_doc)
    await orchestrator2.run_until_idle()

    artifacts2 = await orchestrator2.store.list_by_type("Document")
    print(f"Total documents: {len(artifacts2)}")
    print("Controlled feedback: Stopped at depth limit (depth < 3)")
    print("Circuit breaker provides failsafe (max 1000 iterations)\n")

    # Seed (depth=0) -> v2 (depth=1) -> v3 (depth=2) -> v4 (depth=3, filtered)
    assert len(artifacts2) == 4, f"Expected 4 documents (depths 0-2 + input), got {len(artifacts2)}"

    # Example 3: Circuit breaker protection
    print("\nExample 3: Circuit Breaker Protection")
    print("=" * 60)

    orchestrator3 = Flock(max_agent_iterations=5)

    (
        orchestrator3.agent("unlimited")
        .description("Tries to loop forever but circuit breaker stops it")
        .consumes(Document)  # No depth limit!
        .publishes(Document)
        .with_engines(DocumentProcessor())
        .prevent_self_trigger(False)  # Allow feedback
    )

    loop_seed = Document(content="Loop seed", version=1, depth=0)
    await orchestrator3.publish(loop_seed)
    await orchestrator3.run_until_idle()

    artifacts3 = await orchestrator3.store.list_by_type("Document")
    print(f"Circuit breaker stopped agent at {orchestrator3.max_agent_iterations} iterations")
    print("Prevented infinite loop even without depth limit")
    print(f"Total artifacts: {len(artifacts3)}\n")

    # Input artifact + 10 iterations = 11 total
    assert len(artifacts3) == orchestrator3.max_agent_iterations + 1, (
        f"Expected 11 documents (circuit breaker limit), got {len(artifacts3)}"
    )

    print("🎯 Summary:")
    print("- Default prevent_self_trigger=True keeps agents safe")
    print("- Explicit .prevent_self_trigger(False) for intentional feedback")
    print("- Always add limits (where clause, depth checks)")
    print("- Circuit breaker provides automatic failsafe")


if __name__ == "__main__":
    asyncio.run(main())
