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


@flock_type
class BugReport(BaseModel):
    title: str
    description: str
    reporter: str
    timestamp: datetime = Field(default_factory=datetime.now)


@flock_type
class BugDiagnosis(BaseModel):
    severity: str = Field(pattern="^(Critical|High|Medium|Low)$")
    category: str = Field(description="Bug category")
    root_cause_hypothesis: str = Field(min_length=50)
    confidence_score: float = Field(ge=0.0, le=1.0)


flock = Flock("openai/gpt-4.1")


code_detective = (
    flock.agent("code_detective")
    .description("A brilliant detective who analyzes bug reports and provides structured diagnoses")
    .consumes(BugReport)  # "I react when BugReport appears on the blackboard"
    .publishes(BugDiagnosis)  # "I produce BugDiagnosis artifacts"
)


async def main():
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

    await flock.publish(bug)

    await flock.run_until_idle()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
