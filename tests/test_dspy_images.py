"""LLM agents receive flock.Image fields as images (#510)."""

from __future__ import annotations

import typing

import dspy
import pytest
from pydantic import BaseModel, ConfigDict, Field, computed_field

from flock.core.agent import AgentOutput, OutputGroup
from flock.core.artifacts import Artifact, ArtifactSpec
from flock.core.image import Image
from flock.engines.dspy.image_inputs import (
    dspy_input_model,
    ensure_vision_support,
    to_dspy_input,
)
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
class ImgNode(BaseModel):
    """A tree of pictures: the model refers to itself."""

    picture: Image | None = None
    children: list[ImgNode] = []


@flock_type
class ImgPair(BaseModel):
    pictures: tuple[Image, Image]


@flock_type
class ImgAliased(BaseModel):
    """Aliased fields, validated by alias only (pydantic's default)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    caption_text: str = Field(alias="captionText")
    picture: Image


@flock_type
class ImgMeasured(BaseModel):
    """A computed field ends up in the payload and should reach the model too."""

    width: int
    height: int
    picture: Image

    @computed_field
    @property
    def area(self) -> int:
        return self.width * self.height


@flock_type
class ImgDerived(BaseModel):
    """The only picture is computed."""

    encoded: str

    @computed_field
    @property
    def picture(self) -> Image:
        return Image(url=self.encoded)


class ImgTextData(BaseModel):
    data: dict[str, str]


class ImgPhotoData(BaseModel):
    data: Image


@flock_type
class ImgAmbiguous(BaseModel):
    """Pydantic picks the first union branch that validates: the text one."""

    item: ImgTextData | ImgPhotoData


@flock_type
class ImgDataUrlText(BaseModel):
    """A text field that happens to hold a data URL: not an image input."""

    raw: str


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


def test_recursive_models_with_images_are_built():
    node = dspy_input_model(ImgNode)

    assert _annotations(node)["picture"] == dspy.Image | None
    assert _annotations(node)["children"] == list[node]
    tree = node.model_validate({
        "picture": None,
        "children": [{"picture": _png().model_dump(), "children": []}],
    })
    assert isinstance(tree.children[0].picture, dspy.Image)


def test_the_copy_keeps_the_model_configuration_and_aliases():
    picture = _png()
    value = ImgAliased(captionText="  a red square  ", picture=picture)

    copied = to_dspy_input(value, ImgAliased)

    assert dspy_input_model(ImgAliased).model_config["str_strip_whitespace"] is True
    assert copied.caption_text == "a red square"
    assert copied.picture.url == picture.url


def test_computed_fields_are_kept():
    value = ImgMeasured(width=3, height=4, picture=_png())

    copied = to_dspy_input(value, ImgMeasured)

    assert copied.model_dump()["area"] == 12


def test_a_computed_picture_is_sent_as_an_image():
    picture = _png()
    copied = to_dspy_input(ImgDerived(encoded=picture.url), ImgDerived)

    assert dspy_input_model(ImgDerived) is not ImgDerived
    assert isinstance(copied.picture, dspy.Image)
    with pytest.raises(ValueError, match=r"ImgDerived\.picture"):
        ensure_vision_support(
            "openai/gpt-3.5-turbo",
            EvalInputs(
                artifacts=[_artifact(ImgDerived(encoded=picture.url))], state={}
            ),
            openai_api=True,
        )


def test_vision_models_skip_the_payload_scan(monkeypatch):
    """A model with vision support never needs the (decoding) payload scan."""
    from flock.engines.dspy import image_inputs

    def fail(_inputs):
        raise AssertionError("payload scanned")

    monkeypatch.setattr(image_inputs, "_image_fields", fail)
    inputs = EvalInputs(
        artifacts=[_artifact(ImgCaption(text="x", picture=_png()))], state={}
    )

    ensure_vision_support("openai/gpt-4.1", inputs, openai_api=True)


def _formatted(payload_inputs: EvalInputs, *, batched: bool = False):
    builder = DSPySignatureBuilder()
    signature = builder.prepare_signature_for_output_group(
        dspy,
        agent=Agent(),
        inputs=payload_inputs,
        output_group=_output_group(),
        batched=batched,
    )
    payload = builder.prepare_execution_payload_for_output_group(
        payload_inputs,
        _output_group(),
        batched=batched,
        has_context=False,
        context_history=None,
        sys_desc="Describe the pictures",
    )
    messages = dspy.ChatAdapter().format(signature, demos=[], inputs=payload)
    image_parts, text = [], []
    for message in messages:
        content = message["content"]
        for part in content if isinstance(content, list) else [content]:
            if isinstance(part, dict) and part.get("type") == "image_url":
                image_parts.append(part["image_url"]["url"])
            else:
                text.append(part["text"] if isinstance(part, dict) else str(part))
    return image_parts, " ".join(text)


def test_joined_inputs_send_every_picture():
    caption_picture, cover = _png("red"), _png("green")
    inputs = EvalInputs(
        artifacts=[
            _artifact(ImgCaption(text="a red square", picture=caption_picture)),
            _artifact(ImgAlbum(title="greens", cover=cover)),
        ],
        state={},
    )

    image_parts, text = _formatted(inputs)

    assert caption_picture.url in image_parts
    assert cover.url in image_parts
    assert caption_picture.base64_data not in text
    assert cover.base64_data not in text


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


def test_context_images_inside_tuples_are_described():
    first, second = _png("red"), _png("blue")
    pair = Artifact(
        type=type_registry.name_for(ImgPair),
        payload={"pictures": (first.model_dump(), second.model_dump())},
        produced_by="external",
    )

    payload = DSPySignatureBuilder().prepare_execution_payload_for_output_group(
        EvalInputs(artifacts=[_artifact(ImgPlain(text="now"))], state={}),
        _output_group(),
        batched=False,
        has_context=True,
        context_history=[pair],
        sys_desc="Answer",
    )

    described = payload["context"][0].payload["pictures"]
    assert all(item["url"].startswith("🖼 image/") for item in described)


def test_a_known_text_only_model_fails_with_a_clear_error():
    inputs = EvalInputs(
        artifacts=[_artifact(ImgCaption(text="x", picture=_png()))], state={}
    )

    with pytest.raises(ValueError, match=r"openai/gpt-3\.5-turbo.*ImgCaption\.picture"):
        ensure_vision_support("openai/gpt-3.5-turbo", inputs, openai_api=True)


@pytest.mark.parametrize(
    ("model", "openai_api"),
    [
        ("openai/gpt-4.1", True),
        ("openai/gpt-3.5-turbo", False),  # an OpenAI-compatible server: not checked
        ("azure/gpt-3.5-turbo", False),  # a deployment name, not a model
        ("local/unknown", False),
    ],
)
def test_vision_and_unknown_models_pass(model, openai_api):
    inputs = EvalInputs(
        artifacts=[_artifact(ImgCaption(text="x", picture=_png()))], state={}
    )

    ensure_vision_support(model, inputs, openai_api=openai_api)


@pytest.mark.parametrize(
    "value",
    [
        ImgPlain(text="x"),
        ImgAlbum(title="empty"),  # image fields, but no picture in the payload
        ImgDataUrlText(raw=_png().url),  # a data URL in a str field stays text
        ImgAmbiguous(item=ImgTextData(data={"url": _png().url})),  # sent as text
    ],
)
def test_inputs_without_pictures_are_never_rejected(value):
    inputs = EvalInputs(artifacts=[_artifact(value)], state={})

    ensure_vision_support("openai/gpt-3.5-turbo", inputs, openai_api=True)


async def test_the_engine_rejects_images_for_a_text_only_model(monkeypatch):
    from flock.engines.dspy_engine import DSPyEngine

    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)

    engine = DSPyEngine(model="openai/gpt-3.5-turbo")
    inputs = EvalInputs(
        artifacts=[_artifact(ImgCaption(text="x", picture=_png()))], state={}
    )

    with pytest.raises(ValueError, match="does not accept images"):
        await engine._evaluate_internal(
            Agent(), None, inputs, batched=False, output_group=_output_group()
        )
