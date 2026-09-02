"""Visibility deserialization utilities.

This module handles complex visibility object deserialization from JSON data.
Extracted from store.py to reduce complexity and improve testability.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from flock.core.visibility import (
    AfterVisibility,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
    Visibility,
)


_VISIBILITY_MODELS = {
    "Public": PublicVisibility,
    "Private": PrivateVisibility,
    "Labelled": LabelledVisibility,
    "Tenant": TenantVisibility,
    "After": AfterVisibility,
}


def _normalize_iso_duration(value: Any) -> Any:
    if (
        isinstance(value, str)
        and value.startswith("P")
        and "T" not in value
        and any(unit in value for unit in "HMS")
    ):
        return f"PT{value[1:]}"
    return value


def parse_iso_duration(value: str | timedelta | None) -> timedelta:
    """
    Parse ISO 8601 duration string to timedelta.

    Args:
        value: ISO 8601 duration string (e.g., "PT1H30M")

    Returns:
        Parsed timedelta, or zero timedelta if invalid

    Examples:
        >>> parse_iso_duration("PT1H")
        timedelta(hours=1)
        >>> parse_iso_duration("PT30M")
        timedelta(minutes=30)
        >>> parse_iso_duration(None)
        timedelta(0)
    """
    if isinstance(value, timedelta):
        return value
    if not isinstance(value, str) or not value.startswith("P"):
        return timedelta(0)
    value = _normalize_iso_duration(value)
    try:
        return AfterVisibility.model_validate({"ttl": value}).ttl
    except ValueError:
        return timedelta(0)


def deserialize_visibility(
    data: Any, *, strict: bool = False, validate_shape: bool = False
) -> Visibility:
    """
    Deserialize visibility object from JSON data.

    Handles all visibility types: Public, Private, Labelled, Tenant, After.
    Uses dictionary dispatch to reduce complexity vs if-elif chain.

    Args:
        data: JSON data dict or Visibility instance
        strict: Reject malformed policies instead of falling back to Public
        validate_shape: Reject unknown kinds and fields while preserving model defaults

    Returns:
        Visibility object (defaults to PublicVisibility if invalid)

    Examples:
        >>> deserialize_visibility({"kind": "Public"})
        PublicVisibility()
        >>> deserialize_visibility({"kind": "Private", "agents": ["agent1"]})
        PrivateVisibility(agents={"agent1"})
    """
    if strict:
        return _validate_visibility(data)
    if validate_shape:
        return _validate_visibility_shape(data)

    # Early returns for simple cases
    if isinstance(data, Visibility):
        return data
    if not data:
        return PublicVisibility()

    # Extract kind
    kind = data.get("kind") if isinstance(data, dict) else None
    if not kind:
        return PublicVisibility()

    # Dispatch to appropriate deserializer
    return _VISIBILITY_DESERIALIZERS.get(kind, _deserialize_public)(data)


def _validate_visibility_shape(data: Any) -> Visibility:
    """Validate the discriminated shape without changing core model semantics."""
    if isinstance(data, Visibility):
        return data
    if not isinstance(data, dict):
        raise TypeError("visibility must be an object")

    kind = data.get("kind")
    fields_by_kind = {
        "Public": set(),
        "Private": {"agents"},
        "Labelled": {"required_labels"},
        "Tenant": {"tenant_id"},
        "After": {"ttl", "then"},
    }
    if kind not in fields_by_kind:
        raise ValueError(f"unknown visibility kind: {kind!r}")
    if unexpected := set(data) - {"kind"} - fields_by_kind[kind]:
        raise ValueError(
            f"unexpected fields for {kind} visibility: {sorted(unexpected)}"
        )
    model_data = data
    if kind == "After" and "ttl" in data:
        model_data = {**data, "ttl": _normalize_iso_duration(data["ttl"])}
    return _VISIBILITY_MODELS[kind].model_validate(model_data)


def _validate_visibility(data: Any) -> Visibility:
    """Validate policies accepted from an external trust boundary."""
    visibility = _validate_visibility_shape(data)
    if isinstance(data, Visibility):
        data = data.model_dump(mode="python")
    kind = data["kind"]

    list_fields = {"Private": "agents", "Labelled": "required_labels"}
    if field := list_fields.get(kind):
        values = data.get(field)
        if (
            not isinstance(values, (list, set, tuple))
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            raise ValueError(f"{kind} visibility requires a non-empty {field} list")

    if kind == "Tenant":
        tenant_id = data.get("tenant_id")
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("Tenant visibility requires a non-empty tenant_id")

    if kind == "After":
        ttl = data.get("ttl")
        if not isinstance(ttl, (str, timedelta)) or parse_iso_duration(
            ttl
        ) <= timedelta(0):
            raise ValueError("After visibility requires a positive ISO 8601 ttl")
        if data.get("then") is not None:
            _validate_visibility(data["then"])
    return visibility


def _deserialize_public(data: dict[str, Any]) -> PublicVisibility:
    """Deserialize PublicVisibility."""
    return PublicVisibility()


def _deserialize_private(data: dict[str, Any]) -> PrivateVisibility:
    """Deserialize PrivateVisibility."""
    return PrivateVisibility(agents=set(data.get("agents", [])))


def _deserialize_labelled(data: dict[str, Any]) -> LabelledVisibility:
    """Deserialize LabelledVisibility."""
    return LabelledVisibility(required_labels=set(data.get("required_labels", [])))


def _deserialize_tenant(data: dict[str, Any]) -> TenantVisibility:
    """Deserialize TenantVisibility."""
    return TenantVisibility(tenant_id=data.get("tenant_id"))


def _deserialize_after(data: dict[str, Any]) -> AfterVisibility:
    """
    Deserialize AfterVisibility with recursive 'then' handling.

    Args:
        data: JSON data dict with 'ttl' and optional 'then' fields

    Returns:
        AfterVisibility instance
    """
    ttl = parse_iso_duration(data.get("ttl"))
    then_data = data.get("then") if isinstance(data, dict) else None
    then_visibility = deserialize_visibility(then_data) if then_data else None
    return AfterVisibility(ttl=ttl, then=then_visibility)


# Dispatch table for visibility types
_VISIBILITY_DESERIALIZERS = {
    "Public": _deserialize_public,
    "Private": _deserialize_private,
    "Labelled": _deserialize_labelled,
    "Tenant": _deserialize_tenant,
    "After": _deserialize_after,
}
