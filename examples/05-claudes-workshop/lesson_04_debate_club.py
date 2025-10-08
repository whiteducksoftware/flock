"""
🎭 LESSON 04: The Debate Club - Feedback Loops & Iterative Refinement
======================================================================

🎯 LEARNING OBJECTIVES:
----------------------
In this lesson, you'll learn:
1. How to build feedback loops where agents critique each other
2. How to use conditional consumption to control iterations
3. How prevent_self_trigger works (safety against infinite loops)
4. How to create iterative refinement systems

🎬 THE SCENARIO:
---------------
You're building a debate club AI where two agents engage in intellectual debate:
- The Debater proposes arguments
- The Critic evaluates them (harshly!)
- The Debater refines based on criticism
- This continues until the argument is convincing (score >= 9/10)

This demonstrates controlled feedback loops - a powerful pattern for
iterative improvement without infinite recursion.

⏱️  TIME: 20 minutes
💡 COMPLEXITY: ⭐⭐⭐ Advanced

Let's debate! 🎭👇
"""

import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 STEP 1: Define the Debate Artifacts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@flock_type
class DebateTopic(BaseModel):
    """
    SEED INPUT: What we're debating

    This triggers the initial argument from the debater.
    """

    topic: str = Field(description="The debate topic or thesis to argue")
    position: str = Field(
        description="Which side to argue: for or against",
        pattern="^(for|against)$",
    )
    context: str = Field(
        description="Additional context or constraints for the debate",
        default="General audience, academic tone",
    )


@flock_type
class Argument(BaseModel):
    """
    DEBATER OUTPUT → CRITIC INPUT: A structured argument

    The debater produces this, and the critic consumes it.
    This creates the first half of the feedback loop.
    """

    topic: str
    position: str
    thesis_statement: str = Field(
        description="Clear, concise thesis statement",
        min_length=50,
        max_length=200,
    )
    supporting_points: list[str] = Field(
        description="3-5 supporting arguments with evidence",
        min_length=3,
        max_length=5,
    )
    counterargument_addressed: str = Field(
        description="Acknowledgment and rebuttal of strongest counterargument"
    )
    conclusion: str = Field(description="Compelling conclusion that reinforces thesis")
    version: int = Field(
        description="Which iteration of the argument this is (starts at 1)",
        default=1,
    )


@flock_type
class Critique(BaseModel):
    """
    CRITIC OUTPUT → DEBATER INPUT: Harsh but constructive criticism

    The critic produces this, and the debater consumes it (if score < 9).
    This creates the second half of the feedback loop.

    🔥 THE FEEDBACK LOOP:
    Argument (v1) → Critique (score 6) → Argument (v2) → Critique (score 8) → Argument (v3) → Critique (score 9) → DONE!
    """

    score: int = Field(
        description="Quality score from 1-10 (be harsh!)",
        ge=1,
        le=10,
    )
    strengths: list[str] = Field(
        description="What's good about this argument",
        min_length=1,
        max_length=3,
    )
    weaknesses: list[str] = Field(
        description="Critical flaws and areas for improvement",
        min_length=1,
        max_length=5,
    )
    specific_suggestions: list[str] = Field(
        description="Actionable advice for improving the argument",
        min_length=2,
    )
    overall_assessment: str = Field(description="Summary judgment: is this argument convincing?")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 STEP 2: Create Orchestrator with Circuit Breaker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 💡 SAFETY FIRST: Feedback loops can be dangerous!
# We set max_agent_iterations to prevent runaway loops.
# If the agents don't converge, Flock will stop them automatically.

flock = Flock("openai/gpt-4.1", max_agent_iterations=20)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 STEP 3: Define the Debate Agents with Conditional Consumption
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🎤 Agent 1: The Debater
# Watches for: DebateTopic (initial) AND Critique (for refinement)
# Produces: Argument

debater = (
    flock.agent("debater")
    .description(
        "A skilled debater who constructs persuasive arguments. "
        "Can refine arguments based on critical feedback."
    )
    .consumes(DebateTopic)  # Initial trigger
    .consumes(
        Critique,
        where=lambda c: c.score < 9,  # 🔥 CONDITIONAL: Only if score is weak!
    )
    .publishes(Argument)
)

# 💡 WHAT'S HAPPENING WITH where=lambda c: c.score < 9?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# This is a PREDICATE - a filter function that determines whether to consume.
#
# Flow:
# 1. Critic publishes Critique with score=6
# 2. Flock checks: c.score < 9? → 6 < 9 → TRUE
# 3. Debater consumes it and refines the argument
#
# 4. Critic publishes Critique with score=9
# 5. Flock checks: c.score < 9? → 9 < 9 → FALSE
# 6. Debater does NOT consume it - loop ends!
#
# This is how we create CONTROLLED feedback loops without infinite recursion.

