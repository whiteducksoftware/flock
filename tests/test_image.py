"""flock.Image: images as base64 data URLs inside artifacts."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image as PILImage
from pydantic import BaseModel, ValidationError

from flock import Image
from flock.core.artifacts import ArtifactSpec
from flock.registry import flock_type


def png_bytes(size=(64, 32), color=(200, 30, 30), mode="RGB") -> bytes:
    buf = io.BytesIO()
    PILImage.new(mode, size, color).save(buf, "PNG")
    return buf.getvalue()


def decode(image: Image) -> PILImage.Image:
    return PILImage.open(io.BytesIO(image.to_bytes()))


def test_from_bytes_produces_a_jpeg_data_url():
    image = Image.from_bytes(png_bytes())

    assert image.url.startswith("data:image/jpeg;base64,")
    assert image.mime_type == "image/jpeg"
    assert decode(image).size == (64, 32)


def test_transparent_images_stay_png():
    image = Image.from_bytes(png_bytes(mode="RGBA", color=(10, 20, 30, 128)))

    assert image.mime_type == "image/png"
    assert decode(image).mode == "RGBA"


def test_large_images_are_downscaled_to_max_side():
    image = Image.from_bytes(png_bytes(size=(3000, 1500)))

    assert decode(image).size == (1024, 512)
    assert decode(
        Image.from_bytes(png_bytes(size=(3000, 1500)), max_side=300)
    ).size == (
        300,
        150,
    )


def test_max_side_none_keeps_the_size():
    assert decode(
        Image.from_bytes(png_bytes(size=(3000, 1500)), max_side=None)
    ).size == (
        3000,
        1500,
    )


def test_exif_metadata_is_stripped():
    source = PILImage.new("RGB", (40, 40), (1, 2, 3))
    exif = PILImage.Exif()
    exif[0x010F] = "SecretCam"  # Make
    exif[0x8825] = {2: (48.0, 8.0, 0.0)}  # GPSInfo: latitude
    buf = io.BytesIO()
    source.save(buf, "JPEG", exif=exif)
    assert PILImage.open(io.BytesIO(buf.getvalue())).getexif()

    image = Image.from_bytes(buf.getvalue())

    assert not decode(image).getexif()


def test_from_file_and_from_pil(tmp_path):
    path = tmp_path / "square.png"
    path.write_bytes(png_bytes(size=(20, 10)))

    assert decode(Image.from_file(path)).size == (20, 10)
    assert decode(Image.from_pil(PILImage.new("RGB", (5, 7)))).size == (5, 7)


def test_base64_data_is_the_raw_payload_of_the_url():
    image = Image.from_bytes(png_bytes())

    assert image.base64_data == image.url.split(",", 1)[1]
    assert base64.b64decode(image.base64_data) == image.to_bytes()


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/cat.jpg",
        "file:///etc/passwd",
        "/etc/passwd",
        "data:text/plain;base64,aGVsbG8=",
        "data:image/png;base64,not base64!",
        "data:image/png,rawbytes",
    ],
)
def test_only_base64_image_data_urls_are_accepted(url):
    with pytest.raises(ValidationError):
        Image(url=url)


@flock_type
class Photo(BaseModel):
    caption: str
    photo: Image


def test_image_fields_round_trip_through_artifacts():
    image = Image.from_bytes(png_bytes())

    artifact = ArtifactSpec.from_model(Photo).build(
        produced_by="test", data={"caption": "red", "photo": image}
    )
    restored = Photo(**artifact.payload)

    assert artifact.payload["photo"] == {"url": image.url}
    assert restored.photo == image


def test_oversized_image_data_is_rejected_before_decoding(monkeypatch):
    from flock.core import image as image_module

    monkeypatch.setattr(image_module, "MAX_IMAGE_BYTES", 1_000)
    data = base64.b64encode(png_bytes(size=(400, 400), color=(1, 2, 3)) * 2).decode()

    with pytest.raises(ValidationError, match="larger than"):
        Image(url=f"data:image/png;base64,{data}")


def test_images_with_too_many_pixels_are_rejected(monkeypatch):
    from flock.core import image as image_module

    monkeypatch.setattr(image_module, "MAX_IMAGE_PIXELS", 10_000)
    data = base64.b64encode(png_bytes(size=(200, 200))).decode()

    with pytest.raises(ValidationError, match="pixels"):
        Image(url=f"data:image/png;base64,{data}")


def test_base64_that_is_no_readable_image_is_still_accepted():
    """Formats Pillow cannot read may still be readable by a provider."""
    data = base64.b64encode(b"not an image Pillow knows").decode()

    assert Image(url=f"data:image/heic;base64,{data}").mime_type == "image/heic"
