import asyncio

from pydantic import BaseModel

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class CrimeScene(BaseModel):
    location: str
    evidence: list[str]
    witness_statements: list[str]
    time_of_incident: str

@flock_type
class Investigation(BaseModel):
    case_id: str
    evidence_analysis: list[str]
    suspect_profiles: list[dict[str, str]]
    timeline: list[str]
    confidence_level: float

@flock_type
class CaseReport(BaseModel):
    case_id: str
    prime_suspect: str
    motive: str
    method: str
    opportunity: str
    evidence_strength: str
    recommendation: str

flock = Flock("openai/gpt-4.1")

detective = (
    flock.agent("detective")
    .description("Analyzes crime scenes and builds investigation profiles")
    .consumes(CrimeScene)
    .publishes(Investigation)
)

prosecutor = (
    flock.agent("prosecutor")
    .description("Reviews investigations and builds legal cases")
    .consumes(Investigation)
    .publishes(CaseReport)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