# 🎯 Agent 2: The Critic
# Watches for: Argument
# Produces: Critique

critic = (
    flock.agent("critic")
    .description(
        "A harsh but fair critic who evaluates arguments with high standards. "
        "Provides constructive feedback and scores arguments out of 10."
    )
    .consumes(Argument)
    .publishes(Critique)
    .prevent_self_trigger(True)  # 🔥 SAFETY: Don't trigger on own outputs
)

# 💡 WHY prevent_self_trigger(True)?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# This prevents the agent from consuming artifacts it produced itself.
# Without this, if an agent both consumes and publishes the same type,
# it could trigger infinite self-loops!
#
# Example danger without prevent_self_trigger:
#   Agent publishes Critique → Sees own Critique → Processes it again → Infinite loop!
#
# With prevent_self_trigger=True (default in Flock):
#   Agent publishes Critique → Flock filters out self-produced artifacts → Safe!

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 4: Run the Debate with Iteration Tracking
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    Watch a debate evolve through feedback:
    1. Debater makes initial argument
    2. Critic evaluates (usually harsh at first)
    3. Debater refines based on criticism
    4. Repeat until score >= 9
    5. Final polished argument emerges!
    """

    print("🎭 Starting The Debate Club...\n")

    # 🎯 Set the debate topic
    topic = DebateTopic(
        topic="Artificial intelligence will do more good than harm for humanity",
        position="for",
        context="University debate competition, educated audience, formal academic style",
    )

    print("=" * 70)
    print("📋 DEBATE SETUP")
    print("=" * 70)
    print(f"Topic: {topic.topic}")
    print(f"Position: Arguing {topic.position.upper()}")
    print(f"Context: {topic.context}")
    print("=" * 70)
    print()

    print("🎤 Debate is starting...")
    print("   (Watch as the argument improves through iteration)\n")

    # 📤 Publish the topic to start the debate
    await flock.publish(topic)

    # ⏳ Wait for the debate to conclude
    # The loop will run until the critic gives score >= 9
    await flock.run_until_idle()

    # 📊 Retrieve the debate history
    print("\n" + "=" * 70)
    print("📜 DEBATE TRANSCRIPT")
    print("=" * 70)

    arguments = await flock.store.get_artifacts_by_type("Argument")
    critiques = await flock.store.get_artifacts_by_type("Critique")

    # Show the evolution
    for i, (arg, crit) in enumerate(zip(arguments, critiques, strict=False), 1):
        arg_obj = arg.obj
        crit_obj = crit.obj

        print(f"\n{'─' * 70}")
        print(f"🔄 ITERATION {i}")
        print(f"{'─' * 70}")

        print(f"\n💭 ARGUMENT v{arg_obj.version}:")
        print(f"   Thesis: {arg_obj.thesis_statement}")
        print("\n   Supporting Points:")
        for j, point in enumerate(arg_obj.supporting_points, 1):
            print(f"      {j}. {point[:100]}...")

        print("\n🎯 CRITIQUE:")
        print(f"   Score: {crit_obj.score}/10")
        print("\n   Strengths:")
        for strength in crit_obj.strengths:
            print(f"      + {strength}")
        print("\n   Weaknesses:")
        for weakness in crit_obj.weaknesses:
            print(f"      - {weakness}")
        print("\n   Suggestions:")
        for suggestion in crit_obj.specific_suggestions:
            print(f"      → {suggestion}")

        if crit_obj.score >= 9:
            print("\n✅ DEBATE CONCLUDED - High quality achieved!")
        else:
            print("\n🔄 Continuing to next iteration...")

    # Show final argument
    if arguments:
        final_arg = arguments[-1].obj
        print("\n" + "=" * 70)
        print("🏆 FINAL POLISHED ARGUMENT")
        print("=" * 70)
        print(f"\nThesis: {final_arg.thesis_statement}")
        print(f"\nConclusion: {final_arg.conclusion}")
        print(f"\nTotal Iterations: {len(arguments)}")
        print("=" * 70)

    print("\n✨ Debate complete!")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 LEARNING CHECKPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
🎉 CONGRATULATIONS! You built a controlled feedback loop system!

🔑 KEY TAKEAWAYS:
-----------------

1️⃣ CONDITIONAL CONSUMPTION
   - where=lambda enables smart filtering
   - Only consume artifacts that match criteria
   - Perfect for quality gates and thresholds

2️⃣ FEEDBACK LOOPS
   - Agent A publishes → Agent B consumes → Agent A consumes feedback
   - Use predicates to control when loops stop
   - Example: where=lambda c: c.score < 9 creates exit condition

3️⃣ SAFETY MECHANISMS
   - max_agent_iterations prevents runaway loops
   - prevent_self_trigger prevents self-consumption
   - Flock has built-in circuit breakers

4️⃣ ITERATIVE REFINEMENT
   - Start with rough draft
   - Iteratively improve based on feedback
   - Converge to high quality output
   - Common pattern: quality gates, approval workflows

🆚 VS TRADITIONAL APPROACHES:
-----------------------------

❌ Manual Loop Control:
```python
for i in range(max_iterations):
    argument = debater.run(topic if i == 0 else critique)
    critique = critic.run(argument)
    if critique.score >= 9:
        break
# Imperative, hard to scale, couples agents
```

✅ Declarative Blackboard with Predicates:
```python
debater.consumes(DebateTopic)
debater.consumes(Critique, where=lambda c: c.score < 9)
critic.consumes(Argument)
# Loop emerges from type subscriptions!
# No manual orchestration needed!
```

💡 REAL-WORLD APPLICATIONS:
--------------------------

1. **Code Review Systems**:
```python
developer.consumes(Task).publishes(Code)
reviewer.consumes(Code).publishes(Review)
developer.consumes(Review, where=lambda r: not r.approved)
# Auto-iterates until code is approved!
```

2. **Content Quality Gates**:
```python
writer.consumes(Outline).publishes(Draft)
editor.consumes(Draft).publishes(Feedback)
writer.consumes(Feedback, where=lambda f: f.score < 8)
# Refines until quality threshold met
```

3. **Research Paper Refinement**:
```python
researcher.consumes(Topic).publishes(Paper)
peer_reviewer.consumes(Paper).publishes(ReviewComments)
researcher.consumes(ReviewComments, where=lambda c: c.major_revisions_needed)
# Academic peer review loop!
```

4. **Design Iteration**:
```python
designer.consumes(Brief).publishes(Design)
client.consumes(Design).publishes(ClientFeedback)
designer.consumes(ClientFeedback, where=lambda f: not f.approved)
# Iterate until client approval
```

🧪 EXPERIMENT IDEAS:
-------------------

1. **Add a Third Agent (Moderator)**:
```python
moderator = (
    flock.agent("moderator")
    .consumes(Critique)
    .publishes(ModeratorDecision)  # Can end debate early
)
debater.consumes(Critique, where=lambda c: c.score < 9 and not moderator_ended)
```

2. **Multi-Round Debates**:
   - Add a "round" counter
   - Different quality thresholds per round
   - Progressive refinement

3. **Parallel Debaters**:
   - Multiple debaters arguing different positions
   - Critic compares and ranks them
   - Best argument wins

4. **Add Audience Voting**:
```python
audience = (
    flock.agent("audience")
    .consumes(Argument)
    .publishes(AudienceVote)
)
# Debater refines based on both critic AND audience
```

5. **Trace the Feedback Loop**:
```bash
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
# Query to see iteration count:
SELECT COUNT(*) as iterations
FROM spans
WHERE name = 'Agent.execute' AND service = 'debater'
```

⚠️  COMMON PITFALLS:
-------------------

1. **Infinite Loops Without Exit Condition**:
   ❌ debater.consumes(Critique)  # No where clause!
   ✅ debater.consumes(Critique, where=lambda c: c.score < 9)

2. **Forgetting prevent_self_trigger**:
   ❌ agent.consumes(Type).publishes(Type)  # Danger!
   ✅ agent.consumes(Type).publishes(Type).prevent_self_trigger(True)

3. **No Circuit Breaker**:
   ❌ Flock()  # Defaults to high limit
   ✅ Flock(max_agent_iterations=20)  # Explicit safety

4. **Predicate Too Strict**:
   ❌ where=lambda c: c.score == 10  # May never stop!
   ✅ where=lambda c: c.score < 9  # Reasonable threshold

📈 NEXT LESSON:
--------------
Lesson 05: Debugging the Detective
- Deep dive into unified tracing with traced_run()
- Query DuckDB traces to understand execution
- AI-assisted debugging
- Performance profiling

🎯 READY TO CONTINUE?
Run: uv run examples/claudes-flock-course/lesson_05_tracing_detective.py
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
