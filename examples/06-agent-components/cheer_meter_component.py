from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import AgentComponent, EngineComponent
from flock.runtime import EvalInputs, EvalResult


@flock_type(name="Pitch")
class Pitch(BaseModel):
    product: str = Field(description="What we're pitching")
    audience: str = Field(description="Who the pitch is for")
    highlight: str = Field(description="Biggest wow factor")


@flock_type(name="PitchResult")
class PitchResult(BaseModel):
    tagline: str
    closer: str


class CheerMeterComponent(AgentComponent):
    """Keeps the hype alive and reports crowd energy after each pitch."""

    applause_level: int = Field(default=0, description="Number of successful pitches so far")

    async def on_post_evaluate(
        self, agent, ctx, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        self.applause_level += 1
        crowd_energy = min(1.0, self.applause_level / 5)

        result.metrics["crowd_energy"] = crowd_energy
        result.logs.append(f"Crowd energy surged to {crowd_energy:.2f}")

        # Make the engine's downstream outputs aware of the vibe.
        result.state["crowd_energy"] = crowd_energy
        return result

    async def on_post_publish(self, agent, ctx, artifact) -> None:
        tagline = artifact.payload.get("tagline", "the latest pitch")
        print(f"👏  Crowd erupts for: {tagline}")


class PepTalkEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        pitch = inputs.first_as(Pitch)
        if not pitch:
            return EvalResult.empty()

        crowd_energy = ctx.state.get("crowd_energy", 0.0)
        if crowd_energy >= 0.6:
            closer = "The standing ovation continues—let's sign that contract!"
        else:
            closer = "Imagine the applause once this idea hits the main stage."

        tagline = (
            f"{pitch.product}: the {pitch.highlight} your {pitch.audience.lower()} "
            "didn't realize they were waiting for."
        )

        result = PitchResult(tagline=tagline, closer=closer)
        return EvalResult.from_object(result, agent=agent)


async def main() -> None:
    flock = Flock()

    (
        flock.agent("pep_talk_lead")
        .description("Adds a hype meter to every pitch.")
        .consumes(Pitch)
        .publishes(PitchResult)
        .with_utilities(CheerMeterComponent())
        .with_engines(PepTalkEngine())
    )

    await flock.publish(
        Pitch(
            product="Nebula Notebook",
            audience="space-obsessed teens",
            highlight="self-illuminating constellation pages",
        )
    )
    await flock.publish(
        Pitch(
            product="Tempo Tumbler",
            audience="remote teams",
            highlight="rhythm-based coffee reminders",
        )
    )
    await flock.publish(
        Pitch(
            product="Dream Dossier",
            audience="storytellers",
            highlight="AI-curated plot twists at sunrise",
        )
    )

    await flock.run_until_idle()

    print("\nPitch Recap")
    print("-----------")
    for artifact in await flock.store.list():
        if artifact.produced_by != "pep_talk_lead":
            continue
        payload = artifact.payload
        print(f"\n🎤 {payload['tagline']}")
        print(f"   {payload['closer']}")


if __name__ == "__main__":
    asyncio.run(main())
