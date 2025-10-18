"""Tests for VisibilityDeserializer utility."""

from datetime import timedelta

import pytest

from flock.core.visibility import (
    AfterVisibility,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
)
from flock.utils.visibility import VisibilityDeserializer


def test_deserialize_public_from_dict():
    """Test deserializing public visibility from dict."""
    result = VisibilityDeserializer.deserialize({"kind": "Public"})
    assert isinstance(result, PublicVisibility)
    assert result.kind == "Public"


def test_deserialize_public_from_string():
    """Test deserializing public visibility from string."""
    result = VisibilityDeserializer.deserialize("Public")
    assert isinstance(result, PublicVisibility)


def test_deserialize_private_with_agents():
    """Test deserializing private visibility with agents."""
    result = VisibilityDeserializer.deserialize({
        "kind": "Private",
        "agents": ["agent1", "agent2"],
    })
    assert isinstance(result, PrivateVisibility)
    assert result.agents == {"agent1", "agent2"}


def test_deserialize_private_without_agents():
    """Test deserializing private visibility without agents field."""
    result = VisibilityDeserializer.deserialize({"kind": "Private"})
    assert isinstance(result, PrivateVisibility)
    assert result.agents == set()


def test_deserialize_labelled_with_labels():
    """Test deserializing labelled visibility with required labels."""
    result = VisibilityDeserializer.deserialize({
        "kind": "Labelled",
        "required_labels": ["label1", "label2"],
    })
    assert isinstance(result, LabelledVisibility)
    assert result.required_labels == {"label1", "label2"}


def test_deserialize_labelled_without_labels():
    """Test deserializing labelled visibility without labels field."""
    result = VisibilityDeserializer.deserialize({"kind": "Labelled"})
    assert isinstance(result, LabelledVisibility)
    assert result.required_labels == set()


def test_deserialize_tenant_with_id():
    """Test deserializing tenant visibility with tenant ID."""
    result = VisibilityDeserializer.deserialize({
        "kind": "Tenant",
        "tenant_id": "tenant-123",
    })
    assert isinstance(result, TenantVisibility)
    assert result.tenant_id == "tenant-123"


def test_deserialize_tenant_without_id():
    """Test deserializing tenant visibility without tenant ID."""
    result = VisibilityDeserializer.deserialize({"kind": "Tenant"})
    assert isinstance(result, TenantVisibility)
    assert result.tenant_id is None


def test_deserialize_after_with_ttl_seconds():
    """Test deserializing after visibility with TTL in seconds."""
    result = VisibilityDeserializer.deserialize({"kind": "After", "ttl": 3600})
    assert isinstance(result, AfterVisibility)
    assert result.ttl == timedelta(seconds=3600)


def test_deserialize_after_with_ttl_dict():
    """Test deserializing after visibility with TTL as dict."""
    result = VisibilityDeserializer.deserialize({
        "kind": "After",
        "ttl": {"hours": 1, "minutes": 30},
    })
    assert isinstance(result, AfterVisibility)
    assert result.ttl == timedelta(hours=1, minutes=30)


def test_deserialize_after_with_then_clause():
    """Test deserializing after visibility with then clause."""
    result = VisibilityDeserializer.deserialize({
        "kind": "After",
        "ttl": 60,
        "then": {"kind": "Public"},
    })
    assert isinstance(result, AfterVisibility)
    assert result.then is not None
    assert isinstance(result.then, PublicVisibility)


def test_deserialize_after_without_ttl():
    """Test deserializing after visibility without TTL."""
    result = VisibilityDeserializer.deserialize({"kind": "After"})
    assert isinstance(result, AfterVisibility)
    assert result.ttl == timedelta()


def test_deserialize_unknown_kind_raises_error():
    """Test that unknown visibility kind raises ValueError."""
    with pytest.raises(ValueError, match="Unknown visibility kind"):
        VisibilityDeserializer.deserialize({"kind": "UnknownKind"})


def test_deserialize_nested_after_visibility():
    """Test deserializing nested after visibility."""
    result = VisibilityDeserializer.deserialize({
        "kind": "After",
        "ttl": 60,
        "then": {
            "kind": "Private",
            "agents": ["agent1"],
        },
    })
    assert isinstance(result, AfterVisibility)
    assert isinstance(result.then, PrivateVisibility)
    assert result.then.agents == {"agent1"}
