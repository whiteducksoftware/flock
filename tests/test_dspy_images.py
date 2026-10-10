"""LLM agents receive flock.Image fields as images (#510)."""

from __future__ import annotations

import typing

import dspy
import pytest
from pydantic import BaseModel

from flock.core.agent import AgentOutput, OutputGroup
from flock.core.artifacts import Artifact, ArtifactSpec
from flock.core.image import Image
from flock.engines.dspy.image_inputs import dspy_input_model, ensure_vision_support
from flock.engines.dspy.signature_builder import DSPySignatureBuilder
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalInputs


def _png(color: str = "red") -> Image:
    from PIL import Image as PILImage

    return Image.from_pil(PILImage.new("RGB", (8, 8), color))


@flock_type
class ImgCaption(BaseModel):
    text: str
    picture: Image


@flock_type
class ImgAlbum(BaseModel):
    title: str
    cover: Image | None = None
    pages: list[Image] = []
    captions: list[ImgCaption] = []


@flock_type
class ImgPlain(BaseModel):
    text: str


@flock_type
class ImgVerdict(BaseModel):
    summary: str


class Agent:
    name = "viewer"
    description = "Describes pictures"


def _output_group() -> OutputGroup:
    spec = ArtifactSpec(type_name=type_registry.name_for(ImgVerdict), model=ImgVerdict)
    return OutputGroup(outputs=[AgentOutput(spec=spec, default_visibility=None)])


def _artifact(model: BaseModel) -> Artifact:
    return Artifact(
        type=type_registry.name_for(type(model)),
        payload=model.model_dump(),
        produced_by="external",
    )


def _annotations(model: type[BaseModel]) -> dict[str, typing.Any]:
    return {name: field.annotation for name, field in model.model_fields.items()}


def test_models_without_images_are_used_as_they_are():
    assert dspy_input_model(ImgPlain) is ImgPlain


def test_image_fields_become_dspy_images_at_any_depth():
    album = dspy_input_model(ImgAlbum)
    caption = dspy_input_model(ImgCaption)

    assert album.__name__ == "ImgAlbum"
    assert _annotations(caption) == {"text": str, "picture": dspy.Image}
    assert _annotations(album) == {
        "title": str,
        "cover": dspy.Image | None,
        "pages": list[dspy.Image],
        "captions": list[caption],
    }
    assert dspy_input_model(ImgAlbum) is album  # built once per model


@pytest.mark.parametrize("batched", [False, True])
def test_the_model_receives_the_picture_not_its_base64_text(batched):
    builder = DSPySignatureBuilder()
    picture = _png()
    inputs = EvalInputs(
        artifacts=[_artifact(ImgCaption(text="a red square", picture=picture))],
        state={},
    )
    signature = builder.prepare_signature_for_output_group(
        dspy,
        agent=Agent(),
        inputs=inputs,
        output_group=_output_group(),
        batched=batched,
    )
    payload = builder.prepare_execution_payload_for_output_group(
        inputs,
        _output_group(),
        batched=batched,
        has_context=False,
        context_history=None,
        sys_desc="Describe the picture",
    )

    messages = dspy.ChatAdapter().format(signature, demos=[], inputs=payload)

    parts = [
        part
        for message in messages
        if isinstance(message["content"], list)
        for part in message["content"]
    ]
    assert {"type": "image_url", "image_url": {"url": picture.url}} in parts
    text = " ".join(
        part["text"]
        if isinstance(part, dict) and part.get("type") == "text"
        else str(part)
        for message in messages
        for part in (
            message["content"]
            if isinstance(message["content"], list)
            else [message["content"]]
        )
        if not (isinstance(part, dict) and part.get("type") == "image_url")
    )
    assert picture.base64_data not in text
    assert "a red square" in text


def test_context_images_are_described_not_inlined():
    builder = DSPySignatureBuilder()
    picture = _png("blue")
    earlier = _artifact(ImgCaption(text="earlier", picture=picture))

    payload = builder.prepare_execution_payload_for_output_group(
        EvalInputs(artifacts=[_artifact(ImgPlain(text="now"))], state={}),
        _output_group(),
        batched=False,
        has_context=True,
        context_history=[earlier],
        sys_desc="Answer",
    )

    (context_item,) = payload["context"]
    assert context_item.payload["picture"]["url"].startswith("🖼 image/")
    assert earlier.payload["picture"]["url"] == picture.url  # the artifact is untouched


def test_a_known_text_only_model_fails_with_a_clear_error():
    inputs = EvalInputs(
        artifacts=[_artifact(ImgCaption(text="x", picture=_png()))], state={}
    )

    with pytest.raises(ValueError, match=r"openai/gpt-3\.5-turbo.*ImgCaption\.picture"):
        ensure_vision_support("openai/gpt-3.5-turbo", inputs)


@pytest.mark.parametrize(
    "model", ["openai/gpt-4.1", "azure/any-deployment-name", "local/unknown"]
)
def test_vision_and_unknown_models_pass(model):
    inputs = EvalInputs(
        artifacts=[_artifact(ImgCaption(text="x", picture=_png()))], state={}
    )

    ensure_vision_support(model, inputs)  # unknown models: the provider decides


def test_inputs_without_images_are_never_checked():
    inputs = EvalInputs(artifacts=[_artifact(ImgPlain(text="x"))], state={})

    ensure_vision_support("openai/gpt-3.5-turbo", inputs)


async def test_the_engine_rejects_images_for_a_text_only_model():
    from flock.engines.dspy_engine import DSPyEngine

    engine = DSPyEngine(model="openai/gpt-3.5-turbo")
    inputs = EvalInputs(
        artifacts=[_artifact(ImgCaption(text="x", picture=_png()))], state={}
    )

    with pytest.raises(ValueError, match="does not accept images"):
        await engine._evaluate_internal(
            Agent(), None, inputs, batched=False, output_group=_output_group()
        )
