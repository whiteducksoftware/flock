import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.core.visibility import Visibility


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


flock = Flock()

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


async def main():
    missions = [
        Mission(
            codename="Operation Nightfall",
            target="Foreign intelligence network",
            objective="Identify and neutralize security threat to diplomatic summit",
            classification_level="TOP SECRET",
        ),
        Mission(
            codename="Project Moonbeam",
            target="Cybercriminal organization",
            objective="Track cryptocurrency laundering operation",
            classification_level="SECRET",
        ),
    ]

    for mission in missions:
        print(f"🕵️ Starting mission: {mission.codename}")
        await flock.publish(mission)

    await flock.run_until_idle()

    intel_reports = await flock.store.get_by_type(IntelReport)
    briefings = await flock.store.get_by_type(ClassifiedBriefing)
    public_statements = await flock.store.get_by_type(PublicStatement)

    print("\n🔒 CLASSIFIED OPERATIONS SUMMARY:")
    print(f"   Intelligence reports: {len(intel_reports)} (PRIVATE)")
    print(f"   Strategic briefings: {len(briefings)} (PRIVATE)")
    print(f"   Public statements: {len(public_statements)} (PUBLIC)")

    print("\n📢 PUBLIC INFORMATION:")
    for i, statement in enumerate(public_statements):
        print(f"   Statement {i + 1}: {statement.headline}")
        print(f"   Response: {statement.official_response[:100]}...")

    print("\n🔐 CLASSIFIED METRICS:")
    if intel_reports:
        avg_confidence = sum(r.confidence for r in intel_reports) / len(intel_reports)
        print(f"   Average intel confidence: {avg_confidence:.2f}")

    if briefings:
        avg_success = sum(b.success_probability for b in briefings) / len(briefings)
        total_assets = sum(b.assets_deployed for b in briefings)
        print(f"   Average success probability: {avg_success:.2f}")
        print(f"   Total assets deployed: {total_assets}")


if __name__ == "__main__":
    asyncio.run(main())
