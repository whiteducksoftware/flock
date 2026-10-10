"""Traces describe image data instead of copying it into every span."""

from __future__ import annotations

import json

from PIL import Image as PILImage

from flock.core.image import Image, describe_image_data
from flock.logging.trace_and_logged import _extract_span_attributes, _serialize_value


IMAGE = Image.from_pil(PILImage.effect_noise((300, 300), 60).convert("RGB"))


def test_describe_image_data_names_type_and_size():
    text = describe_image_data(IMAGE.url)

    assert text.startswith("🖼 image/jpeg · ")
    assert text.endswith(" KB")
    assert describe_image_data("hello") is None
    assert describe_image_data("data:text/plain;base64,aGk=") is None


def test_serialized_payloads_describe_images():
    payload = {"label": "noise", "photo": {"url": IMAGE.url}, "album": [IMAGE.url]}

    serialized = _serialize_value(payload)

    assert serialized["label"] == "noise"
    assert serialized["photo"] == {"url": describe_image_data(IMAGE.url)}
    assert serialized["album"] == [describe_image_data(IMAGE.url)]


def test_image_objects_are_described():
    serialized = _serialize_value(IMAGE)

    assert serialized["url"] == describe_image_data(IMAGE.url)


def test_span_attributes_stay_small_with_images():
    def evaluate(inputs):
        return inputs

    attributes = _extract_span_attributes(
        evaluate, ({"payload": {"photo": {"url": IMAGE.url}}},), {}
    )

    encoded = json.dumps(attributes)
    assert "data:image/" not in encoded
    assert len(encoded) < 1000 < len(IMAGE.url)


def test_other_long_strings_are_unchanged():
    text = "x" * 20_000

    assert _serialize_value(text) == text
