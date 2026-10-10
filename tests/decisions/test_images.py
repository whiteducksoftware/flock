"""Image inputs for decision models."""

from __future__ import annotations

import io
import json

import httpx
import pytest
from PIL import Image as PILImage
from pydantic import BaseModel

from flock import Choice, Decision, Flock, Image
from flock.decisions.providers import (
    DecisionQuestion,
    FakeDecider,
    OpenAIDecisionsProvider,
    SystemOneProvider,
    resolve_provider,
)
from flock.models.system_artifacts import WorkflowError
from flock.registry import flock_type, type_registry


def square(color: tuple[int, int, int]) -> Image:
    buf = io.BytesIO()
    PILImage.new("RGB", (32, 32), color).save(buf, "PNG")
    return Image.from_bytes(buf.getvalue())


RED, BLUE = square((220, 30, 30)), square((30, 60, 220))


@flock_type
class Swatch(BaseModel):
    caption: str
    photo: Image


@flock_type
class Album(BaseModel):
    title: str
    photos: list[Image]


class Color(Choice):
    """What is the color of the square in the image?"""

    red = "Red"
    blue = "Blue"


QUESTION = DecisionQuestion(
    name="Color", instructions="What color?", options={"red": "Red", "blue": "Blue"}
)


@pytest.fixture
def flock() -> Flock:
    orchestrator = Flock()
    orchestrator.is_dashboard = True
    return orchestrator


async def test_images_go_to_the_provider_and_placeholders_into_the_state(flock):
    decider = FakeDecider({"red": 0.9, "blue": 0.1})
    flock.agent("painter").consumes(Swatch).decides(Color, model=decider)

    await flock.publish(Swatch(caption="a square", photo=RED))
    await flock.run_until_idle()

    [(state, _)] = decider.calls
    assert state == 'Swatch: {"caption": "a square", "photo": "<image 1>"}'
    assert decider.received_images == [[RED]]


async def test_several_and_nested_images_keep_their_order(flock):
    decider = FakeDecider({"red": 0.9, "blue": 0.1})
    flock.agent("painter").consumes(Album).decides(Color, model=decider)

    await flock.publish(Album(title="two", photos=[RED, BLUE]))
    await flock.run_until_idle()

    [(state, _)] = decider.calls
    assert state == 'Album: {"title": "two", "photos": ["<image 1>", "<image 2>"]}'
    assert decider.received_images == [[RED, BLUE]]


async def test_text_only_providers_refuse_images(flock):
    decider = FakeDecider({"red": 0.9, "blue": 0.1}, supports_images=False)
    flock.agent("painter").consumes(Swatch).decides(Color, model=decider)

    await flock.publish(Swatch(caption="a square", photo=RED))
    await flock.run_until_idle()

    assert decider.calls == []
    name = type_registry.name_for(Decision.of(Color))
    assert [a for a in await flock.store.list() if a.type == name] == []
    [error] = [
        a
        for a in await flock.store.list()
        if a.type == type_registry.name_for(WorkflowError)
    ]
    assert "does not accept images" in error.payload["error_message"]


def _capture(answer_json: dict) -> tuple[list[httpx.Request], httpx.MockTransport]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=answer_json)

    return captured, httpx.MockTransport(handler)


SYSTEMONE_ANSWER = {
    "answers": {"Color": {"choice": "red", "probabilities": {"red": 1.0, "blue": 0.0}}}
}


async def test_systemone_sends_raw_base64_images():
    captured, transport = _capture(SYSTEMONE_ANSWER)
    provider = SystemOneProvider(
        "http://127.0.0.1:8080/v1/systemone",
        label="local/clef",
        supports_images=True,
        transport=transport,
    )

    await provider.decide("Swatch: <image 1>", QUESTION, images=[RED, BLUE])
    await provider.decide("text only", QUESTION)

    with_images, without = (json.loads(r.content) for r in captured)
    assert with_images["images"] == [RED.base64_data, BLUE.base64_data]
    assert "images" not in without


async def test_openai_sends_images_as_input_parts():
    captured, transport = _capture(
        {
            "answers": [
                {
                    "name": "Color",
                    "choice": "red",
                    "probabilities": [
                        {"value": "red", "probability": 1.0},
                        {"value": "blue", "probability": 0.0},
                    ],
                }
            ]
        }
    )
    provider = OpenAIDecisionsProvider(
        "https://api.openai.com/v1/decisions",
        model="gpt-6-luna",
        api_key="sk-test",
        label="openai/gpt-6-luna",
        transport=transport,
    )

    await provider.decide("Swatch: <image 1>", QUESTION, images=[RED])
    await provider.decide("text only", QUESTION)

    with_images, without = (json.loads(r.content) for r in captured)
    assert with_images["input"] == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Swatch: <image 1>"},
                {"type": "input_image", "image_url": RED.url},
            ],
        }
    ]
    assert without["input"] == "text only"


def test_provider_image_capabilities(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_API_BASE", "https://res.example.com")
    monkeypatch.setenv("AZURE_API_KEY", "k")

    assert resolve_provider("local/clef").supports_images
    assert resolve_provider("openai/gpt-6-luna").supports_images
    assert not resolve_provider("jev/jev-latest").supports_images
    assert not resolve_provider("azure/decision-1").supports_images
