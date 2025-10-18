import asyncio

from pydantic import BaseModel, Field

from flock import Flock
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


flock = Flock()

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
    topics = [
        DebateTopic(
            statement="Remote work is more productive than office work",
            context="Post-pandemic workplace transformation debate",
            stakes="Future of work policies for millions of employees",
        ),
        DebateTopic(
            statement="AI should be regulated like nuclear technology",
            context="Rapid advancement of artificial intelligence capabilities",
            stakes="Balancing innovation with safety for humanity's future",
        ),
    ]

    for topic in topics:
        print(f"⚖️ Starting debate: {topic.statement}")
        await flock.publish(topic)

    await flock.run_until_idle()

    verdicts = await flock.store.get_by_type(DebateVerdict)
    arguments = await flock.store.get_by_type(Argument)

    for i, verdict in enumerate(verdicts):
        print(f"\n🏆 DEBATE VERDICT {i + 1}:")
        print(f"   Winner: {verdict.winner}")
        print(f"   Reasoning: {verdict.reasoning}")
        print(f"   Key Factors: {verdict.key_factors}")
        print(f"   Vote Margin: {verdict.vote_margin}")
        print(f"   Most Compelling: {verdict.most_compelling_point}")

    pro_args = [a for a in arguments if a.position.lower().startswith("pro")]
    con_args = [a for a in arguments if a.position.lower().startswith("con")]

    print("\n📊 DEBATE STATISTICS:")
    print(f"   Pro arguments: {len(pro_args)}")
    print(f"   Con arguments: {len(con_args)}")
    if pro_args and con_args:
        avg_pro_strength = sum(a.strength_score for a in pro_args) / len(pro_args)
        avg_con_strength = sum(a.strength_score for a in con_args) / len(con_args)
        print(f"   Avg Pro strength: {avg_pro_strength:.1f}/10")
        print(f"   Avg Con strength: {avg_con_strength:.1f}/10")


if __name__ == "__main__":
    asyncio.run(main())
