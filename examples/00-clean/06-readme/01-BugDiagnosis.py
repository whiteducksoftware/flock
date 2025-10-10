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
    .description("Analyzes bug reports and provides structured diagnoses")
    .consumes(BugReport)
    .publishes(BugDiagnosis)
)

async def main():
    bug_report = BugReport(
        title="User login fails on mobile devices",
        description="Multiple users reporting authentication failures on mobile app. Error occurs after entering credentials. Works fine on desktop version.",
        reporter="mobile.team@company.com"
    )
    
    print(f"🐛 Analyzing: {bug_report.title}")
    await flock.publish(bug_report)
    await flock.run_until_idle()
    
    diagnoses = await flock.store.get_by_type(BugDiagnosis)
    if diagnoses:
        diagnosis = diagnoses[0]
        print(f"📊 Diagnosis: {diagnosis.severity} severity")
        print(f"📁 Category: {diagnosis.category}")
        print(f"🔍 Root cause: {diagnosis.root_cause_hypothesis}")
        print(f"📈 Confidence: {diagnosis.confidence_score:.2f}")
    else:
        print("❌ No diagnosis generated")

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
