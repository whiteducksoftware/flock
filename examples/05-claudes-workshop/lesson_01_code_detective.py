"""
🔍 LESSON 01: The Code Detective
================================

🎯 LEARNING OBJECTIVES:
----------------------
In this lesson, you'll learn:
1. How to define typed artifacts with Pydantic models
2. How to create a single-agent transformation
3. Why declarative contracts beat prompt engineering
4. How the blackboard architecture works at its simplest

🎬 THE SCENARIO:
---------------
You're building a bug triage system. Developers submit bug reports (unstructured),
and you need a "Code Detective" agent to analyze them and produce structured
diagnoses. No prompts. Just type contracts.

⏱️  TIME: 10 minutes
💡 COMPLEXITY: ⭐ Beginner

Let's dive in! 👇
"""

import asyncio
from datetime import datetime

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 STEP 1: Define Your Data Contracts (The "What")
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🎯 KEY CONCEPT: @flock_type decorator
# This registers the model with Flock's type registry, allowing agents to
# subscribe to it. Think of it as "publishing" a data schema that agents can react to.


@flock_type
class BugReport(BaseModel):
    """
    INPUT: The messy, unstructured bug report from a developer

    This is what comes IN to your system - raw, unstructured data.
    Notice: No constraints, no validation. Just free-form text.
    """

    title: str
    description: str
    reporter: str
    timestamp: datetime = Field(default_factory=datetime.now)


