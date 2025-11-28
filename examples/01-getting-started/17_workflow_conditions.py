"""
Example 17: Workflow Control with Conditions

This example demonstrates Flock's powerful condition DSL for controlling
workflow execution. Instead of just waiting for all work to complete,
you can specify exactly when to stop.

Key concepts:
    - run_until() vs run_until_idle()
    - Until helper for termination conditions
    - Condition composition with &, |, ~
    - Timeout handling

Run:
    uv run python examples/01-getting-started/17_workflow_conditions.py
"""

import asyncio
import uuid

from pydantic import BaseModel

from flock import Flock, flock_type
from flock.core.conditions import Until


@flock_type
class ResearchQuestion(BaseModel):
    """A question to research."""

    topic: str
    max_hypotheses: int = 5


@flock_type
class Hypothesis(BaseModel):
    """A research hypothesis with confidence score."""

    content: str
    confidence: float  # 0.0 to 1.0
    reasoning: str


async def main():
    """Demonstrate workflow control with conditions."""
    print("=" * 70)
    print("Flock Workflow Control with Conditions")
    print("=" * 70)

    # Create Flock instance
    flock = Flock()

    # Define research agents
    # Hypothesis generator - produces multiple hypotheses
    flock.agent("hypothesis_generator").description(
        "Generates research hypotheses about a topic. "
        "For each question, generate multiple hypotheses with varying confidence levels."
    ).consumes(ResearchQuestion).publishes(Hypothesis, fan_out=5)

    # NOTE: For multi-agent workflows with fan_out, you might add a report_writer:
    #   flock.agent("report_writer").consumes(
    #       Hypothesis,
    #       batch=BatchSpec(size=5),  # Collect all 5 before processing
    #   ).publishes(FinalReport)
    # This demo focuses on Until conditions (termination control), not batching.
    # See examples/02-patterns for batch and join patterns.

    # Generate a correlation ID to track this workflow
    correlation_id = str(uuid.uuid4())

    # =========================================================================
    # Example 1: Stop when we have enough results
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 1: Stop after 3 hypotheses")
    print("=" * 70)

    # Publish research question
    await flock.publish(
        ResearchQuestion(
            topic="What causes the Northern Lights?",
            max_hypotheses=10,
        ),
        correlation_id=correlation_id,
    )

    # Wait until we have at least 3 hypotheses
    condition = Until.artifact_count(Hypothesis, correlation_id=correlation_id).at_least(
        3
    )

    print("\nRunning workflow with condition: 'at least 3 hypotheses'...")
    success = await flock.run_until(condition, timeout=60.0)

    if success:
        print("Condition met! We have 3+ hypotheses.")
    else:
        print("Timeout reached before condition was met.")

    # Check how many we actually got
    artifacts = await flock.store.get_by_type(Hypothesis, correlation_id=correlation_id)
    print(f"Total hypotheses generated: {len(artifacts)}")

    # =========================================================================
    # Example 2: Stop on high-confidence result
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 2: Stop when confidence >= 0.9")
    print("=" * 70)

    # New correlation for fresh run
    correlation_id_2 = str(uuid.uuid4())

    await flock.publish(
        ResearchQuestion(
            topic="Why is the sky blue?",
            max_hypotheses=10,
        ),
        correlation_id=correlation_id_2,
    )

    # Stop when ANY hypothesis has confidence >= 0.9
    high_confidence = Until.any_field(
        Hypothesis,
        field="confidence",
        predicate=lambda v: v is not None and v >= 0.9,
        correlation_id=correlation_id_2,
    )

    print("\nRunning workflow with condition: 'any hypothesis with confidence >= 0.9'...")
    success = await flock.run_until(high_confidence, timeout=60.0)

    if success:
        # Find the high-confidence hypothesis
        # Note: get_by_type returns Pydantic model instances, not Artifact wrappers
        artifacts = await flock.store.get_by_type(
            Hypothesis, correlation_id=correlation_id_2
        )
        for a in artifacts:
            if a.confidence >= 0.9:
                print(f"Found high-confidence hypothesis: {a.content[:60]}...")
                print(f"Confidence: {a.confidence:.2f}")
                break
    else:
        print("No high-confidence hypothesis found within timeout.")

    # =========================================================================
    # Example 3: Composite conditions with |, &
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 3: Composite conditions (5 results OR high confidence)")
    print("=" * 70)

    correlation_id_3 = str(uuid.uuid4())

    await flock.publish(
        ResearchQuestion(
            topic="What makes honey never spoil?",
            max_hypotheses=10,
        ),
        correlation_id=correlation_id_3,
    )

    # Stop when EITHER:
    # - We have 5 hypotheses, OR
    # - Any hypothesis has confidence >= 0.9
    composite_condition = (
        Until.artifact_count(Hypothesis, correlation_id=correlation_id_3).at_least(5)
        | Until.any_field(
            Hypothesis,
            field="confidence",
            predicate=lambda v: v is not None and v >= 0.9,
            correlation_id=correlation_id_3,
        )
    )

    print("\nRunning workflow with composite condition...")
    print("  Stop when: (5+ hypotheses) OR (any confidence >= 0.9)")
    success = await flock.run_until(composite_condition, timeout=60.0)

    if success:
        artifacts = await flock.store.get_by_type(
            Hypothesis, correlation_id=correlation_id_3
        )
        print(f"Condition met! Total hypotheses: {len(artifacts)}")

        # Check which sub-condition was satisfied
        # Note: artifacts are Pydantic models, access fields directly
        has_high_conf = any(a.confidence >= 0.9 for a in artifacts)
        if has_high_conf:
            print("  Reason: High-confidence hypothesis found")
        else:
            print("  Reason: Reached 5 hypotheses")
    else:
        print("Timeout reached before either condition was met.")

    # =========================================================================
    # Example 4: Comparison with run_until_idle()
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 4: run_until() vs run_until_idle()")
    print("=" * 70)

    print("""
    run_until_idle():
        - Waits for ALL agents to complete
        - No early termination
        - Best for: "Let everything finish"

    run_until(condition):
        - Stops when condition is True
        - Enables early termination
        - Best for: "Stop at specific milestone"

    Common patterns:
        # Wait for results AND system to settle
        await flock.run_until(
            Until.artifact_count(Result).at_least(5) & Until.idle()
        )

        # Stop at results OR error OR timeout
        await flock.run_until(
            Until.artifact_count(Result).at_least(5)
            | Until.workflow_error(cid),
            timeout=60
        )
    """)

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("Summary: Available Until Conditions")
    print("=" * 70)
    print(
        """
    Until.idle()                        - No pending work
    Until.artifact_count(Model)         - Count-based (at_least, at_most, exactly)
    Until.exists(Model)                 - Any artifact of type exists
    Until.none(Model)                   - No artifacts of type exist
    Until.any_field(Model, field, fn)   - Field value matches predicate
    Until.workflow_error(cid)           - Error occurred in workflow

    Composition:
        condition1 & condition2         - Both must be True
        condition1 | condition2         - Either must be True
        ~condition                      - Inverts condition

    For more details, see: docs/guides/workflow-control.md
    """
    )


if __name__ == "__main__":
    asyncio.run(main())
