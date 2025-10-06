"""Contract tests for TypeRegistry.resolve_name() method.

This test file validates type name normalization behavior,
ensuring simple names resolve to canonical forms correctly.
"""

import pytest
from pydantic import BaseModel

from flock.registry import RegistryError, flock_type, type_registry


class TestTypeNormalizationContract:
    """Contract tests for TypeRegistry.resolve_name()."""

    def setup_method(self):
        """Save and clear registry before each test."""
        self._saved_by_name = type_registry._by_name.copy()
        self._saved_by_cls = type_registry._by_cls.copy()
        type_registry._by_name.clear()
        type_registry._by_cls.clear()

    def teardown_method(self):
        """Restore registry after each test."""
        type_registry._by_name.clear()
        type_registry._by_cls.clear()
        type_registry._by_name.update(self._saved_by_name)
        type_registry._by_cls.update(self._saved_by_cls)

    def test_canonical_name_pass_through(self):
        """B1: Canonical names pass through unchanged."""

        @flock_type
        class Document(BaseModel):
            content: str

        canonical = type_registry.name_for(Document)
        assert canonical == "test_type_normalization_contract.Document"

        # This will FAIL - method doesn't exist yet
        result = type_registry.resolve_name(canonical)
        assert result == canonical

    def test_simple_name_resolution(self):
        """B2: Simple names resolve to canonical form."""

        @flock_type
        class Document(BaseModel):
            content: str

        # This will FAIL - method doesn't exist yet
        result = type_registry.resolve_name("Document")
        assert result == type_registry.name_for(Document)

    def test_unregistered_type_error(self):
        """B4: Unregistered types raise RegistryError."""
        with pytest.raises(RegistryError, match="Unknown artifact type"):
            type_registry.resolve_name("NonExistent")

    def test_ambiguous_simple_name_error(self):
        """B5: Multiple types with same simple name raise error."""

        # Create two classes with same __name__ by defining in different scopes
        class User(BaseModel):
            name: str

        # Register first User
        type_registry.register(User, name="app.User")

        # Create another class also named User
        class User(BaseModel):
            email: str

        # Register second User with different canonical name
        type_registry.register(User, name="test.User")

        # Now resolving "User" should be ambiguous
        with pytest.raises(RegistryError, match="[Aa]mbiguous"):
            type_registry.resolve_name("User")

    def test_explicit_name_registration(self):
        """B3: Explicit decorator names are canonical."""

        @flock_type(name="CustomName")
        class MyType(BaseModel):
            value: int

        # Explicit name is the canonical form
        result = type_registry.resolve_name("CustomName")
        assert result == "CustomName"

    def test_module_qualified_resolution(self):
        """B6: Qualified names allow disambiguation."""

        class User1(BaseModel):
            name: str

        class User2(BaseModel):
            email: str

        type_registry.register(User1, name="app.models.User")
        type_registry.register(User2, name="test.fixtures.User")

        # Qualified names work fine
        result1 = type_registry.resolve_name("app.models.User")
        assert result1 == "app.models.User"

        result2 = type_registry.resolve_name("test.fixtures.User")
        assert result2 == "test.fixtures.User"
