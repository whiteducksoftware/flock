"""
Getting Started: Tracing Detective

This example demonstrates the unified tracing feature that captures complete
execution history for debugging and analysis. Shows how to use traced_run() wrapper.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.registry import flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


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


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("🔍 Starting traced investigation workflow...\n")

    async with flock.traced_run("mystery_cases"):
        scene = CrimeScene(
            location="Corporate boardroom, 42nd floor",
            evidence=[
                "USB drive with encrypted files",
                "Coffee cup with lipstick",
                "Deleted security footage timestamp",
            ],
            witness_statements=["Heard shouting around 9 PM", "Saw someone in maintenance uniform"],
            time_of_incident="2025-10-09 21:15",
        )

        print(f"🚨 Processing crime scene: {scene.location}")
        await flock.publish(scene)
        await flock.run_until_idle()

    reports = await flock.store.get_by_type(CaseReport)

    if reports:
        report = reports[0]
        print("\n📋 CASE REPORT:")
        print(f"   Case ID: {report.case_id}")
        print(f"   Prime Suspect: {report.prime_suspect}")
        print(f"   Motive: {report.motive}")
        print(f"   Evidence: {report.evidence_strength}")
        print(f"   Recommendation: {report.recommendation}")

    print("\n💡 Check .flock/traces.duckdb for complete execution tracing!")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
