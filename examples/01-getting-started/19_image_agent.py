"""
Getting Started: Agents That Look at Images

An LLM agent receives `flock.Image` fields as pictures, not as text. Here a
fact checker compares each drawing with its caption: two captions are right,
one is wrong, and only a model that sees the picture can tell which.

🎯 Key Concepts:
- `Image` fields in artifacts (`Image.from_pil`, `from_file`, `from_bytes`)
- The DSPy engine sends them to the model as images, in single runs, batches
  and joins; images in conversation context are described, not inlined
- Use a model with vision support (e.g. openai/gpt-4.1); a model known to be
  text-only fails with a clear error before any request

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from PIL import Image as PILImage
from PIL import ImageDraw
from pydantic import BaseModel, Field

from flock import Flock, Image
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class Drawing(BaseModel):
    """A picture with the caption someone wrote for it."""

    caption: str
    picture: Image


@flock_type
class CaptionCheck(BaseModel):
    caption: str
    seen: str = Field(description="What the picture actually shows: shape and color")
    caption_is_correct: bool


def draw(shape: str, color: str) -> Image:
    canvas = PILImage.new("RGB", (256, 256), "white")
    pen = ImageDraw.Draw(canvas)
    box = (48, 48, 208, 208)
    if shape == "circle":
        pen.ellipse(box, fill=color)
    elif shape == "square":
        pen.rectangle(box, fill=color)
    else:
        pen.polygon([(128, 40), (216, 216), (40, 216)], fill=color)
    return Image.from_pil(canvas)


flock = Flock()

fact_checker = (
    flock.agent("fact_checker")
    .description(
        "Look at the picture and check whether the caption describes it: "
        "the shape and its color must both match."
    )
    .consumes(Drawing)
    .publishes(CaptionCheck)
)


DRAWINGS = [
    Drawing(caption="a red circle", picture=draw("circle", "red")),
    Drawing(caption="a blue square", picture=draw("square", "blue")),
    Drawing(caption="a green circle", picture=draw("triangle", "orange")),  # wrong
]


async def main_cli():
    for drawing in DRAWINGS:
        await flock.publish(drawing)
    await flock.run_until_idle()

    for check in await flock.store.get_by_type(CaptionCheck):
        verdict = "✅" if check.caption_is_correct else "❌"
        print(f"{verdict} '{check.caption}' - the picture shows {check.seen}")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    for drawing in DRAWINGS:
        await flock.publish(drawing)
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
