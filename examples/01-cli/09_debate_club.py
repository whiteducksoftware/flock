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

async def main():
    topic = DebateTopic(
        statement="Remote work is more productive than office work",
        context="Post-pandemic workplace transformation debate",
        stakes="Future of work policies for millions of employees"
    )

    print(f"⚖️  Starting debate: {topic.statement}\n")

    await flock.publish(topic)
    await flock.run_until_idle()

    verdicts = await flock.store.get_by_type(DebateVerdict)

    if verdicts:
        verdict = verdicts[0]
        print(f"🏆 VERDICT:")
        print(f"   Winner: {verdict.winner}")
        print(f"   Reasoning: {verdict.reasoning}")
        print(f"   Key Factors: {verdict.key_factors}")
        print(f"   Vote Margin: {verdict.vote_margin}")

if __name__ == "__main__":
    asyncio.run(main())
