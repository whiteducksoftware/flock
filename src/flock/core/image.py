"""Images inside artifacts.

An :class:`Image` holds the picture itself as a base64 ``data:image/...`` URL,
so it round-trips through stores, the REST API and the dashboard like any
other field. Flock never fetches images from URLs or file paths named in an
artifact: only inline data is accepted.

Create images with :meth:`Image.from_file`, :meth:`Image.from_bytes` or
:meth:`Image.from_pil`. They downscale to ``max_side`` (default 1024 px) and
re-encode the picture, which also drops EXIF metadata such as GPS positions.
"""

from __future__ import annotations

import base64
import binascii
import io
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, field_validator


if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

DEFAULT_MAX_SIDE = 1024
# Ingestion limits: artifacts can come from the REST API, and every image is
# decoded again for providers and thumbnails.
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # decoded file size
MAX_IMAGE_PIXELS = 50_000_000  # width x height, e.g. 8660 x 5773
_DATA_URL = re.compile(r"^data:(image/[a-z0-9.+-]+);base64,([A-Za-z0-9+/=]+)$")


def describe_image_data(value: str) -> str | None:
    """``🖼 image/jpeg · 42 KB`` for an image data URL, else None.

    Logs, traces and the dashboard use this instead of copying image data.
    """
    if not value.startswith("data:image/"):
        return None
    match = _DATA_URL.match(value)
    if match is None:
        return None
    size_kb = max(1, round(len(match.group(2)) * 3 / 4 / 1024))
    return f"🖼 {match.group(1)} · {size_kb} KB"


def _check_pixels(data: bytes) -> None:
    """Reject images whose header announces more than ``MAX_IMAGE_PIXELS``.

    Only the header is read. Data Pillow cannot identify passes: a provider may
    still read formats Pillow does not know.
    """
    from PIL import Image as PILImageModule
    from PIL import UnidentifiedImageError

    try:
        with PILImageModule.open(io.BytesIO(data)) as picture:
            width, height = picture.size
    except (UnidentifiedImageError, OSError, ValueError):
        return
    except PILImageModule.DecompressionBombError as exc:
        raise ValueError(f"Image has too many pixels ({exc})") from None
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(
            f"Image has {width} x {height} pixels; at most {MAX_IMAGE_PIXELS:,} "
            "are accepted. Downscale it, e.g. with Image.from_file()."
        )


class Image(BaseModel):
    """An image stored inline as a base64 data URL."""

    # Lets the dashboard recognise image fields in artifact schemas
    model_config = ConfigDict(json_schema_extra={"x-flock-image": True})

    url: str

    @field_validator("url")
    @classmethod
    def _inline_image_data_only(cls, value: str) -> str:
        match = _DATA_URL.match(value)
        if match is None:
            raise ValueError(
                "Image.url must be a base64 data URL (data:image/<type>;base64,...); "
                "use Image.from_file() or Image.from_bytes() to create one."
            )
        encoded = match.group(2)
        padding = len(encoded) - len(encoded.rstrip("="))
        # Canonical base64 only: extra "=" would shrink the size estimate below
        # and Python's decoder accepts them after complete groups.
        if len(encoded) % 4 or padding > 2 or "=" in encoded.rstrip("="):
            raise ValueError("Image.url contains invalid base64 data")
        if len(encoded) * 3 // 4 - padding > MAX_IMAGE_BYTES:  # before decoding
            raise ValueError(
                f"Image data is larger than {MAX_IMAGE_BYTES / (1024 * 1024):g} MB; "
                "downscale it, e.g. with Image.from_file()."
            )
        try:
            data = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Image.url contains invalid base64 data") from exc
        _check_pixels(data)
        return value

    @property
    def mime_type(self) -> str:
        """The image's MIME type, e.g. ``image/jpeg``."""
        return _DATA_URL.match(self.url).group(1)

    @property
    def base64_data(self) -> str:
        """The base64 payload without the ``data:`` prefix."""
        return self.url.split(",", 1)[1]

    def to_bytes(self) -> bytes:
        """The encoded image file (JPEG or PNG bytes)."""
        return base64.b64decode(self.base64_data)

    @classmethod
    def from_pil(
        cls, image: PILImage, *, max_side: int | None = DEFAULT_MAX_SIDE
    ) -> Image:
        """Encode a Pillow image (downscaled to ``max_side``, metadata dropped)."""
        from PIL import ImageOps

        picture = ImageOps.exif_transpose(image)
        has_alpha = picture.mode in ("RGBA", "LA") or (
            picture.mode == "P" and "transparency" in picture.info
        )
        picture = picture.convert("RGBA" if has_alpha else "RGB")
        if max_side is not None:
            picture.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        if has_alpha:
            picture.save(buffer, "PNG", optimize=True)
            mime = "image/png"
        else:
            picture.save(buffer, "JPEG", quality=85)
            mime = "image/jpeg"
        data = base64.b64encode(buffer.getvalue()).decode("ascii")
        return cls(url=f"data:{mime};base64,{data}")

    @classmethod
    def from_bytes(
        cls, data: bytes, *, max_side: int | None = DEFAULT_MAX_SIDE
    ) -> Image:
        """Encode image file bytes (any format Pillow reads)."""
        from PIL import Image as PILImageModule

        with PILImageModule.open(io.BytesIO(data)) as picture:
            picture.load()
            return cls.from_pil(picture, max_side=max_side)

    @classmethod
    def from_file(
        cls, path: str | Path, *, max_side: int | None = DEFAULT_MAX_SIDE
    ) -> Image:
        """Encode an image file from disk."""
        return cls.from_bytes(Path(path).read_bytes(), max_side=max_side)

    def __repr__(self) -> str:
        return f"Image({self.mime_type}, {len(self.base64_data)} base64 chars)"


def check_inline_images(value: Any) -> None:
    """Raise ``ValueError`` if a payload holds inline image data over the limits.

    Models validate their ``Image`` fields when they are created, but a payload
    can also arrive without that check (``Artifact`` objects, component
    publishes, a model changed after creation), so every artifact is checked
    before it is stored. Only valid image data URLs under a ``url`` key are
    checked; other values are left alone.
    """
    if isinstance(value, dict):
        url = value.get("url")
        if isinstance(url, str) and _DATA_URL.match(url):
            Image(url=url)  # size and pixel limits; ValidationError is a ValueError
        for key, item in value.items():
            if key != "url":  # sibling keys may hold more images
                check_inline_images(item)
    elif isinstance(value, list | tuple):
        for item in value:
            check_inline_images(item)


__all__ = ["DEFAULT_MAX_SIDE", "Image", "check_inline_images", "describe_image_data"]