@flock_type
class BugDiagnosis(BaseModel):
    """
    OUTPUT: The structured, analyzed diagnosis from our detective

    This is what comes OUT - validated, structured, actionable data.
    Notice the rich schema with constraints and descriptions!

    🔥 THE MAGIC:
    By defining this schema, you're implicitly telling the LLM:
    "Take a BugReport and transform it into THIS exact structure"

    No 500-line prompt needed. The types ARE the instruction.
    """

    # Basic info
    severity: str = Field(
        description="Critical, High, Medium, or Low",
        pattern="^(Critical|High|Medium|Low)$",
    )

    category: str = Field(
        description="Bug category",
        examples=["Backend", "Frontend", "Database", "API", "UI/UX", "Performance"],
    )

    # The detective's analysis
    root_cause_hypothesis: str = Field(
        description="Detective's hypothesis about what's causing the bug",
        min_length=50,
    )

    affected_components: list[str] = Field(
        description="List of system components likely affected",
        min_length=1,
    )

    suggested_actions: list[str] = Field(
        description="Recommended next steps for the dev team",
        min_length=1,
        max_length=5,
    )

    # Metadata
    confidence_score: float = Field(
        description="Detective's confidence in the diagnosis (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 STEP 2: Create the Orchestrator (The Blackboard)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 💡 THINK OF IT AS:
# The orchestrator is a shared whiteboard where all data lives.
# Agents watch this whiteboard and react when relevant data appears.
# No workflow graph. No routing logic. Just subscriptions.

flock = Flock("openai/gpt-4.1")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🕵️ STEP 3: Define the Detective Agent (The "Who")
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🔥 THIS IS THE ENTIRE AGENT DEFINITION:
# No prompts. No instructions. Just type subscriptions.

code_detective = (
    flock.agent("code_detective")
    .description("A brilliant detective who analyzes bug reports and provides structured diagnoses")
    .consumes(BugReport)  # "I react when BugReport appears on the blackboard"
    .publishes(BugDiagnosis)  # "I produce BugDiagnosis artifacts"
)

# 💬 WHAT JUST HAPPENED?
# ━━━━━━━━━━━━━━━━━━━━━
# You declared:
# - WHO: An agent named "code_detective"
# - WHAT IT DOES: Described its role (optional, but helpful for multi-agent systems)
# - WHAT IT WATCHES: BugReport artifacts
# - WHAT IT PRODUCES: BugDiagnosis artifacts
#
# Flock automatically:
# 1. ✅ Generates a system prompt from the type schemas
# 2. ✅ Configures structured output parsing
# 3. ✅ Sets up validation against the BugDiagnosis schema
# 4. ✅ Subscribes the agent to the blackboard
# 5. ✅ Handles all the LLM complexity
#
# You maintain TYPES, not PROMPTS. 🎉

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 4: Run the Investigation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    The investigation workflow:
    1. Create a bug report
    2. Publish it to the blackboard
    3. Let the detective analyze it
    4. Observe the structured diagnosis
    """

    print("🔍 Starting the Code Detective Investigation...\n")

    # 🐛 Create a bug report (this is our input)
    bug = BugReport(
        title="App crashes when uploading large images",
        description="""
        Users report that when they try to upload images larger than 10MB,
        the app freezes for about 30 seconds and then crashes with a memory error.
        This happens on both iOS and Android. The logs show 'OutOfMemoryError'
        in the image processing service. It started happening after we deployed
        the new image compression feature last Tuesday.
        """,
        reporter="alice@example.com",
    )

    print("📋 Bug Report Submitted:")
    print(f"   Title: {bug.title}")
    print(f"   Reporter: {bug.reporter}")
    print(f"   Time: {bug.timestamp}\n")

    # 📤 Publish the bug to the blackboard
    # This makes it visible to all agents subscribed to BugReport
    print("📤 Publishing bug to blackboard...")
    await flock.publish(bug)

    # ⏳ Wait for all agents to finish processing
    # (In this case, just code_detective, but could be many agents!)
    print("🕵️  Code Detective is analyzing...\n")
    await flock.run_until_idle()

    # 📊 Retrieve the diagnosis from the blackboard
    diagnoses = await flock.store.get_by_type(BugDiagnosis)

    if diagnoses:
        diagnosis = diagnoses[-1]  # Get the most recent diagnosis

        print("=" * 70)
        print("🎯 DIAGNOSIS COMPLETE!")
        print("=" * 70)
        print(f"\n🚨 Severity: {diagnosis.severity}")
        print(f"📁 Category: {diagnosis.category}")
        print("\n💡 Root Cause Hypothesis:")
        print(f"   {diagnosis.root_cause_hypothesis}")
        print("\n⚙️  Affected Components:")
        for component in diagnosis.affected_components:
            print(f"   - {component}")
        print("\n✅ Suggested Actions:")
        for i, action in enumerate(diagnosis.suggested_actions, 1):
            print(f"   {i}. {action}")
        print(f"\n📊 Confidence Score: {diagnosis.confidence_score:.0%}")
        print("=" * 70)
    else:
        print("❌ No diagnosis produced (something went wrong)")

    print("\n✨ Investigation complete!")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 LEARNING CHECKPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
🎉 CONGRATULATIONS! You just built your first Flock agent!

🔑 KEY TAKEAWAYS:
-----------------

1️⃣ DECLARATIVE > IMPERATIVE
   - You defined WHAT (BugReport → BugDiagnosis)
   - Not HOW (no prompts about "analyze this bug...")
   - The schema IS the instruction

2️⃣ TYPE SAFETY WINS
   - Pydantic validates outputs automatically
   - Field constraints ensure quality
   - Errors caught at parse time, not later

3️⃣ BLACKBOARD ARCHITECTURE
   - publish() puts data on the blackboard
   - Agents subscribe to types, not to each other
   - run_until_idle() waits for all reactions to complete

4️⃣ ZERO PROMPTS NEEDED
   - No "You are a bug detective..."
   - No "Please analyze the following..."
   - Just types: BugReport in, BugDiagnosis out

🆚 VS PROMPT-BASED APPROACH:
---------------------------
Traditional prompt engineering:
```python
prompt = "You are a bug detective. Analyze this bug report and provide..."
# 500 lines later...
result = llm.invoke(prompt)  # Unstructured output, no validation
```

Flock's declarative approach:
```python
agent.consumes(BugReport).publishes(BugDiagnosis)
# That's it. Types are the contract.
```

🧪 EXPERIMENT IDEAS:
-------------------
Try modifying this example:

1. Change the BugDiagnosis schema:
   - Add a `priority_ranking: int` field
   - Add `estimated_fix_time: str`
   - Watch how the agent adapts automatically!

2. Add more constraints:
   - Set `min_length` on root_cause_hypothesis to 100
   - Limit `suggested_actions` to exactly 3 items
   - See how Flock enforces these

3. Create different bug reports:
   - Performance bugs
   - Security vulnerabilities
   - UI glitches
   - See how diagnosis changes

📈 NEXT LESSON:
--------------
Lesson 02: Band Formation Pipeline
- Learn multi-agent chaining
- See how agents auto-compose through the blackboard
- No graph wiring required!

🎯 READY TO CONTINUE?
Run: uv run examples/claudes-flock-course/lesson_02_band_formation.py
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
