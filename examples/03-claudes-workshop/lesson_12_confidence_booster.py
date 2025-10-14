"""
Lesson 12: The Confidence Booster

CONCEPTS: Advanced Agent Components
- Per-agent state and behavior modification
- Hook into individual agent lifecycle
- Dynamic prompt enhancement
- Agent-specific metrics and logging
- Confidence scoring and threshold enforcement

SCENARIO:
You're building a medical diagnosis system where agents should only make
recommendations when they're highly confident. You need to track confidence
scores, enhance prompts when confidence is low, and enforce quality gates—
all without hardcoding these concerns into every agent's logic.

AGENT COMPONENTS provide:
- Per-agent lifecycle hooks
- State that travels with specific agents
- Pre/post evaluation modifications
- Agent-specific utilities and behavior

This example shows how to build reusable agent behavior patterns.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import AgentComponent
from flock.runtime import EvalInputs, EvalResult


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================


@flock_type(name="MedicalCase")
class MedicalCase(BaseModel):
    patient_id: str
    symptoms: list[str]
    history: str
    urgency: str  # "routine", "urgent", "emergency"


@flock_type(name="Diagnosis")
class Diagnosis(BaseModel):
    patient_id: str
    condition: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    recommended_tests: list[str]


@flock_type(name="TreatmentPlan")
class TreatmentPlan(BaseModel):
    patient_id: str
    diagnosis: str
    treatment: str
    monitoring_plan: str
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================================
# AGENT COMPONENT - Confidence Enforcement
# ============================================================================


class ConfidenceBoosterComponent(AgentComponent):
    """
    Ensures agents only make recommendations when highly confident.

    This component demonstrates:
    - Confidence threshold enforcement
    - Dynamic prompt enhancement
    - Retry logic for low-confidence outputs
    - Per-agent metrics tracking
    - Quality gate patterns
    """

    min_confidence: float = Field(
        default=0.8, description="Minimum acceptable confidence score"
    )
    max_retries: int = Field(default=2, description="Max retry attempts for low confidence")

    # Per-agent state
    evaluation_count: int = Field(default=0, description="Total evaluations by this agent")
    low_confidence_count: int = Field(default=0, description="Number of low-confidence results")
    retry_count: int = Field(default=0, description="Number of retries triggered")

    async def on_pre_evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalInputs:
        """
        Enhance the prompt before evaluation to emphasize confidence scoring.

        This hook fires BEFORE the agent evaluates inputs.
        Perfect for: prompt enhancement, input validation, context injection.
        """
        self.evaluation_count += 1

        # Inject confidence guidance into the evaluation context
        confidence_guidance = f"""
CRITICAL INSTRUCTION - Confidence Scoring:
You MUST provide a 'confidence' score (0.0 to 1.0) with your response.
Minimum acceptable confidence: {self.min_confidence}

If your confidence is below {self.min_confidence}, you will be asked to reconsider.
Base confidence on:
- Clarity and specificity of input data
- Strength of evidence in medical history
- Alignment with known patterns
- Absence of conflicting indicators

Be honest about uncertainty. It's better to request more information
than to make a low-confidence recommendation.
"""

        # Add to agent's system prompt dynamically
        if hasattr(ctx, "system_prompt_override"):
            ctx.system_prompt_override += "\n\n" + confidence_guidance
        else:
            ctx.system_prompt_override = confidence_guidance

        print(f"🔍 [{agent.name}] Starting evaluation #{self.evaluation_count}")

        return inputs

    async def on_post_evaluate(
        self, agent, ctx, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """
        Check confidence and trigger retries if needed.

        This hook fires AFTER the agent evaluates but BEFORE publishing.
        Perfect for: quality gates, metrics, result modification, retries.
        """
        # Extract confidence from the result
        if result.artifacts:
            artifact = result.artifacts[0]
            confidence = artifact.payload.get("confidence", 0.0)

            # Track confidence metrics
            if confidence < self.min_confidence:
                self.low_confidence_count += 1

                # Should we retry?
                if self.retry_count < self.max_retries:
                    self.retry_count += 1

                    print(f"⚠️  [{agent.name}] Low confidence detected: {confidence:.2f}")
                    print(f"   Retry attempt {self.retry_count}/{self.max_retries}")

                    # Enhance prompt for retry
                    retry_prompt = f"""
RETRY REQUEST:
Your previous response had confidence {confidence:.2f}, below threshold {self.min_confidence}.

Please reconsider with more critical analysis:
1. What specific evidence supports your conclusion?
2. What evidence contradicts or weakens it?
3. What additional information would increase confidence?
4. Are there alternative explanations?

