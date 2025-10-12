import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.visibility import Visibility


@flock_type
class Mission(BaseModel):
    codename: str
    target: str
    objective: str
    classification_level: str

@flock_type
class IntelReport(BaseModel):
    agent_id: str
    findings: list[str]
    risk_assessment: str
    recommended_action: str
    confidence: float = Field(ge=0.0, le=1.0)

@flock_type
class ClassifiedBriefing(BaseModel):
    mission_status: str
    threat_level: str
    next_steps: list[str]
    assets_deployed: int
    success_probability: float

@flock_type
class PublicStatement(BaseModel):
    headline: str
    official_response: str
    media_talking_points: list[str]
    public_reassurance: str

flock = Flock("openai/gpt-4.1")

field_agent = (
    flock.agent("field_agent")
    .description("Gathers intelligence and assesses threats in the field")
    .consumes(Mission)
    .publishes(IntelReport, visibility=Visibility.PRIVATE)
)

analyst = (
    flock.agent("analyst")
    .description("Analyzes intelligence reports for strategic planning")
    .consumes(IntelReport, visibility=Visibility.PRIVATE)
    .publishes(ClassifiedBriefing, visibility=Visibility.PRIVATE)
)

press_secretary = (
    flock.agent("press_secretary")
    .description("Creates public statements while protecting classified information")
    .consumes(Mission)
    .publishes(PublicStatement, visibility=Visibility.PUBLIC)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
