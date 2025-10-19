from __future__ import annotations

import asyncio
from textwrap import fill

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import EngineComponent
from flock.runtime import EvalInputs, EvalResult
from flock.subscription import BatchSpec


@flock_type(name="PotionIngredient")
class PotionIngredient(BaseModel):
    name: str = Field(description="Ingredient name, e.g., Moondew")
    effect: str = Field(description="What the ingredient contributes to the brew")


@flock_type(name="PotionRecipe")
class PotionRecipe(BaseModel):
    title: str = Field(description="Name of the completed potion")
    incantation: str = Field(description="Short mantra for dramatic flair")
    tasting_notes: str = Field(description="How the potion feels when activated")
    ingredients: list[str] = Field(description="Ingredient summary", default_factory=list)


class PotionBatchEngine(EngineComponent):
    """Engine that only reveals its magic once enough ingredients arrive.

    Auto-detects batch mode via ctx.is_batch flag to determine whether to
    create a draft or full potion recipe.
    """

    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        """Process single ingredient or batch with auto-detection.

        Auto-detects batch mode via ctx.is_batch flag (set by orchestrator when
        BatchSpec flushes accumulated ingredients).

        Args:
            agent: Agent instance
            ctx: Execution context (check ctx.is_batch for batch mode)
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce

        Returns:
            EvalResult with PotionRecipe artifact
        """
        # Auto-detect batch mode from context
        is_batch = bool(getattr(ctx, "is_batch", False))

        if is_batch:
            # Batch mode: Create full potion recipe from accumulated ingredients
            ingredients = inputs.all_as(PotionIngredient)
            if not ingredients:
                return EvalResult.empty()

            title = self._name_potion(ingredients)
            incantation = self._craft_incantation(ingredients)
            tasting_notes = self._describe_feel(ingredients)

            recipe = PotionRecipe(
                title=title,
                incantation=incantation,
                tasting_notes=tasting_notes,
                ingredients=[f"{item.name} ({item.effect})" for item in ingredients],
            )
            return EvalResult.from_object(recipe, agent=agent)
        else:
            # Single mode: Create draft placeholder
            ingredient = inputs.first_as(PotionIngredient)
            if not ingredient:
                return EvalResult.empty()

            hint = (
                f"{ingredient.name} whispers that patience is key. "
                "Add a few more curious ingredients to coax the potion to life."
            )
            placeholder = PotionRecipe(
                title="Potion Draft",
                incantation="Not quite ready...",
                tasting_notes=hint,
                ingredients=[ingredient.name],
            )
            return EvalResult.from_object(placeholder, agent=agent)

    def _name_potion(self, ingredients: list[PotionIngredient]) -> str:
        anchors = [item.name for item in ingredients]
        if len(anchors) == 1:
            return f"Essence of {anchors[0]}"
        if len(anchors) == 2:
            return f"Elixir of {anchors[0]} & {anchors[1]}"
        return f"Symphony of {' • '.join(anchors)}"

    def _craft_incantation(self, ingredients: list[PotionIngredient]) -> str:
        verbs = [item.effect.split()[0] for item in ingredients if item.effect]
        chant = " ".join(word.capitalize() for word in verbs[:4])
        return f"{chant}! Stir the cosmos, awaken the brew!"

    def _describe_feel(self, ingredients: list[PotionIngredient]) -> str:
        effects = ", ".join(item.effect for item in ingredients)
        sentence = (
            f"The potion crackles with a blend of {effects}. "
            "Sip slowly—each shimmer tells a different tale."
        )
        return fill(sentence, width=72)


async def main() -> None:
    flock = Flock()

    (
        flock.agent("potion_brewer")
        .description("Collects whimsical ingredients and forges a batch potion recipe.")
        .consumes(PotionIngredient, batch=BatchSpec(size=3))
        .publishes(PotionRecipe)
        .with_engines(PotionBatchEngine())
    )

    await flock.publish(PotionIngredient(name="Moondew", effect="glows gently in starlight"))
    await flock.publish(PotionIngredient(name="Thunderpetal", effect="sparks courage in the heart"))
    await flock.publish(PotionIngredient(name="Echofern", effect="echoes forgotten melodies"))

    await flock.publish(PotionIngredient(name="Frostvine", effect="chills time for a moment"))
    await flock.publish(PotionIngredient(name="Sunburst Zest", effect="radiates joyful warmth"))
    await flock.publish(PotionIngredient(name="Silver Husk", effect="shields the dreamer"))

    await flock.run_until_idle()

    print("\nPotion Recipes")
    print("-------------")
    for artifact in await flock.store.list():
        if artifact.produced_by != "potion_brewer":
            continue
        payload = artifact.payload
        print(f"\n✨ {payload['title']}")
        print(f"   Incantation: {payload['incantation']}")
        print(f"   Tasting notes: {payload['tasting_notes']}")
        print("   Ingredient lineup:")
        for entry in payload["ingredients"]:
            print(f"     • {entry}")


if __name__ == "__main__":
    asyncio.run(main())
