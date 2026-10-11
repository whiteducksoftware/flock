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

from flock.core.artifacts import Artifact, model_from_payload
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
        ) or any(
            _contains_image(computed.return_type, inner)
            for computed in annotation.model_computed_fields.values()
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
        # Computed values are in the payload (model_dump); keep them as plain
        # fields so the model sees the same data as for a model without images
        for name, computed in model.model_computed_fields.items():
            fields[name] = (_to_dspy(computed.return_type), None)
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


def _sends_image(value: Any) -> bool:
    """True if a value of a DSPy input copy holds a ``dspy.Image``."""
    import dspy

    if isinstance(value, dspy.Image):
        return True
    if isinstance(value, BaseModel):
        return any(
            _sends_image(getattr(value, name)) for name in type(value).model_fields
        )
    if isinstance(value, dict):
        return any(_sends_image(item) for item in value.values())
    if isinstance(value, list | tuple | set | frozenset):
        return any(_sends_image(item) for item in value)
    return False


def _image_fields(inputs: EvalInputs) -> list[str]:
    """``Type.field`` for every input field that is sent to the model as an image.

    Checks the DSPy input copy itself, so it agrees with what the engine sends
    (including the branch Pydantic picks for a union).
    """
    fields: list[str] = []
    for artifact in inputs.artifacts:
        try:
            model = type_registry.resolve(artifact.type)
        except KeyError:
            continue
        if dspy_input_model(model) is model:
            continue
        try:
            sent = to_dspy_input(
                model_from_payload(model, artifact.payload or {}), model
            )
        except Exception:  # noqa: S112 - invalid payloads are passed on as data
            continue
        for name in [*model.model_fields, *model.model_computed_fields]:
            path = f"{model.__name__}.{name}"
            if _sends_image(getattr(sent, name)) and path not in fields:
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
    import litellm

    info = litellm.model_cost.get(model_name.split("/", 1)[-1])
    if info is None or info.get("supports_vision"):
        return
    fields = _image_fields(inputs)  # validates payloads: only for text-only models
    if not fields:
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
