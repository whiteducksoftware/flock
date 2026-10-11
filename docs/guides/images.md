---
title: Images
description: Pictures in artifacts - creating them, limits, publishing, agents and decision models, the dashboard, and the security rules
tags:
  - images
  - guide
  - security
---

# Images

An artifact can carry pictures in `flock.Image` fields. The picture is stored inline, as a base64 `data:image/...` URL, so it moves through stores, the REST API, the dashboard and agents like any other field.

```python
from pydantic import BaseModel

from flock import Flock, Image, flock_type


@flock_type
class ProductPhoto(BaseModel):
    sku: str
    photo: Image                 # also: Image | None, list[Image], nested models


flock = Flock("openai/gpt-4.1")
await flock.publish(ProductPhoto(sku="A-17", photo=Image.from_file("a17.jpg")))
```

## Creating images

`Image.from_file()`, `Image.from_bytes()` and `Image.from_pil()` scale a picture down to `max_side` (default 1024 px) and re-encode it. Pictures without transparency become JPEG, pictures with transparency become PNG. Re-encoding drops metadata such as EXIF and GPS positions. `Image(url="data:image/png;base64,...")` takes an existing data URL as it is.

## Limits

| Limit | Value | Checked |
|---|---|---|
| Decoded size | 20 MB | When an `Image` is created; for `Artifact` objects published directly, at publish time |
| Pixels | 50 million (e.g. 8660 x 5773) | From the image header, before decoding |
| Source | Inline `data:image/...;base64,...` only | URLs and file paths are rejected |
| Uploads per request (REST) | 20 files | Before the request body is parsed |

The limits hold on every publish path:

- **Models:** `flock.publish(ProductPhoto(...))` validates the `Image` field when the model is created.
- **Dicts:** `flock.publish({"type": ..., "payload": ...})` validates the payload against the registered model.
- **Artifacts:** an `Artifact` object published directly has its inline image data checked against the same limits.
- **REST:** `POST /api/v1/artifacts` (JSON) and `POST /api/v1/artifacts/upload` (multipart; see the [REST API guide](rest-api.md#publish-artifact-with-images)).
- **Dashboard:** the publish panel. The server re-encodes those pictures as well.

Smaller pictures are faster and cheaper: every image is sent to the model in full and counts against its context.

## Agents and decision models

- **LLM agents** (DSPy engine) receive `Image` fields as pictures, also in batches and joins. Images in conversation context are described (`🖼 image/jpeg · 42 KB`), not inlined. See [image inputs](dspy-engine.md#image-inputs).
- **Decision models** that accept images decide about pictures. See [decision models](decisions.md#images).

## Dashboard and API responses

- **Publishing:** the publish panel has a picture picker for `Image` and `list[Image]` fields.
- **Viewing:** graph nodes, the message detail window, the message history and the historical blackboard show 160 px thumbnails. A click loads the full image through `GET /api/v1/artifacts/{id}`.
- **Transfer:** graph snapshots and WebSocket events carry descriptions and thumbnails, never full image data. API clients can request the same form with `images=thumbnails` ([REST API guide](rest-api.md#images-in-responses)).
- **Traces:** spans record a description (`🖼 image/png · 12 KB`), not the pixels.

## Security rules

- **No fetching.** Flock never loads an image from a URL or a file path named in an artifact. Only inline data is accepted, so artifacts cannot make the server or a model provider fetch remote content.
- **Checked uploads.** Uploaded files must be JPEG, PNG, GIF, WebP or BMP. Formats that run external tools, such as EPS, are refused. Size and pixel limits are checked before decoding, and every upload and dashboard picture is re-encoded, which drops metadata.
- **Visibility.** Image data is part of the payload and follows the artifact's [visibility](visibility.md): the REST endpoints return neither the image nor its thumbnail to callers who may not see the artifact. Two gaps are known and tracked for 1.0:
    - WebSocket events, including thumbnails, currently go to every dashboard client ([#431](https://github.com/whiteducksoftware/flock/issues/431)).
    - Graph, message history and trace reads are not yet authorized per caller ([#432](https://github.com/whiteducksoftware/flock/issues/432)).

    Until both are closed, run the dashboard only where every viewer may see every artifact.
- **Storage.** Inline images make artifacts large, about 4/3 of the file size, and every copy (stores, exports) carries the full data. Keep `max_side` modest. Dapr state stores can have size limits per item.

## Examples

| Example | Shows |
|---|---|
| [`examples/01-getting-started/19_image_agent.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/01-getting-started/19_image_agent.py) | An LLM agent checking captions against pictures |
| [`examples/15-decisions/03_color_sorter.py`](https://github.com/whiteducksoftware/flock/blob/main/examples/15-decisions/03_color_sorter.py) | A decision model sorting pictures by color |
