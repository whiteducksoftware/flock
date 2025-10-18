"""Visibility deserialization utilities.

This module handles complex visibility object deserialization from JSON data.
Extracted from store.py to reduce complexity and improve testability.
"""

from __future__ import annotations

import re
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


ISO_DURATION_RE = re.compile(
    r"^P(?:T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)$"
)


def parse_iso_duration(value: str | None) -> timedelta:
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
    if not value:
        return timedelta(0)
    match = ISO_DURATION_RE.match(value)
    if not match:
        return timedelta(0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def deserialize_visibility(data: Any) -> Visibility:
    """
    Deserialize visibility object from JSON data.

    Handles all visibility types: Public, Private, Labelled, Tenant, After.
    Uses dictionary dispatch to reduce complexity vs if-elif chain.

    Args:
        data: JSON data dict or Visibility instance

    Returns:
        Visibility object (defaults to PublicVisibility if invalid)

    Examples:
        >>> deserialize_visibility({"kind": "Public"})
        PublicVisibility()
        >>> deserialize_visibility({"kind": "Private", "agents": ["agent1"]})
        PrivateVisibility(agents={"agent1"})
    """
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
