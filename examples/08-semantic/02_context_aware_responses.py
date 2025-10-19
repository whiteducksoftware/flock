"""
Semantic Subscriptions: Context-Aware Incident Response

This example demonstrates using SemanticContextProvider to find similar
historical incidents and provide informed responses based on past resolutions.

🎯 Key Concepts:
- SemanticContextProvider for historical context
- Learning from past similar cases
- Context-enriched decision making

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes

📚 Requires: uv add flock-core[semantic]
"""

import asyncio
from collections import Counter

from pydantic import BaseModel, Field

from flock import Flock
from flock.components.agent import EngineComponent
from flock.registry import flock_type
from flock.semantic import SemanticContextProvider
from flock.utils.runtime import EvalInputs, EvalResult


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# 🎛️  TYPE REGISTRATION: Incident types
# ============================================================================
@flock_type
class Incident(BaseModel):
    """A system incident that needs resolution."""

    description: str = Field(description="Description of the incident")
    severity: str = Field(description="critical, high, medium, or low")
    system: str = Field(description="Affected system or service")
    resolved: bool = Field(default=False, description="Whether incident is resolved")
    resolution: str | None = Field(default=None, description="How it was resolved")


@flock_type
class IncidentResponse(BaseModel):
    """Recommended response to an incident."""

    incident_description: str
    recommended_action: str
    confidence: str
    similar_incidents_found: int
    past_resolutions: list[str] = Field(default_factory=list)


# ============================================================================
# 🎛️  CUSTOM ENGINE: Context-aware incident analyzer
# ============================================================================
class ContextAwareEngine(EngineComponent):
    """Engine that uses historical context to inform decisions."""

    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        """Find similar past incidents and recommend action."""
        from flock.registry import type_registry

        # Get the incoming incident
        artifact = inputs.artifacts[0]
        incident = Incident(**artifact.payload)

        print(f"\n📊 Analyzing: {incident.description}")

        # Use SemanticContextProvider to find similar RESOLVED incidents
        provider = SemanticContextProvider(
            query_text=incident.description,
            artifact_type=Incident,
            where=lambda a: a.payload.get("resolved") is True,
            threshold=0.35,
            limit=5,
        )

        similar = await provider.get_context(ctx.store)
        print(f"   Found {len(similar)} similar past incidents")

        # Extract past resolutions
        past_resolutions = []
        for sim in similar:
            resolution = sim.payload.get("resolution")
            if resolution:
                past_resolutions.append(resolution)
                print(f"   - Past resolution: {resolution}")

        # Determine recommendation based on past success
        if past_resolutions:
            # Use most common resolution
            most_common = Counter(past_resolutions).most_common(1)[0][0]
            recommended = most_common
            confidence = "high"
        else:
            # No historical data
            recommended = "Escalate to on-call engineer for investigation"
            confidence = "low"

        print(f"   Recommendation: {recommended}")
        print(f"   Confidence: {confidence}\n")

        # Create response artifact
        response = IncidentResponse(
            incident_description=incident.description,
            recommended_action=recommended,
            confidence=confidence,
            similar_incidents_found=len(similar),
            past_resolutions=past_resolutions,
        )

        # Return as artifact
        response_artifact = type_registry.resolve("IncidentResponse")(**response.dict())

        return EvalResult(
            artifacts=[artifact],  # Pass through for potential further processing
            state={"response": response.dict()},
        )


# ============================================================================
# 🎛️  SETUP: Create incident response system
# ============================================================================
flock = Flock("openai/gpt-4o-mini")

# Incident responder that learns from history
incident_responder = (
    flock.agent("incident_responder")
    .consumes(Incident)
    .publishes(IncidentResponse)
    .with_engines(ContextAwareEngine())
)


# ============================================================================
# 🎛️  RUN: Simulate incident history and new incidents
# ============================================================================
async def main_cli():
    """CLI mode: Demonstrate context-aware incident response"""
    print("\n🔍 Context-Aware Incident Response Demo\n")
    print("=" * 70)

    # Step 1: Populate incident history
    print("\n📚 Step 1: Populating incident history...")
    print("-" * 70)

    history = [
        Incident(
            description="Database connection pool exhausted",
            severity="high",
            system="postgres",
            resolved=True,
            resolution="Increased max connections from 100 to 200",
        ),
        Incident(
            description="Database timeout errors during peak traffic",
            severity="high",
            system="postgres",
            resolved=True,
            resolution="Increased max connections from 100 to 200",
        ),
        Incident(
            description="API response time degraded significantly",
            severity="medium",
            system="api-gateway",
            resolved=True,
            resolution="Added caching layer with Redis",
        ),
        Incident(
            description="Memory leak in application server",
            severity="critical",
            system="app-server",
            resolved=True,
            resolution="Restarted service and deployed hotfix for leak",
        ),
        Incident(
            description="Slow query causing database locks",
            severity="high",
            system="postgres",
            resolved=True,
            resolution="Added database index on user_id column",
        ),
    ]

    for inc in history:
        await flock.store.publish(
            flock.store._build_artifact(inc, produced_by="history_loader")
        )
        print(f"   ✓ {inc.description}")

    print("\n✅ Historical data loaded!")

    # Step 2: Process new incidents with context
    print("\n📋 Step 2: Processing new incidents with historical context...")
    print("-" * 70)

    new_incidents = [
        Incident(
            description="Database connection failures under load",
            severity="high",
            system="postgres",
        ),
        Incident(
            description="API latency spiking during business hours",
            severity="medium",
            system="api-gateway",
        ),
        Incident(
            description="Disk space running low on server",
            severity="low",
            system="file-server",
        ),
    ]

    for incident in new_incidents:
        await flock.publish(incident)
        await flock.run_until_idle()

    print("\n" + "=" * 70)
    print("✅ Incident analysis complete!")
    print("\n💡 Key Takeaway:")
    print("   The system learned from past resolutions to recommend")
    print("   actions for new but similar incidents automatically!")
    print("\n   - Database connection issues → Increase max connections")
    print("   - API latency → Add caching layer")
    print("   - Unknown issue → Escalate to engineer")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("\n🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8000 to see context-aware responses!")
    print("\n💡 The system will:")
    print("   1. Find similar past incidents using semantic search")
    print("   2. Learn from successful past resolutions")
    print("   3. Recommend actions based on historical data\n")

    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
