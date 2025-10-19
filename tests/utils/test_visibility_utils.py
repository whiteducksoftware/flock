"""Tests for visibility deserialization utilities.

Validates the visibility_utils module handles all visibility types correctly
and reduces complexity through dictionary dispatch pattern.
"""

from __future__ import annotations

from flock.core.visibility import (
    AfterVisibility,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
)
from flock.utils.visibility_utils import deserialize_visibility


class TestDeserializeVisibility:
    """Test visibility deserialization with various input types."""

    def test_deserialize_already_visibility_object(self):
        """Should return visibility object unchanged if already deserialized."""
        vis = PublicVisibility()
        result = deserialize_visibility(vis)
        assert result is vis

    def test_deserialize_none(self):
        """Should return PublicVisibility for None input."""
        result = deserialize_visibility(None)
        assert isinstance(result, PublicVisibility)

    def test_deserialize_empty_dict(self):
        """Should return PublicVisibility for empty dict."""
        result = deserialize_visibility({})
        assert isinstance(result, PublicVisibility)

    def test_deserialize_dict_without_kind(self):
        """Should return PublicVisibility for dict without 'kind' field."""
        result = deserialize_visibility({"some_field": "value"})
        assert isinstance(result, PublicVisibility)

    def test_deserialize_public(self):
        """Should deserialize Public visibility correctly."""
        data = {"kind": "Public"}
        result = deserialize_visibility(data)
        assert isinstance(result, PublicVisibility)

    def test_deserialize_private(self):
        """Should deserialize Private visibility correctly."""
        data = {"kind": "Private"}
        result = deserialize_visibility(data)
        assert isinstance(result, PrivateVisibility)

    def test_deserialize_labelled(self):
        """Should deserialize Labelled visibility with required_labels."""
        data = {"kind": "Labelled", "required_labels": ["admin", "internal"]}
        result = deserialize_visibility(data)
        assert isinstance(result, LabelledVisibility)
        assert result.required_labels == {"admin", "internal"}

    def test_deserialize_labelled_without_labels(self):
        """Should deserialize Labelled visibility with empty required_labels if missing."""
        data = {"kind": "Labelled"}
        result = deserialize_visibility(data)
        assert isinstance(result, LabelledVisibility)
        assert result.required_labels == set()

    def test_deserialize_tenant(self):
        """Should deserialize Tenant visibility with tenant_id."""
        data = {"kind": "Tenant", "tenant_id": "tenant-123"}
        result = deserialize_visibility(data)
        assert isinstance(result, TenantVisibility)
        assert result.tenant_id == "tenant-123"

    def test_deserialize_tenant_without_tenant_id(self):
        """Should deserialize Tenant visibility with None if missing."""
        data = {"kind": "Tenant"}
        result = deserialize_visibility(data)
        assert isinstance(result, TenantVisibility)
        assert result.tenant_id is None

    def test_deserialize_after(self):
        """Should deserialize After visibility with ttl."""
        data = {"kind": "After", "ttl": "PT1H"}
        result = deserialize_visibility(data)
        assert isinstance(result, AfterVisibility)
        from datetime import timedelta

        assert result.ttl == timedelta(hours=1)

    def test_deserialize_after_without_ttl(self):
        """Should deserialize After visibility with zero ttl if missing."""
        data = {"kind": "After"}
        result = deserialize_visibility(data)
        assert isinstance(result, AfterVisibility)
        from datetime import timedelta

        assert result.ttl == timedelta(0)

    def test_deserialize_unknown_kind(self):
        """Should default to PublicVisibility for unknown kind."""
        data = {"kind": "UnknownType"}
        result = deserialize_visibility(data)
        assert isinstance(result, PublicVisibility)

    def test_deserialize_non_dict_non_visibility(self):
        """Should return PublicVisibility for non-dict, non-Visibility input."""
        result = deserialize_visibility("not a dict")
        assert isinstance(result, PublicVisibility)

    def test_dispatch_pattern_coverage(self):
        """Should use dictionary dispatch for all known visibility types."""
        # This test verifies the dispatch pattern works for all types
        test_cases = [
            ({"kind": "Public"}, PublicVisibility),
            ({"kind": "Private"}, PrivateVisibility),
            ({"kind": "Labelled", "required_labels": ["test"]}, LabelledVisibility),
            ({"kind": "Tenant", "tenant_id": "t1"}, TenantVisibility),
            ({"kind": "After", "ttl": "PT1H"}, AfterVisibility),
        ]

        for data, expected_type in test_cases:
            result = deserialize_visibility(data)
            assert isinstance(result, expected_type)
