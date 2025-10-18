import asyncio
from datetime import datetime

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


@flock_type
class BugReport(BaseModel):
    title: str
    description: str
    reporter: str
    timestamp: datetime = Field(default_factory=datetime.now)


@flock_type
class BugDiagnosis(BaseModel):
    severity: str
    root_cause: str
    affected_components: list[str]
    suggested_fix: str
    requires_hotfix: bool
    confidence_score: float = Field(ge=0.0, le=1.0)


flock = Flock()

code_detective = (
    flock.agent("code_detective")
    .description("Analyzes bug reports and provides structured diagnoses")
    .consumes(BugReport)
    .publishes(BugDiagnosis)
)


async def main():
    bug_reports = [
        BugReport(
            title="App crashes when user clicks submit",
            description="Users are reporting that when they click the submit button on the contact form, the entire application crashes. This happens on both mobile and desktop. Error message shows 'TypeError: Cannot read property of undefined'. Started happening after yesterday's deployment.",
            reporter="sarah.dev@company.com",
        ),
        BugReport(
            title="Login page not loading",
            description="The login page shows a white screen. Console shows 404 error for login.css file. Happens only in production, works fine locally.",
            reporter="mike.frontend@company.com",
        ),
    ]

    for report in bug_reports:
        print(f"🐛 Processing: {report.title}")
        await flock.publish(report)

    await flock.run_until_idle()

    diagnoses = await flock.store.get_by_type(BugDiagnosis)

    for i, diagnosis in enumerate(diagnoses):
        print(f"\n📊 DIAGNOSIS {i + 1}:")
        print(f"   Severity: {diagnosis.severity}")
        print(f"   Root Cause: {diagnosis.root_cause}")
        print(f"   Components: {', '.join(diagnosis.affected_components)}")
        print(f"   Fix: {diagnosis.suggested_fix}")
        print(f"   Hotfix Needed: {diagnosis.requires_hotfix}")
        print(f"   Confidence: {diagnosis.confidence_score:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
