"""The sinks demos (examples/16-sinks) close their loops without API keys: the
app publishes, the decider decides, the sink delivers back to the app (#618)."""

from __future__ import annotations

import importlib.util
import io
import json
import random
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
    monkeypatch.setattr(module, "random", random.Random(618))  # the same game each run
    yield module
    sys.modules.pop("sink_demo_snake", None)


@pytest.fixture
def quick_draw(monkeypatch):
    module = load("03_quick_draw.py", "sink_demo_quick_draw")
    monkeypatch.setattr(module, "THINK_SECONDS", 0)
    yield module
    sys.modules.pop("sink_demo_quick_draw", None)


def read_back(flock):
    """A respx side effect for GET /api/v1/artifacts/{id}: the artifact from the store."""
    from uuid import UUID

    async def respond(request: httpx.Request) -> httpx.Response:
        artifact = await flock.store.get(UUID(request.url.path.rsplit("/", 1)[-1]))
        return httpx.Response(200, json={"payload": artifact.payload})

    return respond


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
    # Every state got a move, delivered once; a fatal move is no step
    moves = played.step + (0 if played.alive else 1)
    assert kinds.count("SnakeState") == kinds.count("Delivered") == moves
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
        router.get(
            url__regex=rf"http://127\.0\.0\.1:{quick_draw.FLOCK_PORT}/api/v1/artifacts/.+"
        ).mock(side_effect=read_back(flock))
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


async def test_a_retried_move_is_played_once(snake, monkeypatch):
    published: list[int] = []

    async def publish(game):
        published.append(game.step)

    monkeypatch.setattr(snake, "publish", publish)
    game = (await snake.new_game())["game"]
    envelope = {
        "id": "decision-1",
        "correlation_id": game,
        "payload": {"choice": "up", "best_guess": None, "probabilities": {"up": 0.9}},
    }

    await snake.move(envelope)
    await snake.move(envelope)  # the sink retries after a failed answer

    assert snake.games[game].step == 1
    assert published == [0, 1, 1]  # the start, the step, the same step again


async def test_quick_draw_answers_strokes_drawn_ahead_in_order(quick_draw, monkeypatch):
    import asyncio

    answer = quick_draw.StrokeByStroke.decide_many
    calls = 0

    async def slow_first(self, state, questions, images=()):
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.sleep(0.05)  # the first guess takes longer than the next
        return await answer(self, state, questions, images)

    monkeypatch.setattr(quick_draw.StrokeByStroke, "decide_many", slow_first)
    flock = quick_draw.build_flock(fake=True)
    pushed: list[dict] = []
    quick_draw.listeners.append(_Recorder(pushed))

    with respx.mock() as router:
        router.post(f"http://127.0.0.1:{quick_draw.APP_PORT}/guess").mock(
            side_effect=answer_with(quick_draw.guess)
        )
        router.get(
            url__regex=rf"http://127\.0\.0\.1:{quick_draw.FLOCK_PORT}/api/v1/artifacts/.+"
        ).mock(side_effect=read_back(flock))
        drawing = (await quick_draw.new_drawing())["drawing"]
        # Six strokes before the first guess is back
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
    # In stroke order: the stand-in grows surer of the prompt with every stroke
    prompt = quick_draw.drawings[drawing]["prompt"]
    sureness = [event["probabilities"][prompt] for event in pushed]
    assert sureness == sorted(sureness)
    assert [event["strokes"] for event in pushed if event["got_it"]] == [4]


async def test_quick_draw_shows_each_guess_once_with_the_stroke_it_answers(
    quick_draw, monkeypatch
):
    """A failed guess leaves its stroke out; a retried delivery is shown once."""
    answer = quick_draw.StrokeByStroke.decide_many

    async def fail_stroke_two(self, state, questions, images=()):
        if '"stroke": 2' in state:
            raise RuntimeError("the model is down for a moment")
        return await answer(self, state, questions, images)

    monkeypatch.setattr(quick_draw.StrokeByStroke, "decide_many", fail_stroke_two)
    flock = quick_draw.build_flock(fake=True)
    pushed: list[dict] = []
    quick_draw.listeners.append(_Recorder(pushed))
    delivered: list[dict] = []

    async def deliver_twice(envelope):
        delivered.append(envelope)
        await quick_draw.guess(envelope)
        return await quick_draw.guess(envelope)  # as after a lost answer

    with respx.mock() as router:
        router.post(f"http://127.0.0.1:{quick_draw.APP_PORT}/guess").mock(
            side_effect=answer_with(deliver_twice)
        )
        router.get(
            url__regex=rf"http://127\.0\.0\.1:{quick_draw.FLOCK_PORT}/api/v1/artifacts/.+"
        ).mock(side_effect=read_back(flock))
        drawing = (await quick_draw.new_drawing())["drawing"]
        for stroke in range(1, 6):
            await flock.publish(
                quick_draw.Sketch(
                    drawing=drawing, stroke=stroke, image=Image.from_bytes(sketch_png())
                ),
                correlation_id=drawing,
            )
        await flock.run_until_idle()

    assert [event["strokes"] for event in pushed] == [1, 3, 4, 5]
    assert [event["strokes"] for event in pushed if event["got_it"]] == [4]


async def test_an_overlapping_retry_shows_a_guess_once(quick_draw, monkeypatch):
    import asyncio

    pushed: list[dict] = []
    quick_draw.listeners.append(_Recorder(pushed))
    delays = [0.05, 0]  # the first lookup is slow, the retry overtakes it

    async def stroke_of(sketch_id):
        await asyncio.sleep(delays.pop(0))
        return 1

    monkeypatch.setattr(quick_draw, "stroke_of", stroke_of)
    drawing = (await quick_draw.new_drawing())["drawing"]
    envelope = {
        "id": "decision-1",
        "correlation_id": drawing,
        "payload": {
            "choice": "UNSURE",
            "best_guess": "sun",
            "probabilities": {"sun": 0.4},
            "subject_ids": ["s-1"],
        },
    }

    await asyncio.gather(quick_draw.guess(envelope), quick_draw.guess(envelope))

    assert len(pushed) == 1


async def test_a_paused_game_holds_its_next_step_until_it_resumes(snake, monkeypatch):
    published: list[int] = []

    async def publish(game):
        published.append(game.step)

    monkeypatch.setattr(snake, "publish", publish)
    game = (await snake.new_game())["game"]
    await snake.pause(game)

    # The decision in flight still moves the snake, the next step waits
    await snake.move({
        "id": "decision-1",
        "correlation_id": game,
        "payload": {"choice": "up", "best_guess": None, "probabilities": {"up": 0.9}},
    })
    assert published == [0]

    await snake.resume(game)
    assert published == [0, 1]


async def test_the_game_publishes_where_the_page_points_it(snake):
    from fastapi import HTTPException

    with respx.mock() as router:
        route = router.post("http://127.0.0.1:9100/api/v1/artifacts").mock(
            return_value=httpx.Response(200, json={"status": "accepted"})
        )
        await snake.set_settings(snake.Settings(flock_url=" http://127.0.0.1:9100/ "))
        await snake.new_game()

    assert route.call_count == 1
    with pytest.raises(HTTPException):
        await snake.set_settings(snake.Settings(flock_url="localhost:9100"))
