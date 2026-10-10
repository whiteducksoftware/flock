"""Image files uploaded through the REST API (#511).

Uploaded files go into ``Image`` fields: one file per ``Image`` field, several
for ``list[Image]``. Uploads come from outside, so a file is checked before
it is decoded: at most ``MAX_IMAGE_BYTES``, a common image format (no
formats that run external tools, such as EPS) and at most
``MAX_IMAGE_PIXELS``. It is then re-encoded like ``Image.from_bytes``, which
also drops metadata such as GPS positions.
"""

from __future__ import annotations

import io
import types
import typing
from typing import Any, Literal

from pydantic import BaseModel

from flock.core.image import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS, Image


UPLOAD_FORMATS = ("JPEG", "PNG", "GIF", "WEBP", "BMP")


class UploadError(ValueError):
    """An upload that cannot be published; ``status_code`` is the HTTP status."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def image_slot(
    model: type[BaseModel], field_name: str
) -> Literal["one", "many"] | None:
    """How many images a field takes: ``Image`` (optional or not) or ``list[Image]``."""
    field = model.model_fields.get(field_name)
    if field is None:
        return None
    annotation = field.annotation
    if typing.get_origin(annotation) in (types.UnionType, typing.Union):
        options = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(options) != 1:
            return None
        annotation = options[0]
    if annotation is Image:
        return "one"
    if typing.get_origin(annotation) is list and typing.get_args(annotation) == (
        Image,
    ):
        return "many"
    return None


def image_from_upload(field_name: str, data: bytes) -> Image:
    """An ``Image`` from an uploaded file, checked before it is decoded."""
    from PIL import Image as PILImage
    from PIL import UnidentifiedImageError

    if len(data) > MAX_IMAGE_BYTES:
        raise UploadError(
            f"File for '{field_name}' is larger than "
            f"{MAX_IMAGE_BYTES / (1024 * 1024):g} MB.",
            status_code=413,
        )
    try:
        with PILImage.open(io.BytesIO(data), formats=UPLOAD_FORMATS) as picture:
            if picture.width * picture.height > MAX_IMAGE_PIXELS:
                raise UploadError(
                    f"Image for '{field_name}' has {picture.width} x {picture.height} "
                    f"pixels; at most {MAX_IMAGE_PIXELS:,} are accepted."
                )
            picture.load()
            return Image.from_pil(picture)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, UploadError):
            raise
        raise UploadError(
            f"File for '{field_name}' is not a supported image "
            f"({', '.join(UPLOAD_FORMATS)})."
        ) from exc


def apply_uploads(
    model: type[BaseModel], payload: dict[str, Any], files: dict[str, list[bytes]]
) -> dict[str, Any]:
    """``payload`` with the uploaded files placed into their ``Image`` fields."""
    result = dict(payload)
    for field_name, contents in files.items():
        slot = image_slot(model, field_name)
        if slot is None:
            raise UploadError(
                f"'{field_name}' is not an Image field of {model.__name__}; "
                "files can only be uploaded into Image or list[Image] fields."
            )
        if slot == "one" and len(contents) != 1:
            raise UploadError(f"'{field_name}' takes one image, got {len(contents)}.")
        images = [image_from_upload(field_name, data).model_dump() for data in contents]
        result[field_name] = images if slot == "many" else images[0]
    return result


__all__ = [
    "UPLOAD_FORMATS",
    "UploadError",
    "apply_uploads",
    "image_from_upload",
    "image_slot",
]
