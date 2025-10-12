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
    severity: str
    root_cause: str
    affected_components: list[str]
    suggested_fix: str
    requires_hotfix: bool
    confidence_score: float = Field(ge=0.0, le=1.0)

flock = Flock("openai/gpt-4.1")

code_detective = (
    flock.agent("code_detective")
    .description("Analyzes bug reports and provides structured diagnoses")
    .consumes(BugReport)
    .publishes(BugDiagnosis)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
