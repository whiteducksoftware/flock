"""The sinks demos (examples/16-sinks) close their loops without API keys: the
app publishes, the decider decides, the sink delivers back to the app (#618)."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image as PILImage

from flock.core.image import Image


EXAMPLES = Path(__file__).parents[1] / "examples" / "16-sinks"


def load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def snake(monkeypatch):
    module = load("02_snake.py", "sink_demo_snake")
    monkeypatch.setattr(module, "THINK_SECONDS", 0)
    yield module
    sys.modules.pop("sink_demo_snake", None)


@pytest.fixture
def quick_draw(monkeypatch):
    module = load("03_quick_draw.py", "sink_demo_quick_draw")
    monkeypatch.setattr(module, "THINK_SECONDS", 0)
    yield module
    sys.modules.pop("sink_demo_quick_draw", None)


def answer_with(handler):
    """A respx side effect that hands the sink's request to the app's handler."""

    async def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=await handler(json.loads(request.content)))

    return respond


async def test_snake_plays_one_decision_per_step_in_order(snake, monkeypatch):
    flock = snake.build_flock(fake=True)
    steps = 30

    async def publish(game):
        # In process instead of over REST; the game stops after a few steps
        if game.step < steps:
            await flock.publish(game.state(), correlation_id=game.id)

    monkeypatch.setattr(snake, "publish", publish)
    with respx.mock() as router:
        router.post(f"http://127.0.0.1:{snake.GAME_PORT}/move").mock(
            side_effect=answer_with(snake.move)
        )
        game = (await snake.new_game())["game"]
        await flock.run_until_idle()

    played = snake.games[game]
    assert played.step == steps or not played.alive
    artifacts = [a for a in await flock.store.list() if a.correlation_id == game]
    kinds = [a.type.rsplit(".", 1)[-1] for a in artifacts]
    assert kinds.count("SnakeState") == kinds.count("Delivered") == played.step
    assert "DeliveryFailed" not in kinds
    # The heuristic moves toward the food
    assert played.eaten >= 1


def sketch_png() -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (64, 64), "white").save(buffer, "PNG")
    return buffer.getvalue()


async def test_quick_draw_gets_it_once_the_guesser_is_sure(quick_draw):
    flock = quick_draw.build_flock(fake=True)
    pushed: list[dict] = []
    quick_draw.listeners.append(_Recorder(pushed))

    with respx.mock() as router:
        router.post(f"http://127.0.0.1:{quick_draw.APP_PORT}/guess").mock(
            side_effect=answer_with(quick_draw.guess)
        )
        drawing = (await quick_draw.new_drawing())["drawing"]
        for stroke in range(1, 7):
            quick_draw.drawings[drawing]["strokes"] = stroke
            await flock.publish(
                quick_draw.Sketch(
                    drawing=drawing, stroke=stroke, image=Image.from_bytes(sketch_png())
                ),
                correlation_id=drawing,
            )
            await flock.run_until_idle()

    assert [event["strokes"] for event in pushed] == [1, 2, 3, 4, 5, 6]
    got_it = [event for event in pushed if event["got_it"]]
    assert len(got_it) == 1
    assert got_it[0]["choice"] == quick_draw.drawings[drawing]["prompt"]
    assert got_it[0]["strokes"] == 4  # 0.12 + 0.13 * strokes passes 0.6


class _Recorder:
    """A listener queue that keeps what the app pushes to the page."""

    def __init__(self, events: list[dict]) -> None:
        self.events = events

    def put_nowait(self, event: dict) -> None:
        self.events.append(event)
