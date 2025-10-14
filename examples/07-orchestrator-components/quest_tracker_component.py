from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import OrchestratorComponent
from flock.runtime import Context


@flock_type(name="Quest")
class Quest(BaseModel):
    hero: str = Field(description="The brave adventurer")
    objective: str = Field(description="What they must achieve")
    difficulty: str = Field(description="Easy, medium, or hard")


@flock_type(name="QuestProgress")
class QuestProgress(BaseModel):
    hero: str
    status: str
    completion_bonus: int


@flock_type(name="QuestComplete")
class QuestComplete(BaseModel):
    hero: str
    achievement: str
    total_score: int


class QuestTrackerComponent(OrchestratorComponent):
    """Tracks hero progress across quests and awards achievement points."""

    hero_scores: dict[str, int] = Field(default_factory=dict)
    total_quests: int = Field(default=0, description="Total quests started")

    async def on_pre_publish(self, ctx: Context, artifact) -> None:
        """Award starting points when a new quest begins."""
        if artifact.type_name == "Quest":
            hero = artifact.payload.get("hero")
            difficulty = artifact.payload.get("difficulty", "medium")

            self.total_quests += 1

            # Starting bonus based on difficulty
            bonus_map = {"easy": 5, "medium": 10, "hard": 20}
            starting_bonus = bonus_map.get(difficulty.lower(), 10)

            current_score = self.hero_scores.get(hero, 0)
            self.hero_scores[hero] = current_score + starting_bonus

            print(f"🗡️  {hero} accepted a {difficulty} quest! (+{starting_bonus} points)")
            print(f"   Current score: {self.hero_scores[hero]}")

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        """Award completion points when quests finish."""
        if artifact.type_name == "QuestProgress":
            hero = artifact.payload.get("hero")
            status = artifact.payload.get("status", "")

            if "complete" in status.lower() or "success" in status.lower():
                # Completion bonus!
                completion_bonus = 50
                current_score = self.hero_scores.get(hero, 0)
                self.hero_scores[hero] = current_score + completion_bonus

                print(f"✨ {hero} completed their quest! (+{completion_bonus} points)")
                print(f"   Total score: {self.hero_scores[hero]}")

    async def on_cycle_complete(self, ctx: Context) -> None:
        """Show leaderboard after each processing cycle."""
        if not self.hero_scores:
            return

        print("\n🏆 Hero Leaderboard 🏆")
        print("=" * 40)
        sorted_heroes = sorted(self.hero_scores.items(), key=lambda x: x[1], reverse=True)
        for rank, (hero, score) in enumerate(sorted_heroes, 1):
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
            print(f"{medal} {rank}. {hero:15} - {score:4} points")
        print("=" * 40)
        print(f"Total quests tracked: {self.total_quests}\n")


async def main() -> None:
    flock = Flock()

    # Add quest tracker component
    flock.with_components(QuestTrackerComponent())

    # Quest handler agent
    (
        flock.agent("quest_handler")
        .description("Processes quests and reports progress")
        .consumes(Quest)
        .publishes(QuestProgress)
        .system_prompt("You track quest progress. Reply with status updates.")
    )

    # Achievement agent
    (
        flock.agent("achievement_herald")
        .description("Announces major achievements")
        .consumes(QuestProgress)
        .publishes(QuestComplete)
        .system_prompt(
            "When heroes complete quests, create epic achievement announcements."
        )
    )

    print("🎮 Quest Tracker Demo")
    print("=" * 40)

    # Launch some quests!
    await flock.publish(
        Quest(
            hero="Aria the Swift",
            objective="Retrieve the Crystal of Dawn",
            difficulty="hard",
        )
    )

    await flock.publish(
        Quest(
            hero="Thor Ironheart",
            objective="Defeat the Shadow Dragon",
            difficulty="hard",
        )
    )

    await flock.publish(
        Quest(
            hero="Luna Starbright",
            objective="Find the Lost Spellbook",
            difficulty="medium",
        )
    )

    await flock.publish(
        Quest(
            hero="Aria the Swift",
            objective="Explore the Sunken Ruins",
            difficulty="easy",
        )
    )

    await flock.run_until_idle()

    # Show final artifacts
    print("\n📜 Quest Artifacts")
    print("=" * 40)
    for artifact in await flock.store.list():
        if artifact.type_name == "QuestComplete":
            payload = artifact.payload
            print(f"\n🎖️  {payload.get('achievement', 'Achievement unlocked!')}")
            print(f"    Hero: {payload.get('hero', 'Unknown')}")
            print(f"    Score: {payload.get('total_score', 0)}")


if __name__ == "__main__":
    asyncio.run(main())
