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
from typing import TYPE_CHECKING, Any, Literal

from flock.core.image import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS, Image


if TYPE_CHECKING:
    from pydantic import BaseModel


UPLOAD_FORMATS = ("JPEG", "PNG", "GIF", "WEBP", "BMP")
MAX_UPLOAD_FILES = 20  # files per request
MAX_FORM_BYTES = 1024 * 1024  # the other form fields and the multipart framing


def max_request_bytes() -> int:
    """The largest upload request accepted, checked before it is parsed."""
    return MAX_UPLOAD_FILES * MAX_IMAGE_BYTES + MAX_FORM_BYTES


class UploadError(ValueError):
    """An upload that cannot be published; ``status_code`` is the HTTP status."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _field(model: type[BaseModel], name: str) -> Any:
    """The field a form part names: by field name or by its alias."""
    for field_name, field in model.model_fields.items():
        if name in (field_name, field.alias, field.validation_alias):
            return field
    return None


def image_slot(model: type[BaseModel], name: str) -> Literal["one", "many"] | None:
    """How many images a field takes: ``Image`` (optional or not) or ``list[Image]``."""
    field = _field(model, name)
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


def check_image_field(model: type[BaseModel], name: str) -> None:
    """Reject a file part for a field that takes no images, before reading it."""
    if image_slot(model, name) is None:
        raise UploadError(
            f"'{name}' is not an Image field of {model.__name__}; "
            "files can only be uploaded into Image or list[Image] fields."
        )


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


def place_images(
    model: type[BaseModel], payload: dict[str, Any], images: dict[str, list[Image]]
) -> dict[str, Any]:
    """``payload`` with the uploaded images in their fields.

    ``images`` is keyed by :func:`payload_key`, so a field's name and its alias
    share one entry and one count.
    """
    result = dict(payload)
    for name, uploaded in images.items():
        slot = image_slot(model, name)
        if slot == "one" and len(uploaded) != 1:
            raise UploadError(f"'{name}' takes one image, got {len(uploaded)}.")
        dumped = [image.model_dump() for image in uploaded]
        result[name] = dumped if slot == "many" else dumped[0]
    return result


def payload_key(model: type[BaseModel], name: str) -> str:
    """The key validation accepts for the field a part names: its alias, if any."""
    for field_name, field in model.model_fields.items():
        if name in (field_name, field.alias, field.validation_alias):
            if isinstance(field.validation_alias, str):
                return field.validation_alias
            return field.alias or field_name
    return name


__all__ = [
    "MAX_UPLOAD_FILES",
    "UPLOAD_FORMATS",
    "UploadError",
    "check_image_field",
    "image_from_upload",
    "image_slot",
    "max_request_bytes",
    "payload_key",
    "place_images",
]
