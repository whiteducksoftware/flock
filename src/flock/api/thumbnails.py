"""Small previews of artifact images for dashboard graph snapshots.

Graph snapshots are rebuilt on every dashboard refresh, so full images would
be shipped again and again. Nodes carry small thumbnails instead, and the
payload shown in the JSON view replaces image data with a short description.
Thumbnails are cached by a digest of the image data, so the cache never holds
the full images.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any

from flock.core.image import Image


THUMB_SIDE = 160
_CACHE_SIZE = 1024
_cache: OrderedDict[bytes, str] = OrderedDict()


def is_image_data(value: Any) -> bool:
    """True for an ``Image`` payload: ``{"url": "data:image/..."}``."""
    return (
        isinstance(value, dict)
        and len(value) == 1
        and isinstance(value.get("url"), str)
        and value["url"].startswith("data:image/")
    )


def find_images(value: Any, path: str = "") -> list[tuple[str, str]]:
    """``(field path, data URL)`` of every image in a payload, in order."""
    if is_image_data(value):
        return [(path, value["url"])]
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found += find_images(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            found += find_images(item, f"{path}[{index}]")
    return found


def describe(url: str) -> str:
    """Short text for an image in the JSON view, e.g. ``🖼 image/jpeg · 42 KB``."""
    mime = url[5 : url.index(";")]
    size_kb = max(1, round(len(url.split(",", 1)[1]) * 3 / 4 / 1024))
    return f"🖼 {mime} · {size_kb} KB"


def compact(value: Any) -> Any:
    """``value`` with image data replaced by :func:`describe` text."""
    if is_image_data(value):
        return describe(value["url"])
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [compact(item) for item in value]
    return value


def thumbnail(url: str) -> str | None:
    """A data URL of the image scaled to at most ``THUMB_SIDE`` px (cached)."""
    key = hashlib.blake2b(url.encode("ascii"), digest_size=16).digest()
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached
    try:
        thumb = Image.from_bytes(Image(url=url).to_bytes(), max_side=THUMB_SIDE).url
    except Exception:  # unreadable image data: show no preview
        return None
    _cache[key] = thumb
    if len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return thumb


def image_summaries(payload: Any) -> list[dict[str, Any]]:
    """Dashboard data for each image in ``payload``."""
    summaries = []
    for path, url in find_images(payload):
        thumb = thumbnail(url)
        if thumb is None:
            continue
        summaries.append({
            "path": path,
            "mime": url[5 : url.index(";")],
            "bytes": round(len(url.split(",", 1)[1]) * 3 / 4),
            "thumb": thumb,
        })
    return summaries


def first_thumbnail(payload: Any) -> str | None:
    """Thumbnail of the first image in ``payload``, if any."""
    for _path, url in find_images(payload):
        thumb = thumbnail(url)
        if thumb is not None:
            return thumb
    return None


__all__ = [
    "THUMB_SIDE",
    "compact",
    "describe",
    "find_images",
    "first_thumbnail",
    "image_summaries",
    "is_image_data",
    "thumbnail",
]
