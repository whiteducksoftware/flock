from __future__ import annotations

import asyncio
from datetime import datetime

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import OrchestratorComponent
from flock.runtime import Context


@flock_type(name="Dish")
class Dish(BaseModel):
    name: str = Field(description="Dish name")
    chef: str = Field(description="Who's cooking")
    spice_level: int = Field(ge=1, le=5, description="Heat level 1-5")


@flock_type(name="Review")
class Review(BaseModel):
    dish_name: str
    rating: int = Field(ge=1, le=5)
    comment: str


@flock_type(name="ChefRanking")
class ChefRanking(BaseModel):
    chef: str
    total_dishes: int
    avg_rating: float
    spice_mastery: str


class KitchenMonitorComponent(OrchestratorComponent):
    """Monitors kitchen activity and tracks chef statistics in real-time."""

    dishes_in_progress: int = Field(default=0, description="Dishes currently being prepared")
    completed_dishes: int = Field(default=0, description="Dishes that finished cooking")
    chef_stats: dict[str, dict] = Field(
        default_factory=dict, description="Per-chef statistics"
    )
    spice_warnings: int = Field(default=0, description="Number of extra-spicy dishes")
    start_time: datetime | None = Field(default=None, description="When kitchen opened")

    async def on_pre_publish(self, ctx: Context, artifact) -> None:
        """Track when dishes enter the kitchen."""
        if artifact.type_name == "Dish":
            if self.start_time is None:
                self.start_time = datetime.now()

            self.dishes_in_progress += 1
            chef = artifact.payload.get("chef")
            dish_name = artifact.payload.get("name")
            spice = artifact.payload.get("spice_level", 1)

            # Initialize chef stats if needed
            if chef not in self.chef_stats:
                self.chef_stats[chef] = {
                    "dishes": 0,
                    "total_spice": 0,
                    "reviews": [],
                }

            self.chef_stats[chef]["dishes"] += 1
            self.chef_stats[chef]["total_spice"] += spice

            # Spice warning!
            if spice >= 4:
                self.spice_warnings += 1
                print(f"🌶️  SPICE ALERT! {chef} is preparing {dish_name} (🔥 Level {spice})")

            print(f"🍳 {chef} started cooking '{dish_name}' (in kitchen: {self.dishes_in_progress})")

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        """Track reviews and completion."""
        if artifact.type_name == "Review":
            dish = artifact.payload.get("dish_name")
            rating = artifact.payload.get("rating", 3)
            comment = artifact.payload.get("comment", "")

            # Find which chef made this dish
            for chef, stats in self.chef_stats.items():
                stats["reviews"].append(rating)

            self.dishes_in_progress = max(0, self.dishes_in_progress - 1)
            self.completed_dishes += 1

            stars = "⭐" * rating
            print(f"📝 Review for '{dish}': {stars} - {comment}")

    async def on_cycle_complete(self, ctx: Context) -> None:
        """Show kitchen status after each cycle."""
        if not self.chef_stats:
            return

        elapsed = (
            (datetime.now() - self.start_time).total_seconds()
            if self.start_time
            else 0
        )

        print("\n" + "=" * 50)
        print("🔥 KITCHEN STATUS BOARD 🔥")
        print("=" * 50)
        print(f"⏱️  Service time: {elapsed:.1f}s")
        print(f"📊 Dishes in progress: {self.dishes_in_progress}")
        print(f"✅ Dishes completed: {self.completed_dishes}")
        print(f"🌶️  Spice warnings issued: {self.spice_warnings}")
        print()

        print("👨‍🍳 Chef Performance:")
        print("-" * 50)

        for chef, stats in sorted(self.chef_stats.items()):
            dishes = stats["dishes"]
            avg_spice = stats["total_spice"] / dishes if dishes > 0 else 0
            reviews = stats["reviews"]
            avg_rating = sum(reviews) / len(reviews) if reviews else 0

            # Determine spice mastery
            if avg_spice >= 4:
                mastery = "🔥 Fire Master"
            elif avg_spice >= 3:
                mastery = "🌶️  Spice Veteran"
            elif avg_spice >= 2:
                mastery = "🫑 Mild Enthusiast"
            else:
                mastery = "🧊 Cool & Calm"

            stars = "⭐" * int(avg_rating) if reviews else "⏳ Pending"

            print(f"\n  {chef}")
            print(f"    Dishes made: {dishes}")
            print(f"    Avg rating: {stars} ({avg_rating:.1f})")
            print(f"    Spice style: {mastery} (avg {avg_spice:.1f})")

        print("=" * 50 + "\n")


async def main() -> None:
    flock = Flock()

    # Add kitchen monitor
    flock.with_components(KitchenMonitorComponent())

    # Cooking agent
    (
        flock.agent("kitchen_crew")
        .description("Prepares dishes and awaits reviews")
        .consumes(Dish)
        .publishes(Review)
        .system_prompt(
            "You are a food critic. Rate dishes 1-5 stars and write brief, "
            "colorful reviews. Focus on flavor, presentation, and heat level."
        )
    )

    # Rankings agent
    (
        flock.agent("ranking_board")
        .description("Compiles chef rankings")
        .consumes(Review)
        .publishes(ChefRanking)
        .system_prompt("Create chef rankings based on reviews.")
    )

    print("🍽️  Welcome to The Flock Kitchen!")
    print("=" * 50 + "\n")

    # Chefs start cooking!
    await flock.publish(
        Dish(name="Dragon's Breath Curry", chef="Chef Akira", spice_level=5)
    )

    await flock.publish(
        Dish(name="Honey Glazed Salmon", chef="Chef Marie", spice_level=1)
    )

    await flock.publish(
        Dish(name="Inferno Tacos", chef="Chef Carlos", spice_level=4)
    )

    await flock.publish(
        Dish(name="Truffle Risotto", chef="Chef Marie", spice_level=2)
    )

    await flock.publish(
        Dish(name="Volcanic Ramen", chef="Chef Akira", spice_level=5)
    )

    await flock.publish(
        Dish(name="Mild Mushroom Soup", chef="Chef Elena", spice_level=1)
    )

    await flock.run_until_idle()

    # Final summary
    print("\n🎉 Service Complete!")
    print("=" * 50)
    all_artifacts = await flock.store.list()
    reviews = [a for a in all_artifacts if a.type_name == "Review"]
    print(f"Total reviews collected: {len(reviews)}")

    if reviews:
        avg = sum(a.payload.get("rating", 0) for a in reviews) / len(reviews)
        print(f"Overall kitchen rating: {'⭐' * int(avg)} ({avg:.2f}/5.0)")


if __name__ == "__main__":
    asyncio.run(main())
