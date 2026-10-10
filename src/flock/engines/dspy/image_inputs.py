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
    if origin in (types.UnionType, typing.Union):
        return typing.Union[new_args]  # noqa: UP007 - may hold forward references
    return origin[new_args if len(new_args) > 1 else new_args[0]]


# Copies built so far, and forward references for copies still being built
# (a model that refers to itself, directly or through other models).
_copies: dict[type[BaseModel], type[BaseModel]] = {}
_in_progress: dict[type[BaseModel], typing.ForwardRef] = {}
_namespace: dict[str, type[BaseModel]] = {}


def dspy_input_model(model: type[BaseModel]) -> type[BaseModel]:
    """``model``, or a copy of it with ``dspy.Image`` fields if it holds images."""
    if model in _copies:
        return _copies[model]
    if model in _in_progress:
        return _in_progress[model]  # resolved by model_rebuild below
    if not _contains_image(model):
        return model
    reference = f"{model.__name__}_{id(model):x}"
    _in_progress[model] = typing.ForwardRef(reference)
    try:
        fields: dict[str, Any] = {}
        for name, field in model.model_fields.items():
            field_copy = copy.copy(field)
            field_copy.annotation = _to_dspy(field.annotation)
            fields[name] = (field_copy.annotation, field_copy)
        copied = create_model(
            model.__name__,
            __config__=model.model_config,
            __doc__=model.__doc__,
            __module__=__name__,
            **fields,
        )
    finally:
        del _in_progress[model]
    _namespace[reference] = copied
    _copies[model] = copied
    if not _in_progress:  # outermost call: every forward reference is known now
        for pending in _copies.values():
            if not pending.__pydantic_complete__:
                pending.model_rebuild(_types_namespace=_namespace)
    return copied


def to_dspy_input(value: Any, model: type[BaseModel]) -> Any:
    """A validated input as an instance of :func:`dspy_input_model`."""
    target = dspy_input_model(model)
    if target is model or not isinstance(value, model):
        return value
    # Field names, whatever the model's alias settings
    return target.model_validate(value.model_dump(), by_name=True)


def _describe_images(value: Any) -> Any:
    if isinstance(value, str):
        return describe_image_data(value) or value
    if isinstance(value, dict):
        return {key: _describe_images(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(_describe_images(item) for item in value)
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


def _is_image_data(value: Any) -> bool:
    if isinstance(value, Image):
        return True
    return (
        isinstance(value, dict)
        and isinstance(value.get("url"), str)
        and describe_image_data(value["url"]) is not None
    )


def _holds_image(annotation: Any, value: Any) -> bool:
    """True if ``value`` has image data where ``annotation`` declares an Image."""
    if value is None:
        return False
    if annotation is Image:
        return _is_image_data(value)
    if _is_model(annotation):
        return _model_holds_image(annotation, value)
    if not typing.get_args(annotation) or not _contains_image(annotation):
        return False
    return _container_holds_image(annotation, value)


def _model_holds_image(model: type[BaseModel], value: Any) -> bool:
    if isinstance(value, BaseModel):
        value = value.model_dump()
    return isinstance(value, dict) and any(
        _holds_image(field.annotation, value.get(name))
        for name, field in model.model_fields.items()
    )


def _container_holds_image(annotation: Any, value: Any) -> bool:
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin in (types.UnionType, typing.Union):
        return any(_holds_image(arg, value) for arg in args)
    if origin is dict:
        items = value.values() if isinstance(value, dict) else []
        return any(_holds_image(args[-1], item) for item in items)
    if not isinstance(value, list | tuple | set | frozenset):
        return False
    if origin is tuple and len(args) > 1 and args[-1] is not Ellipsis:
        pairs = zip(args, value, strict=False)  # a short payload is just short
        return any(_holds_image(arg, item) for arg, item in pairs)
    return any(_holds_image(args[0], item) for item in value)


def _image_fields(inputs: EvalInputs) -> list[str]:
    """``Type.field`` for every input field that holds a picture."""
    fields: list[str] = []
    for artifact in inputs.artifacts:
        try:
            model = type_registry.resolve(artifact.type)
        except KeyError:
            continue
        payload = artifact.payload or {}
        for name, field in model.model_fields.items():
            path = f"{model.__name__}.{name}"
            if _holds_image(field.annotation, payload.get(name)) and path not in fields:
                fields.append(path)
    return fields


def ensure_vision_support(
    model_name: str, inputs: EvalInputs, *, openai_api: bool
) -> None:
    """Fail clearly when images go to an OpenAI API model known to be text-only.

    Only models of the OpenAI API itself (``openai_api``) are checked against
    LiteLLM's model table: elsewhere a model name can be a deployment alias
    (Azure, gateways, local servers), so the provider decides.
    """
    if not openai_api:
        return
    fields = _image_fields(inputs)
    if not fields:
        return
    import litellm

    info = litellm.model_cost.get(model_name.split("/", 1)[-1])
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
