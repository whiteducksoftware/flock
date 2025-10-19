import asyncio

from pydantic import BaseModel

from flock import Flock
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


flock = Flock()

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


async def main():
    print("🔍 Starting traced investigation workflow...")

    async with flock.traced_run("mystery_cases"):
        crime_scenes = [
            CrimeScene(
                location="Corporate boardroom, 42nd floor",
                evidence=[
                    "USB drive with encrypted files",
                    "Coffee cup with lipstick",
                    "Deleted security footage timestamp",
                ],
                witness_statements=[
                    "Heard shouting around 9 PM",
                    "Saw someone in maintenance uniform",
                    "Elevator was broken that evening",
                ],
                time_of_incident="2025-10-09 21:15",
            ),
            CrimeScene(
                location="Art gallery after charity auction",
                evidence=[
                    "Broken alarm sensor",
                    "Muddy footprints size 10",
                    "Missing painting worth $2M",
                ],
                witness_statements=[
                    "Delivery truck parked outside",
                    "Staff left early",
                    "Power outage lasted 10 minutes",
                ],
                time_of_incident="2025-10-09 23:45",
            ),
        ]

        for scene in crime_scenes:
            print(f"🚨 Processing crime scene: {scene.location}")
            await flock.publish(scene)

        await flock.run_until_idle()

    reports = await flock.store.get_by_type(CaseReport)
    investigations = await flock.store.get_by_type(Investigation)

    for i, report in enumerate(reports):
        print(f"\n📋 CASE REPORT {i + 1}:")
        print(f"   Case ID: {report.case_id}")
        print(f"   Prime Suspect: {report.prime_suspect}")
        print(f"   Motive: {report.motive}")
        print(f"   Method: {report.method}")
        print(f"   Opportunity: {report.opportunity}")
        print(f"   Evidence Strength: {report.evidence_strength}")
        print(f"   Recommendation: {report.recommendation}")

    print("\n🔬 INVESTIGATION SUMMARY:")
    print(f"   Crime scenes processed: {len(crime_scenes)}")
    print(f"   Investigations completed: {len(investigations)}")
    print(f"   Case reports filed: {len(reports)}")

    if investigations:
        avg_confidence = sum(inv.confidence_level for inv in investigations) / len(investigations)
        print(f"   Average confidence level: {avg_confidence:.2f}")

    print("\n💡 Check .flock/traces.duckdb for complete execution tracing!")


if __name__ == "__main__":
    asyncio.run(main())
