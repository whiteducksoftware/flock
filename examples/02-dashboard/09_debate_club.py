import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class DebateTopic(BaseModel):
    statement: str
    context: str
    stakes: str

@flock_type
class Argument(BaseModel):
    position: str
    main_points: list[str]
    evidence: list[str]
    counterarguments_addressed: list[str]
    strength_score: int = Field(ge=1, le=10)

@flock_type
class DebateVerdict(BaseModel):
    winner: str
    reasoning: str
    key_factors: list[str]
    vote_margin: str
    most_compelling_point: str

flock = Flock("openai/gpt-4.1")

pro_debater = (
    flock.agent("pro_debater")
    .description("Argues FOR the debate statement with evidence and logic")
    .consumes(DebateTopic)
    .publishes(Argument)
)

con_debater = (
    flock.agent("con_debater")
    .description("Argues AGAINST the debate statement with counter-evidence")
    .consumes(DebateTopic)
    .publishes(Argument)
)

judge = (
    flock.agent("judge")
    .description("Evaluates both arguments and declares a winner")
    .consumes(Argument)
    .publishes(DebateVerdict)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