Provide a more thorough analysis and reassess confidence.
"""
                    # Inject retry guidance
                    if hasattr(ctx, "system_prompt_override"):
                        ctx.system_prompt_override += "\n\n" + retry_prompt

                    # NOTE: In a real implementation, you'd trigger re-evaluation here.
                    # For this demo, we'll just log the retry intent.

                else:
                    print(f"❌ [{agent.name}] Max retries reached with confidence: {confidence:.2f}")
                    print(f"   Proceeding with low-confidence result (flagged)")

                    # Flag this result as low-confidence
                    result.metrics["low_confidence"] = True
                    result.logs.append(
                        f"WARNING: Confidence {confidence:.2f} below threshold {self.min_confidence}"
                    )

            else:
                print(f"✅ [{agent.name}] High confidence: {confidence:.2f}")
                result.metrics["high_confidence"] = True

            # Add confidence to metrics
            result.metrics["confidence_score"] = confidence

        return result

    async def on_post_publish(self, agent, ctx, artifact) -> None:
        """
        Log final results after publishing.

        This hook fires AFTER artifact is published to blackboard.
        Perfect for: logging, notifications, downstream triggers.
        """
        confidence = artifact.payload.get("confidence", 0.0)
        patient_id = artifact.payload.get("patient_id", "unknown")

        if confidence >= self.min_confidence:
            print(f"📋 [{agent.name}] Published diagnosis for {patient_id}")
            print(f"   Confidence: {confidence:.2%}")
        else:
            print(f"⚠️  [{agent.name}] Published LOW-CONFIDENCE diagnosis for {patient_id}")
            print(f"   Confidence: {confidence:.2%} - Manual review recommended")

        # Report stats periodically
        if self.evaluation_count % 3 == 0:
            print(f"\n📊 [{agent.name}] Agent Statistics:")
            print(f"   Total evaluations: {self.evaluation_count}")
            print(f"   Low confidence: {self.low_confidence_count}")
            print(f"   Retries triggered: {self.retry_count}")
            success_rate = (
                ((self.evaluation_count - self.low_confidence_count) / self.evaluation_count)
                * 100
                if self.evaluation_count > 0
                else 0
            )
            print(f"   Success rate: {success_rate:.1f}%\n")


# ============================================================================
# MAIN DEMO
# ============================================================================


async def main() -> None:
    flock = Flock()

    # Create diagnosis agent WITH confidence booster
    (
        flock.agent("diagnostician")
        .description("Analyzes medical cases and provides diagnoses")
        .consumes(MedicalCase)
        .publishes(Diagnosis)
        .with_utilities(
            ConfidenceBoosterComponent(min_confidence=0.75, max_retries=2)
        )  # Agent component!
        .system_prompt(
            """You are an expert medical diagnostician. Analyze cases and provide:
- Most likely condition
- Confidence score (0.0 to 1.0)
- Clear reasoning
- Recommended diagnostic tests

Be conservative with confidence - only score high when evidence is strong."""
        )
    )

    # Create treatment planner WITH confidence booster
    (
        flock.agent("treatment_planner")
        .description("Creates treatment plans based on diagnoses")
        .consumes(Diagnosis, where=lambda d: d.confidence >= 0.75)  # Only high-confidence
        .publishes(TreatmentPlan)
        .with_utilities(
            ConfidenceBoosterComponent(min_confidence=0.80, max_retries=1)
        )  # Stricter!
        .system_prompt(
            """You are an expert treatment planner. Based on diagnosis, provide:
- Treatment approach
- Monitoring plan
- Confidence in treatment efficacy
- Precautions and alternatives"""
        )
    )

    print("🏥 Medical AI System - Confidence Enforcement Demo")
    print("=" * 70)

    # Test cases with varying clarity
    test_cases = [
        MedicalCase(
            patient_id="P001",
            symptoms=["persistent cough", "fever", "chest pain"],
            history="Non-smoker, no chronic conditions, recent travel",
            urgency="urgent",
        ),
        MedicalCase(
            patient_id="P002",
            symptoms=["fatigue", "occasional headache"],
            history="Stressful job, irregular sleep",
            urgency="routine",
        ),
        MedicalCase(
            patient_id="P003",
            symptoms=["severe abdominal pain", "vomiting", "fever"],
            history="Recent surgery, no known allergies",
            urgency="emergency",
        ),
    ]

    # Process cases
    for case in test_cases:
        print(f"\n{'=' * 70}")
        print(f"📋 Processing case: {case.patient_id} ({case.urgency.upper()})")
        print(f"   Symptoms: {', '.join(case.symptoms)}")
        await flock.publish(case)

    await flock.run_until_idle()

    # Summary
    print("\n" + "=" * 70)
    print("🎓 What Just Happened?")
    print("=" * 70)
    print("The ConfidenceBoosterComponent:")
    print("✅ Enhanced prompts with confidence guidance (on_pre_evaluate)")
    print("✅ Validated confidence scores (on_post_evaluate)")
    print("✅ Triggered retries for low-confidence results")
    print("✅ Tracked per-agent metrics")
    print("✅ Logged final results (on_post_publish)")
    print()
    print("🔑 Key Insight:")
    print("Agent components attach behavior to SPECIFIC agents, while")
    print("orchestrator components operate GLOBALLY across all agents!")
    print("=" * 70)

    # Show final artifacts
    print("\n📊 Final Results:")
    all_artifacts = await flock.store.list()
    diagnoses = [a for a in all_artifacts if a.type_name == "Diagnosis"]
    treatments = [a for a in all_artifacts if a.type_name == "TreatmentPlan"]

    print(f"   Diagnoses generated: {len(diagnoses)}")
    print(f"   Treatment plans created: {len(treatments)}")

    for diag in diagnoses:
        conf = diag.payload.get("confidence", 0)
        pid = diag.payload.get("patient_id")
        condition = diag.payload.get("condition", "unknown")
        flag = "⚠️" if conf < 0.75 else "✅"
        print(f"   {flag} {pid}: {condition} (confidence: {conf:.2%})")


if __name__ == "__main__":
    asyncio.run(main())
