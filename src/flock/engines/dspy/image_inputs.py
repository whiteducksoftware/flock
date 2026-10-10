"""``flock.Image`` fields as DSPy image inputs (#510).

Artifacts carry images as :class:`flock.core.image.Image`, a base64 data URL.
DSPy sends an image to a multimodal model only when the signature types it as
``dspy.Image``; otherwise the model gets the base64 text. The DSPy engine
therefore builds, for each input model that contains images, a copy whose
``Image`` fields are ``dspy.Image`` (at any depth: lists, optionals, nested
models) and passes the inputs as instances of that copy.

Images in conversation context are described (``🖼 image/png · 12 KB``) rather
than inlined, so earlier artifacts do not flood the prompt with base64 text.
"""

from __future__ import annotations

import copy
import functools
import operator
import types
import typing
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, create_model

from flock.core.artifacts import Artifact
from flock.core.image import Image, describe_image_data
from flock.registry import type_registry
from flock.utils.runtime import EvalInputs


def _is_model(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _contains_image(annotation: Any, seen: frozenset[type] = frozenset()) -> bool:
    if annotation is Image:
        return True
    if _is_model(annotation):
        if annotation in seen:
            return False
        inner = seen | {annotation}
        return any(
            _contains_image(field.annotation, inner)
            for field in annotation.model_fields.values()
        )
    return any(_contains_image(arg, seen) for arg in typing.get_args(annotation))


def _to_dspy(annotation: Any) -> Any:
    """``annotation`` with ``Image`` replaced by ``dspy.Image``."""
    if annotation is Image:
        import dspy

        return dspy.Image
    if _is_model(annotation):
        return dspy_input_model(annotation)
    args = typing.get_args(annotation)
    if not args or not _contains_image(annotation):
        return annotation
    origin = typing.get_origin(annotation)
    new_args = tuple(_to_dspy(arg) for arg in args)
    if origin is types.UnionType:
        return functools.reduce(operator.or_, new_args)
    if origin is typing.Union:
        return typing.Union[new_args]  # noqa: UP007 - rebuilds the given form
    return origin[new_args if len(new_args) > 1 else new_args[0]]


@functools.cache
def dspy_input_model(model: type[BaseModel]) -> type[BaseModel]:
    """``model``, or a copy of it with ``dspy.Image`` fields if it holds images."""
    if not _contains_image(model):
        return model
    fields: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        field_copy = copy.copy(field)
        field_copy.annotation = _to_dspy(field.annotation)
        fields[name] = (field_copy.annotation, field_copy)
    return create_model(model.__name__, __doc__=model.__doc__, **fields)


def to_dspy_input(value: Any, model: type[BaseModel]) -> Any:
    """A validated input as an instance of :func:`dspy_input_model`."""
    target = dspy_input_model(model)
    if target is model or not isinstance(value, model):
        return value
    return target.model_validate(value.model_dump())


def _describe_images(value: Any) -> Any:
    if isinstance(value, str):
        return describe_image_data(value) or value
    if isinstance(value, dict):
        return {key: _describe_images(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_describe_images(item) for item in value]
    return value


def describe_context_images(items: Iterable[Any]) -> list[Any]:
    """Context items with image data replaced by a short description.

    Items are artifacts (copied, never modified) or plain data.
    """
    described = []
    for item in items:
        if isinstance(item, Artifact):
            payload = _describe_images(item.payload)
            if payload != item.payload:
                item = item.model_copy(update={"payload": payload})
            described.append(item)
        else:
            described.append(_describe_images(item))
    return described


def _image_fields(inputs: EvalInputs) -> list[str]:
    fields: list[str] = []
    for artifact in inputs.artifacts:
        try:
            model = type_registry.resolve(artifact.type)
        except KeyError:
            continue
        for name, field in model.model_fields.items():
            path = f"{model.__name__}.{name}"
            if _contains_image(field.annotation) and path not in fields:
                fields.append(path)
    return fields


def _known_model_info(model_name: str) -> dict[str, Any] | None:
    import litellm

    for key in (model_name, model_name.split("/", 1)[-1]):
        info = litellm.model_cost.get(key)
        if info is not None:
            return info
    return None


def ensure_vision_support(model_name: str, inputs: EvalInputs) -> None:
    """Fail clearly when image inputs go to a model known to be text-only.

    Unknown models (for example Azure deployment names) are not checked; the
    provider decides.
    """
    fields = _image_fields(inputs)
    if not fields:
        return
    info = _known_model_info(model_name)
    if info is None or info.get("supports_vision"):
        return
    raise ValueError(
        f"Model {model_name} does not accept images, but the input "
        f"{', '.join(fields)} contains images. Use a model with vision support."
    )


__all__ = [
    "describe_context_images",
    "dspy_input_model",
    "ensure_vision_support",
    "to_dspy_input",
]
