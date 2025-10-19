from __future__ import annotations

import asyncio
import random

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import AgentComponent, EngineComponent
from flock.runtime import EvalInputs, EvalResult


@flock_type(name="StoryIdea")
class StoryIdea(BaseModel):
    hero: str = Field(description="Protagonist name")
    goal: str = Field(description="What the hero wants most")
    obstacle: str = Field(description="What stands in the way")
    genre: str = Field(description="Tone of the tale (mystery, comedy, etc.)")


@flock_type(name="StoryBeat")
class StoryBeat(BaseModel):
    synopsis: str
    foreshadowing: str | None = None
    surprise: str | None = None


class ForeshadowingComponent(AgentComponent):
    """Slip a hint into the agent's state right before the engine runs."""

    sprinkle_count: int = Field(default=0, description="How many hints we've added so far")

    GENRE_CLUES: dict[str, list[str]] = {
        "mystery": [
            "A pocket watch ticks backwards somewhere off-stage.",
            "Someone misplaced a single chess piece—intentionally.",
            "A raven drops a key no one remembers forging.",
        ],
        "comedy": [
            "A banana peel in act one never goes unused.",
            "Someone swapped the hero's script with a karaoke playlist.",
            "A suspiciously squeaky floorboard cues the laugh track.",
        ],
        "fantasy": [
            "The moon blushes a shade deeper than usual.",
            "A prophecy scribbles in the margins on its own.",
            "The dragon hums a lullaby nobody taught it.",
        ],
    }

    async def on_pre_evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalInputs:
        if not inputs.artifacts:
            return inputs

        idea = StoryIdea(**inputs.artifacts[0].payload)
        clue = self._choose_clue(idea.genre.lower())

        self.sprinkle_count += 1
        inputs.state["foreshadow"] = clue
        inputs.state["sprinkle_count"] = self.sprinkle_count
        return inputs

    def _choose_clue(self, genre: str) -> str:
        clues = self.GENRE_CLUES.get(genre, self.GENRE_CLUES["fantasy"])
        return random.choice(clues)


class CampfireStoryEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        idea = inputs.first_as(StoryIdea)
        if not idea:
            return EvalResult.empty()

        foreshadow = inputs.state.get("foreshadow")
        sprinkle_count = inputs.state.get("sprinkle_count", 0)

        synopsis = (
            f"{idea.hero} pursues {idea.goal}, but {idea.obstacle} complicates everything. "
            "Tonight's storyteller leans in and lowers their voice..."
        )
        surprise = (
            f"Twist #{sprinkle_count}: {idea.hero} discovers the clue was planted by an ally."
            if foreshadow
            else "No twists tonight—cozy endings all around."
        )

        beat = StoryBeat(synopsis=synopsis, foreshadowing=foreshadow, surprise=surprise)
        return EvalResult.from_object(beat, agent=agent)


async def main() -> None:
    flock = Flock()

    (
        flock.agent("campfire_bard")
        .description("Spins a short story beat and sneaks in a tiny plot twist.")
        .consumes(StoryIdea)
        .publishes(StoryBeat)
        .with_utilities(ForeshadowingComponent())
        .with_engines(CampfireStoryEngine())
    )

    await flock.publish(
        StoryIdea(
            hero="Lena the Locksmith",
            goal="to reopen the sealed observatory",
            obstacle="the mayor's missing signet ring",
            genre="mystery",
        )
    )
    await flock.publish(
        StoryIdea(
            hero="Jasper the Jester",
            goal="to deliver the royal speech",
            obstacle="a severe case of magical hiccups",
            genre="comedy",
        )
    )

    await flock.run_until_idle()

    print("\nCampfire Story Beats")
    print("--------------------")
    for artifact in await flock.store.list():
        if artifact.produced_by != "campfire_bard":
            continue
        payload = artifact.payload
        print(f"\n🌙 {payload['synopsis']}")
        if payload.get("foreshadowing"):
            print(f"   Foreshadowing: {payload['foreshadowing']}")
        if payload.get("surprise"):
            print(f"   Surprise: {payload['surprise']}")


if __name__ == "__main__":
    asyncio.run(main())
