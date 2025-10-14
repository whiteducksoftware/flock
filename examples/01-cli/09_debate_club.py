import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class DebateTopic(BaseModel):
    statement: str = Field(
        default="Blackboard multi-agent systems will revolutionize AI development and are way cooler than traditional graph based architectures.",
        description="The statement to be debated",
    )
    context: str = Field(
        default="The AI agent system of the future",
        description="The context in which the debate takes place",
    )
    stakes: str = Field(
        default="Future of humanity depends on it", description="The stakes of the debate"
    )


@flock_type
class ProArgument(BaseModel):
    position: str
    main_points: list[str]
    evidence: list[str]
    counterarguments_addressed: list[str]
    strength_score: int = Field(ge=1, le=10)


@flock_type
class ContraArgument(BaseModel):
    position: str
    main_points: list[str]
    evidence: list[str]
    counterarguments_addressed: list[str]
    strength_score: int = Field(ge=1, le=10)


@flock_type
class DebateVerdict(BaseModel):
    winner: Literal["pro", "contra"]
    reasoning: str
    key_factors: list[str]
    vote_margin: str
    most_compelling_point: str


flock = Flock()

pro_debater = (
    flock.agent("pro_debater")
    .description(
        "Argues FOR the debate statement with evidence and logic, or when losing is trying to improve its argument"
    )
    .consumes(DebateTopic)
    .consumes(DebateVerdict, where=lambda r: "contra" in r.winner)
    .publishes(ProArgument)
)

con_debater = (
    flock.agent("con_debater")
    .description(
        "Argues AGAINST the debate statement with counter-evidence, or when losing is trying to improve its argument"
    )
    .consumes(DebateTopic)
    .consumes(DebateVerdict, where=lambda r: "pro" in r.winner)
    .publishes(ContraArgument)
)

judge = (
    flock.agent("judge")
    .description("Evaluates both arguments and declares a winner")
    .consumes(ProArgument, ContraArgument)
    .publishes(DebateVerdict)
)


async def main():
    await flock.serve(dashboard=True)
    topic = DebateTopic(
        statement="Blackboard multi-agent systems will revolutionize AI development and are way cooler than traditional graph based architectures.",
        context="The AI agent system of the future",
        stakes="Future of humanity depends on it",
    )

    print(f"⚖️  Starting debate: {topic.statement}\n")

    await flock.publish(topic)
    await flock.run_until_idle()

    verdicts = await flock.store.get_by_type(DebateVerdict)

    if verdicts:
        verdict = verdicts[0]
        print("🏆 VERDICT:")
        print(f"   Winner: {verdict.winner}")
        print(f"   Reasoning: {verdict.reasoning}")
        print(f"   Key Factors: {verdict.key_factors}")
        print(f"   Vote Margin: {verdict.vote_margin}")


if __name__ == "__main__":
    asyncio.run(main())
