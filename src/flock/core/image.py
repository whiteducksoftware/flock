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
from typing import TYPE_CHECKING

from pydantic import BaseModel, field_validator


if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

DEFAULT_MAX_SIDE = 1024
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


class Image(BaseModel):
    """An image stored inline as a base64 data URL."""

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
        try:
            base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Image.url contains invalid base64 data") from exc
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


__all__ = ["DEFAULT_MAX_SIDE", "Image", "describe_image_data"]
