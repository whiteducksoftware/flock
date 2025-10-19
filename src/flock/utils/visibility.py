"""Visibility deserialization utilities."""

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


class VisibilityDeserializer:
    """Deserializes visibility from dict/str representation.

    This utility eliminates 5+ duplicate visibility deserialization patterns
    scattered across store.py, context_provider.py, and orchestrator.py.
    """

    @staticmethod
    def deserialize(data: dict[str, Any] | str) -> Visibility:
        """
        Deserialize visibility from various formats.

        Args:
            data: Dict with 'kind' field or string

        Returns:
            Visibility instance

        Raises:
            ValueError: If visibility kind is unknown

        Example:
            >>> vis = VisibilityDeserializer.deserialize({"kind": "Public"})
            >>> assert isinstance(vis, PublicVisibility)
        """
        if isinstance(data, str):
            kind = data
            props = {}
        else:
            kind = data.get("kind")
            props = data

        if kind == "Public":
            return PublicVisibility()

        if kind == "Private":
            agents = set(props.get("agents", []))
            return PrivateVisibility(agents=agents)

        if kind == "Labelled":
            required_labels = set(props.get("required_labels", []))
            return LabelledVisibility(required_labels=required_labels)

        if kind == "Tenant":
            tenant_id = props.get("tenant_id")
            return TenantVisibility(tenant_id=tenant_id)

        if kind == "After":
            ttl_value = props.get("ttl")
            # Handle timedelta or raw seconds
            if isinstance(ttl_value, (int, float)):
                ttl = timedelta(seconds=ttl_value)
            elif isinstance(ttl_value, dict):
                # Pydantic dict representation
                ttl = timedelta(**ttl_value)
            else:
                ttl = ttl_value or timedelta()

            then_data = props.get("then")
            then = VisibilityDeserializer.deserialize(then_data) if then_data else None

            return AfterVisibility(ttl=ttl, then=then)

        raise ValueError(f"Unknown visibility kind: {kind}")
