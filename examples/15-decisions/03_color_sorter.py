"""
Decision Models: Sorting Images by Color

A decision agent looks at generated shapes and sorts them into color bins.
Orange and purple shapes sit between two bins on purpose. With gpt-6-luna,
pure colors come back at p = 1.00 while orange leans to yellow and purple to
blue at 0.85-0.95, so a threshold of 0.97 sends the in-between shapes to the
`inspector` (UNSURE) instead of a bin.

🎯 Key Concepts:
- `flock.Image` fields in artifacts (`Image.from_pil`, `from_file`, `from_bytes`)
- `.decides(...)` with an image-capable decision model
- Bin agents subscribe to options and receive the shape itself

🎛️  CONFIGURATION:
- USE_DASHBOARD = True serves the dashboard and publishes a shape every
  second: watch the decider's option lanes fill with thumbnails.
- IMAGE_DECISION_MODEL: a decision model that accepts images, e.g.
  "openai/gpt-6-luna" (OPENAI_API_KEY) or "local/<name>" for a local
  systemone server running a vision-enabled model. Microsoft-Decision-1
  (`azure/decision-1`) and Jev accept text only.
"""

import asyncio
import os
import random

from PIL import Image as PILImage
from PIL import ImageDraw
from pydantic import BaseModel

from flock import Choice, Decision, EngineComponent, EvalResult, Flock, Image
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
IMAGE_DECISION_MODEL = os.getenv("IMAGE_DECISION_MODEL", "openai/gpt-6-luna")
SHAPES = 16
THRESHOLD = 0.97  # pure colors score 1.00, in-between colors 0.85-0.95
# ============================================================================

PALETTE = {
    "red": (220, 40, 40),
    "green": (40, 170, 70),
    "blue": (40, 80, 220),
    "yellow": (240, 210, 40),
    "orange": (245, 140, 30),  # between red and yellow
    "purple": (140, 60, 190),  # between red and blue
}


@flock_type
class Shape(BaseModel):
    """A drawn shape whose color decides its bin."""

    label: str
    picture: Image


@flock_type
class Binned(BaseModel):
    """Where a shape ended up."""

    bin: str
    label: str


class ColorBin(Choice):
    """Which color bin does the shape in the image belong to?"""

    red = "Red shapes"
    green = "Green shapes"
    blue = "Blue shapes"
    yellow = "Yellow shapes"


def draw_shape(color_name: str, kind: str, rng: random.Random) -> Image:
    canvas = PILImage.new("RGB", (256, 256), (245, 245, 240))
    pen = ImageDraw.Draw(canvas)
    box = [
        rng.randint(20, 60),
        rng.randint(20, 60),
        rng.randint(190, 236),
        rng.randint(190, 236),
    ]
    color = PALETTE[color_name]
    if kind == "circle":
        pen.ellipse(box, fill=color)
    elif kind == "triangle":
        pen.polygon(
            [(box[0], box[3]), ((box[0] + box[2]) // 2, box[1]), (box[2], box[3])],
            fill=color,
        )
    else:
        pen.rectangle(box, fill=color)
    return Image.from_pil(canvas)


class BinEngine(EngineComponent):
    """Deterministic bin: records which shapes arrived (no LLM)."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        shape = inputs.first_as(Shape)
        return EvalResult.from_object(
            Binned(bin=agent.name, label=shape.label), agent=agent
        )


flock = Flock()

sorter = (
    flock.agent("color_sorter")
    .consumes(Shape)
    .decides(ColorBin, model=IMAGE_DECISION_MODEL, threshold=THRESHOLD)
)
for name, handle in [
    ("red_bin", ColorBin.red),
    ("green_bin", ColorBin.green),
    ("blue_bin", ColorBin.blue),
    ("yellow_bin", ColorBin.yellow),
    ("inspector", ColorBin.UNSURE),
]:
    flock.agent(name).consumes(handle).with_engines(BinEngine()).publishes(Binned)


def shapes(count: int) -> list[Shape]:
    rng = random.Random(7)
    result = []
    for _ in range(count):
        color, kind = (
            rng.choice(list(PALETTE)),
            rng.choice(["circle", "square", "triangle"]),
        )
        result.append(
            Shape(label=f"{color} {kind}", picture=draw_shape(color, kind, rng))
        )
    return result


async def main_cli():
    print(f"\n🎨 Sorting {SHAPES} shapes with {IMAGE_DECISION_MODEL}\n")
    for shape in shapes(SHAPES):
        await flock.publish(shape)
    await flock.run_until_idle()

    labels = {
        str(a.id): a.payload["label"]
        for a in await flock.store.list()
        if a.type == type_registry.name_for(Shape)
    }
    for artifact in await flock.store.list():
        if artifact.type != type_registry.name_for(Decision.of(ColorBin)):
            continue
        decision = Decision.of(ColorBin)(**artifact.payload)
        label = labels[decision.subject_ids[0]]
        p = decision.probabilities[decision.best_guess]
        print(
            f"{label:<18} → {decision.choice:<7} (best guess {decision.best_guess} {p:.2f})"
        )


async def main_dashboard():
    async def feed():
        await asyncio.sleep(8)  # let the dashboard start
        for shape in shapes(SHAPES):
            await flock.publish(shape)
            await asyncio.sleep(1.0)

    feeder = asyncio.create_task(feed())
    await flock.serve(dashboard=True)
    await feeder


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
