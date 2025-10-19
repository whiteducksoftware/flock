"""
Getting Started: Secret Agents

This example demonstrates visibility controls in Flock, where different agents
have different access levels to artifacts (public vs private vs classified).

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.core.visibility import PrivateVisibility, PublicVisibility

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


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
    .publishes(IntelReport, visibility=PrivateVisibility(agents={"analyst"}))
)

analyst = (
    flock.agent("analyst")
    .description("Analyzes intelligence reports for strategic planning")
    .consumes(IntelReport)
    .publishes(ClassifiedBriefing)
)

press_secretary = (
    flock.agent("press_secretary")
    .description("Creates public statements while protecting classified information")
    .consumes(Mission)
    .publishes(PublicStatement)
)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    mission = Mission(
        codename="Operation Nightfall",
        target="Foreign intelligence network",
        objective="Identify and neutralize security threat to diplomatic summit",
        classification_level="TOP SECRET",
    )

    print(f"🕵️  Starting mission: {mission.codename}\n")

    await flock.publish(mission)
    await flock.run_until_idle()

    intel_reports = await flock.store.get_by_type(IntelReport)
    briefings = await flock.store.get_by_type(ClassifiedBriefing)
    public_statements = await flock.store.get_by_type(PublicStatement)

    print("🔒 CLASSIFIED SUMMARY:")
    print(f"   Intelligence reports: {len(intel_reports)} (PRIVATE)")
    print(f"   Strategic briefings: {len(briefings)} (PRIVATE)")
    print(f"   Public statements: {len(public_statements)} (PUBLIC)")

    if public_statements:
        statement = public_statements[0]
        print("\n📢 PUBLIC INFORMATION:")
        print(f"   {statement.headline}")
        print(f"   {statement.official_response[:100]}...")


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
